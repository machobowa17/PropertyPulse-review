"""ETL: OS Open Greenspace → core_green_space. Bible: Tab 3 Green Space."""
import os, psycopg2
import geopandas as gpd
from shapely.geometry import MultiPolygon

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
SRC = os.path.expanduser("~/Desktop/geodepth/etl/data/greenspace/Data/opgrsp_gb.gpkg")

def ingest():
    print("Ingesting green space...")
    if not os.path.exists(SRC):
        # Try extracting from zip
        zip_path = os.path.expanduser("~/Desktop/geodepth/etl/data/opgrsp_gpkg_gb.zip")
        if os.path.exists(zip_path):
            import zipfile
            dest = os.path.expanduser("~/Desktop/geodepth/etl/data/greenspace")
            os.makedirs(dest, exist_ok=True)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(dest)
            print("  Extracted greenspace zip")

    gdf = gpd.read_file(SRC, layer="greenspace_site")
    gdf = gdf.to_crs(epsg=4326)
    print(f"  Read {len(gdf):,} greenspace_site features, columns: {list(gdf.columns)[:8]}")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_green_space CASCADE")

    count = 0
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        if geom.geom_type == "Polygon":
            geom = MultiPolygon([geom])
        elif geom.geom_type != "MultiPolygon":
            continue

        name = row.get("distName1", row.get("function", ""))
        site_type = row.get("function", "")
        centroid = geom.centroid
        area = row.get("Area", 0) or 0

        cur.execute("""INSERT INTO core_green_space (site_name, site_type, area_hectares, latitude, longitude, geom)
            VALUES (%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))""",
            (name, site_type, area / 10000 if area > 100 else area, centroid.y, centroid.x, geom.wkt))
        count += 1
        if count % 10000 == 0:
            conn.commit()
            print(f"  Inserted {count:,}...")

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_green_space")
    print(f"core_green_space: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
