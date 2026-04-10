"""
sources/boundaries.py — ONS Open Geography boundary polygons → 4 boundary tables

Ingests:
    core_lsoa_boundaries  — LSOA polygons (Dec 2021, England + Wales)
    core_ward_boundaries  — Ward polygons (May 2025, supported countries)
    core_lad_boundaries   — LAD polygons (May 2025, supported countries)
    core_county_boundaries — County/unitary authority polygons derived via
                             ST_Union of LAD boundaries grouped by parent name
                             from core_lad_county_lookup.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_lsoa_boundaries)

Sources (live ArcGIS FeatureServer — no local files required):
    ONS Open Geography Portal
    https://geoportal.statistics.gov.uk/
"""

import psycopg2
import requests
import geopandas as gpd
from shapely.geometry import MultiPolygon

from constants import (
    PLANNED_COUNTRY_PREFIXES,
    SCHEDULE_FOUNDATION,
    SUPPORTED_COUNTRY_PREFIXES,
    TABLE_NAMES,
    countries_with_counties,
)

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "boundaries",
    "description": (
        "ONS Open Geography LSOA/ward/LAD boundaries + derived county boundaries "
        "→ core_lsoa_boundaries, core_ward_boundaries, core_lad_boundaries, core_county_boundaries."
    ),
    "schedule":           SCHEDULE_FOUNDATION,
    "depends_on":         ["postcodes"],
    "tables_written":     [
        TABLE_NAMES["lsoa_boundaries"],
        TABLE_NAMES["ward_boundaries"],
        TABLE_NAMES["lad_boundaries"],
        TABLE_NAMES["county_boundaries"],
    ],
    "cache_key_patterns": ["lsoa_sess:*", "area:*", "boundary:*", "choropleth:*"],
    "expected_row_range": (33_000, 35_000),   # core_lsoa_boundaries
}

# ---------------------------------------------------------------------------
# ArcGIS FeatureServer URLs (ONS Generalised Clipped boundaries)
# ---------------------------------------------------------------------------

_BOUNDARY_URLS = {
    "lsoa": (
        "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
        "Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V5/FeatureServer/0/query"
    ),
    "ward": (
        "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
        "WD_MAY_2025_UK_BGC_V2/FeatureServer/0/query"
    ),
    "lad": (
        "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
        "LAD_MAY_2025_UK_BGC_V2/FeatureServer/0/query"
    ),
}

