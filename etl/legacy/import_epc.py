#!/usr/bin/env python3
"""
Import EPC domestic certificates from the bulk download ZIP into core_epc_domestic.

Usage:
    python3 import_epc.py ~/Downloads/domestic-csv.zip

Strategy (optimised for speed):
1. Detect all columns dynamically from the ZIP (superset across all CSVs)
2. Drop and recreate table as UNLOGGED with ALL TEXT columns, no PK/indexes
3. COPY directly from CSV batches (no staging, no conflict checks)
4. After all data loaded: deduplicate, cast types, add PK + indexes
"""

import csv
import io
import os
import sys
import time
import zipfile

import psycopg2

# --- Config ---
DB_DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
BATCH_SIZE = 500_000
TABLE = "core_epc_domestic"

# Columns to cast from TEXT to a proper type after bulk load.
# Only columns that exist in the data will be cast (others silently skipped).
TYPE_CASTS = {
    # Dates
    "inspection_date":              "DATE",
    "lodgement_date":               "DATE",
    # Floats
    "total_floor_area":             "REAL",
    "floor_height":                 "REAL",
    "co2_emissions_current":        "REAL",
    "co2_emissions_potential":      "REAL",
    "co2_emiss_curr_per_floor_area": "REAL",
    "energy_consumption_current":   "REAL",
    "energy_consumption_potential": "REAL",
    "lighting_cost_current":        "REAL",
    "lighting_cost_potential":      "REAL",
    "heating_cost_current":         "REAL",
    "heating_cost_potential":       "REAL",
    "hot_water_cost_current":       "REAL",
    "hot_water_cost_potential":     "REAL",
    # Small integers (scores, counts, percentages)
    "current_energy_efficiency":                "SMALLINT",
    "potential_energy_efficiency":              "SMALLINT",
    "environment_impact_current":               "SMALLINT",
    "environment_impact_potential":             "SMALLINT",
    "number_habitable_rooms":                   "SMALLINT",
    "number_heated_rooms":                      "SMALLINT",
    "number_open_fireplaces":                   "SMALLINT",
    "extension_count":                          "SMALLINT",
    "low_energy_lighting":                      "SMALLINT",
    "low_energy_fixed_lighting_outlets_count":  "SMALLINT",
    "fixed_lighting_outlets_count":             "SMALLINT",
    "flat_storey_count":                        "SMALLINT",
    "wind_turbine_count":                       "SMALLINT",
    "photo_supply":                             "SMALLINT",
    "multi_glaze_proportion":                   "SMALLINT",
    "main_heating_controls":                    "SMALLINT",
    # Big integer (UPRN is a 12-digit number)
    "uprn":                         "BIGINT",
}


def detect_columns(zip_path):
    """Scan all CSVs in the ZIP and return the superset of all column names (in first-seen order)."""
    seen = {}  # ordered dict behaviour via insertion order
    with zipfile.ZipFile(zip_path) as zf:
        csv_files = sorted([n for n in zf.namelist() if n.lower().endswith(".csv") and "certificates" in n.lower()])
        for entry in csv_files:
            with zf.open(entry) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace"))
                if reader.fieldnames:
                    for col in reader.fieldnames:
                        seen[col] = True
    cols = list(seen.keys())
    print(f"Detected {len(cols)} columns across {len(csv_files)} CSV files", flush=True)
    return cols


def setup_fast_table(cur, columns):
    """Drop and recreate table as UNLOGGED with all TEXT cols, no constraints."""
    cur.execute(f"DROP TABLE IF EXISTS {TABLE}")
    col_defs = ", ".join(f'"{c}" TEXT' for c in columns)
    cur.execute(f"CREATE UNLOGGED TABLE {TABLE} ({col_defs})")
    print(f"Created fast-load table (UNLOGGED, {len(columns)} TEXT columns, no indexes)", flush=True)


