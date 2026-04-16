"""
sources/epc_lsoa.py — ONS/Nomis Energy Efficiency of Housing → core_epc_lsoa

Reads the pre-downloaded Nomis NM_2401_1 bulk CSV and aggregates EPC band
distributions to LSOA level.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_epc_lsoa)

Data files required in etl/data/ (or set EPC_LSOA_PATH env var):
    epc_lsoa_nomis.csv  — Nomis NM_2401_1 bulk download
    URL: https://www.nomisweb.co.uk/api/v01/dataset/NM_2401_1.bulk.csv
"""

import csv
import os

import psycopg2
from psycopg2.extras import execute_values

from constants import EPC_BAND_SCORES, SCHEDULE_QUARTERLY, TABLE_NAMES
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "epc_lsoa",
    "description": "ONS/Nomis Energy Efficiency of Housing (NM_2401_1) → core_epc_lsoa.",
    "schedule":           SCHEDULE_QUARTERLY,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["epc_lsoa"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (30_000, 36_000),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_EPC_PATH = os.environ.get(
    "EPC_LSOA_PATH",
    os.path.join(_DATA_DIR, "epc_lsoa_nomis.csv"),
)

# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest Nomis EPC LSOA aggregates → core_epc_lsoa.
    Returns final row count.
    """
    if not os.path.exists(_EPC_PATH):
        raise FileNotFoundError(
            f"Nomis EPC CSV not found: {_EPC_PATH}. "
            "Download from https://www.nomisweb.co.uk/api/v01/dataset/NM_2401_1.bulk.csv "
            "and place in etl/data/epc_lsoa_nomis.csv, or set EPC_LSOA_PATH env var."
        )

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['epc_lsoa']}_new (LIKE {TABLE_NAMES['epc_lsoa']} INCLUDING ALL)")
    conn.commit()

    # EPC band → midpoint energy efficiency score (from constants)
    band_score = EPC_BAND_SCORES   # {"A": 92, "B": 81, ...}

    rows = []
    with open(_EPC_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lsoa = r.get("geography code", "").strip()
            if not lsoa.startswith(("E01", "W01")):   # England and Wales LSOAs only
                continue

            def _pct(key):
                v = r.get(key, "").strip()
                try:
                    return float(v) if v else 0.0
                except (ValueError, TypeError):
                    return 0.0

            def _int(key):
                v = r.get(key, "").strip()
                try:
                    return int(v) if v else 0
                except (ValueError, TypeError):
                    return 0

            total = _int("Energy efficiency rating: Total; measures: Value")
            if total == 0:
                continue

            pct_a = _pct("Energy efficiency rating: Band A; measures: Percent")
            pct_b = _pct("Energy efficiency rating: Band B; measures: Percent")
            pct_c = _pct("Energy efficiency rating: Band C; measures: Percent")
            pct_d = _pct("Energy efficiency rating: Band D; measures: Percent")
            pct_e = _pct("Energy efficiency rating: Band E; measures: Percent")
            pct_f = _pct("Energy efficiency rating: Band F; measures: Percent")
            pct_g = _pct("Energy efficiency rating: Band G; measures: Percent")

            pct_ab = round(pct_a + pct_b, 2)
            pct_eg = round(pct_e + pct_f + pct_g, 2)

            # Weighted average energy efficiency score using band midpoints
            avg_score = round(
                (pct_a * band_score["A"] + pct_b * band_score["B"]
                 + pct_c * band_score["C"] + pct_d * band_score["D"]
                 + pct_e * band_score["E"] + pct_f * band_score["F"]
                 + pct_g * band_score["G"]) / 100,
                1,
            )

            rows.append((
                lsoa, total, avg_score, pct_ab, pct_c, pct_d, pct_eg, None
            ))

    print(f"  Collected {len(rows):,} LSOA EPC records", flush=True)

    if rows:
        execute_values(
            cur,
            f"""INSERT INTO {TABLE_NAMES['epc_lsoa']}_new (
                    lsoa_code, total_certs, avg_energy_score,
                    pct_rating_a_b, pct_rating_c, pct_rating_d, pct_rating_e_g,
                    avg_co2_emissions
                ) VALUES %s
                ON CONFLICT DO NOTHING""",
            rows,
            page_size=10_000,
        )
        conn.commit()

    blue_green_swap(conn, TABLE_NAMES['epc_lsoa'])

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['epc_lsoa']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_epc_lsoa: {count:,} rows", flush=True)
    return count
