"""ETL: NHS ODS → core_nhs_facilities. Bible: Tab 2/4 Health Facilities.
Data format: [{ods_code, name, facility_type, postcode}] — geocode via core_postcodes."""
import os, json, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
NHS_DIR = os.path.expanduser("~/Desktop/geodepth/etl/data/nhs")

FACILITY_FILES = {
    "GP": "gp.json",
    "Hospital": "hospital.json",
    "Dentist": "dentist.json",
}

def ingest():
    print("Ingesting NHS facilities...")
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_nhs_facilities CASCADE")

    # Build postcode→lat/lon lookup from core_postcodes
    print("  Building postcode geocode lookup...")
    cur.execute("SELECT postcode, latitude, longitude FROM core_postcodes WHERE latitude IS NOT NULL")
    pc_lookup = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    print(f"  Loaded {len(pc_lookup):,} postcode coordinates")

    rows = []
    for ftype, fname in FACILITY_FILES.items():
        fpath = os.path.join(NHS_DIR, fname)
        if not os.path.exists(fpath):
            print(f"  Skipping {fname} (not found)")
            continue
        with open(fpath, "r") as f:
            data = json.load(f)
        facilities = data if isinstance(data, list) else data.get("Organisations", data.get("features", []))
        count = 0
        for item in facilities:
            if not isinstance(item, dict):
                continue
            org_code = item.get("ods_code", item.get("OrganisationCode", item.get("code", "")))
            name = item.get("name", item.get("OrganisationName", ""))
            postcode = item.get("postcode", item.get("Postcode", "")).strip()

            # Get lat/lon from postcode lookup
            coords = pc_lookup.get(postcode)
            lat = coords[0] if coords else None
            lon = coords[1] if coords else None

            if lat is not None and lon is not None:
                rows.append((org_code, name, ftype, lat, lon, postcode))
                count += 1

        print(f"  {ftype}: {count:,} geocoded")

    print(f"  Total collected: {len(rows):,} facilities")
    if rows:
        execute_values(cur, """INSERT INTO core_nhs_facilities
            (org_code, name, facility_type, latitude, longitude, postcode)
            VALUES %s""", rows, page_size=5000)
        conn.commit()

    cur.execute("""UPDATE core_nhs_facilities
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL""")
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_nhs_facilities")
    print(f"core_nhs_facilities: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
