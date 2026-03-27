"""ETL: Ofcom Connected Nations → core_broadband_postcode. Bible: Tab 2 Connectivity.
Uses Ofcom postcode-level fixed coverage data (multiple CSV files by postcode area)."""
import os, csv, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
# Already extracted
BROADBAND_DIR = os.path.expanduser(
    "~/Desktop/Manus Take 2/etl/data/broadband/202407_fixed_postcode_coverage_r01/postcode_files"
)

def ingest():
    print("Ingesting broadband data...")

    csv_files = [
        os.path.join(BROADBAND_DIR, f) for f in os.listdir(BROADBAND_DIR) if f.endswith(".csv")
    ]
    print(f"  Found {len(csv_files)} postcode area files")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_broadband_postcode CASCADE")

    total = 0
    for csv_path in sorted(csv_files):
        rows = []
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for r in reader:
                pc = r.get("postcode_space", "").strip()
                if not pc:
                    continue

                try:
                    sfbb = float(r.get("SFBB availability (% premises)", "") or 0)
                    ufbb = float(r.get("UFBB availability (% premises)", "") or 0)
                    gigabit = float(r.get("Gigabit availability (% premises)", "") or 0)
                    # No direct avg speed in coverage data — use 0 as placeholder
                    # Coverage data has availability percentages, not speeds
                except (ValueError, TypeError):
                    continue

                rows.append((pc, None, None, sfbb, ufbb, gigabit, None))

        if rows:
            execute_values(cur, """INSERT INTO core_broadband_postcode
                (postcode, avg_download_mbps, avg_upload_mbps, superfast_pct, ultrafast_pct, gigabit_pct, fttp_pct)
                VALUES %s ON CONFLICT DO NOTHING""", rows, page_size=10000)
            conn.commit()
            total += len(rows)

    print(f"  Inserted {total:,} postcodes total")
    cur.execute("SELECT COUNT(*) FROM core_broadband_postcode")
    print(f"core_broadband_postcode: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
