"""ETL: Water Company Boundaries → core_water_company_lad.
Source: Ofwat via Stream Water Data Portal (CC-BY 4.0).
Maps LAD centroids to water company service areas via spatial lookup."""
import os, json, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
GEOJSON_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/water_company_boundaries.geojson")

def ingest():
    print("Ingesting water company boundaries...")

    # Load GeoJSON into PostGIS temp table, then spatial join with LAD centroids
    conn = psycopg2.connect(DB)
    cur = conn.cursor()

    # Create water company polygon table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS _tmp_water_companies (
            id SERIAL PRIMARY KEY,
            company TEXT,
            acronym TEXT,
            co_type TEXT,
            geom GEOMETRY(MultiPolygon, 4326)
        )
    """)
    cur.execute("TRUNCATE TABLE _tmp_water_companies")

    # Parse GeoJSON and insert polygons
    print("  Loading GeoJSON features...")
    with open(GEOJSON_PATH, "r") as f:
        data = json.load(f)

    features = data.get("features", [])
    print(f"  Total features: {len(features)}")

    inserted = 0
    for feat in features:
        props = feat.get("properties", {})
        company = props.get("COMPANY", "")
        acronym = props.get("Acronym", "")
        co_type = props.get("CoType", "")
        geom = feat.get("geometry")
        if not geom or not company:
            continue

        # Only include main regional companies (not NAV insets)
        if "NAV" in (co_type or ""):
            continue

        geom_type = geom.get("type", "")
        geom_json = json.dumps(geom)

        # Convert Polygon to MultiPolygon if needed
        if geom_type == "Polygon":
            geom_json = json.dumps({"type": "MultiPolygon", "coordinates": [geom["coordinates"]]})

        try:
            cur.execute("""
                INSERT INTO _tmp_water_companies (company, acronym, co_type, geom)
                VALUES (%s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
            """, (company, acronym, co_type, geom_json))
            inserted += 1
        except Exception as e:
            conn.rollback()
            continue

    conn.commit()
    print(f"  Inserted {inserted} water company polygons")

    # Create LAD → water company mapping via spatial join
    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_water_company_lad (
            lad_code TEXT PRIMARY KEY,
            water_company TEXT,
            water_company_type TEXT
        )
    """)
    cur.execute("TRUNCATE TABLE core_water_company_lad")

    cur.execute("""
        INSERT INTO core_water_company_lad (lad_code, water_company, water_company_type)
        SELECT DISTINCT ON (l.lad_code)
            l.lad_code,
            w.company,
            w.co_type
        FROM core_lad_boundaries l
        JOIN _tmp_water_companies w ON ST_Intersects(l.geom, w.geom)
        ORDER BY l.lad_code, ST_Area(ST_Intersection(l.geom, w.geom)) DESC
    """)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_water_company_lad")
    total = cur.fetchone()[0]
    print(f"  core_water_company_lad: {total} rows")

    cur.execute("SELECT water_company, COUNT(*) FROM core_water_company_lad GROUP BY water_company ORDER BY COUNT(*) DESC LIMIT 10")
    for row in cur.fetchall():
        print(f"    {row[0]}: {row[1]} LADs")

    # Cleanup temp table
    cur.execute("DROP TABLE IF EXISTS _tmp_water_companies")
    conn.commit()
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
