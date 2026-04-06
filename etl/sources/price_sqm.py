"""
sources/price_sqm.py — UCL House Price per Square Metre

Reads the UCL/London Datastore HPM ZIP (per-transaction price-per-sqm data)
and produces three tables:
  - core_price_sqm_lad:          LAD-level snapshot (2020+ records)
  - core_price_sqm_lsoa:         LSOA-level snapshot (2020+ records)
  - core_price_sqm_lsoa_yearly:  LSOA × year × property_type (ALL years 1995+)

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_price_sqm_lsoa)

Data files required in etl/data/ (or set PRICE_SQM_ZIP_PATH env var):
    hpm_la_2024.zip  — UCL/London Datastore HPM dataset
    Download from: https://data.london.gov.uk/dataset/house-price-per-square-metre-in-england-and-wales-epo9w/
    Licence: CC-BY 4.0
"""

import csv
import io
import os
import zipfile
from collections import defaultdict

import psycopg2
from psycopg2.extras import execute_values

from constants import PRICE_TYPES, SCHEDULE_ANNUAL, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "price_sqm",
    "description": "UCL House Price per Square Metre → core_price_sqm_lad, core_price_sqm_lsoa, core_price_sqm_lsoa_yearly.",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         ["postcodes"],
    "tables_written":     [
        TABLE_NAMES["price_sqm_lad"],
        TABLE_NAMES["price_sqm_lsoa"],
        "core_price_sqm_lsoa_yearly",
    ],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (30_000, 36_000),   # core_price_sqm_lsoa
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR    = os.path.join(os.path.dirname(__file__), "..", "data")
_ZIP_PATH    = os.environ.get("PRICE_SQM_ZIP_PATH",
                               os.path.join(_DATA_DIR, "hpm_la_2024.zip"))
_SNAPSHOT_MIN_YEAR = 2020  # snapshot tables use 2020+ only
_MAX_PPSM    = 50_000      # sanity cap (£/sqm)
_PRICE_TYPES = set(PRICE_TYPES)

# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Parse UCL HPM ZIP and aggregate price-per-sqm at LAD, LSOA, and LSOA-yearly level.
    Returns row count in core_price_sqm_lsoa.
    """
    if not os.path.exists(_ZIP_PATH):
        raise FileNotFoundError(
            f"UCL HPM ZIP not found: {_ZIP_PATH}. "
            "Download from https://data.london.gov.uk/dataset/house-price-per-square-metre-in-england-and-wales-epo9w/ "
            "and place in etl/data/hpm_la_2024.zip, or set PRICE_SQM_ZIP_PATH env var."
        )

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    # Load postcode → LSOA mapping
    print("  Loading postcode → LSOA mapping...", flush=True)
    cur.execute(
        f"SELECT postcode, lsoa_code FROM {TABLE_NAMES['postcodes']} WHERE lsoa_code IS NOT NULL"
    )
    pc_to_lsoa = {
        pc.replace(" ", "").upper(): lsoa
        for pc, lsoa in cur.fetchall()
    }
    print(f"  Loaded {len(pc_to_lsoa):,} postcode→LSOA mappings", flush=True)

    # Accumulators — snapshot (2020+)
    lad_data  = defaultdict(lambda: {
        "total": 0.0, "count": 0,
        "by_type": defaultdict(lambda: {"total": 0.0, "count": 0}),
    })
    lsoa_data = defaultdict(lambda: {
        "total": 0.0, "count": 0,
        "by_type": defaultdict(lambda: {"total": 0.0, "count": 0}),
    })

    # Accumulator — yearly (ALL years)
    # key: (lsoa_code, year, property_type) → {"total": float, "count": int}
    lsoa_yearly = defaultdict(lambda: {"total": 0.0, "count": 0})

    with zipfile.ZipFile(_ZIP_PATH) as z:
        csv_files = [n for n in z.namelist() if n.endswith(".csv")]
        print(f"  Processing {len(csv_files)} LAD files...", flush=True)

        for i, name in enumerate(csv_files):
            with z.open(name) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                for r in reader:
                    try:
                        year = int(r.get("year", "0"))
                    except ValueError:
                        continue

                    ppsm_str = r.get("priceper", "")
                    lad      = r.get("lad23cd", "").strip()
                    postcode = r.get("postcode", "").replace(" ", "").upper()
                    ptype    = r.get("propertytype", "").strip()

                    if not ppsm_str:
                        continue
                    try:
                        ppsm = float(ppsm_str)
                    except ValueError:
                        continue
                    if ppsm <= 0 or ppsm > _MAX_PPSM:
                        continue

                    # LSOA-level yearly aggregation (ALL years, ALL valid types)
                    lsoa = pc_to_lsoa.get(postcode)
                    if lsoa and ptype in _PRICE_TYPES:
                        lsoa_yearly[(lsoa, year, ptype)]["total"] += ppsm
                        lsoa_yearly[(lsoa, year, ptype)]["count"] += 1

                    # Snapshot tables (2020+ only)
                    if year < _SNAPSHOT_MIN_YEAR:
                        continue

                    # LAD-level aggregation
                    if lad and lad.startswith("E"):
                        lad_data[lad]["total"]  += ppsm
                        lad_data[lad]["count"]  += 1
                        if ptype in _PRICE_TYPES:
                            lad_data[lad]["by_type"][ptype]["total"] += ppsm
                            lad_data[lad]["by_type"][ptype]["count"] += 1

                    # LSOA-level snapshot aggregation
                    if lsoa:
                        lsoa_data[lsoa]["total"] += ppsm
                        lsoa_data[lsoa]["count"] += 1
                        if ptype in _PRICE_TYPES:
                            lsoa_data[lsoa]["by_type"][ptype]["total"] += ppsm
                            lsoa_data[lsoa]["by_type"][ptype]["count"] += 1

            if (i + 1) % 50 == 0:
                print(f"    Processed {i+1}/{len(csv_files)} files...", flush=True)

    def _avg(d, ptype=None):
        if ptype:
            bt = d["by_type"][ptype]
            return round(bt["total"] / bt["count"], 2) if bt["count"] else None
        return round(d["total"] / d["count"], 2) if d["count"] else None

    # Load LAD snapshot table
    print(f"  LADs with data: {len(lad_data):,}", flush=True)
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['price_sqm_lad']}")
    lad_rows = [
        (lad,
         _avg(d), _avg(d, "D"), _avg(d, "S"), _avg(d, "T"), _avg(d, "F"),
         d["count"])
        for lad, d in lad_data.items() if d["count"] > 0
    ]
    execute_values(
        cur,
        f"""INSERT INTO {TABLE_NAMES['price_sqm_lad']} (
                lad_code, avg_price_per_sqm,
                avg_ppsm_detached, avg_ppsm_semi, avg_ppsm_terraced, avg_ppsm_flat,
                transaction_count
            ) VALUES %s""",
        lad_rows,
    )
    conn.commit()

    # Load LSOA snapshot table
    print(f"  LSOAs with data: {len(lsoa_data):,}", flush=True)
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['price_sqm_lsoa']}")
    lsoa_rows = [
        (lsoa,
         _avg(d), _avg(d, "D"), _avg(d, "S"), _avg(d, "T"), _avg(d, "F"),
         d["count"])
        for lsoa, d in lsoa_data.items() if d["count"] > 0
    ]
    execute_values(
        cur,
        f"""INSERT INTO {TABLE_NAMES['price_sqm_lsoa']} (
                lsoa_code, avg_price_per_sqm,
                avg_ppsm_detached, avg_ppsm_semi, avg_ppsm_terraced, avg_ppsm_flat,
                transaction_count
            ) VALUES %s""",
        lsoa_rows,
    )
    conn.commit()

    # Load LSOA yearly table (ALL years)
    print(f"  LSOA-yearly combinations: {len(lsoa_yearly):,}", flush=True)
    cur.execute("TRUNCATE TABLE core_price_sqm_lsoa_yearly")
    yearly_rows = [
        (lsoa, year, ptype,
         round(d["total"] / d["count"], 2),
         d["count"])
        for (lsoa, year, ptype), d in lsoa_yearly.items()
        if d["count"] > 0
    ]
    # Batch insert in chunks of 50k
    chunk_size = 50_000
    for start in range(0, len(yearly_rows), chunk_size):
        execute_values(
            cur,
            """INSERT INTO core_price_sqm_lsoa_yearly
                    (lsoa_code, year, property_type, avg_ppsm, transaction_count)
                VALUES %s""",
            yearly_rows[start:start + chunk_size],
        )
    conn.commit()
    print(f"  core_price_sqm_lsoa_yearly: {len(yearly_rows):,} rows", flush=True)

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['price_sqm_lsoa']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_price_sqm_lad: {len(lad_rows):,}, core_price_sqm_lsoa: {count:,}", flush=True)
    return count
