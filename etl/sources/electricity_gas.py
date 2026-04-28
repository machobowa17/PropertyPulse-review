"""
sources/electricity_gas.py — DNO & GDN boundaries → core_electricity_dno_lad + core_gas_gdn_lad

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_electricity_dno_lad)

Data files required in etl/data/:
    gb_dno_licence_areas.geojson — NESO DNO licence area boundaries (EPSG:27700)
        Download from https://www.neso.energy/data-portal/gis-boundaries-gb-dno-license-areas

Strategy:
    1. Load DNO GeoJSON (14 polygons, EPSG:27700).
    2. Spatial join: LAD boundaries × DNO polygons → assign each LAD to DNO with largest overlap.
    3. Derive GDN from DNO region code (approximate — GDN regions roughly align with DNO regions).
    4. Blue-green swap both tables.
"""

import json
import os

import psycopg2

from constants import SCHEDULE_ANNUAL, TABLE_NAMES
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "electricity_gas",
    "description":        "NESO DNO licence area GeoJSON → core_electricity_dno_lad + core_gas_gdn_lad via LAD spatial join.",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         ["boundaries"],
    "tables_written":     [TABLE_NAMES["electricity_dno_lad"], TABLE_NAMES["gas_gdn_lad"]],
    "cache_key_patterns": [],
    "expected_row_range": (300, 400),
}

# ---------------------------------------------------------------------------
# DNO region code → GDN mapping
# ---------------------------------------------------------------------------
# GDN regions broadly align with DNO regions. 4 GDN operators, 8 GDN regions.
# This mapping is approximate (~95% accuracy at LAD level).
# Edge case: South London is SGN not Cadent — handled by the SGN Southern mapping
# since UKPN South East (_J) covers south London and maps to SGN.

DNO_TO_GDN = {
    "_A": ("Cadent", "East of England"),
    "_B": ("Cadent", "East Midlands"),
    "_C": ("Cadent", "North London"),
    "_D": ("Cadent", "North West"),
    "_E": ("Cadent", "West Midlands"),
    "_F": ("Northern Gas Networks", "North of England"),
    "_G": ("Cadent", "North West"),
    "_H": ("SGN", "Southern"),
    "_J": ("SGN", "Southern"),
    "_K": ("Wales & West Utilities", "Wales"),
    "_L": ("Wales & West Utilities", "South West"),
    "_M": ("Northern Gas Networks", "Yorkshire"),
    "_N": ("SGN", "Scotland"),
    "_P": ("SGN", "Scotland"),
}

