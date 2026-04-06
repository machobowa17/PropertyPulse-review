"""
ETL: ONS Open Geography Portal → core_lsoa_boundaries, core_ward_boundaries, core_lad_boundaries
Source: ONS ArcGIS FeatureServer (GeoJSON bulk download)
Schema: Build Bible Part 2, Section 2.1
"""
import os
import requests
import geopandas as gpd
import psycopg2
from shapely import wkb
from shapely.geometry import shape, MultiPolygon, Polygon

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres@localhost:5432/ukproperty",
)

# ONS Open Geography Portal — generalised clipped boundaries (BGC = Generalised Clipped)
BOUNDARY_URLS = {
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

# Column mappings per boundary type
COLUMN_MAPS = {
    "lsoa": {
        "code_field": "LSOA21CD",
        "name_field": "LSOA21NM",
    },
    "ward": {
        "code_field": "WD25CD",
        "name_field": "WD25NM",
    },
    "lad": {
        "code_field": "LAD25CD",
        "name_field": "LAD25NM",
    },
}


def fetch_all_features(url, code_field):
    """Fetch all features from an ArcGIS FeatureServer with pagination."""
    all_features = []
    offset = 0
    page_size = 1000

    while True:
        params = {
            "where": f"{code_field} LIKE 'E%'",  # England only
            "outFields": "*",
            "outSR": "4326",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": page_size,
        }
        print(f"  Fetching offset {offset}...")
        resp = requests.get(url, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)
        offset += len(features)

        # If we got fewer than page_size, we're done
        if len(features) < page_size:
            break

    return {"type": "FeatureCollection", "features": all_features}


def ensure_multipolygon(geom):
    """Convert Polygon to MultiPolygon if needed."""
    if geom is None:
        return None
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    return geom


def ingest_lsoa_boundaries(conn):
    """Ingest LSOA boundaries into core_lsoa_boundaries."""
    print("\n=== Ingesting LSOA boundaries ===")
    url = BOUNDARY_URLS["lsoa"]
    cols = COLUMN_MAPS["lsoa"]

    geojson = fetch_all_features(url, cols["code_field"])
    print(f"  Fetched {len(geojson['features'])} LSOA features")

    if not geojson["features"]:
        print("  WARNING: No features fetched. Skipping.")
        return

    gdf = gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")

    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_lsoa_boundaries CASCADE")

    count = 0
    for _, row in gdf.iterrows():
        code = row.get(cols["code_field"])
        name = row.get(cols["name_field"])
        geom = ensure_multipolygon(row.geometry)
        if code is None or geom is None:
            continue

        # Get MSOA and LAD codes from core_postcodes (majority vote)
        msoa_code = None
        lad_code = None

        wkt = geom.wkt
        cur.execute(
            """INSERT INTO core_lsoa_boundaries (lsoa_code, lsoa_name, msoa_code, lad_code, geom)
               VALUES (%s, %s, %s, %s, ST_GeomFromText(%s, 4326))
               ON CONFLICT (lsoa_code) DO UPDATE SET
                 lsoa_name = EXCLUDED.lsoa_name,
                 geom = EXCLUDED.geom""",
            (code, name, msoa_code, lad_code, wkt),
        )
        count += 1

    conn.commit()

    # Backfill msoa_code and lad_code from core_postcodes
    print("  Backfilling MSOA and LAD codes from core_postcodes...")
    cur.execute("""
        UPDATE core_lsoa_boundaries lb
        SET msoa_code = sub.msoa_code,
            lad_code = sub.lad_code
        FROM (
            SELECT lsoa_code,
                   MODE() WITHIN GROUP (ORDER BY msoa_code) AS msoa_code,
                   MODE() WITHIN GROUP (ORDER BY lad_code) AS lad_code
            FROM core_postcodes
            WHERE lsoa_code IS NOT NULL
            GROUP BY lsoa_code
        ) sub
        WHERE lb.lsoa_code = sub.lsoa_code
    """)
    conn.commit()

    print(f"  Inserted {count} LSOA boundaries")
    cur.close()


def ingest_ward_boundaries(conn):
    """Ingest ward boundaries into core_ward_boundaries."""
    print("\n=== Ingesting Ward boundaries ===")
    url = BOUNDARY_URLS["ward"]
    cols = COLUMN_MAPS["ward"]

    geojson = fetch_all_features(url, cols["code_field"])
    print(f"  Fetched {len(geojson['features'])} Ward features")

    if not geojson["features"]:
        print("  WARNING: No features fetched. Skipping.")
        return

    gdf = gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")

    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_ward_boundaries CASCADE")

    count = 0
    for _, row in gdf.iterrows():
        code = row.get(cols["code_field"])
        name = row.get(cols["name_field"])
        geom = ensure_multipolygon(row.geometry)
        if code is None or geom is None:
            continue

        # Get LAD code from core_postcodes
        lad_code = None

        wkt = geom.wkt
        cur.execute(
            """INSERT INTO core_ward_boundaries (ward_code, ward_name, lad_code, geom)
               VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326))
               ON CONFLICT (ward_code) DO UPDATE SET
                 ward_name = EXCLUDED.ward_name,
                 geom = EXCLUDED.geom""",
            (code, name, lad_code, wkt),
        )
        count += 1

    conn.commit()

    # Backfill lad_code from core_postcodes
    print("  Backfilling LAD codes from core_postcodes...")
    cur.execute("""
        UPDATE core_ward_boundaries wb
        SET lad_code = sub.lad_code
        FROM (
            SELECT ward_code,
                   MODE() WITHIN GROUP (ORDER BY lad_code) AS lad_code
            FROM core_postcodes
            WHERE ward_code IS NOT NULL
            GROUP BY ward_code
        ) sub
        WHERE wb.ward_code = sub.ward_code
    """)
    conn.commit()

    print(f"  Inserted {count} Ward boundaries")
    cur.close()


def ingest_lad_boundaries(conn):
    """Ingest LAD boundaries into core_lad_boundaries."""
    print("\n=== Ingesting LAD boundaries ===")
    url = BOUNDARY_URLS["lad"]
    cols = COLUMN_MAPS["lad"]

    geojson = fetch_all_features(url, cols["code_field"])
    print(f"  Fetched {len(geojson['features'])} LAD features")

    if not geojson["features"]:
        print("  WARNING: No features fetched. Skipping.")
        return

    gdf = gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")

    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_lad_boundaries CASCADE")

    count = 0
    for _, row in gdf.iterrows():
        code = row.get(cols["code_field"])
        name = row.get(cols["name_field"])
        geom = ensure_multipolygon(row.geometry)
        if code is None or geom is None:
            continue

        wkt = geom.wkt
        cur.execute(
            """INSERT INTO core_lad_boundaries (lad_code, lad_name, geom)
               VALUES (%s, %s, ST_GeomFromText(%s, 4326))
               ON CONFLICT (lad_code) DO UPDATE SET
                 lad_name = EXCLUDED.lad_name,
                 geom = EXCLUDED.geom""",
            (code, name, wkt),
        )
        count += 1

    conn.commit()

    # Backfill county and region from core_postcodes
    print("  Backfilling county and region from core_postcodes...")
    cur.execute("""
        UPDATE core_lad_boundaries lb
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
            FROM core_postcodes
            WHERE lad_code IS NOT NULL
            GROUP BY lad_code
        ) sub
        WHERE lb.lad_code = sub.lad_code
    """)
    conn.commit()

    print(f"  Inserted {count} LAD boundaries")
    cur.close()


def ingest():
    conn = psycopg2.connect(DB_URL)
    ingest_lsoa_boundaries(conn)
    ingest_ward_boundaries(conn)
    ingest_lad_boundaries(conn)
    conn.close()
    print("\nAll boundary ingestion complete.")


if __name__ == "__main__":
    ingest()
