"""
sources/epc_domestic.py — MHCLG EPC domestic certificates (all 93 columns) → core_epc_domestic

Imports the full MHCLG bulk ZIP of domestic EPC certificates.
All columns are loaded verbatim (no renaming), then typed, deduplicated, and indexed.

Strategy (optimised for 23M+ rows):
  1. Detect the superset of all columns across all CSVs in the ZIP.
  2. Recreate core_epc_domestic as UNLOGGED with all TEXT columns, no constraints.
  3. Stream-COPY all CSVs in batches of 500k rows.
  4. Deduplicate (keep earliest certificate_number).
  5. Cast numeric/date columns to proper types.
  6. Add primary key, postcode indexes, UPRN sparse index.
  7. Convert table from UNLOGGED to LOGGED.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_epc_domestic)

Data files required (set EPC_ZIP_PATH env var or place in etl/data/):
    domestic-csv.zip  — MHCLG bulk EPC download
    Download from: https://epc.opendatacommunities.org/downloads/domestic
    Licence: Open Government Licence v3.0
"""

import csv
import io
import os
import time
import zipfile

import psycopg2

from constants import SCHEDULE_MONTHLY, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "epc_domestic",
    "description": (
        "MHCLG EPC domestic certificates bulk ZIP (all 93 columns) → core_epc_domestic."
    ),
    "schedule":           SCHEDULE_MONTHLY,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["epc_domestic"]],
    "cache_key_patterns": ["pois:*", "area:*"],
    "expected_row_range": (20_000_000, 30_000_000),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
_TABLE      = TABLE_NAMES["epc_domestic"]
_BATCH_SIZE = 500_000

# Column type casts applied after bulk load.
# Only columns that exist in the loaded data are cast (others silently skipped).
_TYPE_CASTS = {
    "inspection_date":                      "DATE",
    "lodgement_date":                       "DATE",
    "total_floor_area":                     "REAL",
    "floor_height":                         "REAL",
    "co2_emissions_current":                "REAL",
    "co2_emissions_potential":              "REAL",
    "co2_emiss_curr_per_floor_area":        "REAL",
    "energy_consumption_current":           "REAL",
    "energy_consumption_potential":         "REAL",
    "lighting_cost_current":                "REAL",
    "lighting_cost_potential":              "REAL",
    "heating_cost_current":                 "REAL",
    "heating_cost_potential":               "REAL",
    "hot_water_cost_current":               "REAL",
    "hot_water_cost_potential":             "REAL",
    "current_energy_efficiency":            "SMALLINT",
    "potential_energy_efficiency":          "SMALLINT",
    "environment_impact_current":           "SMALLINT",
    "environment_impact_potential":         "SMALLINT",
    "number_habitable_rooms":               "SMALLINT",
    "number_heated_rooms":                  "SMALLINT",
    "number_open_fireplaces":               "SMALLINT",
    "extension_count":                      "SMALLINT",
    "low_energy_lighting":                  "SMALLINT",
    "low_energy_fixed_lighting_outlets_count": "SMALLINT",
    "fixed_lighting_outlets_count":         "SMALLINT",
    "flat_storey_count":                    "SMALLINT",
    "wind_turbine_count":                   "SMALLINT",
    "photo_supply":                         "SMALLINT",
    "multi_glaze_proportion":               "SMALLINT",
    "main_heating_controls":                "SMALLINT",
    "uprn":                                 "BIGINT",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_zip_path():
    path = os.environ.get("EPC_ZIP_PATH")
    if path:
        return path
    candidate = os.path.join(_DATA_DIR, "domestic-csv.zip")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        "EPC ZIP not found. Download the MHCLG bulk domestic EPC ZIP from "
        "https://epc.opendatacommunities.org/downloads/domestic "
        "and place at etl/data/domestic-csv.zip, or set EPC_ZIP_PATH env var."
    )


def _detect_columns(zip_path):
    """Scan all certificate CSVs in the ZIP; return ordered superset of column names."""
    seen = {}
    with zipfile.ZipFile(zip_path) as zf:
        csv_files = sorted([
            n for n in zf.namelist()
            if n.lower().endswith(".csv") and "certificates" in n.lower()
        ])
        for entry in csv_files:
            with zf.open(entry) as raw:
                reader = csv.DictReader(
                    io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
                )
                if reader.fieldnames:
                    for col in reader.fieldnames:
                        seen[col] = True
    cols = list(seen.keys())
    print(f"  Detected {len(cols)} columns across {len(csv_files)} CSV files", flush=True)
    return cols, len(csv_files)


def _setup_fast_table(conn, columns):
    """Recreate table as UNLOGGED with all TEXT columns, no constraints."""
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {_TABLE}")
        col_defs = ", ".join(f'"{c}" TEXT' for c in columns)
        cur.execute(f"CREATE UNLOGGED TABLE {_TABLE} ({col_defs})")
    conn.commit()
    print(f"  Created UNLOGGED {_TABLE} ({len(columns)} TEXT columns)", flush=True)


def _flush_batch(conn, buf, cols_sql, batch_num, batch_count):
    buf.seek(0)
    t0 = time.time()
    with conn.cursor() as cur:
        cur.copy_expert(
            f'COPY {_TABLE} ({cols_sql}) FROM STDIN WITH (FORMAT csv, NULL \'\')',
            buf,
        )
    conn.commit()
    print(f"    Batch {batch_num}: {batch_count:,} rows ({time.time()-t0:.1f}s)", flush=True)


