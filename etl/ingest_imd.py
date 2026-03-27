"""ETL: IMD 2019 (all domains) → core_imd_lsoa. Bible: MHCLG Index of Multiple Deprivation."""
import os, pandas as pd, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
SRC = os.path.expanduser("~/Desktop/geodepth/etl/data/iod2019_all_domains.csv")

def ingest():
    df = pd.read_csv(SRC)
    df = df[df["LSOA code (2011)"].str.startswith("E")]
    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_imd_lsoa CASCADE")
    rows = []
    for _, r in df.iterrows():
        rows.append((
            r["LSOA code (2011)"],
            r["Index of Multiple Deprivation (IMD) Score"],
            r["Index of Multiple Deprivation (IMD) Rank (where 1 is most deprived)"],
            r["Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)"],
            r["Income Score (rate)"],
            r["Employment Score (rate)"],
            r["Education, Skills and Training Score"],
            r["Health Deprivation and Disability Score"],
            r["Crime Score"],
            r["Barriers to Housing and Services Score"],
            r["Living Environment Score"],
        ))
    execute_values(cur, """INSERT INTO core_imd_lsoa (lsoa_code, imd_score, imd_rank, imd_decile,
        income_score, employment_score, education_score, health_score, crime_score,
        barriers_score, living_env_score) VALUES %s ON CONFLICT DO NOTHING""", rows, page_size=5000)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_imd_lsoa")
    print(f"core_imd_lsoa: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__": ingest()
