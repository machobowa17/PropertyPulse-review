"""
sources/flood.py — EA Historic Flood Map → core_flood_zones

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_flood_zones)

Data files required in etl/data/ (or set env var to override):
    FLOOD_GPKG_PATH — Historic_Flood_Map.gpkg  (EA Flood Map for Planning)

Download from:
    https://www.data.gov.uk/dataset/bed63fc1-dd26-4685-b143-2941088923b3/flood-map-for-planning-rivers-and-sea-flood-zone-3
"""

import os

import geopandas as gpd
import psycopg2
from shapely.geometry import MultiPolygon

from constants import SCHEDULE_ANNUAL, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "flood",
    "description":        "EA Historic Flood Map GeoPackage → core_flood_zones (Flood Zone 2 and 3 polygons).",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         ["boundaries"],
    "tables_written":     [TABLE_NAMES["flood_zones"]],
    "cache_key_patterns": [],
    "expected_row_range": (10_000, 500_000),
}

# ---------------------------------------------------------------------------
# Helper: resolve data file path
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_gpkg_path():
    path = os.environ.get("FLOOD_GPKG_PATH")
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, "Historic_Flood_Map.gpkg")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"No Historic_Flood_Map.gpkg found at {candidate}. "
        "Download from https://www.data.gov.uk/dataset/bed63fc1-dd26-4685-b143-2941088923b3 "
        "and place in etl/data/, or set the FLOOD_GPKG_PATH env var."
    )


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest EA Historic Flood Map → core_flood_zones.

    Strategy:
    1. Read GeoPackage with geopandas; reproject to EPSG:4326.
    2. Truncate core_flood_zones.
    3. Insert each Polygon/MultiPolygon feature with flood_zone (2 or 3).
    4. Return final row count.
    """
    gpkg_path = _resolve_gpkg_path()
    print(f"  Flood source: {gpkg_path}", flush=True)

    gdf = gpd.read_file(gpkg_path)
    gdf = gdf.to_crs(epsg=4326)
    print(f"  Read {len(gdf):,} features; columns: {list(gdf.columns)}", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['flood_zones']} CASCADE")
    conn.commit()

    count = 0
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        if geom.geom_type == "Polygon":
            geom = MultiPolygon([geom])
        elif geom.geom_type != "MultiPolygon":
            continue

        # Determine flood zone from available attribute columns
        zone_raw = str(row.get("layer", row.get("type", row.get("ZONE", "3"))))
        flood_zone = "2" if "2" in zone_raw else "3"

        cur.execute(
            f"INSERT INTO {TABLE_NAMES['flood_zones']} (flood_zone, geom) "
            "VALUES (%s, ST_GeomFromText(%s, 4326))",
            (flood_zone, geom.wkt),
        )
        count += 1
        if count % 5000 == 0:
            conn.commit()
            print(f"    Inserted {count:,}...", flush=True)

    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['flood_zones']}")
    final = cur.fetchone()[0]
    cur.close()
    conn.close()
    return final
