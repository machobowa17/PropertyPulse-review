"""
sources/imd.py — MHCLG IMD 2025 → core_imd_lsoa

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_imd_lsoa)

Data files required in etl/data/ (or set env var to override):
    IMD_PATH — iod2025_all_domains.csv  (MHCLG Index of Multiple Deprivation, all domains)

Download from:
    https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019
    (Note: update path when IMD 2025 is published)
"""

import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ONE_TIME, TABLE_NAMES
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "imd",
    "description":        "MHCLG IMD 2025 (all 7 domains) → core_imd_lsoa (England, 2021 LSOAs).",
    "schedule":           SCHEDULE_ONE_TIME,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["imd_lsoa"]],
    "cache_key_patterns": [],
    "expected_row_range": (32_000, 36_000),
}

# ---------------------------------------------------------------------------
# Helper: resolve data file path
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_imd_path():
    path = os.environ.get("IMD_PATH")
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, "iod2025_all_domains.csv")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"No iod2025_all_domains.csv found at {candidate}. "
        "Download MHCLG Indices of Deprivation from "
        "https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019 "
        "and place in etl/data/, or set the IMD_PATH env var."
    )


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest MHCLG IMD 2025 → core_imd_lsoa.

    Strategy:
    1. Load CSV; filter to England LSOAs.
    2. Truncate core_imd_lsoa and bulk insert all scores + ranks + deciles.
    3. Return final row count.
    """
    imd_path = _resolve_imd_path()
    print(f"  IMD source: {imd_path}", flush=True)

    df = pd.read_csv(imd_path)
    df = df[df["LSOA code (2021)"].str.startswith("E", na=False)]
    print(f"  England LSOAs: {len(df):,}", flush=True)

    rows = []
    for _, r in df.iterrows():
        rows.append((
            r["LSOA code (2021)"],
            r["Index of Multiple Deprivation (IMD) Score"],
            r["Index of Multiple Deprivation (IMD) Rank (where 1 is most deprived)"],
            r["Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)"],
            r["Income Score (rate)"],
            r["Employment Score (rate)"],
            r["Education, Skills and Training Score"],
            r["Health Deprivation and Disability Score"],
            r["Crime Score"],
            r["Barriers to Housing and Services Score"],
            r["Living Environment Score"],
        ))

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['imd_lsoa']}_new (LIKE {TABLE_NAMES['imd_lsoa']} INCLUDING ALL)")
    conn.commit()

    execute_values(
        cur,
        f"""
        INSERT INTO {TABLE_NAMES['imd_lsoa']}_new
            (lsoa_code, imd_score, imd_rank, imd_decile,
             income_score, employment_score, education_score, health_score,
             crime_score, barriers_score, living_env_score)
        VALUES %s
        ON CONFLICT DO NOTHING
        """,
        rows,
        page_size=5_000,
    )
    conn.commit()

    blue_green_swap(conn, TABLE_NAMES['imd_lsoa'])

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['imd_lsoa']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