def _load_csv_entry(zf, entry_name, conn, all_columns):
    t0 = time.time()
    raw_count = 0
    batch_num = 0

    with zf.open(entry_name) as raw:
        reader = csv.DictReader(
            io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
        )
        if not reader.fieldnames:
            print(f"  SKIP {entry_name}: no headers", flush=True)
            return 0

        file_cols = [c for c in all_columns if c in reader.fieldnames]
        missing   = [c for c in all_columns if c not in reader.fieldnames]
        if missing:
            print(f"  NOTE {entry_name}: {len(missing)} columns absent, filled NULL", flush=True)

        cols_sql = ", ".join(f'"{c}"' for c in file_cols)

        buf         = io.StringIO()
        writer      = csv.writer(buf)
        batch_count = 0

        for row in reader:
            if not (row.get("postcode") or "").strip():
                continue
            writer.writerow([(row.get(c) or "").strip() for c in file_cols])
            raw_count   += 1
            batch_count += 1

            if batch_count >= _BATCH_SIZE:
                batch_num += 1
                _flush_batch(conn, buf, cols_sql, batch_num, batch_count)
                buf         = io.StringIO()
                writer      = csv.writer(buf)
                batch_count = 0

        if batch_count > 0:
            batch_num += 1
            _flush_batch(conn, buf, cols_sql, batch_num, batch_count)

    print(f"  {entry_name}: {raw_count:,} rows ({time.time()-t0:.1f}s)", flush=True)
    return raw_count


def _finalise_table(conn, columns):
    """Deduplicate, cast types, add PK + indexes, convert to LOGGED."""
    col_set = set(columns)

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {_TABLE}")
        before = cur.fetchone()[0]
    print(f"  Rows before dedup: {before:,}", flush=True)

    with conn.cursor() as cur:
        t0 = time.time()
        cur.execute(f"""
            DELETE FROM {_TABLE} a USING {_TABLE} b
            WHERE a.certificate_number = b.certificate_number
              AND a.ctid > b.ctid
        """)
        dupes = cur.rowcount
    conn.commit()
    print(f"  Removed {dupes:,} duplicates ({time.time()-t0:.1f}s)", flush=True)

    with conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM {_TABLE} WHERE certificate_number IS NULL OR certificate_number = ''"
        )
        nulls = cur.rowcount
    conn.commit()
    if nulls:
        print(f"  Removed {nulls:,} rows with no certificate_number", flush=True)

    # Cast columns to proper types
    casts = {col: pg_type for col, pg_type in _TYPE_CASTS.items() if col in col_set}
    if casts:
        t0 = time.time()
        alter_parts = []
        for col, pg_type in casts.items():
            if pg_type == "DATE":
                using = f'CASE WHEN "{col}" = \'\' THEN NULL ELSE "{col}"::date END'
            elif pg_type == "BIGINT":
                using = f'CASE WHEN "{col}" = \'\' THEN NULL ELSE "{col}"::bigint END'
            elif pg_type == "SMALLINT":
                using = f'CASE WHEN "{col}" = \'\' THEN NULL ELSE "{col}"::smallint END'
            else:  # REAL
                using = f'CASE WHEN "{col}" = \'\' THEN NULL ELSE "{col}"::real END'
            alter_parts.append(f'ALTER COLUMN "{col}" TYPE {pg_type} USING {using}')
        with conn.cursor() as cur:
            cur.execute(f"ALTER TABLE {_TABLE} " + ", ".join(alter_parts))
        conn.commit()
        print(f"  Cast {len(casts)} columns ({time.time()-t0:.1f}s)", flush=True)

    # Primary key
    t0 = time.time()
    with conn.cursor() as cur:
        cur.execute(f'ALTER TABLE {_TABLE} ADD PRIMARY KEY (certificate_number)')
        cur.execute(f'ALTER TABLE {_TABLE} ALTER COLUMN postcode SET NOT NULL')
    conn.commit()
    print(f"  PK added ({time.time()-t0:.1f}s)", flush=True)

    # Indexes
    t0 = time.time()
    with conn.cursor() as cur:
        cur.execute(f'CREATE INDEX idx_epc_postcode ON {_TABLE} (postcode)')
        cur.execute(f'CREATE INDEX idx_epc_postcode_date ON {_TABLE} (postcode, lodgement_date DESC)')
        if "uprn" in col_set:
            cur.execute(f'CREATE INDEX idx_epc_uprn ON {_TABLE} (uprn) WHERE uprn IS NOT NULL')
    conn.commit()
    print(f"  Indexes created ({time.time()-t0:.1f}s)", flush=True)

    # Convert UNLOGGED → LOGGED
    t0 = time.time()
    with conn.cursor() as cur:
        cur.execute(f"ALTER TABLE {_TABLE} SET LOGGED")
    conn.commit()
    print(f"  Table set LOGGED ({time.time()-t0:.1f}s)", flush=True)


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Import MHCLG EPC domestic certificates bulk ZIP → core_epc_domestic.
    Returns final row count.
    """
    zip_path = _resolve_zip_path()
    print(f"  EPC ZIP: {zip_path} ({os.path.getsize(zip_path) / 1e9:.2f} GB)", flush=True)

    all_columns, n_files = _detect_columns(zip_path)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    _setup_fast_table(conn, all_columns)

    total_rows = 0
    t_start    = time.time()

    with zipfile.ZipFile(zip_path) as zf:
        csv_files = sorted([
            n for n in zf.namelist()
            if n.lower().endswith(".csv") and "certificates" in n.lower()
        ])
        for i, entry in enumerate(csv_files, 1):
            print(f"\n  [{i}/{len(csv_files)}] {entry}", flush=True)
            total_rows += _load_csv_entry(zf, entry, conn, all_columns)

    print(f"\n  All files loaded: {total_rows:,} rows in {time.time()-t_start:.0f}s", flush=True)

    _finalise_table(conn, all_columns)

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {_TABLE}")
        count = cur.fetchone()[0]

    conn.close()
    print(f"  core_epc_domestic: {count:,} rows", flush=True)
    return count
