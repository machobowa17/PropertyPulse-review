"""
ETL: OS Open Names → core_place_names (Gazetteer)
Source: ~/Desktop/geodepth/etl/data/opname_csv_gb.zip
Schema: Build Bible Part 2, Section 2.1

OS Open Names CSV has no header. Column positions (0-indexed):
  2  = place_name
  6  = place_type (e.g., populatedPlace, transportNetwork)
  7  = place_subtype (e.g., Suburban Area, City, Town, Village)
  8  = easting (BNG EPSG:27700)
  9  = northing (BNG EPSG:27700)
 16  = postcode_prefix (e.g., SE1, CR5)
 21  = local_authority_name
 24  = county_name
 27  = region_name
 29  = country_name
"""
import os
import json
import zipfile
import csv
import psycopg2
from psycopg2.extras import execute_values
from pyproj import Transformer

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://ukproperty:ukproperty_dev@localhost:5433/ukproperty",
)

OPNAME_ZIP = os.path.expanduser(
    "~/Desktop/geodepth/etl/data/opname_csv_gb.zip"
)

CATCHMENT_NAMES_PATH = os.path.expanduser(
    "~/Desktop/geodepth/etl/data/catchment_names.json"
)

# Only these place types are useful for the gazetteer
WANTED_TYPES = {"populatedPlace", "other"}

# BNG to WGS84 transformer
transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def build_lad_name_to_code():
    """Reverse lookup: LAD name → LAD code from catchment names."""
    with open(CATCHMENT_NAMES_PATH) as f:
        catchment = json.load(f)
    return {v: k for k, v in catchment.get("lad", {}).items()}


def ingest():
    lad_name_to_code = build_lad_name_to_code()

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_place_names CASCADE")
    conn.commit()

    rows = []
    seen = set()

    print(f"Reading OS Open Names from {OPNAME_ZIP}...")
    with zipfile.ZipFile(OPNAME_ZIP, "r") as zf:
        csv_files = [n for n in zf.namelist() if n.endswith(".csv")]
        print(f"  Found {len(csv_files)} tile files")

        for csv_name in csv_files:
            with zf.open(csv_name) as f:
                reader = csv.reader(line.decode("utf-8-sig") for line in f)
                for cols in reader:
                    if len(cols) < 30:
                        continue

                    place_name = cols[2].strip()
                    place_type = cols[6].strip()
                    place_subtype = cols[7].strip()
                    country = cols[29].strip() if len(cols) > 29 else ""

                    # England only, populated places only
                    if country != "England":
                        continue
                    if place_type not in WANTED_TYPES:
                        continue
                    if not place_name:
                        continue

                    try:
                        easting = float(cols[8])
                        northing = float(cols[9])
                    except (ValueError, IndexError):
                        continue

                    postcode_prefix = cols[16].strip() if len(cols) > 16 else None
                    la_name = cols[21].strip() if len(cols) > 21 else None

                    # Convert BNG to lat/lon
                    lon, lat = transformer.transform(easting, northing)

                    # Resolve LAD code from name
                    lad_code = lad_name_to_code.get(la_name, None)

                    # Dedup key: place_name + lad_code
                    dedup_key = (place_name.lower(), lad_code)
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    rows.append((
                        place_name,
                        place_name.lower(),
                        place_subtype if place_subtype else place_type,
                        lad_code,
                        None,  # ward_code (not in OS Open Names)
                        postcode_prefix if postcode_prefix else None,
                        lat,
                        lon,
                        None,  # population (not in OS Open Names)
                    ))

    print(f"  Collected {len(rows):,} place name entries")

    if rows:
        sql = """
            INSERT INTO core_place_names (
                place_name, place_name_lower, place_type,
                lad_code, ward_code, postcode_prefix,
                latitude, longitude, population
            ) VALUES %s
        """
        execute_values(cur, sql, rows, page_size=5000)
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_place_names")
    count = cur.fetchone()[0]
    print(f"Done. core_place_names has {count:,} rows.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ingest()