# ---------------------------------------------------------------------------
# Helper: resolve data file path
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_geojson_path():
    path = os.environ.get("DNO_GEOJSON_PATH")
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, "gb_dno_licence_areas.geojson")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"No gb_dno_licence_areas.geojson found at {candidate}. "
        "Download from https://www.neso.energy/data-portal/gis-boundaries-gb-dno-license-areas "
        "and place in etl/data/, or set the DNO_GEOJSON_PATH env var."
    )


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest DNO licence area boundaries → core_electricity_dno_lad + core_gas_gdn_lad.

    Strategy:
    1. Load GeoJSON; insert DNO polygons into a temp table.
    2. Spatial join core_lad_boundaries × temp DNO areas; assign each LAD
       to the DNO with the largest intersection area.
    3. Derive GDN from DNO region code.
    4. Blue-green swap both tables; return final row count.
    """
    geojson_path = _resolve_geojson_path()
    print(f"  DNO GeoJSON: {geojson_path}", flush=True)

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    print(f"  Total features: {len(features)}", flush=True)

    # Detect CRS — NESO file uses EPSG:27700 (BNG)
    crs = data.get("crs", {})
    crs_name = crs.get("properties", {}).get("name", "")
    is_bng = "27700" in crs_name
    srid = 27700 if is_bng else 4326
    print(f"  CRS: {crs_name} → SRID {srid}", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    # Create temp table for DNO polygons
    cur.execute("DROP TABLE IF EXISTS _tmp_dno_areas")
    cur.execute(f"""
        CREATE UNLOGGED TABLE _tmp_dno_areas (
            id          SERIAL PRIMARY KEY,
            dno_code    TEXT,
            dno_name    TEXT,
            dno_region  TEXT,
            geom        GEOMETRY(MultiPolygon, {srid})
        )
    """)
    conn.commit()

    inserted = 0
    for feat in features:
        props = feat.get("properties", {}) or {}
        dno_code = props.get("Name", "")
        dno_name = props.get("DNO_Full", "") or props.get("DNO", "")
        dno_region = props.get("Area", "")
        geom = feat.get("geometry")

        if not geom or not dno_name:
            continue

        geom_type = geom.get("type", "")
        if geom_type == "Polygon":
            geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}

        geom_json = json.dumps(geom)
        try:
            cur.execute(
                f"""
                INSERT INTO _tmp_dno_areas (dno_code, dno_name, dno_region, geom)
                VALUES (
                    %s, %s, %s,
                    ST_Multi(
                        ST_CollectionExtract(
                            ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(%s), {srid})),
                            3
                        )
                    )
                )
                """,
                (dno_code, dno_name, dno_region, geom_json),
            )
            inserted += 1
        except Exception as e:
            print(f"  WARN: Failed to insert {dno_code}: {e}", flush=True)
            conn.rollback()

    conn.commit()
    print(f"  Inserted {inserted} DNO polygons", flush=True)

    # Spatial index for join performance
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tmp_dno_geom ON _tmp_dno_areas USING GIST (geom)")
    conn.commit()

    # --- Electricity DNO ---
    tbl_dno = TABLE_NAMES["electricity_dno_lad"]
    cur.execute(f"CREATE UNLOGGED TABLE {tbl_dno}_new (LIKE {tbl_dno} INCLUDING ALL)")
    conn.commit()

    # If source is BNG (27700), LAD boundaries are also BNG — direct join.
    # If source is 4326, transform LAD boundaries.
    if is_bng:
        join_sql = f"""
            INSERT INTO {tbl_dno}_new (lad_code, dno_name, dno_region, dno_code)
            SELECT DISTINCT ON (l.lad_code)
                l.lad_code,
                d.dno_name,
                d.dno_region,
                d.dno_code
            FROM {TABLE_NAMES['lad_boundaries']} l
            JOIN _tmp_dno_areas d
              ON NOT ST_IsEmpty(d.geom)
             AND ST_Intersects(ST_Transform(l.geom, 27700), d.geom)
            ORDER BY l.lad_code, ST_Area(ST_Intersection(ST_Transform(l.geom, 27700), ST_MakeValid(d.geom))) DESC
        """
    else:
        join_sql = f"""
            INSERT INTO {tbl_dno}_new (lad_code, dno_name, dno_region, dno_code)
            SELECT DISTINCT ON (l.lad_code)
                l.lad_code,
                d.dno_name,
                d.dno_region,
                d.dno_code
            FROM {TABLE_NAMES['lad_boundaries']} l
            JOIN _tmp_dno_areas d
              ON NOT ST_IsEmpty(d.geom)
             AND ST_Intersects(l.geom, d.geom)
            ORDER BY l.lad_code, ST_Area(ST_Intersection(l.geom, ST_MakeValid(d.geom))) DESC
        """

    cur.execute(join_sql)
    conn.commit()

    blue_green_swap(conn, tbl_dno)
    cur.execute(f"SELECT COUNT(*) FROM {tbl_dno}")
    dno_count = cur.fetchone()[0]
    print(f"  core_electricity_dno_lad: {dno_count} rows", flush=True)

    # --- Gas GDN (derived from DNO) ---
    tbl_gdn = TABLE_NAMES["gas_gdn_lad"]
    cur.execute(f"CREATE UNLOGGED TABLE {tbl_gdn}_new (LIKE {tbl_gdn} INCLUDING ALL)")
    conn.commit()

    cur.execute(f"SELECT lad_code, dno_code FROM {tbl_dno}")
    dno_rows = cur.fetchall()

    gdn_count = 0
    for lad_code, dno_code in dno_rows:
        gdn = DNO_TO_GDN.get(dno_code)
        if gdn:
            cur.execute(
                f"INSERT INTO {tbl_gdn}_new (lad_code, gdn_name, gdn_region) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (lad_code, gdn[0], gdn[1]),
            )
            gdn_count += 1

    conn.commit()
    blue_green_swap(conn, tbl_gdn)
    print(f"  core_gas_gdn_lad: {gdn_count} rows", flush=True)

    # Clean up
    cur.execute("DROP TABLE IF EXISTS _tmp_dno_areas")
    conn.commit()

    cur.close()
    conn.close()
    return dno_count
