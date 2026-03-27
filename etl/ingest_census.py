"""ETL: Census 2021 → core_census_demographics_lsoa + core_census_housing_lsoa.
Bible: ONS Census 2021 at LSOA level. Tab 4: Community & Education.
Sources: TS001 (population), TS006 (density), TS003 (household composition),
         TS007A (age bands), TS054 (tenure), TS044 (accommodation type)."""
import os, pandas as pd, psycopg2
from psycopg2.extras import execute_values

DB = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
CENSUS_DIR = os.path.expanduser("~/Desktop/Manus Take 2/etl/data/census")

def read_census(filename):
    df = pd.read_csv(os.path.join(CENSUS_DIR, filename))
    df = df[df["geography code"].str.startswith("E")]
    return df

def estimate_median_age(row):
    """Estimate median age from 5-year age band counts using linear interpolation."""
    bands = [
        (0, 4, row.get("Age: Aged 4 years and under", 0)),
        (5, 9, row.get("Age: Aged 5 to 9 years", 0)),
        (10, 14, row.get("Age: Aged 10 to 14 years", 0)),
        (15, 19, row.get("Age: Aged 15 to 19 years", 0)),
        (20, 24, row.get("Age: Aged 20 to 24 years", 0)),
        (25, 29, row.get("Age: Aged 25 to 29 years", 0)),
        (30, 34, row.get("Age: Aged 30 to 34 years", 0)),
        (35, 39, row.get("Age: Aged 35 to 39 years", 0)),
        (40, 44, row.get("Age: Aged 40 to 44 years", 0)),
        (45, 49, row.get("Age: Aged 45 to 49 years", 0)),
        (50, 54, row.get("Age: Aged 50 to 54 years", 0)),
        (55, 59, row.get("Age: Aged 55 to 59 years", 0)),
        (60, 64, row.get("Age: Aged 60 to 64 years", 0)),
        (65, 69, row.get("Age: Aged 65 to 69 years", 0)),
        (70, 74, row.get("Age: Aged 70 to 74 years", 0)),
        (75, 79, row.get("Age: Aged 75 to 79 years", 0)),
        (80, 84, row.get("Age: Aged 80 to 84 years", 0)),
        (85, 90, row.get("Age: Aged 85 years and over", 0)),
    ]
    total = sum(c for _, _, c in bands)
    if total == 0:
        return None
    half = total / 2
    cumulative = 0
    for low, high, count in bands:
        if cumulative + count >= half:
            # Interpolate within this band
            fraction = (half - cumulative) / count if count > 0 else 0
            return round(low + fraction * (high - low + 1), 1)
        cumulative += count
    return None

def ingest_demographics():
    """TS001=population, TS006=density, TS003=household composition, TS007A=age bands."""
    print("Ingesting census demographics...")

    # TS001: Total population
    ts001 = read_census("census2021-ts001-lsoa.csv")
    ts001 = ts001.rename(columns={"geography code": "lsoa_code"})
    ts001["total_population"] = pd.to_numeric(
        ts001["Residence type: Total; measures: Value"], errors="coerce").astype("Int64")

    # TS006: Population density
    ts006 = read_census("census2021-ts006-lsoa.csv")
    ts006 = ts006.rename(columns={"geography code": "lsoa_code"})
    ts006["population_density"] = pd.to_numeric(
        ts006["Population Density: Persons per square kilometre; measures: Value"], errors="coerce")

    # TS003: Household composition
    ts003 = read_census("census2021-ts003-lsoa.csv")
    ts003 = ts003.rename(columns={"geography code": "lsoa_code"})
    total_hh = ts003["Household composition: Total; measures: Value"]
    ts003["pct_families"] = (ts003["Household composition: Single family household; measures: Value"] / total_hh * 100).round(2)
    ts003["pct_singles"] = (ts003["Household composition: One person household; measures: Value"] / total_hh * 100).round(2)
    ts003["pct_sharers"] = (100 - ts003["pct_families"] - ts003["pct_singles"]).round(2)

    # TS007A: Age bands → age percentages + estimated median age
    ts007a = read_census("census2021-ts007a-lsoa.csv")
    ts007a = ts007a.rename(columns={"geography code": "lsoa_code"})
    age_total = pd.to_numeric(ts007a["Age: Total"], errors="coerce")

    # 0-15: under 5 + 5-9 + 10-14 + 15 (approximate: include all of 15-19 band * 1/5 for age 15)
    age_0_14 = (pd.to_numeric(ts007a["Age: Aged 4 years and under"], errors="coerce") +
                pd.to_numeric(ts007a["Age: Aged 5 to 9 years"], errors="coerce") +
                pd.to_numeric(ts007a["Age: Aged 10 to 14 years"], errors="coerce"))
    # Add 1/5 of 15-19 band for age 15
    age_15 = pd.to_numeric(ts007a["Age: Aged 15 to 19 years"], errors="coerce") / 5
    age_0_15 = age_0_14 + age_15

    # 65+
    age_65_plus = (pd.to_numeric(ts007a["Age: Aged 65 to 69 years"], errors="coerce") +
                   pd.to_numeric(ts007a["Age: Aged 70 to 74 years"], errors="coerce") +
                   pd.to_numeric(ts007a["Age: Aged 75 to 79 years"], errors="coerce") +
                   pd.to_numeric(ts007a["Age: Aged 80 to 84 years"], errors="coerce") +
                   pd.to_numeric(ts007a["Age: Aged 85 years and over"], errors="coerce"))

    # 16-64 = total - 0-15 - 65+
    age_16_64 = age_total - age_0_15 - age_65_plus

    ts007a["pct_age_0_15"] = (age_0_15 / age_total * 100).round(2)
    ts007a["pct_age_16_64"] = (age_16_64 / age_total * 100).round(2)
    ts007a["pct_age_65_plus"] = (age_65_plus / age_total * 100).round(2)

    # Estimate median age per LSOA
    ts007a["median_age"] = ts007a.apply(estimate_median_age, axis=1)

    # Merge all
    merged = ts001[["lsoa_code", "total_population"]].merge(
        ts006[["lsoa_code", "population_density"]], on="lsoa_code", how="left"
    ).merge(
        ts007a[["lsoa_code", "median_age", "pct_age_0_15", "pct_age_16_64", "pct_age_65_plus"]], on="lsoa_code", how="left"
    ).merge(
        ts003[["lsoa_code", "pct_families", "pct_singles", "pct_sharers"]], on="lsoa_code", how="left"
    )

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_census_demographics_lsoa CASCADE")
    rows = []
    for _, r in merged.iterrows():
        rows.append((
            r["lsoa_code"],
            int(r["total_population"]) if pd.notna(r["total_population"]) else None,
            round(float(r["population_density"]), 2) if pd.notna(r.get("population_density")) else None,
            round(float(r["median_age"]), 1) if pd.notna(r.get("median_age")) else None,
            round(float(r["pct_age_0_15"]), 2) if pd.notna(r.get("pct_age_0_15")) else None,
            round(float(r["pct_age_16_64"]), 2) if pd.notna(r.get("pct_age_16_64")) else None,
            round(float(r["pct_age_65_plus"]), 2) if pd.notna(r.get("pct_age_65_plus")) else None,
            round(float(r["pct_families"]), 2) if pd.notna(r.get("pct_families")) else None,
            round(float(r["pct_singles"]), 2) if pd.notna(r.get("pct_singles")) else None,
            round(float(r["pct_sharers"]), 2) if pd.notna(r.get("pct_sharers")) else None,
        ))
    execute_values(cur, """INSERT INTO core_census_demographics_lsoa
        (lsoa_code, total_population, population_density, median_age,
         pct_age_0_15, pct_age_16_64, pct_age_65_plus, pct_families, pct_singles, pct_sharers)
        VALUES %s ON CONFLICT DO NOTHING""", rows, page_size=5000)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_census_demographics_lsoa WHERE total_population IS NOT NULL")
    pop_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM core_census_demographics_lsoa")
    total_count = cur.fetchone()[0]
    print(f"  core_census_demographics_lsoa: {total_count:,} rows ({pop_count:,} with population)")
    cur.close(); conn.close()

