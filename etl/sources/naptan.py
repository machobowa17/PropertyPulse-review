"""
sources/naptan.py — DfT NaPTAN → core_transport_stops

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_transport_stops)

Data files required in etl/data/ (or set env var to override):
    NAPTAN_PATH — naptan.csv  (DfT NaPTAN full CSV export)

Download from:
    https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv
"""

import csv
import os

import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ANNUAL, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "naptan",
    "description":        "DfT NaPTAN CSV → core_transport_stops (bus stops, rail stations, etc. for England).",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["transport_stops"]],
    "cache_key_patterns": [],
    "expected_row_range": (200_000, 600_000),
}

# Rough lat bounds to keep England (and exclude Scotland / NI)
_LAT_MIN = 49.9
_LAT_MAX = 56.0

# ---------------------------------------------------------------------------
# Helper: resolve data file path
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_naptan_path():
    path = os.environ.get("NAPTAN_PATH")
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, "naptan.csv")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"No naptan.csv found at {candidate}. "
        "Download from https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv "
        "and place in etl/data/, or set the NAPTAN_PATH env var."
    )


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest DfT NaPTAN → core_transport_stops.

    Strategy:
    1. Stream NaPTAN CSV; filter to England lat/lon range.
    2. Truncate core_transport_stops and bulk insert all stops.
    3. Build PostGIS geometry for all rows.
    4. Return final row count.
    """
    naptan_path = _resolve_naptan_path()
    print(f"  NaPTAN source: {naptan_path}", flush=True)

    rows = []
    with open(naptan_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            atco = r.get("ATCOCode", "").strip()
            if not atco:
                continue

            try:
                lat = float(r["Latitude"])  if r.get("Latitude")  else None
                lon = float(r["Longitude"]) if r.get("Longitude") else None
            except (ValueError, TypeError):
                continue

            if lat is None or lon is None:
                continue

            # England-only lat bounds (excludes Scotland and Northern Ireland)
            if not (_LAT_MIN <= lat <= _LAT_MAX):
                continue

            rows.append((
                atco,
                r.get("CommonName", ""),
                r.get("StopType", ""),
                lat,
                lon,
                None,   # lad_code — not populated here
            ))

    print(f"  Collected {len(rows):,} England stops", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['transport_stops']} CASCADE")
    conn.commit()

    if rows:
        execute_values(
            cur,
            f"""
            INSERT INTO {TABLE_NAMES['transport_stops']}
                (atco_code, stop_name, stop_type, latitude, longitude, lad_code)
            VALUES %s
            ON CONFLICT DO NOTHING
            """,
            rows,
            page_size=10_000,
        )
        conn.commit()

    # Build PostGIS geometry
    cur.execute(
        f"""
        UPDATE {TABLE_NAMES['transport_stops']}
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND geom IS NULL
        """
    )
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['transport_stops']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