_COLUMN_MAPS = {
    "lsoa": {"code_field": "LSOA21CD", "name_field": "LSOA21NM"},
    "ward": {"code_field": "WD25CD",   "name_field": "WD25NM"},
    "lad":  {"code_field": "LAD25CD",  "name_field": "LAD25NM"},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COUNTY_PREFIXES = tuple(countries_with_counties())

def _fetch_all_features(url, code_field, code_prefixes=("E",)):
    """
    Page through an ArcGIS FeatureServer, returning a GeoJSON FeatureCollection.
    Code prefixes determine which country families are included.
    """
    all_features = []
    offset    = 0
    page_size = 1000

    while True:
        where_parts = [f"{code_field} LIKE '{prefix}%'" for prefix in code_prefixes]
        params = {
            "where":             " OR ".join(where_parts),
            "outFields":         "*",
            "outSR":             "4326",
            "f":                 "geojson",
            "resultOffset":      offset,
            "resultRecordCount": page_size,
        }
        print(f"    Fetching {code_field} offset {offset}...", flush=True)
        resp = requests.get(url, params=params, timeout=120)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if not features:
            break
        all_features.extend(features)
        offset += len(features)
        if len(features) < page_size:
            break

    return {"type": "FeatureCollection", "features": all_features}


def _ensure_multipolygon(geom):
    if geom is None:
        return None
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    return geom


# ---------------------------------------------------------------------------
# Per-table ingest functions
# ---------------------------------------------------------------------------

def _ingest_lsoa_boundaries(conn):
    url  = _BOUNDARY_URLS["lsoa"]
    cols = _COLUMN_MAPS["lsoa"]
    geojson = _fetch_all_features(url, cols["code_field"], ("E", "W"))
    print(f"  Fetched {len(geojson['features'])} LSOA features", flush=True)
    if not geojson["features"]:
        raise RuntimeError("No LSOA features returned — aborting to avoid truncating live data.")

    gdf = gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['lsoa_boundaries']} CASCADE")

    count = 0
    for _, row in gdf.iterrows():
        code = row.get(cols["code_field"])
        name = row.get(cols["name_field"])
        geom = _ensure_multipolygon(row.geometry)
        if code is None or geom is None:
            continue
        cur.execute(
            f"""INSERT INTO {TABLE_NAMES['lsoa_boundaries']}
                    (lsoa_code, lsoa_name, msoa_code, lad_code, geom)
               VALUES (%s, %s, NULL, NULL, ST_GeomFromText(%s, 4326))
               ON CONFLICT (lsoa_code) DO UPDATE SET
                   lsoa_name = EXCLUDED.lsoa_name,
                   geom = EXCLUDED.geom""",
            (code, name, geom.wkt),
        )
        count += 1

    conn.commit()

    # Backfill msoa_code and lad_code from core_postcodes (majority vote per LSOA)
    print("  Backfilling MSOA and LAD codes from core_postcodes...", flush=True)
    cur.execute(f"""
        UPDATE {TABLE_NAMES['lsoa_boundaries']} lb
        SET msoa_code = sub.msoa_code,
            lad_code  = sub.lad_code
        FROM (
            SELECT lsoa_code,
                   MODE() WITHIN GROUP (ORDER BY msoa_code) AS msoa_code,
                   MODE() WITHIN GROUP (ORDER BY lad_code)  AS lad_code
            FROM {TABLE_NAMES['postcodes']}
            WHERE lsoa_code IS NOT NULL
            GROUP BY lsoa_code
        ) sub
        WHERE lb.lsoa_code = sub.lsoa_code
    """)
    conn.commit()
    cur.close()
    print(f"  Inserted {count} LSOA boundaries", flush=True)
    return count


def _ingest_ward_boundaries(conn):
    url  = _BOUNDARY_URLS["ward"]
    cols = _COLUMN_MAPS["ward"]
    geojson = _fetch_all_features(url, cols["code_field"], SUPPORTED_COUNTRY_PREFIXES)
    print(f"  Fetched {len(geojson['features'])} Ward features", flush=True)
    if not geojson["features"]:
        raise RuntimeError("No Ward features returned — aborting to avoid truncating live data.")

    gdf = gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['ward_boundaries']} CASCADE")

    count = 0
    for _, row in gdf.iterrows():
        code = row.get(cols["code_field"])
        name = row.get(cols["name_field"])
        geom = _ensure_multipolygon(row.geometry)
        if code is None or geom is None:
            continue
        cur.execute(
            f"""INSERT INTO {TABLE_NAMES['ward_boundaries']}
                    (ward_code, ward_name, lad_code, geom)
               VALUES (%s, %s, NULL, ST_GeomFromText(%s, 4326))
               ON CONFLICT (ward_code) DO UPDATE SET
                   ward_name = EXCLUDED.ward_name,
                   geom = EXCLUDED.geom""",
            (code, name, geom.wkt),
        )
        count += 1

    conn.commit()

    print("  Backfilling LAD codes from core_postcodes...", flush=True)
    cur.execute(f"""
        UPDATE {TABLE_NAMES['ward_boundaries']} wb
        SET lad_code = sub.lad_code
        FROM (
            SELECT ward_code,
                   MODE() WITHIN GROUP (ORDER BY lad_code) AS lad_code
            FROM {TABLE_NAMES['postcodes']}
            WHERE ward_code IS NOT NULL
            GROUP BY ward_code
        ) sub
        WHERE wb.ward_code = sub.ward_code
    """)
    conn.commit()
    cur.close()
    print(f"  Inserted {count} Ward boundaries", flush=True)
    return count


