"""
sources/hpi.py — ONS/Land Registry House Price Index → core_hpi_lad

Downloads the UK HPI full CSV from the Land Registry open data endpoint.
Filters to supported-country LAD / council-area records using the shared
federated geography contract.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_hpi_lad)

Data is downloaded live; cached at etl/data/uk_hpi.csv between runs.
To force a fresh download, delete etl/data/uk_hpi.csv.
"""

import csv
import os

import psycopg2
import requests
from psycopg2.extras import execute_values

from constants import SCHEDULE_MONTHLY, TABLE_NAMES, is_supported_lad_code
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "hpi",
    "description": "ONS/Land Registry House Price Index → core_hpi_lad.",
    "schedule":           SCHEDULE_MONTHLY,
    "depends_on":         ["boundaries"],
    "tables_written":     [TABLE_NAMES["hpi_lad"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (80_000, 200_000),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_HPI_PATH = os.path.join(_DATA_DIR, "uk_hpi.csv")

# Land Registry HPI full file URL — update year suffix when a newer version ships
_HPI_URL  = os.environ.get(
    "HPI_URL",
    "http://publicdata.landregistry.gov.uk/market-trend-data/"
    "house-price-index-data/UK-HPI-full-file-2025-01.csv",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _download_hpi():
    if os.path.exists(_HPI_PATH):
        print(f"  HPI file present at {_HPI_PATH}, skipping download", flush=True)
        return
    print(f"  Downloading HPI from {_HPI_URL}...", flush=True)
    os.makedirs(_DATA_DIR, exist_ok=True)
    resp = requests.get(_HPI_URL, timeout=120)
    resp.raise_for_status()
    with open(_HPI_PATH, "wb") as f:
        f.write(resp.content)
    print(f"  Downloaded {len(resp.content) / 1_048_576:.1f} MB", flush=True)


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Download (if needed) and ingest UK HPI into core_hpi_lad.
    Returns final row count.
    """
    _download_hpi()

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['hpi_lad']}_new (LIKE {TABLE_NAMES['hpi_lad']} INCLUDING ALL)")
    conn.commit()

    rows = []
    with open(_HPI_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            area_code = r.get("AreaCode", "").strip()
            # Supported-country LAD / council-area codes only.
            if not is_supported_lad_code(area_code):
                continue

            date_str = r.get("Date", "").strip()
            if not date_str:
                continue

            def _float(key):
                v = r.get(key, "").strip()
                return float(v) if v else None

            def _int(key):
                v = r.get(key, "").strip()
                try:
                    return int(float(v)) if v else None
                except (ValueError, TypeError):
                    return None

            try:
                rows.append((
                    area_code,
                    date_str,
                    _float("AveragePrice"),
                    _float("Index"),
                    _int("SalesVolume"),
                    _float("DetachedPrice"),
                    _float("SemiDetachedPrice"),
                    _float("TerracedPrice"),
                    _float("FlatPrice"),
                    _float("12m%Change"),
                ))
            except (ValueError, TypeError):
                continue

    print(f"  Collected {len(rows):,} HPI records", flush=True)

    if rows:
        execute_values(
            cur,
            f"""INSERT INTO {TABLE_NAMES['hpi_lad']}_new (
                    lad_code, date, average_price, index_value, sales_volume,
                    detached_price, semi_detached_price, terraced_price,
                    flat_price, yearly_change_pct
                ) VALUES %s
                ON CONFLICT DO NOTHING""",
            rows,
            page_size=10_000,
        )
        conn.commit()

    blue_green_swap(conn, TABLE_NAMES['hpi_lad'])

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['hpi_lad']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_hpi_lad: {count:,} rows", flush=True)
    return count
