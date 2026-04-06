"""ETL: UCL House Price per Square Metre → core_price_sqm_lsoa.
Source: UCL/London Datastore hpm_la_2024.zip (CC-BY 4.0).
Joins postcode → core_postcodes.lsoa_code to aggregate at LSOA level.
"""
import os, csv, io, zipfile, psycopg2
from collections import defaultdict
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
ZIP_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/hpm_la_2024.zip")


def ingest():
    print("Building LSOA-level price per sqm...")

    # Step 1: Load postcode → LSOA mapping from DB
    print("  Loading postcode → LSOA mapping...")
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT postcode, lsoa_code FROM core_postcodes WHERE lsoa_code IS NOT NULL")
    pc_to_lsoa = {}
    for pc, lsoa in cur.fetchall():
        # Normalize postcode: uppercase, strip spaces
        pc_to_lsoa[pc.replace(" ", "").upper()] = lsoa
    print(f"  Loaded {len(pc_to_lsoa):,} postcode→LSOA mappings")

    # Step 2: Parse UCL data, aggregate by LSOA
    lsoa_data = defaultdict(lambda: {
        "total_ppsm": 0.0, "count": 0,
        "by_type": defaultdict(lambda: {"total": 0.0, "count": 0}),
    })
    matched = 0
    unmatched = 0

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
                postcode = r.get("postcode", "").replace(" ", "").upper()
                ptype = r.get("propertytype", "").strip()

                if not ppsm_str or not postcode:
                    continue
                try:
                    ppsm = float(ppsm_str)
                except ValueError:
                    continue
                if ppsm <= 0 or ppsm > 50000:
                    continue

                lsoa = pc_to_lsoa.get(postcode)
                if not lsoa:
                    unmatched += 1
                    continue
                matched += 1

                lsoa_data[lsoa]["total_ppsm"] += ppsm
                lsoa_data[lsoa]["count"] += 1
                if ptype in ("D", "S", "T", "F"):
                    lsoa_data[lsoa]["by_type"][ptype]["total"] += ppsm
                    lsoa_data[lsoa]["by_type"][ptype]["count"] += 1

        if (i + 1) % 50 == 0:
            print(f"    Processed {i+1}/{len(csv_files)} files...")

    print(f"  Matched: {matched:,}, Unmatched: {unmatched:,}")
    print(f"  LSOAs with data: {len(lsoa_data):,}")

    # Step 3: Create table and insert
    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_price_sqm_lsoa (
            lsoa_code TEXT PRIMARY KEY,
            avg_price_per_sqm NUMERIC(10,2),
            avg_ppsm_detached NUMERIC(10,2),
            avg_ppsm_semi NUMERIC(10,2),
            avg_ppsm_terraced NUMERIC(10,2),
            avg_ppsm_flat NUMERIC(10,2),
            transaction_count INTEGER
        )
    """)
    cur.execute("TRUNCATE TABLE core_price_sqm_lsoa")

    rows = []
    for lsoa, d in lsoa_data.items():
        if d["count"] == 0:
            continue
        avg_ppsm = round(d["total_ppsm"] / d["count"], 2)
        by_type = d["by_type"]
        avg_d = round(by_type["D"]["total"] / by_type["D"]["count"], 2) if by_type["D"]["count"] else None
        avg_s = round(by_type["S"]["total"] / by_type["S"]["count"], 2) if by_type["S"]["count"] else None
        avg_t = round(by_type["T"]["total"] / by_type["T"]["count"], 2) if by_type["T"]["count"] else None
        avg_f = round(by_type["F"]["total"] / by_type["F"]["count"], 2) if by_type["F"]["count"] else None
        rows.append((lsoa, avg_ppsm, avg_d, avg_s, avg_t, avg_f, d["count"]))

    execute_values(cur, """
        INSERT INTO core_price_sqm_lsoa
        (lsoa_code, avg_price_per_sqm, avg_ppsm_detached, avg_ppsm_semi,
         avg_ppsm_terraced, avg_ppsm_flat, transaction_count)
        VALUES %s
    """, rows)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_price_sqm_lsoa")
    print(f"  core_price_sqm_lsoa: {cur.fetchone()[0]:,} rows")

    cur.execute("""
        SELECT lsoa_code, avg_price_per_sqm, transaction_count
        FROM core_price_sqm_lsoa ORDER BY avg_price_per_sqm DESC LIMIT 5
    """)
    print("  Top 5 most expensive LSOAs (per sqm):")
    for row in cur.fetchall():
        print(f"    {row[0]}: £{row[1]:,.0f}/sqm ({row[2]:,} txns)")

    cur.execute("""
        SELECT lsoa_code, avg_price_per_sqm, transaction_count
        FROM core_price_sqm_lsoa ORDER BY transaction_count DESC LIMIT 5
    """)
    print("  Top 5 LSOAs by transaction count:")
    for row in cur.fetchall():
        print(f"    {row[0]}: £{row[1]:,.0f}/sqm ({row[2]:,} txns)")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ingest()
