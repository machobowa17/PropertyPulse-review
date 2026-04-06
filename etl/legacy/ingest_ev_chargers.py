"""ETL: OZEV Open Charge Point Data → core_ev_chargers. Bible: Tab 2."""
import os, csv, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
SRC = os.path.expanduser("~/Desktop/geodepth/etl/data/ev_chargepoints.csv")

def ingest():
    print("Ingesting EV chargepoints...")
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_ev_chargers CASCADE")

    rows = []
    with open(SRC, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lat = r.get("latitude", "")
            lon = r.get("longitude", "")
            try:
                lat_f = float(lat) if lat else None
                lon_f = float(lon) if lon else None
            except ValueError:
                continue
            if lat_f is None or lon_f is None:
                continue
            ref = r.get("referenceID", r.get("chargeDeviceID", ""))
            name = r.get("name", r.get("chargeDeviceName", ""))
            operator = r.get("deviceControllerName", r.get("operator", ""))
            try:
                connectors = int(r.get("connectorCount", r.get("connector1RatedOutputkW", "0")) or 0)
            except ValueError:
                connectors = 0
            try:
                power = float(r.get("ratedOutputKW", r.get("connector1RatedOutputkW", "0")) or 0)
            except ValueError:
                power = 0
            rows.append((ref, name, lat_f, lon_f, connectors, power, operator))

    print(f"  Collected {len(rows):,} chargepoints")
    if rows:
        execute_values(cur, """INSERT INTO core_ev_chargers
            (reference_id, name, latitude, longitude, connector_count, max_power_kw, operator)
            VALUES %s""", rows, page_size=5000)
        conn.commit()

    cur.execute("""UPDATE core_ev_chargers
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL""")
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_ev_chargers")
    print(f"core_ev_chargers: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
