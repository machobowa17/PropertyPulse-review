"""
sources/ashe.py — ONS ASHE median annual earnings by LAD → core_earnings_lad

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_earnings_lad)

Data files required in etl/data/ (or set ASHE_PATH env var):
    ashe_median_earnings.csv  — Nomis NM_30_1 ASHE Resident Analysis
    Download from: https://www.nomisweb.co.uk/ → ASHE → Resident Analysis → LA level
    Licence: OGL v3.0
"""

import csv
import os

import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ANNUAL, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "ashe",
    "description": "ONS ASHE median earnings by LAD → core_earnings_lad.",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["earnings_lad"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (250, 400),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_SRC_PATH = os.environ.get(
    "ASHE_PATH",
    os.path.join(_DATA_DIR, "ashe_median_earnings.csv"),
)

# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest ONS ASHE median earnings → core_earnings_lad.
    Returns final row count.
    """
    if not os.path.exists(_SRC_PATH):
        raise FileNotFoundError(
            f"ASHE CSV not found: {_SRC_PATH}. "
            "Download from https://www.nomisweb.co.uk/ (ASHE Resident Analysis, LA level) "
            "and place in etl/data/ashe_median_earnings.csv, or set ASHE_PATH env var."
        )

    rows = []
    with open(_SRC_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lad_code = r.get("GEOGRAPHY_CODE", "").strip()
            if not lad_code.startswith("E"):
                continue
            val = r.get("OBS_VALUE", "").strip()
            if not val or val == "..":
                continue
            try:
                median_earnings = float(val)
            except ValueError:
                continue
            rows.append((
                lad_code,
                r.get("GEOGRAPHY_NAME", "").strip(),
                median_earnings,
            ))

    print(f"  Parsed {len(rows):,} LADs with ASHE earnings data", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['earnings_lad']}")
    conn.commit()

    if rows:
        execute_values(
            cur,
            f"""INSERT INTO {TABLE_NAMES['earnings_lad']} (
                    lad_code, lad_name, median_annual_earnings
                ) VALUES %s""",
            rows,
        )
        conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['earnings_lad']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_earnings_lad: {count:,} rows", flush=True)
    return count
