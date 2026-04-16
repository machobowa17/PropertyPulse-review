"""
sources/nhs.py — NHS ODS → core_nhs_facilities

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_nhs_facilities)

Data files required in etl/data/nhs/ (or set env var to override):
    NHS_DIR — directory containing:
                gp.json       — GP practices
                hospital.json — NHS hospitals
                dentist.json  — NHS dentists

The JSON files are arrays of objects with fields:
    ods_code / OrganisationCode / code
    name / OrganisationName
    postcode / Postcode

Download from NHS ODS (Organisation Data Service):
    https://digital.nhs.uk/services/organisation-data-service/export-data-files/csv-downloads/gp-and-gp-practice-related-data
"""

import json
import os

import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ANNUAL, TABLE_NAMES
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "nhs",
    "description":        "NHS ODS JSON (GP, Hospital, Dentist) → core_nhs_facilities. Geocoded via core_postcodes.",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         ["postcodes"],
    "tables_written":     [TABLE_NAMES["nhs_facilities"]],
    "cache_key_patterns": [],
    "expected_row_range": (5_000, 100_000),
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FACILITY_FILES = {
    "GP":       "gp.json",
    "Hospital": "hospital.json",
    "Dentist":  "dentist.json",
}

# ---------------------------------------------------------------------------
# Helper: resolve data directory
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_nhs_dir():
    path = os.environ.get("NHS_DIR")
    if path:
        return path
    return os.path.join(_ETL_DATA_DIR, "nhs")


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest NHS facility JSON files → core_nhs_facilities.

    Strategy:
    1. Build postcode → (lat, lon) lookup from core_postcodes.
    2. For each facility type, load JSON, geocode via postcode lookup.
    3. Truncate core_nhs_facilities and bulk insert all geocoded facilities.
    4. Build PostGIS geometry for all rows.
    5. Return final row count.
    """
    nhs_dir = _resolve_nhs_dir()
    print(f"  NHS data dir: {nhs_dir}", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    # Build postcode → (lat, lon) lookup from core_postcodes
    print("  Building postcode geocode lookup from core_postcodes...", flush=True)
    cur.execute(
        f"SELECT postcode, latitude, longitude FROM {TABLE_NAMES['postcodes']} "
        "WHERE latitude IS NOT NULL"
    )
    pc_lookup = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    print(f"  Loaded {len(pc_lookup):,} postcode coordinates", flush=True)

    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['nhs_facilities']}_new (LIKE {TABLE_NAMES['nhs_facilities']} INCLUDING ALL)")
    conn.commit()

    rows = []
    for ftype, fname in _FACILITY_FILES.items():
        fpath = os.path.join(nhs_dir, fname)
        if not os.path.exists(fpath):
            print(f"  Skipping {fname} (not found)", flush=True)
            continue

        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Support both plain array and wrapper objects
        facilities = (
            data if isinstance(data, list)
            else data.get("Organisations", data.get("features", []))
        )

        count = 0
        for item in facilities:
            if not isinstance(item, dict):
                continue

            org_code = item.get("ods_code",
                        item.get("OrganisationCode",
                        item.get("code", "")))
            name     = item.get("name", item.get("OrganisationName", ""))
            postcode = item.get("postcode", item.get("Postcode", "")).strip()

            coords = pc_lookup.get(postcode)
            if coords is None:
                continue
            lat, lon = coords

            rows.append((org_code, name, ftype, lat, lon, postcode))
            count += 1

        print(f"  {ftype}: {count:,} geocoded", flush=True)

    print(f"  Total collected: {len(rows):,} facilities", flush=True)

    if rows:
        execute_values(
            cur,
            f"""
            INSERT INTO {TABLE_NAMES['nhs_facilities']}_new
                (org_code, name, facility_type, latitude, longitude, postcode)
            VALUES %s
            """,
            rows,
            page_size=5_000,
        )
        conn.commit()

    # Build PostGIS geometry
    cur.execute(
        f"""
        UPDATE {TABLE_NAMES['nhs_facilities']}_new
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL AND geom IS NULL
        """
    )
    conn.commit()

    blue_green_swap(conn, TABLE_NAMES['nhs_facilities'])

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['nhs_facilities']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