def ingest_housing():
    """TS054=tenure, TS044=accommodation type."""
    print("Ingesting census housing...")
    ts054 = read_census("census2021-ts054-lsoa.csv")
    ts054 = ts054.rename(columns={"geography code": "lsoa_code"})
    total = ts054["Tenure of household: Total: All households"]
    ts054["total_households"] = total
    ts054["pct_owned"] = (ts054["Tenure of household: Owned"] / total * 100).round(2)
    ts054["pct_social_rent"] = (ts054["Tenure of household: Social rented"] / total * 100).round(2)
    ts054["pct_private_rent"] = (ts054["Tenure of household: Private rented"] / total * 100).round(2)

    ts044 = read_census("census2021-ts044-lsoa.csv")
    ts044 = ts044.rename(columns={"geography code": "lsoa_code"})
    hh_total = ts044["Accommodation type: Total: All households"]
    ts044["pct_detached"] = (ts044["Accommodation type: Detached"] / hh_total * 100).round(2)
    ts044["pct_semi"] = (ts044["Accommodation type: Semi-detached"] / hh_total * 100).round(2)
    ts044["pct_terraced"] = (ts044["Accommodation type: Terraced"] / hh_total * 100).round(2)
    flat_cols = [c for c in ts044.columns if "flat" in c.lower() or "purpose-built" in c.lower() or "converted" in c.lower()]
    ts044["pct_flat"] = (ts044[flat_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1) / hh_total * 100).round(2)

    merged = ts054[["lsoa_code", "total_households", "pct_owned", "pct_social_rent", "pct_private_rent"]].merge(
        ts044[["lsoa_code", "pct_detached", "pct_semi", "pct_terraced", "pct_flat"]], on="lsoa_code", how="left"
    )

    conn = psycopg2.connect(DB)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_census_housing_lsoa CASCADE")
    rows = [(r["lsoa_code"], int(r["total_households"]), round(float(r["pct_owned"]), 2),
             round(float(r["pct_social_rent"]), 2), round(float(r["pct_private_rent"]), 2),
             round(float(r["pct_detached"]), 2) if pd.notna(r.get("pct_detached")) else None,
             round(float(r["pct_semi"]), 2) if pd.notna(r.get("pct_semi")) else None,
             round(float(r["pct_terraced"]), 2) if pd.notna(r.get("pct_terraced")) else None,
             round(float(r["pct_flat"]), 2) if pd.notna(r.get("pct_flat")) else None)
            for _, r in merged.iterrows()]
    execute_values(cur, """INSERT INTO core_census_housing_lsoa
        (lsoa_code, total_households, pct_owned, pct_social_rent, pct_private_rent,
         pct_detached, pct_semi, pct_terraced, pct_flat)
        VALUES %s ON CONFLICT DO NOTHING""", rows, page_size=5000)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM core_census_housing_lsoa")
    print(f"  core_census_housing_lsoa: {cur.fetchone()[0]:,} rows")
    cur.close(); conn.close()

if __name__ == "__main__":
    ingest_demographics()
    ingest_housing()
