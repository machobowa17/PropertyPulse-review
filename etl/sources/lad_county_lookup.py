"""
sources/lad_county_lookup.py — LAD → county/region parent mapping → core_lad_county_lookup

Implements Build Bible Rule 3:
    London borough   → parent_comparison = 'Greater London'
    Metropolitan district → parent_comparison = metropolitan county name
    Unitary authority (no separate county) → parent_comparison = region name
    District (has county) → parent_comparison = county name

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_lad_county_lookup)

Data files required in etl/data/ (or set LAD_CTYUA_PATH env var):
    lad_to_ctyua_2025.csv        — LAD code, LAD name, county/unitary authority code/name
    metro_county_lookup.csv      — E08 metro district → E11 metro county mapping
    Download from ONS Open Geography Portal.
"""

import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from constants import (
    SCHEDULE_FOUNDATION,
    TABLE_NAMES,
    countries_with_counties,
    countries_with_regions,
    country_prefix_from_code,
    default_parent_name_for_country,
    supported_country_prefixes,
)

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "lad_county_lookup",
    "description": (
        "LAD → county/region parent mapping with federated country-aware parent-comparison rules → core_lad_county_lookup."
    ),
    "schedule":           SCHEDULE_FOUNDATION,
    "depends_on":         ["postcodes"],
    "tables_written":     [TABLE_NAMES["lad_county_lookup"]],
    "cache_key_patterns": ["lsoa_sess:*", "area:*"],
    "expected_row_range": (280, 350),
}

# ---------------------------------------------------------------------------
# LAD code prefix constants (England-specific Build Bible Rule 3 handling)
# ---------------------------------------------------------------------------

_LONDON_PREFIX        = "E09"
_METROPOLITAN_PREFIX  = "E08"
_SUPPORTED_PREFIXES = supported_country_prefixes()
_COUNTRIES_WITH_COUNTIES = set(countries_with_counties())
_COUNTRIES_WITH_REGIONS = set(countries_with_regions())

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load_metro_county_map() -> dict[str, tuple[str, str]]:
    """Load E08 metro district → E11 metro county mapping from CSV data file.

    The lad_to_ctyua CSV treats E08 metro districts as self-referencing
    (CTYUA == LAD), but they belong to metropolitan counties that the
    resolver uses for county searches.  This mapping is maintained in
    etl/data/metro_county_lookup.csv so it can be updated without code changes.
    """
    csv_path = os.path.join(_ETL_DATA_DIR, "metro_county_lookup.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Metro county lookup not found at {csv_path}. "
            "Place metro_county_lookup.csv in etl/data/."
        )
    df = pd.read_csv(csv_path, dtype=str)
    return {
        row["lad_code"]: (row["metro_county_code"], row["metro_county_name"])
        for _, row in df.iterrows()
    }


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

    metro_county_map = _load_metro_county_map()
    print(f"  Metro county lookup: {len(metro_county_map)} E08 districts → 6 metro counties", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    # This table has materialized views depending on it (mv_parent_yearly_price_stats,
    # mv_parent_rolling_price_stats). Blue-green swap would fail because PostgreSQL
    # tracks matview dependencies by OID, not by name. Since the table is small (~320
    # rows), we use truncate-and-reload instead of atomic swap.
    cur.execute(f"DROP TABLE IF EXISTS {TABLE_NAMES['lad_county_lookup']}_new")
    conn.commit()

    # Load LAD→county/unitary mapping for supported countries where source rows exist.
    df = pd.read_csv(lad_ctyua_path, dtype=str, encoding="utf-8-sig")
    df = df[df["LAD25CD"].str[0].isin(_SUPPORTED_PREFIXES)]

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
        country_prefix = country_prefix_from_code(lad_code)

        # County and region handling is country-aware. England keeps the
        # existing county/region hierarchy, while countries without those
        # layers fall back to their country default parent label.
        # Metropolitan districts (E08) need special handling: the CSV treats
        # them as self-referencing, but they belong to metropolitan counties.
        metro = metro_county_map.get(lad_code)
        if metro:
            county_code = metro[0]
            county_name = metro[1]
        elif country_prefix in _COUNTRIES_WITH_COUNTIES and ctyua_code != lad_code:
            county_code = ctyua_code
            county_name = ctyua_name
        else:
            county_code = None
            county_name = None

        region_code, region_name = lad_region.get(lad_code, (None, None))
        if country_prefix not in _COUNTRIES_WITH_REGIONS:
            region_code = None
            region_name = None

        is_london = lad_code.startswith(_LONDON_PREFIX)
        is_metro  = lad_code.startswith(_METROPOLITAN_PREFIX)

        # Determine parent_comparison per federated geography rules.
        if is_london:
            parent_comparison = "Greater London"
        elif county_name:
            parent_comparison = county_name
        elif region_name:
            parent_comparison = region_name
        else:
            parent_comparison = default_parent_name_for_country(country_prefix, fallback=lad_name)

        rows.append((
            lad_code, lad_name,
            county_code, county_name,
            region_code, region_name,
            is_london, is_metro,
            parent_comparison,
        ))

    if rows:
        # Truncate-and-reload (not blue-green swap) to preserve matview dependencies.
        cur.execute(f"TRUNCATE {TABLE_NAMES['lad_county_lookup']}")
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