def flush_batch(cur, buf, cols_sql, batch_num, batch_count):
    """COPY buffer contents directly into main table."""
    buf.seek(0)
    t0 = time.time()
    cur.copy_expert(
        f"COPY {TABLE} ({cols_sql}) FROM STDIN WITH (FORMAT csv, NULL '')",
        buf,
    )
    elapsed = time.time() - t0
    print(f"    Batch {batch_num}: {batch_count:,} rows COPYd ({elapsed:.1f}s)", flush=True)


def process_csv_entry(zf, entry_name, conn, all_columns):
    """Process a single CSV file from the ZIP."""
    t0 = time.time()
    raw_count = 0
    batch_num = 0

    with zf.open(entry_name) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace"))

        if not reader.fieldnames:
            print(f"  SKIP {entry_name}: no headers", flush=True)
            return 0

        # Columns present in this particular CSV (older files have fewer)
        file_cols = [c for c in all_columns if c in reader.fieldnames]
        missing = [c for c in all_columns if c not in reader.fieldnames]
        if missing:
            print(f"  NOTE {entry_name}: {len(missing)} columns absent (older format), filled with NULL", flush=True)

        cols_sql = ", ".join(f'"{c}"' for c in file_cols)
        postcode_col = "postcode"

        with conn.cursor() as cur:
            buf = io.StringIO()
            writer = csv.writer(buf)
            batch_count = 0

            for row in reader:
                # Skip rows with no postcode (unusable for matching)
                if not (row.get(postcode_col) or "").strip():
                    continue
                values = [(row.get(c) or "").strip() for c in file_cols]
                writer.writerow(values)
                raw_count += 1
                batch_count += 1

                if batch_count >= BATCH_SIZE:
                    batch_num += 1
                    flush_batch(cur, buf, cols_sql, batch_num, batch_count)
                    conn.commit()
                    buf = io.StringIO()
                    writer = csv.writer(buf)
                    batch_count = 0

            if batch_count > 0:
                batch_num += 1
                flush_batch(cur, buf, cols_sql, batch_num, batch_count)
                conn.commit()

    elapsed = time.time() - t0
    print(f"  {entry_name}: {raw_count:,} rows loaded ({elapsed:.1f}s)", flush=True)
    return raw_count


