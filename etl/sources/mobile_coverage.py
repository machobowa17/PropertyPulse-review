"""
sources/mobile_coverage.py — Ofcom Connected Nations mobile coverage → core_mobile_coverage_lad

Reads the Ofcom Connected Nations CSV (LAUA level) and ingests 4G/5G
outdoor and indoor coverage percentages per English LAD.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_mobile_coverage_lad)

Data files required in etl/data/ (or set MOBILE_COVERAGE_PATH env var):
    202409_mobile_coverage_laua_r01.csv  — Ofcom Connected Nations (LAUA level)
    Download from: https://www.ofcom.org.uk/research-and-data/telecoms-research/connected-nations
"""

import csv
import os

import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_QUARTERLY, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "mobile_coverage",
    "description": "Ofcom Connected Nations mobile 4G/5G coverage by LAD → core_mobile_coverage_lad.",
    "schedule":           SCHEDULE_QUARTERLY,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["mobile_coverage_lad"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (250, 400),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_SRC_PATH = os.environ.get(
    "MOBILE_COVERAGE_PATH",
    os.path.join(_DATA_DIR, "202409_mobile_coverage_laua_r01.csv"),
)

# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest Ofcom mobile coverage CSV → core_mobile_coverage_lad.
    Returns final row count.
    """
    if not os.path.exists(_SRC_PATH):
        raise FileNotFoundError(
            f"Ofcom mobile coverage CSV not found: {_SRC_PATH}. "
            "Download from https://www.ofcom.org.uk/research-and-data/telecoms-research/connected-nations "
            "and place in etl/data/, or set MOBILE_COVERAGE_PATH env var."
        )

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['mobile_coverage_lad']}")
    conn.commit()

    rows = []
    with open(_SRC_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lad = r.get("laua", "").strip()
            if not lad.startswith("E"):
                continue
            name = r.get("laua_name", "").strip()

            def _pct_coverage(no_coverage_key):
                v = r.get(no_coverage_key, "").strip() or "0"
                try:
                    return round(100.0 - float(v), 1)
                except (ValueError, TypeError):
                    return None

            pct_4g_out = _pct_coverage("4G_prem_out_0")
            pct_4g_in  = _pct_coverage("4G_prem_in_0")
            pct_5g_out = _pct_coverage("5G_high_confidence_prem_out_0")

            rows.append((lad, name, pct_4g_out, pct_4g_in, pct_5g_out))

    print(f"  Collected {len(rows):,} LAD mobile coverage records", flush=True)

    if rows:
        execute_values(
            cur,
            f"""INSERT INTO {TABLE_NAMES['mobile_coverage_lad']} (
                    lad_code, lad_name,
                    pct_4g_outdoor, pct_4g_indoor, pct_5g_outdoor
                ) VALUES %s""",
            rows,
        )
        conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['mobile_coverage_lad']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_mobile_coverage_lad: {count:,} rows", flush=True)
    return count
