"""
ETL: Build core_lad_county_lookup table
Source: lad_to_ctyua_2025.csv + core_postcodes (for region)
Schema: Build Bible Part 2, Section 2.1

This table determines the parent_comparison for every LAD, per Bible Rule 3:
- London borough → parent = 'Greater London'
- Metropolitan district → parent = region name
- Unitary authority → parent = region name
- District → parent = county name
"""
import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://ukproperty:ukproperty_dev@localhost:5433/ukproperty",
)

LAD_CTYUA_PATH = os.path.expanduser(
    "~/Desktop/geodepth/etl/data/lad_to_ctyua_2025.csv"
)

# London borough LAD codes all start with E09
LONDON_BOROUGH_PREFIX = "E09"

# Metropolitan boroughs start with E08
METROPOLITAN_PREFIX = "E08"

REGION_NAMES = {
    "E12000001": "North East",
    "E12000002": "North West",
    "E12000003": "Yorkshire and The Humber",
    "E12000004": "East Midlands",
    "E12000005": "West Midlands",
    "E12000006": "East of England",
    "E12000007": "London",
    "E12000008": "South East",
    "E12000009": "South West",
}


def ingest():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_lad_county_lookup CASCADE")
    conn.commit()

    # Read LAD-to-CTYUA mapping
    df = pd.read_csv(LAD_CTYUA_PATH, dtype=str, encoding="utf-8-sig")
    df = df[df["LAD25CD"].str.startswith("E")]  # England only

    # Get region codes from core_postcodes
    cur.execute("""
        SELECT lad_code,
               MODE() WITHIN GROUP (ORDER BY region_code) AS region_code,
               MODE() WITHIN GROUP (ORDER BY region_name) AS region_name
        FROM core_postcodes
        WHERE lad_code IS NOT NULL AND region_code IS NOT NULL
        GROUP BY lad_code
    """)
    lad_region = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

    rows = []
    for _, r in df.iterrows():
        lad_code = r["LAD25CD"]
        lad_name = r["LAD25NM"]
        ctyua_code = r["CTYUA25CD"]
        ctyua_name = r["CTYUA25NM"]

        # Determine county
        if ctyua_code != lad_code:
            county_code = ctyua_code
            county_name = ctyua_name
        else:
            county_code = None
            county_name = None

        # Get region
        region_code, region_name = lad_region.get(lad_code, (None, None))

        # Determine flags and parent_comparison per Bible Rule 3
        is_london = lad_code.startswith(LONDON_BOROUGH_PREFIX)
        is_metro = lad_code.startswith(METROPOLITAN_PREFIX)

        if is_london:
            parent_comparison = "Greater London"
        elif county_name:
            parent_comparison = county_name
        elif region_name:
            parent_comparison = region_name
        else:
            parent_comparison = "England"

        rows.append((
            lad_code, lad_name,
            county_code, county_name,
            region_code, region_name,
            is_london, is_metro,
            parent_comparison,
        ))

    if rows:
        sql = """
            INSERT INTO core_lad_county_lookup (
                lad_code, lad_name, county_code, county_name,
                region_code, region_name,
                is_london_borough, is_metropolitan,
                parent_comparison
            ) VALUES %s
            ON CONFLICT (lad_code) DO UPDATE SET
                lad_name = EXCLUDED.lad_name,
                county_code = EXCLUDED.county_code,
                county_name = EXCLUDED.county_name,
                region_code = EXCLUDED.region_code,
                region_name = EXCLUDED.region_name,
                is_london_borough = EXCLUDED.is_london_borough,
                is_metropolitan = EXCLUDED.is_metropolitan,
                parent_comparison = EXCLUDED.parent_comparison
        """
        execute_values(cur, sql, rows, page_size=1000)
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_lad_county_lookup")
    count = cur.fetchone()[0]
    print(f"Done. core_lad_county_lookup has {count:,} rows.")

    # Show some examples
    cur.execute("""
        SELECT lad_name, is_london_borough, is_metropolitan, parent_comparison
        FROM core_lad_county_lookup
        ORDER BY lad_name LIMIT 10
    """)
    for row in cur.fetchall():
        print(f"  {row[0]}: london={row[1]}, metro={row[2]}, parent='{row[3]}'")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ingest()