def finalise_table(conn, columns):
    """Deduplicate, cast types, add PK and indexes."""
    print("\n--- Finalising table ---", flush=True)
    col_set = set(columns)

    with conn.cursor() as cur:
        # 1. Count before dedup
        cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
        before = cur.fetchone()[0]
        print(f"Total rows before dedup: {before:,}", flush=True)

        # 2. Remove duplicates: keep earliest lodgement by ctid
        t0 = time.time()
        cur.execute(f"""
            DELETE FROM {TABLE} a USING {TABLE} b
            WHERE a.certificate_number = b.certificate_number
              AND a.ctid > b.ctid
        """)
        dupes = cur.rowcount
        conn.commit()
        print(f"Removed {dupes:,} duplicates ({time.time()-t0:.1f}s)", flush=True)

        # 3. Remove rows with no certificate_number
        cur.execute(f"DELETE FROM {TABLE} WHERE certificate_number IS NULL OR certificate_number = ''")
        nulls = cur.rowcount
        conn.commit()
        if nulls:
            print(f"Removed {nulls:,} rows with no certificate_number", flush=True)

        # 4. Cast columns to proper types (only those present in this dataset)
        casts_to_apply = {col: pg_type for col, pg_type in TYPE_CASTS.items() if col in col_set}
        if casts_to_apply:
            t0 = time.time()
            alter_parts = []
            for col, pg_type in casts_to_apply.items():
                if pg_type == "DATE":
                    using = f'CASE WHEN "{col}" = \'\' THEN NULL ELSE "{col}"::date END'
                elif pg_type == "BIGINT":
                    using = f'CASE WHEN "{col}" = \'\' THEN NULL ELSE "{col}"::bigint END'
                elif pg_type == "SMALLINT":
                    using = f'CASE WHEN "{col}" = \'\' THEN NULL ELSE "{col}"::smallint END'
                else:  # REAL
                    using = f'CASE WHEN "{col}" = \'\' THEN NULL ELSE "{col}"::real END'
                alter_parts.append(f'ALTER COLUMN "{col}" TYPE {pg_type} USING {using}')
            cur.execute(f"ALTER TABLE {TABLE} " + ", ".join(alter_parts))
            conn.commit()
            print(f"Cast {len(casts_to_apply)} columns to proper types ({time.time()-t0:.1f}s)", flush=True)

        # 5. Add primary key
        t0 = time.time()
        cur.execute(f'ALTER TABLE {TABLE} ADD PRIMARY KEY (certificate_number)')
        conn.commit()
        print(f"Primary key added ({time.time()-t0:.1f}s)", flush=True)

        # 6. NOT NULL on postcode
        cur.execute(f'ALTER TABLE {TABLE} ALTER COLUMN postcode SET NOT NULL')
        conn.commit()

        # 7. Indexes
        t0 = time.time()
        cur.execute(f'CREATE INDEX idx_epc_postcode ON {TABLE} (postcode)')
        cur.execute(f'CREATE INDEX idx_epc_postcode_date ON {TABLE} (postcode, lodgement_date DESC)')
        if "uprn" in col_set:
            cur.execute(f'CREATE INDEX idx_epc_uprn ON {TABLE} (uprn) WHERE uprn IS NOT NULL')
        conn.commit()
        print(f"Indexes created ({time.time()-t0:.1f}s)", flush=True)

        # 8. Convert to LOGGED
        t0 = time.time()
        cur.execute(f"ALTER TABLE {TABLE} SET LOGGED")
        conn.commit()
        print(f"Table set to LOGGED ({time.time()-t0:.1f}s)", flush=True)

        # 9. Final stats
        cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
        final = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(DISTINCT postcode) FROM {TABLE}")
        postcodes = cur.fetchone()[0]
        print(f"\nFinal: {final:,} rows, {postcodes:,} unique postcodes", flush=True)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 import_epc.py <path-to-domestic-csv.zip>")
        sys.exit(1)

    zip_path = os.path.expanduser(sys.argv[1])
    if not os.path.exists(zip_path):
        print(f"File not found: {zip_path}")
        sys.exit(1)

    print(f"Opening {zip_path} ({os.path.getsize(zip_path) / 1e9:.2f} GB)", flush=True)

    # Phase 0: Detect full column superset from all CSVs in the ZIP
    all_columns = detect_columns(zip_path)

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False

    # Phase 1: Setup fast-load table
    with conn.cursor() as cur:
        setup_fast_table(cur, all_columns)
    conn.commit()

    # Phase 2: Load all CSVs
    total = 0
    t_start = time.time()

    with zipfile.ZipFile(zip_path) as zf:
        csv_files = sorted([n for n in zf.namelist() if n.lower().endswith(".csv") and "certificates" in n.lower()])
        print(f"Found {len(csv_files)} certificate CSV files", flush=True)

        for i, entry in enumerate(csv_files, 1):
            print(f"\n[{i}/{len(csv_files)}] {entry}", flush=True)
            n = process_csv_entry(zf, entry, conn, all_columns)
            total += n

    load_elapsed = time.time() - t_start
    print(f"\nAll files loaded: {total:,} rows in {load_elapsed:.0f}s", flush=True)

    # Phase 3: Finalise (dedup, types, indexes)
    finalise_table(conn, all_columns)

    total_elapsed = time.time() - t_start
    print(f"\nDone. Total time: {total_elapsed:.0f}s", flush=True)
    print(f"You can now delete {zip_path} to reclaim disk space.")

    conn.close()


if __name__ == "__main__":
    main()
