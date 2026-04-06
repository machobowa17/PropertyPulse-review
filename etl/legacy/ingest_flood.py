"""ETL: EA Flood Zones → core_flood_zones. Bible: Tab 3 Flood Risk."""
import os, psycopg2
import geopandas as gpd
from shapely.geometry import MultiPolygon

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
SRC = os.path.expanduser("~/Desktop/geodepth/etl/data/Historic_Flood_Map.gpkg")

def ingest():
    print("Ingesting flood zones...")
    gdf = gpd.read_file(SRC)
    gdf = gdf.to_crs(epsg=4326)
    print(f"  Read {len(gdf):,} features, columns: {list(gdf.columns)}")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_flood_zones CASCADE")

    count = 0
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        if geom.geom_type == "Polygon":
            geom = MultiPolygon([geom])
        elif geom.geom_type != "MultiPolygon":
            continue

        # Determine flood zone from attributes
        zone = str(row.get("layer", row.get("type", row.get("ZONE", "3"))))
        if "2" in zone:
            flood_zone = "2"
        else:
            flood_zone = "3"

        cur.execute("""INSERT INTO core_flood_zones (flood_zone, geom)
            VALUES (%s, ST_GeomFromText(%s, 4326))""", (flood_zone, geom.wkt))
        count += 1
        if count % 5000 == 0:
            conn.commit()
            print(f"  Inserted {count:,}...")

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_flood_zones")
    print(f"core_flood_zones: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
