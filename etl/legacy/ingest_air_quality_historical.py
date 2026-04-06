"""ETL: Download historical Defra PCM air quality data (2018-2023) and aggregate to LAD level.
Spatial joins each year's 1km grid to LAD boundaries, stores averages in core_air_quality_lad."""
import os, csv, io, tempfile, urllib.request, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")

DEFRA_BASE = "https://uk-air.defra.gov.uk/datastore/pcm"
YEARS = [2018, 2019, 2020, 2021, 2022, 2023]

FILE_PATTERNS = {
    "pm25": "mappm25{year}g.csv",
    "no2": "mapno2{year}.csv",
    "pm10": "mappm10{year}g.csv",
}


def download_csv(url):
    """Download a CSV from Defra and return the content as string."""
    print(f"  Downloading {url}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse-ETL/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  WARNING: Failed to download {url}: {e}")
        return None


def parse_grid_csv(content):
    """Parse Defra 1km grid CSV content. Returns dict of {(x,y): value}."""
    points = {}
    lines = content.splitlines()
    data_start = False
    for line in lines:
        stripped = line.strip().lower()
        if stripped.startswith("gridcode") or stripped.startswith("ukgridcode"):
            data_start = True
            continue
        if not data_start:
            continue
        parts = line.split(",")
        try:
            x = float(parts[1])
            y = float(parts[2])
            val = float(parts[3])
            points[(x, y)] = val
        except (ValueError, IndexError):
            continue
    return points


def ingest_year(conn, year):
    """Download, parse, temp-insert, spatial-join, and aggregate one year."""
    cur = conn.cursor()

    # Check if year already aggregated
    cur.execute("SELECT COUNT(*) FROM core_air_quality_lad WHERE year = %s", (year,))
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"Year {year}: already have {existing} LAD rows, skipping.")
        return

    print(f"\n=== Processing year {year} ===")

    # Download and parse each pollutant
    pollutant_data = {}
    for pollutant, pattern in FILE_PATTERNS.items():
        filename = pattern.format(year=year)
        url = f"{DEFRA_BASE}/{filename}"

        # Check if we have a local copy first
        local_path = os.path.expanduser(f"~/Desktop/geodepth/etl/data/air_quality/{filename}")
        if os.path.exists(local_path):
            print(f"  Using local file: {local_path}")
            with open(local_path, "r") as f:
                content = f.read()
        else:
            content = download_csv(url)

        if content:
            points = parse_grid_csv(content)
            pollutant_data[pollutant] = points
            print(f"  {pollutant}: {len(points):,} grid points")
        else:
            pollutant_data[pollutant] = {}

    if not any(pollutant_data.values()):
        print(f"  No data for year {year}, skipping.")
        return

    # Merge all grid coords
    all_coords = set()
    for pts in pollutant_data.values():
        all_coords |= set(pts.keys())
    print(f"  Total unique grid points: {len(all_coords):,}")

    # Insert into temporary table for spatial join
    cur.execute("""
        CREATE TEMP TABLE IF NOT EXISTS tmp_aq_grid (
            grid_x DOUBLE PRECISION,
            grid_y DOUBLE PRECISION,
            no2_ugm3 NUMERIC(8,2),
            pm25_ugm3 NUMERIC(8,2),
            pm10_ugm3 NUMERIC(8,2)
        )
    """)
    cur.execute("TRUNCATE tmp_aq_grid")

    rows = []
    for (x, y) in all_coords:
        rows.append((
            x, y,
            pollutant_data.get("no2", {}).get((x, y)),
            pollutant_data.get("pm25", {}).get((x, y)),
            pollutant_data.get("pm10", {}).get((x, y)),
        ))

    execute_values(cur, """
        INSERT INTO tmp_aq_grid (grid_x, grid_y, no2_ugm3, pm25_ugm3, pm10_ugm3)
        VALUES %s
    """, rows, page_size=10000)
    conn.commit()
    print(f"  Inserted {len(rows):,} grid points into temp table")

    # Add geometry column and build points
    cur.execute("ALTER TABLE tmp_aq_grid ADD COLUMN IF NOT EXISTS geom geometry(Point,4326)")
    cur.execute("""
        UPDATE tmp_aq_grid
        SET geom = ST_Transform(ST_SetSRID(ST_MakePoint(grid_x, grid_y), 27700), 4326)
    """)
    conn.commit()
    print("  Built geometries")

    # Create spatial index
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tmp_aq_geom ON tmp_aq_grid USING GIST (geom)")
    conn.commit()

    # Spatial join with LAD boundaries and aggregate
    print("  Running spatial join with LAD boundaries...")
    cur.execute("""
        INSERT INTO core_air_quality_lad (lad_code, year, no2_ugm3, pm25_ugm3, pm10_ugm3)
        SELECT lb.lad_code, %s,
               ROUND(AVG(t.no2_ugm3)::numeric, 2),
               ROUND(AVG(t.pm25_ugm3)::numeric, 2),
               ROUND(AVG(t.pm10_ugm3)::numeric, 2)
        FROM tmp_aq_grid t
        JOIN core_lad_boundaries lb ON ST_Intersects(lb.geom, t.geom)
        GROUP BY lb.lad_code
        ON CONFLICT (lad_code, year) DO UPDATE SET
            no2_ugm3 = EXCLUDED.no2_ugm3,
            pm25_ugm3 = EXCLUDED.pm25_ugm3,
            pm10_ugm3 = EXCLUDED.pm10_ugm3
    """, (year,))
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_air_quality_lad WHERE year = %s", (year,))
    count = cur.fetchone()[0]
    print(f"  Year {year}: {count} LAD rows inserted")

    # Clean up temp table
    cur.execute("TRUNCATE tmp_aq_grid")
    conn.commit()


def main():
    conn = psycopg2.connect(DB)
    for year in YEARS:
        ingest_year(conn, year)
    conn.close()

    # Summary
    conn2 = psycopg2.connect(DB)
    cur = conn2.cursor()
    cur.execute("SELECT year, COUNT(*), ROUND(AVG(pm25_ugm3)::numeric, 2) FROM core_air_quality_lad GROUP BY year ORDER BY year")
    print("\n=== Summary ===")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} LADs, avg PM2.5 = {row[2]} µg/m³")
    cur.close()
    conn2.close()


if __name__ == "__main__":
    main()
