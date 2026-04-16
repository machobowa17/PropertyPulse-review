"""
sources/ev_chargers.py — OZEV Open Charge Point Registry → core_ev_chargers

Reads the OZEV/DESNZ National Charge Point Registry CSV and ingests all
public EV charge points into core_ev_chargers.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_ev_chargers)

Data files required in etl/data/ (or set EV_CHARGERS_PATH env var):
    ev_chargepoints.csv  — OZEV National Charge Point Registry
    Download from: https://www.gov.uk/guidance/find-and-use-data-on-public-electric-vehicle-chargepoints
"""

import csv
import os

import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_QUARTERLY, TABLE_NAMES
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "ev_chargers",
    "description": "OZEV Open Charge Point Registry → core_ev_chargers.",
    "schedule":           SCHEDULE_QUARTERLY,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["ev_chargers"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (10_000, 60_000),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_SRC_PATH = os.environ.get(
    "EV_CHARGERS_PATH",
    os.path.join(_DATA_DIR, "ev_chargepoints.csv"),
)

# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest OZEV charge point CSV → core_ev_chargers.
    Returns final row count.
    """
    if not os.path.exists(_SRC_PATH):
        raise FileNotFoundError(
            f"EV charger CSV not found: {_SRC_PATH}. "
            "Download from https://www.gov.uk/guidance/find-and-use-data-on-public-electric-vehicle-chargepoints "
            "and place in etl/data/ev_chargepoints.csv, or set EV_CHARGERS_PATH env var."
        )

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['ev_chargers']}_new (LIKE {TABLE_NAMES['ev_chargers']} INCLUDING ALL)")
    conn.commit()

    rows = []
    with open(_SRC_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lat_str = r.get("latitude", "")
            lon_str = r.get("longitude", "")
            try:
                lat_f = float(lat_str) if lat_str else None
                lon_f = float(lon_str) if lon_str else None
            except (ValueError, TypeError):
                continue
            if lat_f is None or lon_f is None:
                continue

            ref      = r.get("referenceID") or r.get("chargeDeviceID") or ""
            name     = r.get("name") or r.get("chargeDeviceName") or ""
            operator = r.get("deviceControllerName") or r.get("operator") or ""

            try:
                connectors = int(r.get("connectorCount") or r.get("connector1RatedOutputkW") or 0)
            except (ValueError, TypeError):
                connectors = 0
            try:
                power = float(r.get("ratedOutputKW") or r.get("connector1RatedOutputkW") or 0)
            except (ValueError, TypeError):
                power = 0.0

            rows.append((ref, name, lat_f, lon_f, connectors, power, operator))

    print(f"  Collected {len(rows):,} EV chargepoints", flush=True)

    if rows:
        execute_values(
            cur,
            f"""INSERT INTO {TABLE_NAMES['ev_chargers']}_new (
                    reference_id, name, latitude, longitude,
                    connector_count, max_power_kw, operator
                ) VALUES %s""",
            rows,
            page_size=5000,
        )
        conn.commit()

    cur.execute(f"""
        UPDATE {TABLE_NAMES['ev_chargers']}_new
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL
    """)
    conn.commit()

    blue_green_swap(conn, TABLE_NAMES['ev_chargers'])

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['ev_chargers']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_ev_chargers: {count:,} rows", flush=True)
    return count
