"""
ETL: ONSPD → core_postcodes (FAST version using COPY)
Continues from where the previous run left off (uses ON CONFLICT DO NOTHING).
"""
import os
import json
import csv
import io
import pandas as pd
import psycopg2

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
    "E12000001": "North East", "E12000002": "North West",
    "E12000003": "Yorkshire and The Humber", "E12000004": "East Midlands",
    "E12000005": "West Midlands", "E12000006": "East of England",
    "E12000007": "London", "E12000008": "South East", "E12000009": "South West",
}


def ingest():
    # Load lookups
    with open(CATCHMENT_NAMES_PATH) as f:
        catchment = json.load(f)
    ward_names = catchment.get("ward", {})
    lad_names = catchment.get("lad", {})

    county_lookup = {}
    df_cty = pd.read_csv(LAD_CTYUA_PATH, dtype=str, encoding="utf-8-sig")
    for _, row in df_cty.iterrows():
        lad_cd, ctyua_cd, ctyua_nm = row["LAD25CD"], row["CTYUA25CD"], row["CTYUA25NM"]
        county_lookup[lad_cd] = (ctyua_cd, ctyua_nm) if ctyua_cd != lad_cd else (None, None)

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Use a staging table for fast COPY, then upsert
    cur.execute("DROP TABLE IF EXISTS _stg_postcodes")
    cur.execute("""
        CREATE UNLOGGED TABLE _stg_postcodes (
            postcode TEXT, postcode_compact TEXT, latitude DOUBLE PRECISION,
            longitude DOUBLE PRECISION, lsoa_code TEXT, lsoa_name TEXT,
            msoa_code TEXT, msoa_name TEXT, ward_code TEXT, ward_name TEXT,
            lad_code TEXT, lad_name TEXT, county_code TEXT, county_name TEXT,
            region_code TEXT, region_name TEXT, nation CHAR(1)
        )
    """)
    conn.commit()

    print("Reading and transforming ONSPD...")
    cols = ["pcds", "doterm", "lat", "long", "lsoa21cd", "msoa21cd",
            "wd25cd", "lad25cd", "cty25cd", "rgn25cd", "ctry25cd"]

    chunk_size = 500_000
    total = 0

    for chunk in pd.read_csv(ONSPD_PATH, usecols=cols, dtype=str,
                              chunksize=chunk_size, low_memory=False):
        # Filter active England postcodes
        chunk = chunk[(chunk["doterm"].isna() | (chunk["doterm"] == "")) &
                      (chunk["ctry25cd"].str.startswith("E", na=False))]
        if chunk.empty:
            continue

        # Build CSV buffer for COPY
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter='\t')

        for _, r in chunk.iterrows():
            pc = str(r["pcds"]).strip()
            pc_compact = pc.replace(" ", "").upper()
            try:
                lat = float(r["lat"]) if pd.notna(r["lat"]) else ""
                lon = float(r["long"]) if pd.notna(r["long"]) else ""
            except (ValueError, TypeError):
                lat, lon = "", ""

            lsoa = r["lsoa21cd"] if pd.notna(r.get("lsoa21cd")) else ""
            msoa = r["msoa21cd"] if pd.notna(r.get("msoa21cd")) else ""
            ward = r["wd25cd"] if pd.notna(r.get("wd25cd")) else ""
            lad = r["lad25cd"] if pd.notna(r.get("lad25cd")) else ""
            rgn = r["rgn25cd"] if pd.notna(r.get("rgn25cd")) else ""

            w_name = ward_names.get(ward, "") if ward else ""
            l_name = lad_names.get(lad, "") if lad else ""
            cty = county_lookup.get(lad, (None, None))
            cty_code = cty[0] or ""
            cty_name = cty[1] or ""
            rgn_name = REGION_NAMES.get(rgn, "") if rgn and "99999" not in rgn else ""
            if "99999" in rgn:
                rgn = ""

            writer.writerow([
                pc, pc_compact, lat, lon,
                lsoa, "", msoa, "",
                ward, w_name, lad, l_name,
                cty_code, cty_name, rgn, rgn_name, "E"
            ])

        buf.seek(0)
        cur.copy_from(buf, "_stg_postcodes", sep='\t', null='')
        conn.commit()
        total += len(chunk)
        print(f"  Staged {total:,} rows...")

    # Upsert from staging to core_postcodes
    print("Upserting into core_postcodes...")
    cur.execute("""
        INSERT INTO core_postcodes (
            postcode, postcode_compact, latitude, longitude,
            lsoa_code, lsoa_name, msoa_code, msoa_name,
            ward_code, ward_name, lad_code, lad_name,
            county_code, county_name, region_code, region_name, nation
        )
        SELECT postcode, postcode_compact,
               NULLIF(latitude, 0), NULLIF(longitude, 0),
               NULLIF(lsoa_code, ''), NULLIF(lsoa_name, ''),
               NULLIF(msoa_code, ''), NULLIF(msoa_name, ''),
               NULLIF(ward_code, ''), NULLIF(ward_name, ''),
               NULLIF(lad_code, ''), NULLIF(lad_name, ''),
               NULLIF(county_code, ''), NULLIF(county_name, ''),
               NULLIF(region_code, ''), NULLIF(region_name, ''), nation
        FROM _stg_postcodes
        ON CONFLICT (postcode) DO NOTHING
    """)
    conn.commit()

    # Build geometry
    print("Building PostGIS geometry...")
    cur.execute("""
        UPDATE core_postcodes
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND geom IS NULL
    """)
    cur.execute("UPDATE core_postcodes SET is_active = TRUE, last_updated = CURRENT_DATE WHERE is_active IS NULL")
    conn.commit()

    # Cleanup
    cur.execute("DROP TABLE IF EXISTS _stg_postcodes")
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_postcodes")
    print(f"Done. core_postcodes: {cur.fetchone()[0]:,} rows")
    cur.close()
    conn.close()


if __name__ == "__main__":
    ingest()
