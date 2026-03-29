"""ETL: Census 2021 TS017/TS022/TS058 → DB tables.

Sources:
  - TS017 (Household Size) LSOA → core_census_hh_size_lsoa
  - TS022 (Ethnicity Detailed) Ward → core_census_ethnicity_ward
  - TS058 (Distance to Work) LSOA → core_census_commute_lsoa
"""
import os, csv, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
CENSUS_DIR = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/census")


def ingest_hh_size():
    """TS017: Household size distribution by LSOA."""
    print("Ingesting household size (TS017 LSOA)...")
    path = os.path.join(CENSUS_DIR, "census2021-ts017-lsoa.csv")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lsoa = r["geography code"].strip()
            if not lsoa.startswith("E"):
                continue
            try:
                total = int(r["Household size: Total: All household spaces; measures: Value"] or 0)
                if total == 0:
                    continue
                n1 = int(r["Household size: 1 person in household; measures: Value"] or 0)
                n2 = int(r["Household size: 2 people in household; measures: Value"] or 0)
                n3 = int(r["Household size: 3 people in household; measures: Value"] or 0)
                n4 = int(r["Household size: 4 people in household; measures: Value"] or 0)
                n5plus = sum(int(r.get(f"Household size: {n} people in household; measures: Value") or 0)
                             for n in ["5", "6", "7"]) + \
                         int(r.get("Household size: 8 or more people in household; measures: Value") or 0)
                pct_1 = round(n1 / total * 100, 2)
                pct_2 = round(n2 / total * 100, 2)
                pct_3_4 = round((n3 + n4) / total * 100, 2)
                pct_5plus = round(n5plus / total * 100, 2)
            except (ValueError, KeyError):
                continue
            rows.append((lsoa, total, pct_1, pct_2, pct_3_4, pct_5plus))

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_census_hh_size_lsoa (
            lsoa_code    TEXT PRIMARY KEY,
            total_hh     INTEGER,
            pct_1person  NUMERIC(5,2),
            pct_2person  NUMERIC(5,2),
            pct_3_4person NUMERIC(5,2),
            pct_5plus    NUMERIC(5,2)
        )
    """)
    cur.execute("TRUNCATE TABLE core_census_hh_size_lsoa")
    execute_values(cur, """
        INSERT INTO core_census_hh_size_lsoa
          (lsoa_code, total_hh, pct_1person, pct_2person, pct_3_4person, pct_5plus)
        VALUES %s
    """, rows, page_size=5000)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_census_hh_size_lsoa")
    print(f"  core_census_hh_size_lsoa: {cur.fetchone()[0]:,} rows")
    cur.close()
    conn.close()


def ingest_ethnicity():
    """TS022: Ethnicity (detailed) by Ward — 5 main groups."""
    print("Ingesting ethnicity (TS022 Ward)...")
    path = os.path.join(CENSUS_DIR, "census2021-ts022-ward.csv")

    # Column mapping
    TOTAL_COL = "Ethnic group (detailed): Total: All usual residents"
    ASIAN_COL = "Ethnic group (detailed): Asian, Asian British or Asian Welsh"
    BLACK_AF_COL = "Ethnic group (detailed): Black, Black British, Black Welsh of African background"
    BLACK_CAR_COL = "Ethnic group (detailed): Black, Black British, Black Welsh or Caribbean background"
    MIXED_COL = "Ethnic group (detailed): Mixed or Multiple ethnic groups"
    WHITE_COL = "Ethnic group (detailed): White"
    OTHER_COL = "Ethnic group (detailed): Other ethnic group"

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ward = r["geography code"].strip()
            if not ward.startswith("E"):
                continue
            try:
                total = int(r[TOTAL_COL] or 0)
                if total == 0:
                    continue
                asian = int(r.get(ASIAN_COL) or 0)
                black = int(r.get(BLACK_AF_COL) or 0) + int(r.get(BLACK_CAR_COL) or 0)
                mixed = int(r.get(MIXED_COL) or 0)
                white = int(r.get(WHITE_COL) or 0)
                other = int(r.get(OTHER_COL) or 0)
                pct_white = round(white / total * 100, 2)
                pct_asian = round(asian / total * 100, 2)
                pct_black = round(black / total * 100, 2)
                pct_mixed = round(mixed / total * 100, 2)
                pct_other = round(other / total * 100, 2)
            except (ValueError, KeyError):
                continue
            rows.append((ward, total, pct_white, pct_asian, pct_black, pct_mixed, pct_other))

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_census_ethnicity_ward (
            ward_code   TEXT PRIMARY KEY,
            total_pop   INTEGER,
            pct_white   NUMERIC(5,2),
            pct_asian   NUMERIC(5,2),
            pct_black   NUMERIC(5,2),
            pct_mixed   NUMERIC(5,2),
            pct_other   NUMERIC(5,2)
        )
    """)
    cur.execute("TRUNCATE TABLE core_census_ethnicity_ward")
    execute_values(cur, """
        INSERT INTO core_census_ethnicity_ward
          (ward_code, total_pop, pct_white, pct_asian, pct_black, pct_mixed, pct_other)
        VALUES %s
    """, rows, page_size=5000)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_census_ethnicity_ward")
    print(f"  core_census_ethnicity_ward: {cur.fetchone()[0]:,} rows")
    cur.close()
    conn.close()


