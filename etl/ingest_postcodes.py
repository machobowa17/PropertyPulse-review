"""
ETL: ONS Postcode Directory (ONSPD) → core_postcodes
Source: ~/Desktop/geodepth/etl/data/ONSPD_FEB_2026_UK.csv
Schema: Build Bible Part 2, Section 2.1

Optimized: uses vectorized pandas + batch inserts for speed.
"""
import os
import json
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from io import StringIO

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres@localhost:5432/ukproperty",
)

ONSPD_PATH = os.path.expanduser(
    "~/Desktop/geodepth/etl/data/ONSPD_FEB_2026_UK.csv"
)

CATCHMENT_NAMES_PATH = os.path.expanduser(
    "~/Desktop/geodepth/etl/data/catchment_names.json"
)

LAD_CTYUA_PATH = os.path.expanduser(
    "~/Desktop/geodepth/etl/data/lad_to_ctyua_2025.csv"
)

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


def load_name_lookups():
    """Load all code-to-name mappings."""
    print("Loading name lookups...")

    with open(CATCHMENT_NAMES_PATH) as f:
        catchment = json.load(f)
    ward_names = catchment.get("ward", {})
    lad_names = catchment.get("lad", {})

    # County from LAD-to-CTYUA
    county_lookup = {}
    df_cty = pd.read_csv(LAD_CTYUA_PATH, dtype=str, encoding="utf-8-sig")
    for _, row in df_cty.iterrows():
        lad_cd = row["LAD25CD"]
        ctyua_cd = row["CTYUA25CD"]
        ctyua_nm = row["CTYUA25NM"]
        if ctyua_cd != lad_cd:
            county_lookup[lad_cd] = (ctyua_cd, ctyua_nm)
        else:
            county_lookup[lad_cd] = (None, None)

    print(f"  Ward names: {len(ward_names)}, LAD names: {len(lad_names)}, County: {len(county_lookup)}")
    return ward_names, lad_names, county_lookup


def ingest():
    ward_names, lad_names, county_lookup = load_name_lookups()

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_postcodes CASCADE")
    conn.commit()

    print(f"Reading ONSPD from {ONSPD_PATH}...")
    cols_needed = [
        "pcds", "doterm", "lat", "long",
        "lsoa21cd", "msoa21cd", "wd25cd", "lad25cd",
        "cty25cd", "rgn25cd", "ctry25cd",
    ]

    chunk_size = 200_000
    total = 0

    for chunk in pd.read_csv(
        ONSPD_PATH,
        usecols=cols_needed,
        dtype=str,
        chunksize=chunk_size,
        low_memory=False,
    ):
        # Filter: active England postcodes only
        chunk = chunk[chunk["doterm"].isna() | (chunk["doterm"] == "")]
        chunk = chunk[chunk["ctry25cd"].str.startswith("E", na=False)]

        if chunk.empty:
            continue

        # Vectorised transformations
        chunk["postcode"] = chunk["pcds"].str.strip()
        chunk["postcode_compact"] = chunk["postcode"].str.replace(" ", "", regex=False).str.upper()
        chunk["latitude"] = pd.to_numeric(chunk["lat"], errors="coerce")
        chunk["longitude"] = pd.to_numeric(chunk["long"], errors="coerce")

        # Map names (vectorised via .map())
        chunk["ward_name"] = chunk["wd25cd"].map(ward_names)
        chunk["lad_name"] = chunk["lad25cd"].map(lad_names)
        chunk["region_name"] = chunk["rgn25cd"].map(REGION_NAMES)

        # County lookup
        chunk["county_code"] = chunk["lad25cd"].map(
            lambda x: county_lookup.get(x, (None, None))[0] if pd.notna(x) else None
        )
        chunk["county_name"] = chunk["lad25cd"].map(
            lambda x: county_lookup.get(x, (None, None))[1] if pd.notna(x) else None
        )

        # Clean E99999999 codes to NULL
        for col in ["cty25cd", "rgn25cd"]:
            mask = chunk[col].str.contains("99999", na=True)
            chunk.loc[mask, col] = None

        # Build rows
        rows = []
        for _, r in chunk.iterrows():
            rows.append((
                r["postcode"],
                r["postcode_compact"],
                r["latitude"] if pd.notna(r["latitude"]) else None,
                r["longitude"] if pd.notna(r["longitude"]) else None,
                r["lsoa21cd"] if pd.notna(r.get("lsoa21cd")) else None,
                None,  # lsoa_name - backfill later
                r["msoa21cd"] if pd.notna(r.get("msoa21cd")) else None,
                None,  # msoa_name - backfill later
                r["wd25cd"] if pd.notna(r.get("wd25cd")) else None,
                r["ward_name"] if pd.notna(r.get("ward_name")) else None,
                r["lad25cd"] if pd.notna(r.get("lad25cd")) else None,
                r["lad_name"] if pd.notna(r.get("lad_name")) else None,
                r["county_code"] if pd.notna(r.get("county_code")) else None,
                r["county_name"] if pd.notna(r.get("county_name")) else None,
                r["rgn25cd"] if pd.notna(r.get("rgn25cd")) else None,
                r["region_name"] if pd.notna(r.get("region_name")) else None,
                "E",
            ))

        if rows:
            sql = """
                INSERT INTO core_postcodes (
                    postcode, postcode_compact, latitude, longitude,
                    lsoa_code, lsoa_name, msoa_code, msoa_name,
                    ward_code, ward_name, lad_code, lad_name,
                    county_code, county_name, region_code, region_name,
                    nation
                ) VALUES %s
                ON CONFLICT (postcode) DO NOTHING
            """
            execute_values(cur, sql, rows, page_size=10000)
            conn.commit()

        total += len(rows)
        print(f"  Inserted {total:,} postcodes...")

    # Build PostGIS geometry
    print("Building PostGIS geometry column...")
    cur.execute("""
        UPDATE core_postcodes
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    conn.commit()

    cur.execute("""
        UPDATE core_postcodes SET is_active = TRUE, last_updated = CURRENT_DATE
    """)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_postcodes")
    count = cur.fetchone()[0]
    print(f"Done. core_postcodes has {count:,} rows.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ingest()
