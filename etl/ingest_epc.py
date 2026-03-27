"""ETL: Nomis EPC Aggregated Data → core_epc_lsoa. Bible: Tab 3 Environment.
Source: ONS/Nomis Energy Efficiency of Housing dataset (NM_2401_1).
No API key required — uses .bulk.csv endpoint."""
import os, csv, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
EPC_PATH = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/epc_lsoa_nomis.csv")

def ingest():
    print("Ingesting EPC data from Nomis...")

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_epc_lsoa CASCADE")

    rows = []
    with open(EPC_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lsoa = r.get("geography code", "").strip()
            if not lsoa.startswith("E01"):  # England LSOAs only
                continue

            try:
                total = int(r.get("Energy efficiency rating: Total; measures: Value", "0") or 0)
                pct_a = float(r.get("Energy efficiency rating: Band A; measures: Percent", "0") or 0)
                pct_b = float(r.get("Energy efficiency rating: Band B; measures: Percent", "0") or 0)
                pct_c = float(r.get("Energy efficiency rating: Band C; measures: Percent", "0") or 0)
                pct_d = float(r.get("Energy efficiency rating: Band D; measures: Percent", "0") or 0)
                pct_e = float(r.get("Energy efficiency rating: Band E; measures: Percent", "0") or 0)
                pct_f = float(r.get("Energy efficiency rating: Band F; measures: Percent", "0") or 0)
                pct_g = float(r.get("Energy efficiency rating: Band G; measures: Percent", "0") or 0)
            except (ValueError, TypeError):
                continue

            if total == 0:
                continue

            pct_ab = round(pct_a + pct_b, 2)
            pct_eg = round(pct_e + pct_f + pct_g, 2)
            # Approximate energy score: A=92, B=81, C=69, D=55, E=39, F=21, G=1
            avg_score = round(
                (pct_a * 92 + pct_b * 81 + pct_c * 69 + pct_d * 55 + pct_e * 39 + pct_f * 21 + pct_g * 1) / 100, 1
            )

            rows.append((
                lsoa, total, avg_score, pct_ab, pct_c, pct_d, pct_eg, None
            ))

    print(f"  Collected {len(rows):,} LSOAs")
    if rows:
        execute_values(cur, """INSERT INTO core_epc_lsoa
            (lsoa_code, total_certs, avg_energy_score, pct_rating_a_b, pct_rating_c,
             pct_rating_d, pct_rating_e_g, avg_co2_emissions)
            VALUES %s ON CONFLICT DO NOTHING""", rows, page_size=10000)
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_epc_lsoa")
    print(f"core_epc_lsoa: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
