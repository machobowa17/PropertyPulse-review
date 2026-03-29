"""ETL: Police.uk Bulk Data → core_crime_lsoa. Bible: Tab 3 Environment.
Loads ALL months from the bulk ZIP for full coverage across all forces."""
import os, csv, io, zipfile, psycopg2
from collections import defaultdict
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
ZIP_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/police_latest.zip")

def ingest():
    print("Ingesting crime data...")

    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        all_street = [n for n in zf.namelist() if n.endswith("-street.csv")]
        months = sorted(set(n.split("/")[0] for n in all_street))
        target_months = months  # Load ALL months
        print(f"  Loading {len(target_months)} months: {target_months[0]} → {target_months[-1]}")

        all_rows = []
        for target in target_months:
            target_files = [n for n in all_street if n.startswith(target + "/")]
            print(f"  {target}: {len(target_files)} force files")

            counts = defaultdict(int)
            for fname in target_files:
                with zf.open(fname) as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                    for r in reader:
                        lsoa = r.get("LSOA code", "").strip()
                        if not lsoa.startswith("E"):
                            continue
                        crime_type = r.get("Crime type", "").strip()
                        if not crime_type:
                            continue
                        counts[(lsoa, crime_type)] += 1

            month_date = target + "-01"
            for (lsoa, crime_type), cnt in counts.items():
                all_rows.append((lsoa, month_date, crime_type, cnt))
            print(f"    {len(counts):,} LSOA × crime_type combos")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_crime_lsoa CASCADE")

    if all_rows:
        execute_values(cur, """INSERT INTO core_crime_lsoa
            (lsoa_code, month, crime_type, crime_count)
            VALUES %s ON CONFLICT DO NOTHING""", all_rows, page_size=10000)
        conn.commit()

    cur.execute("SELECT month, COUNT(*), SUM(crime_count) FROM core_crime_lsoa GROUP BY month ORDER BY month")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]:,} rows, {row[2]:,} crimes")
    cur.execute("SELECT COUNT(*) FROM core_crime_lsoa")
    print(f"  core_crime_lsoa total: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