def _ingest_lad_boundaries(conn):
    url  = _BOUNDARY_URLS["lad"]
    cols = _COLUMN_MAPS["lad"]
    geojson = _fetch_all_features(url, cols["code_field"], SUPPORTED_COUNTRY_PREFIXES)
    print(f"  Fetched {len(geojson['features'])} LAD features", flush=True)
    if not geojson["features"]:
        raise RuntimeError("No LAD features returned — aborting to avoid truncating live data.")

    gdf = gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['lad_boundaries']} CASCADE")

    count = 0
    for _, row in gdf.iterrows():
        code = row.get(cols["code_field"])
        name = row.get(cols["name_field"])
        geom = _ensure_multipolygon(row.geometry)
        if code is None or geom is None:
            continue
        cur.execute(
            f"""INSERT INTO {TABLE_NAMES['lad_boundaries']}
                    (lad_code, lad_name, geom)
               VALUES (%s, %s, ST_GeomFromText(%s, 4326))
               ON CONFLICT (lad_code) DO UPDATE SET
                   lad_name = EXCLUDED.lad_name,
                   geom = EXCLUDED.geom""",
            (code, name, geom.wkt),
        )
        count += 1

    conn.commit()

    print("  Backfilling county and region codes from core_postcodes...", flush=True)
    cur.execute(f"""
        UPDATE {TABLE_NAMES['lad_boundaries']} lb
        SET county_code = sub.county_code,
            county_name = sub.county_name,
            region_code = sub.region_code,
            region_name = sub.region_name
        FROM (
            SELECT lad_code,
                   MODE() WITHIN GROUP (ORDER BY county_code) AS county_code,
                   MODE() WITHIN GROUP (ORDER BY county_name) AS county_name,
                   MODE() WITHIN GROUP (ORDER BY region_code) AS region_code,
                   MODE() WITHIN GROUP (ORDER BY region_name) AS region_name
            FROM {TABLE_NAMES['postcodes']}
            WHERE lad_code IS NOT NULL
            GROUP BY lad_code
        ) sub
        WHERE lb.lad_code = sub.lad_code
    """)
    conn.commit()
    cur.close()
    print(f"  Inserted {count} LAD boundaries", flush=True)
    return count


def _derive_county_boundaries(conn):
    """
    Build core_county_boundaries by unioning LAD polygons per parent_comparison
    from core_lad_county_lookup.  No external download needed.
    """
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {TABLE_NAMES['county_boundaries']} CASCADE")
    cur.execute(f"""
        CREATE TABLE {TABLE_NAMES['county_boundaries']} (
            county_name TEXT PRIMARY KEY,
            lad_count   INTEGER NOT NULL,
            geom        GEOMETRY(MultiPolygon, 4326) NOT NULL
        )
    """)
    county_where_clause = " OR ".join(
        [f"lb.lad_code LIKE '{prefix}%'" for prefix in _COUNTY_PREFIXES]
    ) or "FALSE"
    cur.execute(f"""
        INSERT INTO {TABLE_NAMES['county_boundaries']} (county_name, lad_count, geom)
        SELECT cl.parent_comparison,
               COUNT(lb.lad_code)::int,
               ST_Multi(ST_Union(lb.geom))
        FROM {TABLE_NAMES['lad_county_lookup']} cl
        JOIN {TABLE_NAMES['lad_boundaries']} lb ON cl.lad_code = lb.lad_code
        WHERE cl.parent_comparison IS NOT NULL
          AND lb.geom IS NOT NULL
          AND ({county_where_clause})
        GROUP BY cl.parent_comparison
    """)
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_county_boundaries_geom
        ON {TABLE_NAMES['county_boundaries']} USING GIST(geom)
    """)
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_county_boundaries_name
        ON {TABLE_NAMES['county_boundaries']}(county_name)
    """)
    conn.commit()
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['county_boundaries']}")
    count = cur.fetchone()[0]
    cur.close()
    print(f"  Derived {count} county boundaries", flush=True)
    return count


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest all four boundary tables.
    Returns row count in core_lsoa_boundaries (primary validation table).
    """
    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    print("  Ingesting LSOA boundaries...", flush=True)
    lsoa_count = _ingest_lsoa_boundaries(conn)

    print("  Ingesting Ward boundaries...", flush=True)
    _ingest_ward_boundaries(conn)

    print("  Ingesting LAD boundaries...", flush=True)
    _ingest_lad_boundaries(conn)

    if PLANNED_COUNTRY_PREFIXES:
        print("  Deriving county boundaries for England-only comparison parents...", flush=True)
    else:
        print("  Deriving county boundaries...", flush=True)
    _derive_county_boundaries(conn)

    conn.close()
    return lsoa_count
