"""
sources/voa_rents.py — VOA Private Rental Market Statistics → core_voa_rents_lad

Reads the VOA PRMS XLS file (sheets Table2.3–Table2.7) and builds per-LAD
median rent rows by bedroom count.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_voa_rents_lad)

Data files required in etl/data/ (or set VOA_RENTS_PATH env var):
    voa_rents.xls   — VOA Private Rental Market Statistics
    Download from: https://www.gov.uk/government/statistics/
                    private-rental-market-summary-statistics-april-2022-to-march-2023
"""

import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ANNUAL, TABLE_NAMES
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "voa_rents",
    "description": "VOA Private Rental Market Statistics (XLS) → core_voa_rents_lad.",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["voa_rents_lad"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (200, 500),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_SRC_PATH = os.environ.get(
    "VOA_RENTS_PATH",
    os.path.join(_DATA_DIR, "voa_rents.xls"),
)

# XLS sheet name → bedroom key
_SHEETS = {
    "all":  "Table2.7",
    "1bed": "Table2.3",
    "2bed": "Table2.4",
    "3bed": "Table2.5",
    "4bed": "Table2.6",
}

# Reporting period embedded in each row (update when source data changes)
_PERIOD = "2022-23"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_sheet(xls, sheet_name):
    """
    Parse one VOA rents sheet.
    Returns {area_code: median_rent} for England LAD codes (E06/E07/E08/E09).
    Area code is column index 2; median is column index 7 (0-indexed).
    """
    df = xls.parse(sheet_name, header=None, skiprows=6)
    results = {}
    for _, r in df.iterrows():
        area_code = str(r.iloc[2]).strip() if pd.notna(r.iloc[2]) else ""
        if not area_code.startswith("E0"):
            continue
        try:
            median = float(r.iloc[7]) if pd.notna(r.iloc[7]) else None
        except (ValueError, IndexError):
            continue
        if median is not None:
            results[area_code] = median
    return results


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest VOA private rental market statistics → core_voa_rents_lad.
    Returns final row count.
    """
    if not os.path.exists(_SRC_PATH):
        raise FileNotFoundError(
            f"VOA rents XLS not found: {_SRC_PATH}. "
            "Download from https://www.gov.uk/government/statistics/ "
            "private-rental-market-summary-statistics and place in etl/data/voa_rents.xls, "
            "or set VOA_RENTS_PATH env var."
        )

    print(f"  VOA rents source: {_SRC_PATH}", flush=True)
    xls = pd.ExcelFile(_SRC_PATH)

    # Collect median rents per LAD per bedroom count
    medians = {}
    for key, sheet_name in _SHEETS.items():
        data = _parse_sheet(xls, sheet_name)
        print(f"  {key}: {len(data):,} LADs", flush=True)
        for code, val in data.items():
            if code not in medians:
                medians[code] = {}
            medians[code][key] = val

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['voa_rents_lad']}_new (LIKE {TABLE_NAMES['voa_rents_lad']} INCLUDING ALL)")
    conn.commit()

    rows = [
        (
            lad_code, _PERIOD,
            vals.get("all"),
            vals.get("1bed"),
            vals.get("2bed"),
            vals.get("3bed"),
            vals.get("4bed"),
        )
        for lad_code, vals in medians.items()
    ]

    if rows:
        execute_values(
            cur,
            f"""INSERT INTO {TABLE_NAMES['voa_rents_lad']}_new (
                    lad_code, period,
                    median_rent_all, median_rent_1bed, median_rent_2bed,
                    median_rent_3bed, median_rent_4bed
                ) VALUES %s
                ON CONFLICT DO NOTHING""",
            rows,
        )
        conn.commit()

    blue_green_swap(conn, TABLE_NAMES['voa_rents_lad'])

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['voa_rents_lad']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_voa_rents_lad: {count:,} rows", flush=True)
    return count
