"""
sources/wimd.py — Welsh Index of Multiple Deprivation 2019 → core_imd_lsoa

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns Welsh row count inserted/updated)

Data files required in etl/data/ (or set env vars to override):
    WIMD_RANKS_PATH  — wimd_2019_ranks.ods   (WIMD 2019 domain ranks)
    WIMD_SCORES_PATH — wimd_2019_scores.ods   (WIMD 2019 domain scores)

Download from:
    https://gov.wales/welsh-index-multiple-deprivation-full-index-update-ranks-2019
    https://gov.wales/welsh-index-multiple-deprivation-indicator-data-scores-2019

IMPORTANT: This module UPSERTs Welsh LSOAs into the shared core_imd_lsoa table.
           It does NOT truncate — English IMD data is preserved.

Domain mapping (WIMD → DB columns):
    WIMD 2019 score          → imd_score
    WIMD 2019 rank           → imd_rank
    WIMD 2019 overall decile → imd_decile
    Income                   → income_score
    Employment               → employment_score
    Education                → education_score
    Health                   → health_score
    Community Safety         → crime_score
    Access to Services       → barriers_score
    Physical Environment     → living_env_score

    Housing (Welsh-only domain) has no English equivalent column — skipped.
"""

import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ONE_TIME, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "wimd",
    "description":        "Welsh IMD 2019 (8 domains) → core_imd_lsoa (Wales, 2011 LSOAs). Upserts alongside English data.",
    "schedule":           SCHEDULE_ONE_TIME,
    "depends_on":         ["imd"],          # English IMD should be loaded first
    "tables_written":     [TABLE_NAMES["imd_lsoa"]],
    "cache_key_patterns": [],
    "expected_row_range": (1_900, 1_920),   # 1,909 Welsh LSOAs
}

# ---------------------------------------------------------------------------
# Helper: resolve data file paths
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_path(env_var: str, filename: str) -> str:
    path = os.environ.get(env_var)
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, filename)
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"No {filename} found at {candidate}. "
        "Download WIMD 2019 from https://gov.wales/welsh-index-multiple-deprivation "
        f"and place in etl/data/, or set the {env_var} env var."
    )


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest WIMD 2019 → core_imd_lsoa (Welsh LSOAs only, upsert).

    Strategy:
    1. Load ranks ODS (overall rank + domain ranks).
    2. Load scores ODS (overall score + domain scores).
    3. Load deciles from ranks ODS (decile sheet).
    4. Merge on LSOA code, filter to W-prefix LSOAs.
    5. Upsert into core_imd_lsoa (ON CONFLICT DO UPDATE).
    6. Return Welsh row count.
    """
    ranks_path = _resolve_path("WIMD_RANKS_PATH", "wimd_2019_ranks.ods")
    scores_path = _resolve_path("WIMD_SCORES_PATH", "wimd_2019_scores.ods")
    print(f"  WIMD ranks:  {ranks_path}", flush=True)
    print(f"  WIMD scores: {scores_path}", flush=True)

    # --- Load ranks (sheet: WIMD_2019_ranks, header row index 2) ---
    df_ranks = pd.read_excel(ranks_path, sheet_name="WIMD_2019_ranks",
                             header=2, engine="odf")
    df_ranks = df_ranks.rename(columns=lambda c: c.strip())
    df_ranks = df_ranks[["LSOA code", "WIMD 2019"]].copy()
    df_ranks.columns = ["lsoa_code", "imd_rank"]
    df_ranks = df_ranks[df_ranks["lsoa_code"].str.startswith("W", na=False)]
    print(f"  Ranks loaded: {len(df_ranks):,} Welsh LSOAs", flush=True)

    # --- Load scores (sheet: Data, header row index 3) ---
    df_scores = pd.read_excel(scores_path, sheet_name="Data",
                              header=3, engine="odf")
    df_scores = df_scores.rename(columns=lambda c: c.strip())
    df_scores = df_scores[[
        "LSOA code", "WIMD 2019", "Income", "Employment",
        "Health", "Education", "Access to Services",
        "Community Safety", "Physical Environment",
    ]].copy()
    df_scores.columns = [
        "lsoa_code", "imd_score", "income_score", "employment_score",
        "health_score", "education_score", "barriers_score",
        "crime_score", "living_env_score",
    ]
    df_scores = df_scores[df_scores["lsoa_code"].str.startswith("W", na=False)]
    print(f"  Scores loaded: {len(df_scores):,} Welsh LSOAs", flush=True)

    # --- Load deciles (sheet: Deciles_quintiles_quartiles, header row index 3) ---
    df_deciles = pd.read_excel(ranks_path,
                               sheet_name="Deciles_quintiles_quartiles",
                               header=3, engine="odf")
    df_deciles = df_deciles.rename(columns=lambda c: c.strip())
    df_deciles = df_deciles[["LSOA code", "WIMD 2019 overall decile"]].copy()
    df_deciles.columns = ["lsoa_code", "imd_decile"]
    df_deciles = df_deciles[df_deciles["lsoa_code"].str.startswith("W", na=False)]
    print(f"  Deciles loaded: {len(df_deciles):,} Welsh LSOAs", flush=True)

    # --- Merge all three on lsoa_code ---
    df = df_ranks.merge(df_scores, on="lsoa_code", how="inner")
    df = df.merge(df_deciles, on="lsoa_code", how="inner")
    print(f"  Merged: {len(df):,} Welsh LSOAs", flush=True)

    if len(df) == 0:
        raise ValueError("No Welsh LSOAs found after merge — check ODS file format")

    # --- Build row tuples matching core_imd_lsoa schema ---
    rows = []
    for _, r in df.iterrows():
        rows.append((
            r["lsoa_code"],
            r["imd_score"],
            int(r["imd_rank"]),
            int(r["imd_decile"]),
            r["income_score"],
            r["employment_score"],
            r["education_score"],
            r["health_score"],
            r["crime_score"],
            r["barriers_score"],
            r["living_env_score"],
        ))

    # --- Upsert into core_imd_lsoa (preserve English rows) ---
    table = TABLE_NAMES["imd_lsoa"]
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    execute_values(
        cur,
        f"""
        INSERT INTO {table}
            (lsoa_code, imd_score, imd_rank, imd_decile,
             income_score, employment_score, education_score, health_score,
             crime_score, barriers_score, living_env_score)
        VALUES %s
        ON CONFLICT (lsoa_code) DO UPDATE SET
            imd_score        = EXCLUDED.imd_score,
            imd_rank         = EXCLUDED.imd_rank,
            imd_decile       = EXCLUDED.imd_decile,
            income_score     = EXCLUDED.income_score,
            employment_score = EXCLUDED.employment_score,
            education_score  = EXCLUDED.education_score,
            health_score     = EXCLUDED.health_score,
            crime_score      = EXCLUDED.crime_score,
            barriers_score   = EXCLUDED.barriers_score,
            living_env_score = EXCLUDED.living_env_score
        """,
        rows,
        page_size=2_000,
    )
    conn.commit()

    # Verify Welsh count
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE lsoa_code LIKE 'W%%'")
    welsh_count = cur.fetchone()[0]

    cur.close()
    conn.close()

    print(f"  Welsh LSOAs in core_imd_lsoa: {welsh_count:,}", flush=True)
    return welsh_count
