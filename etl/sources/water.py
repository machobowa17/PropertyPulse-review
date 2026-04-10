"""
sources/water.py — Water Company Boundaries → core_water_company_lad

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_water_company_lad)

Data files required in etl/data/ (or set env var to override):
    WATER_GEOJSON_PATH — water_company_boundaries.geojson
                         (Ofwat via Stream Water Data Portal, CC-BY 4.0)

Maps each LAD to its water company via a spatial join: the water company whose
polygon has the largest intersection area with the LAD boundary wins.

Download from:
    https://data.catchmentbasedapproach.org/datasets/water-company-boundaries
"""

import json
import os

import psycopg2

from constants import SCHEDULE_ANNUAL, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "water",
    "description":        "Ofwat water company boundary GeoJSON → core_water_company_lad via LAD spatial join.",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         ["boundaries"],
    "tables_written":     [TABLE_NAMES["water_company_lad"]],
    "cache_key_patterns": [],
    "expected_row_range": (300, 400),
}

# ---------------------------------------------------------------------------
# Helper: resolve data file path
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_geojson_path():
    path = os.environ.get("WATER_GEOJSON_PATH")
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, "water_company_boundaries.geojson")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"No water_company_boundaries.geojson found at {candidate}. "
        "Download from https://data.catchmentbasedapproach.org/datasets/water-company-boundaries "
        "and place in etl/data/, or set the WATER_GEOJSON_PATH env var."
    )


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest water company boundaries → core_water_company_lad.

    Strategy:
    1. Load GeoJSON; insert company polygons into a temp table (skip NAV insets).
    2. Truncate core_water_company_lad.
    3. Spatial join core_lad_boundaries × temp water companies; assign each LAD
       to the company with the largest intersection area.
    4. Drop temp table; return final row count.
    """
    geojson_path = _resolve_geojson_path()
    print(f"  Water GeoJSON: {geojson_path}", flush=True)

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    print(f"  Total features: {len(features)}", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    # Create temp table for company polygons
    cur.execute("DROP TABLE IF EXISTS _tmp_water_companies")
    cur.execute("""
        CREATE UNLOGGED TABLE _tmp_water_companies (
            id      SERIAL PRIMARY KEY,
            company TEXT,
            acronym TEXT,
            co_type TEXT,
            geom    GEOMETRY(MultiPolygon, 4326)
        )
    """)
    conn.commit()

    inserted = 0
    for feat in features:
        props    = feat.get("properties", {}) or {}
        company  = props.get("COMPANY", "")
        acronym  = props.get("Acronym", "")
        co_type  = props.get("CoType", "")
        geom     = feat.get("geometry")

        if not geom or not company:
            continue

        # Skip NAV (New Appointments and Variations) inset companies
        if "NAV" in (co_type or ""):
            continue

        geom_type = geom.get("type", "")
        # Normalise Polygon → MultiPolygon
        if geom_type == "Polygon":
            geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}

        geom_json = json.dumps(geom)
        try:
            cur.execute(
                """
                INSERT INTO _tmp_water_companies (company, acronym, co_type, geom)
                VALUES (
                    %s,
                    %s,
                    %s,
                    ST_Multi(
                        ST_CollectionExtract(
                            ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)),
                            3
                        )
                    )
                )
                """,
                (company, acronym, co_type, geom_json),
            )
            inserted += 1
        except Exception:
            conn.rollback()

    conn.commit()
    print(f"  Inserted {inserted} water company polygons", flush=True)

    # Add spatial index for join performance
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_tmp_water_geom ON _tmp_water_companies USING GIST (geom)"
    )
    conn.commit()

    # Truncate target and fill via spatial join (largest intersection area wins)
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['water_company_lad']} CASCADE")
    cur.execute(
        f"""
        INSERT INTO {TABLE_NAMES['water_company_lad']} (lad_code, water_company, water_company_type)
        SELECT DISTINCT ON (l.lad_code)
            l.lad_code,
            w.company,
            w.co_type
        FROM {TABLE_NAMES['lad_boundaries']} l
        JOIN _tmp_water_companies w
          ON NOT ST_IsEmpty(w.geom)
         AND ST_Intersects(l.geom, w.geom)
        ORDER BY l.lad_code, ST_Area(ST_Intersection(l.geom, ST_MakeValid(w.geom))) DESC
        """
    )
    conn.commit()

    # Drop temp table
    cur.execute("DROP TABLE IF EXISTS _tmp_water_companies")
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['water_company_lad']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
