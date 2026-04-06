"""ETL: Tab 2 extra datasets → PTAL, cycling, mobile coverage.
Sources:
  - TfL PTAL LSOA 2015 (OGL) → core_ptal_lsoa (London only)
  - Census 2021 TS061 Travel to Work (OGL) → core_cycling_lsoa
  - Ofcom Connected Nations Mobile 2024 (OGL) → core_mobile_coverage_lad
"""
import os, csv, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
DATA_DIR = os.path.expanduser("~/Desktop/Manus Take 2/etl/data")

def ingest_ptal():
    """TfL PTAL scores for London LSOAs."""
    print("Ingesting PTAL (London LSOAs)...")
    path = os.path.join(DATA_DIR, "ptal_lsoa_2015.csv")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lsoa = r.get("LSOA2011", "").strip()
            if not lsoa.startswith("E"):
                continue
            try:
                avg_ptai = float(r.get("AvPTAI2015", "0"))
                ptal_band = r.get("PTAL", "").strip()
            except (ValueError, TypeError):
                continue
            rows.append((lsoa, avg_ptai, ptal_band))

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_ptal_lsoa (
            lsoa_code TEXT PRIMARY KEY,
            avg_ptai NUMERIC(8,2),
            ptal_band TEXT
        )
    """)
    cur.execute("TRUNCATE TABLE core_ptal_lsoa")
    execute_values(cur, "INSERT INTO core_ptal_lsoa (lsoa_code, avg_ptai, ptal_band) VALUES %s", rows)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_ptal_lsoa")
    print(f"  core_ptal_lsoa: {cur.fetchone()[0]:,} rows (London only)")
    cur.close(); conn.close()


def ingest_cycling():
    """Census 2021 TS061 — % cycling and % WFH by LSOA."""
    print("Ingesting cycling + WFH (Census TS061)...")
    path = os.path.join(DATA_DIR, "census2021-ts061-lsoa.csv")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lsoa = r.get("geography code", "").strip()
            if not lsoa.startswith("E"):
                continue
            total_col = "Method of travel to workplace: Total: All usual residents aged 16 years and over in employment the week before the census"
            cycle_col = "Method of travel to workplace: Bicycle"
            wfh_col = "Method of travel to workplace: Work mainly at or from home"
            try:
                total = int(r.get(total_col, "0"))
                cycling = int(r.get(cycle_col, "0"))
                wfh = int(r.get(wfh_col, "0"))
            except (ValueError, TypeError):
                continue
            if total == 0:
                continue
            pct_cycling = round(cycling / total * 100, 2)
            pct_wfh = round(wfh / total * 100, 2)
            rows.append((lsoa, total, cycling, pct_cycling, wfh, pct_wfh))

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_cycling_lsoa (
            lsoa_code TEXT PRIMARY KEY,
            total_workers INTEGER,
            cycling_count INTEGER,
            pct_cycling NUMERIC(5,2),
            wfh_count INTEGER,
            pct_wfh NUMERIC(5,2)
        )
    """)
    cur.execute("TRUNCATE TABLE core_cycling_lsoa")
    execute_values(cur, """
        INSERT INTO core_cycling_lsoa (lsoa_code, total_workers, cycling_count, pct_cycling, wfh_count, pct_wfh)
        VALUES %s
    """, rows)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_cycling_lsoa")
    print(f"  core_cycling_lsoa: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()


def ingest_mobile():
    """Ofcom Connected Nations — mobile 4G/5G coverage by LAD."""
    print("Ingesting mobile coverage (Ofcom)...")
    path = os.path.join(DATA_DIR, "202409_mobile_coverage_laua_r01.csv")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lad = r.get("laua", "").strip()
            if not lad.startswith("E"):
                continue
            name = r.get("laua_name", "").strip()
            # 4G: % premises with at least 1 operator outdoor = 100 - 4G_prem_out_0
            try:
                no_4g = float(r.get("4G_prem_out_0", "0") or "0")
                pct_4g = round(100 - no_4g, 1)
            except (ValueError, TypeError):
                pct_4g = None
            # 5G high confidence: % premises with at least 1 operator outdoor = 100 - 5G_high_confidence_prem_out_0
            try:
                no_5g = float(r.get("5G_high_confidence_prem_out_0", "0") or "0")
                pct_5g = round(100 - no_5g, 1)
            except (ValueError, TypeError):
                pct_5g = None
            # 4G indoor: 100 - 4G_prem_in_0
            try:
                no_4g_in = float(r.get("4G_prem_in_0", "0") or "0")
                pct_4g_indoor = round(100 - no_4g_in, 1)
            except (ValueError, TypeError):
                pct_4g_indoor = None

            rows.append((lad, name, pct_4g, pct_4g_indoor, pct_5g))

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_mobile_coverage_lad (
            lad_code TEXT PRIMARY KEY,
            lad_name TEXT,
            pct_4g_outdoor NUMERIC(5,1),
            pct_4g_indoor NUMERIC(5,1),
            pct_5g_outdoor NUMERIC(5,1)
        )
    """)
    cur.execute("TRUNCATE TABLE core_mobile_coverage_lad")
    execute_values(cur, """
        INSERT INTO core_mobile_coverage_lad (lad_code, lad_name, pct_4g_outdoor, pct_4g_indoor, pct_5g_outdoor)
        VALUES %s
    """, rows)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_mobile_coverage_lad")
    print(f"  core_mobile_coverage_lad: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()


if __name__ == "__main__":
    ingest_ptal()
    ingest_cycling()
    ingest_mobile()
