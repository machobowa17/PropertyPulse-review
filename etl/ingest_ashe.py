"""ETL: ONS ASHE Median Earnings → core_earnings_lad.
Source: Nomis NM_30_1 (ASHE Resident Analysis), OGL v3.
Bible: Tab 1, Affordability (rent as % of local median income)."""
import os, csv, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
CSV_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/ashe_median_earnings.csv")

def ingest():
    print("Ingesting ASHE median earnings...")
    rows = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lad_code = r.get("GEOGRAPHY_CODE", "").strip()
            if not lad_code.startswith("E"):
                continue
            val = r.get("OBS_VALUE", "").strip()
            if not val or val == "..":
                continue
            try:
                median_earnings = float(val)
            except ValueError:
                continue
            rows.append((lad_code, r.get("GEOGRAPHY_NAME", "").strip(), median_earnings))

    print(f"  Parsed {len(rows)} LADs with earnings data")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_earnings_lad (
            lad_code TEXT PRIMARY KEY,
            lad_name TEXT,
            median_annual_earnings NUMERIC(10,2)
        )
    """)
    cur.execute("TRUNCATE TABLE core_earnings_lad")
    execute_values(cur, """
        INSERT INTO core_earnings_lad (lad_code, lad_name, median_annual_earnings)
        VALUES %s
    """, rows)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_earnings_lad")
    print(f"  core_earnings_lad: {cur.fetchone()[0]:,} rows")

    cur.execute("SELECT lad_code, lad_name, median_annual_earnings FROM core_earnings_lad ORDER BY median_annual_earnings DESC LIMIT 5")
    for row in cur.fetchall():
        print(f"    {row[1]} ({row[0]}): £{row[2]:,.0f}")

    cur.close(); conn.close()

if __name__ == "__main__": ingest()
