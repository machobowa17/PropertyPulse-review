"""ETL: Defra PCM Air Quality → core_air_quality. Bible: Tab 3 Environment.
CSV format: gridcode,x,y,value (with 5 header rows before data header)."""
import os, csv, psycopg2
from psycopg2.extras import execute_values
from pyproj import Transformer

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
AQ_DIR = os.path.expanduser("~/Desktop/geodepth/etl/data/air_quality")

# BNG to WGS84
transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

def parse_grid_csv(filepath):
    """Parse Defra 1km grid CSV. Format: gridcode,x,y,value with multi-line header."""
    points = {}
    with open(filepath, "r") as f:
        # Skip header rows until we find 'gridcode' row
        for line in f:
            if line.strip().startswith("gridcode"):
                break
        reader = csv.reader(f)
        for row in reader:
            try:
                x = float(row[1])
                y = float(row[2])
                val = float(row[3])
                points[(x, y)] = val
            except (ValueError, IndexError):
                continue
    return points

def ingest():
    print("Ingesting air quality data...")
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_air_quality CASCADE")

    # Parse all three pollutants
    no2 = {}
    pm25 = {}
    pm10 = {}

    no2_file = os.path.join(AQ_DIR, "mapno22024.csv")
    if os.path.exists(no2_file):
        no2 = parse_grid_csv(no2_file)
        print(f"  NO2 points: {len(no2):,}")

    pm25_file = os.path.join(AQ_DIR, "mappm252024g.csv")
    if os.path.exists(pm25_file):
        pm25 = parse_grid_csv(pm25_file)
        print(f"  PM2.5 points: {len(pm25):,}")

    pm10_file = os.path.join(AQ_DIR, "mappm102024g.csv")
    if os.path.exists(pm10_file):
        pm10 = parse_grid_csv(pm10_file)
        print(f"  PM10 points: {len(pm10):,}")

    # Merge all grid points
    all_coords = set(no2.keys()) | set(pm25.keys()) | set(pm10.keys())
    print(f"  Unique grid points: {len(all_coords):,}")

    rows = []
    for (x, y) in all_coords:
        lon, lat = transformer.transform(x, y)
        rows.append((
            x, y,
            no2.get((x, y)),
            pm25.get((x, y)),
            pm10.get((x, y)),
            2024,
            lat, lon
        ))

    if rows:
        execute_values(cur, """INSERT INTO core_air_quality
            (grid_x, grid_y, no2_ugm3, pm25_ugm3, pm10_ugm3, year)
            VALUES %s""",
            [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows], page_size=10000)
        conn.commit()
        print(f"  Inserted {len(rows):,} rows")

        # Build geometry using PostGIS transform (BNG → WGS84)
        print("  Building geometry from BNG coordinates...")
        cur.execute("""
            UPDATE core_air_quality
            SET geom = ST_Transform(ST_SetSRID(ST_MakePoint(grid_x, grid_y), 27700), 4326)
            WHERE geom IS NULL
        """)
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_air_quality")
    print(f"core_air_quality: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
