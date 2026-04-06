"""
sources/place_names.py — OS Open Names → core_place_names

Reads OS Open Names ZIP (no header CSV files) and inserts England populated
places into core_place_names, deduplicating by (place_name_lower, lad_code).

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_place_names)

Data files required in etl/data/ (or set env vars):
    OPNAME_ZIP              — opname_csv_gb.zip (OS Open Names, GB edition)
    CATCHMENT_NAMES_PATH    — catchment_names.json (LAD code/name reverse lookup)

Download OS Open Names from:
    https://osdatahub.os.uk/downloads/open/OpenNames
"""

import csv
import json
import os
import zipfile

import psycopg2
from psycopg2.extras import execute_values
from pyproj import Transformer

from constants import SCHEDULE_FOUNDATION, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "place_names",
    "description": "OS Open Names → core_place_names. Powers place-name search.",
    "schedule":           SCHEDULE_FOUNDATION,
    "depends_on":         ["postcodes"],
    "tables_written":     [TABLE_NAMES["place_names"]],
    "cache_key_patterns": ["resolve:*"],
    "expected_row_range": (1, 500_000),
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# OS Open Names CSV column positions (0-indexed, no header row)
_COL_PLACE_NAME    = 2
_COL_PLACE_TYPE    = 6
_COL_PLACE_SUBTYPE = 7
_COL_EASTING       = 8
_COL_NORTHING      = 9
_COL_POSTCODE_PFX  = 16
_COL_LA_NAME       = 21
_COL_COUNTRY       = 29

# Only ingest populated places and 'other' (towns, villages, suburbs, etc.)
_WANTED_TYPES = frozenset({"populatedPlace", "other"})

# BNG (EPSG:27700) → WGS84 (EPSG:4326) transformer
_TRANSFORMER = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_opname_path():
    path = os.environ.get("OPNAME_ZIP")
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, "opname_csv_gb.zip")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"opname_csv_gb.zip not found in {_ETL_DATA_DIR}. "
        "Download from https://osdatahub.os.uk/downloads/open/OpenNames "
        "and place in etl/data/, or set OPNAME_ZIP env var."
    )


def _resolve_catchment_names_path():
    path = os.environ.get("CATCHMENT_NAMES_PATH")
    if path:
        return path
    return os.path.join(_ETL_DATA_DIR, "catchment_names.json")


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest OS Open Names → core_place_names.
    Returns final row count.
    """
    opname_zip           = _resolve_opname_path()
    catchment_names_path = _resolve_catchment_names_path()
    print(f"  OS Open Names source: {opname_zip}", flush=True)

    # Build reverse lookup: LAD name → LAD code
    with open(catchment_names_path, encoding="utf-8") as f:
        catchment = json.load(f)
    lad_name_to_code = {v: k for k, v in catchment.get("lad", {}).items()}

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['place_names']} CASCADE")
    conn.commit()

    rows = []
    seen = set()   # dedup by (place_name_lower, lad_code)

    with zipfile.ZipFile(opname_zip, "r") as zf:
        csv_files = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        print(f"  Found {len(csv_files)} tile files", flush=True)

        for csv_name in csv_files:
            with zf.open(csv_name) as f:
                reader = csv.reader(line.decode("utf-8-sig") for line in f)
                for cols in reader:
                    if len(cols) <= _COL_COUNTRY:
                        continue

                    place_name    = cols[_COL_PLACE_NAME].strip()
                    place_type    = cols[_COL_PLACE_TYPE].strip()
                    place_subtype = cols[_COL_PLACE_SUBTYPE].strip()
                    country       = cols[_COL_COUNTRY].strip()

                    if country != "England":
                        continue
                    if place_type not in _WANTED_TYPES:
                        continue
                    if not place_name:
                        continue

                    try:
                        easting  = float(cols[_COL_EASTING])
                        northing = float(cols[_COL_NORTHING])
                    except (ValueError, IndexError):
                        continue

                    postcode_pfx = cols[_COL_POSTCODE_PFX].strip() or None
                    la_name      = cols[_COL_LA_NAME].strip() or None
                    lad_code     = lad_name_to_code.get(la_name) if la_name else None

                    dedup_key = (place_name.lower(), lad_code)
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    lon, lat = _TRANSFORMER.transform(easting, northing)

                    rows.append((
                        place_name,
                        place_name.lower(),
                        place_subtype or place_type,
                        lad_code,
                        None,          # ward_code — not in OS Open Names
                        postcode_pfx,
                        lat,
                        lon,
                        None,          # population — not in OS Open Names
                    ))

    print(f"  Collected {len(rows):,} place name entries", flush=True)

    if rows:
        execute_values(
            cur,
            f"""INSERT INTO {TABLE_NAMES['place_names']} (
                    place_name, place_name_lower, place_type,
                    lad_code, ward_code, postcode_prefix,
                    latitude, longitude, population
                ) VALUES %s""",
            rows,
            page_size=5000,
        )
        conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['place_names']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_place_names: {count:,} rows", flush=True)
    return count
