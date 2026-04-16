"""
sources/green_space.py — OS Open Greenspace → core_green_space

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_green_space)

Data files required in etl/data/ (or set env var to override):
    GREENSPACE_GPKG_PATH — path to opgrsp_gb.gpkg
                           (default: etl/data/greenspace/Data/opgrsp_gb.gpkg)

If the GPKG is not present but opgrsp_gpkg_gb.zip exists in etl/data/, it will
be extracted automatically.

Download from:
    https://osdatahub.os.uk/downloads/open/OpenGreenspace
"""

import os
import zipfile

import geopandas as gpd
import psycopg2
from shapely.geometry import MultiPolygon

from constants import SCHEDULE_ANNUAL, TABLE_NAMES
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "green_space",
    "description":        "OS Open Greenspace GeoPackage → core_green_space (parks, playing fields, allotments, etc.).",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["green_space"]],
    "cache_key_patterns": [],
    "expected_row_range": (50_000, 350_000),
}

# ---------------------------------------------------------------------------
# Helper: resolve data file path
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_gpkg_path():
    path = os.environ.get("GREENSPACE_GPKG_PATH")
    if path:
        return path

    # Standard extraction location
    gpkg = os.path.join(_ETL_DATA_DIR, "greenspace", "Data", "opgrsp_gb.gpkg")
    if os.path.exists(gpkg):
        return gpkg

    # Try extracting from ZIP if present
    zip_path = os.path.join(_ETL_DATA_DIR, "opgrsp_gpkg_gb.zip")
    if os.path.exists(zip_path):
        dest = os.path.join(_ETL_DATA_DIR, "greenspace")
        os.makedirs(dest, exist_ok=True)
        print(f"  Extracting {zip_path}...", flush=True)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(dest)
        if os.path.exists(gpkg):
            return gpkg

    raise FileNotFoundError(
        f"No opgrsp_gb.gpkg found. Expected at {gpkg}. "
        "Download OS Open Greenspace from https://osdatahub.os.uk/downloads/open/OpenGreenspace "
        "and place the ZIP in etl/data/, or set the GREENSPACE_GPKG_PATH env var."
    )


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest OS Open Greenspace → core_green_space.

    Strategy:
    1. Read greenspace_site layer from GeoPackage; reproject to EPSG:4326.
    2. Truncate core_green_space.
    3. Insert each Polygon/MultiPolygon site with name, type, area, centroid, geometry.
    4. Return final row count.
    """
    gpkg_path = _resolve_gpkg_path()
    print(f"  Greenspace source: {gpkg_path}", flush=True)

    gdf = gpd.read_file(gpkg_path, layer="greenspace_site")
    gdf = gdf.to_crs(epsg=4326)
    print(f"  Read {len(gdf):,} greenspace_site features", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['green_space']}_new (LIKE {TABLE_NAMES['green_space']} INCLUDING ALL)")
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

        name      = row.get("distName1", row.get("function", "")) or ""
        site_type = row.get("function", "") or ""
        centroid  = geom.centroid
        area_raw  = row.get("Area", 0) or 0
        # Area is in sq metres when large (>100), convert to hectares; already hectares when small
        area_ha   = area_raw / 10000 if area_raw > 100 else area_raw

        cur.execute(
            f"""
            INSERT INTO {TABLE_NAMES['green_space']}_new
                (site_name, site_type, area_hectares, latitude, longitude, geom)
            VALUES (%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))
            """,
            (name, site_type, area_ha, centroid.y, centroid.x, geom.wkt),
        )
        count += 1
        if count % 10_000 == 0:
            conn.commit()
            print(f"    Inserted {count:,}...", flush=True)

    conn.commit()

    blue_green_swap(conn, TABLE_NAMES['green_space'])
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['green_space']}")
    final = cur.fetchone()[0]
    cur.close()
    conn.close()
    return final
