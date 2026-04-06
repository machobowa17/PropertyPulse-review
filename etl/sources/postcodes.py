"""
sources/postcodes.py — ONS Postcode Directory (ONSPD) → core_postcodes

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_postcodes)

Data files required in etl/data/ (or set env vars to override):
    ONSPD_PATH          — ONSPD_*.csv   (active England postcodes)
    CATCHMENT_NAMES_PATH — catchment_names.json  (ward/LAD name lookups)
    LAD_CTYUA_PATH      — lad_to_ctyua_2025.csv (LAD → county/unitary mapping)

Download ONSPD from:
    https://geoportal.statistics.gov.uk/search?q=ONSPD
"""

import csv
import glob
import io
import json
import os

import pandas as pd
import psycopg2

from constants import SCHEDULE_FOUNDATION, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "postcodes",
    "description":        "ONS Postcode Directory (ONSPD) → core_postcodes. Foundation for all geographic joins.",
    "schedule":           SCHEDULE_FOUNDATION,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["postcodes"]],
    "cache_key_patterns": ["lsoa_sess:*", "area:*", "resolve:*"],
    "expected_row_range": (1_400_000, 2_800_000),
}

# ---------------------------------------------------------------------------
# Derived data: region code → region name
# ---------------------------------------------------------------------------

