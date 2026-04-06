"""
sources/council_tax.py — VOA Council Tax Bands → core_council_tax_lad

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_council_tax_lad)

Data files required in etl/data/council/ (or set env var to override):
    COUNCIL_TAX_PATH — ctb1_table8.ods  (VOA council tax band data)

Download from:
    https://www.gov.uk/government/statistics/council-tax-statistics-for-town-and-parish-councils-in-england
    (Table 8 — council tax band charges by billing authority)
"""

import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ANNUAL, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "council_tax",
    "description":        "VOA Council Tax Band charges ODS → core_council_tax_lad (Bands A–H per LAD).",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["council_tax_lad"]],
    "cache_key_patterns": [],
    "expected_row_range": (300, 400),
}

# Region and country-level geography prefixes to exclude
_SKIP_PREFIXES = ("E12", "E92")

# ---------------------------------------------------------------------------
# Helper: resolve data file path
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_council_tax_path():
    path = os.environ.get("COUNCIL_TAX_PATH")
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, "council", "ctb1_table8.ods")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"No ctb1_table8.ods found at {candidate}. "
        "Download VOA Council Tax statistics from "
        "https://www.gov.uk/government/collections/council-tax-statistics "
        "and place in etl/data/council/, or set the COUNCIL_TAX_PATH env var."
    )


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest VOA Council Tax Band charges → core_council_tax_lad.

    Strategy:
    1. Read ODS spreadsheet (header at row 2); extract LAD-level Band A–H charges.
    2. Truncate core_council_tax_lad and bulk insert all England LAD rows.
    3. Return final row count.
    """
    src_path = _resolve_council_tax_path()
    print(f"  Council tax source: {src_path}", flush=True)

    # Columns: 0=E Code, 1=ONS Code (LAD), 2=Authority, 3=Region, 4=Class, 5=Area,
    #          6=Band A, 7=Band B, 8=Band C, 9=Band D, 10=Band E, 11=Band F, 12=Band G, 13=Band H
    df = pd.read_excel(src_path, engine="odf", header=None, skiprows=2)
    print(f"  Read {len(df)} rows from ODS", flush=True)

    rows = []
    for _, r in df.iterrows():
        lad_code = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""
        if not lad_code.startswith("E"):
            continue
        if any(lad_code.startswith(pfx) for pfx in _SKIP_PREFIXES):
            continue

        try:
            bands = [
                float(r.iloc[i]) if pd.notna(r.iloc[i]) else None
                for i in range(6, 14)
            ]
        except (ValueError, IndexError):
            continue

        if any(b is not None for b in bands):
            rows.append((lad_code, *bands))

    print(f"  Collected {len(rows):,} England LAD rows", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['council_tax_lad']} CASCADE")
    conn.commit()

    if rows:
        execute_values(
            cur,
            f"""
            INSERT INTO {TABLE_NAMES['council_tax_lad']}
                (lad_code, band_a, band_b, band_c, band_d, band_e, band_f, band_g, band_h)
            VALUES %s
            ON CONFLICT (lad_code) DO UPDATE SET
                band_a = EXCLUDED.band_a,
                band_b = EXCLUDED.band_b,
                band_c = EXCLUDED.band_c,
                band_d = EXCLUDED.band_d,
                band_e = EXCLUDED.band_e,
                band_f = EXCLUDED.band_f,
                band_g = EXCLUDED.band_g,
                band_h = EXCLUDED.band_h
            """,
            rows,
        )
        conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['council_tax_lad']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
