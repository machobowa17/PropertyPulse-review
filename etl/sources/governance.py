"""
sources/governance.py — Council political control + S114 notices

Builds two tables:
    core_council_control_lad  — Controlling party for each English LAD
    core_s114_notices         — Section 114 (bankruptcy) notices

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_council_control_lad)

Data files required in etl/data/ (or set COUNCIL_CONTROL_PATH env var):
    council_control_2025.csv  — from Open Council Data UK (CC-BY-SA)
    Download from: https://opencouncildata.co.uk/
"""

import csv
import os
from collections import defaultdict

import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_QUARTERLY, TABLE_NAMES
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "governance",
    "description": "Council political control + S114 notices → core_council_control_lad, core_s114_notices.",
    "schedule":           SCHEDULE_QUARTERLY,
    "depends_on":         ["boundaries"],
    "tables_written":     [
        TABLE_NAMES["council_control_lad"],
        TABLE_NAMES["s114_notices"],
    ],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (250, 400),   # core_council_control_lad
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR          = os.path.join(os.path.dirname(__file__), "..", "data")
_COUNCIL_CTRL_PATH = os.environ.get(
    "COUNCIL_CONTROL_PATH",
    os.path.join(_DATA_DIR, "council_control_2025.csv"),
)

# S114 notices: public record (https://www.gov.uk/government/publications/)
# Update this list when a new notice is issued.
_S114_DATA = [
    ("E09000017", "Hillingdon",       "2000-01-01"),
    ("E09000012", "Hackney",          "2000-10-17"),
    ("E10000021", "Northamptonshire", "2018-02-01"),
    ("E09000008", "Croydon",          "2020-11-11"),
    ("E06000039", "Slough",           "2021-07-01"),
    ("E06000034", "Thurrock",         "2022-12-01"),
    ("E07000217", "Woking",           "2023-06-07"),
    ("E08000025", "Birmingham",       "2023-09-01"),
    ("E06000018", "Nottingham",       "2023-11-29"),
]

# ---------------------------------------------------------------------------
# Council control ingestion
# ---------------------------------------------------------------------------

def _ingest_council_control(conn):
    if not os.path.exists(_COUNCIL_CTRL_PATH):
        raise FileNotFoundError(
            f"Council control CSV not found: {_COUNCIL_CTRL_PATH}. "
            "Download from https://opencouncildata.co.uk/ "
            "or set COUNCIL_CONTROL_PATH env var."
        )

    # Count seats by council × party
    council_parties = defaultdict(lambda: defaultdict(int))
    with open(_COUNCIL_CTRL_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            council = r.get("Council", "").strip()
            party   = r.get("Party Name", "").strip()
            if council and party:
                council_parties[council][party] += 1

    # Determine controlling party (majority or NOC)
    controls = {}
    for council, parties in council_parties.items():
        total_seats    = sum(parties.values())
        sorted_parties = sorted(parties.items(), key=lambda x: -x[1])
        top_party, top_seats = sorted_parties[0]
        if top_seats > total_seats / 2:
            controls[council] = (top_party, top_seats, total_seats)
        else:
            controls[council] = ("No Overall Control", top_seats, total_seats)

    print(f"  Councils parsed: {len(controls)}", flush=True)

    # Match council names to LAD codes
    cur = conn.cursor()
    cur.execute(f"SELECT lad_code, lad_name FROM {TABLE_NAMES['lad_boundaries']}")
    lad_map = {}
    for lad_code, lad_name in cur.fetchall():
        lad_map[lad_name.lower()] = lad_code
        clean = (lad_name.lower()
                 .replace("city of ", "")
                 .replace("borough of ", "")
                 .replace("royal borough of ", ""))
        lad_map[clean] = lad_code

    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['council_control_lad']}_new (LIKE {TABLE_NAMES['council_control_lad']} INCLUDING ALL)")
    conn.commit()

    seen_lads = {}
    for council, (party, seats, total) in controls.items():
        lad_code = lad_map.get(council.lower())
        if not lad_code:
            for lad_name_key, code in lad_map.items():
                if council.lower() in lad_name_key or lad_name_key in council.lower():
                    lad_code = code
                    break
        if lad_code and lad_code not in seen_lads:
            seen_lads[lad_code] = (lad_code, council, party, seats, total)

    rows = list(seen_lads.values())
    execute_values(
        cur,
        f"""INSERT INTO {TABLE_NAMES['council_control_lad']}_new
                (lad_code, council_name, controlling_party, majority_seats, total_seats)
            VALUES %s
            ON CONFLICT DO NOTHING""",
        rows,
    )
    conn.commit()

    blue_green_swap(conn, TABLE_NAMES['council_control_lad'])

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['council_control_lad']}")
    count = cur.fetchone()[0]
    cur.close()
    print(f"  core_council_control_lad: {count:,} rows", flush=True)
    return count


# ---------------------------------------------------------------------------
# S114 notices ingestion
# ---------------------------------------------------------------------------

def _ingest_s114(conn):
    cur = conn.cursor()
    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['s114_notices']}_new (LIKE {TABLE_NAMES['s114_notices']} INCLUDING ALL)")
    conn.commit()
    execute_values(
        cur,
        f"""INSERT INTO {TABLE_NAMES['s114_notices']}_new
                (lad_code, council_name, notice_date)
            VALUES %s""",
        _S114_DATA,
    )
    conn.commit()
    blue_green_swap(conn, TABLE_NAMES['s114_notices'])
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['s114_notices']}")
    count = cur.fetchone()[0]
    cur.close()
    print(f"  core_s114_notices: {count:,} rows", flush=True)
    return count


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest council political control + S114 notices.
    Returns row count in core_council_control_lad.
    """
    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    count = _ingest_council_control(conn)
    _ingest_s114(conn)

    conn.close()
    return count