def ingest_commute_distance():
    """TS058: Distance to work by LSOA."""
    print("Ingesting commute distance (TS058 LSOA)...")
    path = os.path.join(CENSUS_DIR, "census2021-ts058-lsoa.csv")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lsoa = r["geography code"].strip()
            if not lsoa.startswith("E"):
                continue
            try:
                total = int(r["Distance travelled to work: Total: All usual residents aged 16 years and over in employment the week before the census"] or 0)
                if total == 0:
                    continue
                lt2 = int(r["Distance travelled to work: Less than 2km"] or 0)
                km2_5 = int(r["Distance travelled to work: 2km to less than 5km"] or 0)
                km5_10 = int(r["Distance travelled to work: 5km to less than 10km"] or 0)
                km10_20 = int(r["Distance travelled to work: 10km to less than 20km"] or 0)
                km20_30 = int(r["Distance travelled to work: 20km to less than 30km"] or 0)
                km30_60 = int(r.get("Distance travelled to work: 30km to less than 40km") or 0) + \
                          int(r.get("Distance travelled to work: 40km to less than 60km") or 0)
                km60plus = int(r.get("Distance travelled to work: 60km and over") or 0)
                wfh = int(r.get("Distance travelled to work: Works mainly from home") or 0)
                pct_lt2 = round(lt2 / total * 100, 2)
                pct_2_10 = round((km2_5 + km5_10) / total * 100, 2)
                pct_10_30 = round((km10_20 + km20_30) / total * 100, 2)
                pct_30plus = round((km30_60 + km60plus) / total * 100, 2)
                pct_wfh = round(wfh / total * 100, 2)
            except (ValueError, KeyError):
                continue
            rows.append((lsoa, total, pct_lt2, pct_2_10, pct_10_30, pct_30plus, pct_wfh))

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS core_census_commute_lsoa (
            lsoa_code   TEXT PRIMARY KEY,
            total_workers INTEGER,
            pct_lt2km   NUMERIC(5,2),
            pct_2_10km  NUMERIC(5,2),
            pct_10_30km NUMERIC(5,2),
            pct_30plus  NUMERIC(5,2),
            pct_wfh     NUMERIC(5,2)
        )
    """)
    cur.execute("TRUNCATE TABLE core_census_commute_lsoa")
    execute_values(cur, """
        INSERT INTO core_census_commute_lsoa
          (lsoa_code, total_workers, pct_lt2km, pct_2_10km, pct_10_30km, pct_30plus, pct_wfh)
        VALUES %s
    """, rows, page_size=5000)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_census_commute_lsoa")
    print(f"  core_census_commute_lsoa: {cur.fetchone()[0]:,} rows")
    cur.close()
    conn.close()


if __name__ == "__main__":
    ingest_hh_size()
    ingest_ethnicity()
    ingest_commute_distance()
    print("Done.")
