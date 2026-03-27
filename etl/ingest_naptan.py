"""ETL: DfT NaPTAN → core_transport_stops. Bible: Tab 2 Transport & Commuting."""
import os, csv, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
SRC = os.path.expanduser("~/Desktop/geodepth/etl/data/naptan.csv")

def ingest():
    print("Ingesting NaPTAN transport stops...")
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_transport_stops CASCADE")

    rows = []
    with open(SRC, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            atco = r.get("ATCOCode", "").strip()
            if not atco:
                continue
            stop_type = r.get("StopType", "")
            lat = r.get("Latitude", "")
            lon = r.get("Longitude", "")
            try:
                lat_f = float(lat) if lat else None
                lon_f = float(lon) if lon else None
            except ValueError:
                continue
            if lat_f is None or lon_f is None:
                continue
            # England only (rough filter: lat > 49.9)
            if lat_f < 49.9 or lat_f > 56:
                continue
            rows.append((atco, r.get("CommonName", ""), stop_type, lat_f, lon_f, None))

    print(f"  Collected {len(rows):,} stops")
    if rows:
        execute_values(cur, """INSERT INTO core_transport_stops
            (atco_code, stop_name, stop_type, latitude, longitude, lad_code)
            VALUES %s ON CONFLICT DO NOTHING""", rows, page_size=10000)
        conn.commit()

    # Build geometry
    cur.execute("""UPDATE core_transport_stops
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL""")
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_transport_stops")
    print(f"core_transport_stops: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