_REGION_NAMES = {
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

# ---------------------------------------------------------------------------
# Helper: resolve data file paths
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_onspd_path():
    path = os.environ.get("ONSPD_PATH")
    if path:
        return path
    # Search for any ONSPD_*.csv in the data directory
    matches = glob.glob(os.path.join(_ETL_DATA_DIR, "ONSPD_*.csv"))
    if matches:
        return sorted(matches)[-1]   # most recent by filename
    raise FileNotFoundError(
        f"No ONSPD_*.csv found in {_ETL_DATA_DIR}. "
        "Download from https://geoportal.statistics.gov.uk/search?q=ONSPD "
        "and place in etl/data/, or set the ONSPD_PATH env var."
    )


def _resolve_catchment_names_path():
    path = os.environ.get("CATCHMENT_NAMES_PATH")
    if path:
        return path
    return os.path.join(_ETL_DATA_DIR, "catchment_names.json")


def _resolve_lad_ctyua_path():
    path = os.environ.get("LAD_CTYUA_PATH")
    if path:
        return path
    # Accept either year variant
    for name in ("lad_to_ctyua_2025.csv", "lad_to_ctyua_2024.csv"):
        candidate = os.path.join(_ETL_DATA_DIR, name)
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(
        f"No lad_to_ctyua_2025.csv found in {_ETL_DATA_DIR}. "
        "Set the LAD_CTYUA_PATH env var or place the file in etl/data/."
    )


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest ONSPD → core_postcodes.

    Strategy:
    1. Load auxiliary lookups (ward/LAD names, LAD→county mapping).
    2. Stream ONSPD CSV in chunks; filter active England postcodes.
    3. Stage rows into a temp UNLOGGED table via COPY.
    4. Upsert from staging into core_postcodes (ON CONFLICT DO NOTHING).
    5. Build PostGIS geometry for rows that don't yet have one.
    6. Return final row count.
    """
    onspd_path           = _resolve_onspd_path()
    catchment_names_path = _resolve_catchment_names_path()
    lad_ctyua_path       = _resolve_lad_ctyua_path()

    print(f"  ONSPD source: {onspd_path}", flush=True)

    # Load ward and LAD name lookups
    with open(catchment_names_path, encoding="utf-8") as f:
        catchment = json.load(f)
    ward_names = catchment.get("ward", {})
    lad_names  = catchment.get("lad", {})

    # Build LAD → (county_code, county_name) lookup
    county_lookup = {}
    df_cty = pd.read_csv(lad_ctyua_path, dtype=str, encoding="utf-8-sig")
    for _, row in df_cty.iterrows():
        lad_cd  = row["LAD25CD"]
        cty_cd  = row["CTYUA25CD"]
        cty_nm  = row["CTYUA25NM"]
        # If county code equals LAD code it's a unitary authority — no separate county
        county_lookup[lad_cd] = (cty_cd, cty_nm) if cty_cd != lad_cd else (None, None)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    # Create staging table
    cur.execute("DROP TABLE IF EXISTS _stg_postcodes")
    cur.execute("""
        CREATE UNLOGGED TABLE _stg_postcodes (
            postcode         TEXT,
            postcode_compact TEXT,
            latitude         DOUBLE PRECISION,
            longitude        DOUBLE PRECISION,
            lsoa_code        TEXT,
            lsoa_name        TEXT,
            msoa_code        TEXT,
            msoa_name        TEXT,
            ward_code        TEXT,
            ward_name        TEXT,
            lad_code         TEXT,
            lad_name         TEXT,
            county_code      TEXT,
            county_name      TEXT,
            region_code      TEXT,
            region_name      TEXT,
            nation           CHAR(1)
        )
    """)
    conn.commit()

    # ONSPD columns we need
    usecols    = ["pcds", "doterm", "lat", "long",
                  "lsoa21cd", "msoa21cd", "wd25cd", "lad25cd",
                  "cty25cd", "rgn25cd", "ctry25cd"]
    chunk_size = 500_000
    total_staged = 0

    for chunk in pd.read_csv(
        onspd_path,
        usecols=usecols,
        dtype=str,
        chunksize=chunk_size,
        low_memory=False,
    ):
        # Active (doterm is blank) England postcodes only
        chunk = chunk[
            (chunk["doterm"].isna() | (chunk["doterm"] == "")) &
            (chunk["ctry25cd"].str.startswith("E", na=False))
        ]
        if chunk.empty:
            continue

        buf    = io.StringIO()
        writer = csv.writer(buf, delimiter="\t")

        for _, r in chunk.iterrows():
            pc         = str(r["pcds"]).strip()
            pc_compact = pc.replace(" ", "").upper()

            try:
                lat = float(r["lat"])  if pd.notna(r["lat"])  else ""
                lon = float(r["long"]) if pd.notna(r["long"]) else ""
            except (ValueError, TypeError):
                lat, lon = "", ""

            lsoa = r["lsoa21cd"] if pd.notna(r.get("lsoa21cd")) else ""
            msoa = r["msoa21cd"] if pd.notna(r.get("msoa21cd")) else ""
            ward = r["wd25cd"]   if pd.notna(r.get("wd25cd"))   else ""
            lad  = r["lad25cd"]  if pd.notna(r.get("lad25cd"))  else ""
            rgn  = r["rgn25cd"]  if pd.notna(r.get("rgn25cd"))  else ""

            w_name   = ward_names.get(ward, "") if ward else ""
            l_name   = lad_names.get(lad, "")  if lad  else ""
            cty      = county_lookup.get(lad, (None, None))
            cty_code = cty[0] or ""
            cty_name = cty[1] or ""

            if rgn and "99999" in rgn:
                rgn = ""
            rgn_name = _REGION_NAMES.get(rgn, "") if rgn else ""

            writer.writerow([
                pc, pc_compact, lat, lon,
                lsoa, "",       # lsoa_name comes from boundaries table
                msoa, "",       # msoa_name
                ward, w_name, lad, l_name,
                cty_code, cty_name, rgn, rgn_name, "E",
            ])

        buf.seek(0)
        cur.copy_from(buf, "_stg_postcodes", sep="\t", null="")
        conn.commit()
        total_staged += len(chunk)
        print(f"    Staged {total_staged:,} rows...", flush=True)

    # Upsert from staging into live table
    print("  Upserting into core_postcodes...", flush=True)
    cur.execute("""
        INSERT INTO core_postcodes (
            postcode, postcode_compact, latitude, longitude,
            lsoa_code, lsoa_name, msoa_code, msoa_name,
            ward_code, ward_name, lad_code, lad_name,
            county_code, county_name, region_code, region_name, nation
        )
        SELECT
            postcode, postcode_compact,
            NULLIF(latitude::text,  '')::double precision,
            NULLIF(longitude::text, '')::double precision,
            NULLIF(lsoa_code,   ''), NULLIF(lsoa_name,   ''),
            NULLIF(msoa_code,   ''), NULLIF(msoa_name,   ''),
            NULLIF(ward_code,   ''), NULLIF(ward_name,   ''),
            NULLIF(lad_code,    ''), NULLIF(lad_name,    ''),
            NULLIF(county_code, ''), NULLIF(county_name, ''),
            NULLIF(region_code, ''), NULLIF(region_name, ''),
            nation
        FROM _stg_postcodes
        ON CONFLICT (postcode) DO NOTHING
    """)
    conn.commit()

    # Build PostGIS geometry for any rows that are missing it
    print("  Building PostGIS geometry...", flush=True)
    cur.execute("""
        UPDATE core_postcodes
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND geom IS NULL
    """)
    cur.execute("""
        UPDATE core_postcodes
        SET is_active = TRUE, last_updated = CURRENT_DATE
        WHERE is_active IS NULL
    """)
    conn.commit()

    # Drop staging table
    cur.execute("DROP TABLE IF EXISTS _stg_postcodes")
    conn.commit()

    # Return final row count
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['postcodes']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
