"""ETL: UCL House Price per Square Metre → core_price_sqm_lad.
Source: UCL/London Datastore hpm_la_2024.zip (CC-BY 4.0).
Bible: Tab 1, Price per Sqft."""
import os, csv, io, zipfile, psycopg2
from collections import defaultdict
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
ZIP_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/hpm_la_2024.zip")

def ingest():
    print("Ingesting price per sqm data...")

    # Aggregate by LAD: sum of prices, count, for recent years (2020+)
    lad_data = defaultdict(lambda: {"total_ppsm": 0.0, "count": 0, "by_type": defaultdict(lambda: {"total": 0.0, "count": 0})})

    z = zipfile.ZipFile(ZIP_PATH)
    csv_files = [n for n in z.namelist() if n.endswith('.csv')]
    print(f"  Processing {len(csv_files)} LAD files...")

    for i, name in enumerate(csv_files):
        with z.open(name) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8', errors='replace'))
            for r in reader:
                try:
                    year = int(r.get("year", "0"))
                except ValueError:
                    continue
                if year < 2020:
                    continue

                ppsm_str = r.get("priceper", "")
                lad = r.get("lad23cd", "").strip()
                ptype = r.get("propertytype", "").strip()

                if not ppsm_str or not lad or not lad.startswith("E"):
                    continue
                try:
                    ppsm = float(ppsm_str)
                except ValueError:
                    continue
                if ppsm <= 0 or ppsm > 50000:  # sanity check
                    continue

                lad_data[lad]["total_ppsm"] += ppsm
                lad_data[lad]["count"] += 1
                if ptype in ("D", "S", "T", "F"):
                    lad_data[lad]["by_type"][ptype]["total"] += ppsm
                    lad_data[lad]["by_type"][ptype]["count"] += 1

        if (i + 1) % 50 == 0:
            print(f"    Processed {i+1}/{len(csv_files)} files...")

    print(f"  LADs with data: {len(lad_data)}")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_price_sqm_lad (
            lad_code TEXT PRIMARY KEY,
            avg_price_per_sqm NUMERIC(10,2),
            avg_ppsm_detached NUMERIC(10,2),
            avg_ppsm_semi NUMERIC(10,2),
            avg_ppsm_terraced NUMERIC(10,2),
            avg_ppsm_flat NUMERIC(10,2),
            transaction_count INTEGER
        )
    """)
    cur.execute("TRUNCATE TABLE core_price_sqm_lad")

    rows = []
    for lad, d in lad_data.items():
        if d["count"] == 0:
            continue
        avg_ppsm = round(d["total_ppsm"] / d["count"], 2)
        by_type = d["by_type"]
        avg_d = round(by_type["D"]["total"] / by_type["D"]["count"], 2) if by_type["D"]["count"] else None
        avg_s = round(by_type["S"]["total"] / by_type["S"]["count"], 2) if by_type["S"]["count"] else None
        avg_t = round(by_type["T"]["total"] / by_type["T"]["count"], 2) if by_type["T"]["count"] else None
        avg_f = round(by_type["F"]["total"] / by_type["F"]["count"], 2) if by_type["F"]["count"] else None
        rows.append((lad, avg_ppsm, avg_d, avg_s, avg_t, avg_f, d["count"]))

    execute_values(cur, """
        INSERT INTO core_price_sqm_lad
        (lad_code, avg_price_per_sqm, avg_ppsm_detached, avg_ppsm_semi,
         avg_ppsm_terraced, avg_ppsm_flat, transaction_count)
        VALUES %s
    """, rows)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_price_sqm_lad")
    print(f"  core_price_sqm_lad: {cur.fetchone()[0]:,} rows")

    cur.execute("SELECT lad_code, avg_price_per_sqm, transaction_count FROM core_price_sqm_lad ORDER BY avg_price_per_sqm DESC LIMIT 5")
    print("  Top 5 most expensive (per sqm):")
    for row in cur.fetchall():
        print(f"    {row[0]}: £{row[1]:,.0f}/sqm ({row[2]:,} txns)")

    cur.close()
    conn.close()

if __name__ == "__main__":
    ingest()
