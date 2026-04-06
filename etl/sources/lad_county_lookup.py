"""
sources/lad_county_lookup.py — LAD → county/region parent mapping → core_lad_county_lookup

Implements Build Bible Rule 3:
    London borough   → parent_comparison = 'Greater London'
    Metropolitan district → parent_comparison = region name
    Unitary authority (no separate county) → parent_comparison = region name
    District (has county) → parent_comparison = county name

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_lad_county_lookup)

Data files required in etl/data/ (or set LAD_CTYUA_PATH env var):
    lad_to_ctyua_2025.csv   — LAD code, LAD name, county/unitary authority code/name
    Download from ONS Open Geography Portal.
"""

import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_FOUNDATION, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "lad_county_lookup",
    "description": (
        "LAD → county/region parent mapping per Build Bible Rule 3 → core_lad_county_lookup."
    ),
    "schedule":           SCHEDULE_FOUNDATION,
    "depends_on":         ["postcodes"],
    "tables_written":     [TABLE_NAMES["lad_county_lookup"]],
    "cache_key_patterns": ["lsoa_sess:*", "area:*"],
    "expected_row_range": (280, 350),
}

# ---------------------------------------------------------------------------
# LAD code prefix constants (Build Bible Rule 3)
# ---------------------------------------------------------------------------

_LONDON_PREFIX        = "E09"
_METROPOLITAN_PREFIX  = "E08"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_lad_ctyua_path():
    path = os.environ.get("LAD_CTYUA_PATH")
    if path:
        return path
    for name in ("lad_to_ctyua_2025.csv", "lad_to_ctyua_2024.csv"):
        candidate = os.path.join(_ETL_DATA_DIR, name)
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(
        f"No lad_to_ctyua_2025.csv found in {_ETL_DATA_DIR}. "
        "Set LAD_CTYUA_PATH env var or place the file in etl/data/."
    )


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Build core_lad_county_lookup from lad_to_ctyua_2025.csv + core_postcodes.
    Returns final row count.
    """
    lad_ctyua_path = _resolve_lad_ctyua_path()
    print(f"  LAD→CTYUA source: {lad_ctyua_path}", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['lad_county_lookup']} CASCADE")
    conn.commit()

    # Load LAD→county/unitary mapping
    df = pd.read_csv(lad_ctyua_path, dtype=str, encoding="utf-8-sig")
    df = df[df["LAD25CD"].str.startswith("E", na=False)]   # England only

    # Pull region codes from core_postcodes (majority vote per LAD)
    cur.execute(f"""
        SELECT lad_code,
               MODE() WITHIN GROUP (ORDER BY region_code) AS region_code,
               MODE() WITHIN GROUP (ORDER BY region_name) AS region_name
        FROM {TABLE_NAMES['postcodes']}
        WHERE lad_code IS NOT NULL AND region_code IS NOT NULL
        GROUP BY lad_code
    """)
    lad_region = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

    rows = []
    for _, r in df.iterrows():
        lad_code   = r["LAD25CD"]
        lad_name   = r["LAD25NM"]
        ctyua_code = r["CTYUA25CD"]
        ctyua_name = r["CTYUA25NM"]

        # If county code equals LAD code it's a unitary authority — no separate county
        county_code = ctyua_code if ctyua_code != lad_code else None
        county_name = ctyua_name if ctyua_code != lad_code else None

        region_code, region_name = lad_region.get(lad_code, (None, None))

        is_london = lad_code.startswith(_LONDON_PREFIX)
        is_metro  = lad_code.startswith(_METROPOLITAN_PREFIX)

        # Determine parent_comparison per Build Bible Rule 3
        if is_london:
            parent_comparison = "Greater London"
        elif county_name:
            parent_comparison = county_name
        elif region_name:
            parent_comparison = region_name
        else:
            parent_comparison = "England"

        rows.append((
            lad_code, lad_name,
            county_code, county_name,
            region_code, region_name,
            is_london, is_metro,
            parent_comparison,
        ))

    if rows:
        execute_values(
            cur,
            f"""INSERT INTO {TABLE_NAMES['lad_county_lookup']} (
                    lad_code, lad_name, county_code, county_name,
                    region_code, region_name,
                    is_london_borough, is_metropolitan,
                    parent_comparison
                ) VALUES %s
                ON CONFLICT (lad_code) DO UPDATE SET
                    lad_name          = EXCLUDED.lad_name,
                    county_code       = EXCLUDED.county_code,
                    county_name       = EXCLUDED.county_name,
                    region_code       = EXCLUDED.region_code,
                    region_name       = EXCLUDED.region_name,
                    is_london_borough = EXCLUDED.is_london_borough,
                    is_metropolitan   = EXCLUDED.is_metropolitan,
                    parent_comparison = EXCLUDED.parent_comparison""",
            rows,
            page_size=1000,
        )
        conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['lad_county_lookup']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_lad_county_lookup: {count:,} rows", flush=True)
    return count
