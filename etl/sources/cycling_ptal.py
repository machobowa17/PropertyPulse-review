"""
sources/cycling_ptal.py — TfL PTAL + Census Cycling → core_ptal_lsoa + core_cycling_lsoa

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_cycling_lsoa)

Data files required in etl/data/ (or set env vars to override):
    PTAL_PATH    — ptal_lsoa_2015.csv  (TfL PTAL scores for London LSOAs)
    CYCLING_PATH — census2021-ts061-lsoa.csv  (Census 2021 method of travel to work)

Download from:
    PTAL: https://data.london.gov.uk/dataset/public-transport-accessibility-levels
    Census TS061: https://www.ons.gov.uk/datasets/TS061/editions/2021/versions/3

Note: WFH data (pct_wfh) now lives in core_census_lsoa (consolidated census table).
      pct_wfh column was dropped from core_cycling_lsoa in session 9.
"""

import csv
import os

import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ANNUAL, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "cycling_ptal",
    "description":        "TfL PTAL 2015 → core_ptal_lsoa (London); Census 2021 TS061 → core_cycling_lsoa (England).",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["ptal_lsoa"], TABLE_NAMES["cycling_lsoa"]],
    "cache_key_patterns": [],
    "expected_row_range": (30_000, 42_000),   # cycling_lsoa row count (primary)
}

# Census TS061 column names (verbatim from ONS export)
_COL_TOTAL   = "Method of travel to workplace: Total: All usual residents aged 16 years and over in employment the week before the census"
_COL_CYCLING = "Method of travel to workplace: Bicycle"

# ---------------------------------------------------------------------------
# Helper: resolve data file paths
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_ptal_path():
    path = os.environ.get("PTAL_PATH")
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, "ptal_lsoa_2015.csv")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"No ptal_lsoa_2015.csv found at {candidate}. "
        "Download TfL PTAL data from "
        "https://data.london.gov.uk/dataset/public-transport-accessibility-levels "
        "and place in etl/data/, or set the PTAL_PATH env var."
    )


def _resolve_cycling_path():
    path = os.environ.get("CYCLING_PATH")
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, "census2021-ts061-lsoa.csv")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"No census2021-ts061-lsoa.csv found at {candidate}. "
        "Download Census 2021 TS061 from "
        "https://www.ons.gov.uk/datasets/TS061/editions/2021/versions/3 "
        "and place in etl/data/, or set the CYCLING_PATH env var."
    )


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest TfL PTAL and Census cycling/WFH data.

    Strategy:
    1. Load ptal_lsoa_2015.csv → core_ptal_lsoa (London LSOAs, England only).
    2. Load census2021-ts061-lsoa.csv → core_cycling_lsoa (all England LSOAs).
    3. Return final row count in core_cycling_lsoa (the larger, national table).
    """
    ptal_path    = _resolve_ptal_path()
    cycling_path = _resolve_cycling_path()

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    # ------------------------------------------------------------------
    # Part 1: core_ptal_lsoa — TfL PTAL (London LSOAs only)
    # ------------------------------------------------------------------
    print(f"  PTAL source: {ptal_path}", flush=True)
    ptal_rows = []
    with open(ptal_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lsoa = r.get("LSOA2011", "").strip()
            if not lsoa.startswith("E"):
                continue
            try:
                avg_ptai  = float(r.get("AvPTAI2015", "0") or "0")
                ptal_band = r.get("PTAL", "").strip()
            except (ValueError, TypeError):
                continue
            ptal_rows.append((lsoa, avg_ptai, ptal_band))

    print(f"  Collected {len(ptal_rows):,} PTAL rows (London)", flush=True)

    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['ptal_lsoa']} CASCADE")
    if ptal_rows:
        execute_values(
            cur,
            f"""
            INSERT INTO {TABLE_NAMES['ptal_lsoa']} (lsoa_code, avg_ptai, ptal_band)
            VALUES %s
            ON CONFLICT (lsoa_code) DO UPDATE SET
                avg_ptai  = EXCLUDED.avg_ptai,
                ptal_band = EXCLUDED.ptal_band
            """,
            ptal_rows,
        )
    conn.commit()

    # ------------------------------------------------------------------
    # Part 2: core_cycling_lsoa — Census 2021 TS061
    # ------------------------------------------------------------------
    print(f"  Cycling source: {cycling_path}", flush=True)
    cycling_rows = []
    with open(cycling_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lsoa = r.get("geography code", "").strip()
            if not lsoa.startswith("E"):
                continue
            try:
                total   = int(r.get(_COL_TOTAL,   "0") or "0")
                cycling = int(r.get(_COL_CYCLING, "0") or "0")
            except (ValueError, TypeError):
                continue
            if total == 0:
                continue
            pct_cycling = round(cycling / total * 100, 2)
            cycling_rows.append((lsoa, total, cycling, pct_cycling))

    print(f"  Collected {len(cycling_rows):,} cycling rows", flush=True)

    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['cycling_lsoa']} CASCADE")
    if cycling_rows:
        execute_values(
            cur,
            f"""
            INSERT INTO {TABLE_NAMES['cycling_lsoa']}
                (lsoa_code, total_workers, cycling_count, pct_cycling)
            VALUES %s
            ON CONFLICT (lsoa_code) DO UPDATE SET
                total_workers = EXCLUDED.total_workers,
                cycling_count = EXCLUDED.cycling_count,
                pct_cycling   = EXCLUDED.pct_cycling
            """,
            cycling_rows,
        )
    conn.commit()

    # Return row count for primary table (cycling_lsoa)
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['cycling_lsoa']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
