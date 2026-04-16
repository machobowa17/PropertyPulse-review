"""
sources/epc_domestic.py — MHCLG EPC domestic certificates → match → master table update

Pipeline steps (all in one run):
  1. Load core_epc_domestic (9 essential columns only, ~23M rows) from MHCLG bulk ZIP.
     Uses UNLOGGED + COPY for maximum speed.
  2. Deduplicate (keep earliest certificate_number per LMK_KEY).
  3. Add PK + postcode indexes, convert to LOGGED.
  4. SQL address-match: UPDATE core_property_transactions with EPC data for all
     transactions where floor_area_sqm IS NULL. Uses TRANSLATE() normalisation
     (strips all non-alnum chars) + DISTINCT ON to pick best cert per transaction
     (prefer cert lodged before transfer date, then closest lodgement date).
  5. Recompute lsoa_month_avg_ppsm / lsoa_month_avg_ppsft aggregates across the
     entire master table (GROUP BY lsoa_code, month, property_type).
  6. DROP core_epc_domestic to reclaim disk space (~5 GB).

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns count of transactions updated with floor area)

Data files required:
    domestic-csv.zip — MHCLG bulk EPC download (requires free registration)
    Download from: https://epc.opendatacommunities.org/downloads/domestic
    Licence: Open Government Licence v3.0
    Place at etl/data/domestic-csv.zip or set EPC_ZIP_PATH env var.

Notes:
  - Only the 9 columns needed for matching + absorption are loaded (not all 93).
    This keeps core_epc_domestic small (~3 GB) during the run.
  - The TRANSLATE() match is pure SQL — no per-row Python. Significant speedup
    over the legacy Jaccard approach.
  - core_epc_domestic is always dropped at end of run to reclaim disk.
    The GDrive backup (gdrive:PropertyPulse/core_epc_domestic.dump) is the archive.
  - STRIP_CHARS removes: space, hyphen, period, comma, slash, semicolon, colon,
    apostrophe, hash, parens, ampersand, at, underscore, double-quote, backslash.
  - price_per_sqm and price_per_sqft are computed inline during the UPDATE.
  - Aggregate recompute updates lsoa_month_avg_ppsm + lsoa_month_avg_ppsft only
    (not the full 12-column rebuild — that is migration 006 territory).
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
        "MHCLG EPC bulk ZIP → load 9-column core_epc_domestic → SQL address-match "
        "→ UPDATE core_property_transactions (floor_area_sqm, habitable_rooms, "
        "epc_rating, price_per_sqm, price_per_sqft) → recompute lsoa_month ppsm/ppsft "
        "→ DROP core_epc_domestic."
    ),
    "schedule":           SCHEDULE_MONTHLY,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["property_transactions"]],
    "cache_key_patterns": ["area:*", "price_history:*"],
    "expected_row_range": (1_000_000, 10_000_000),  # transactions updated, not EPC rows
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")
_EPC_TABLE  = TABLE_NAMES["epc_domestic"]
_TXN_TABLE  = TABLE_NAMES["property_transactions"]
_BATCH_SIZE = 500_000  # rows per COPY batch during load

# TRANSLATE() strips these characters from address strings before matching.
# Covers all common address punctuation to maximise hit rate.
_STRIP_CHARS = " -.,/;:'#()&@_\"" + "\\"

# Only the 9 columns needed. Maps CSV header (uppercase) → DB column (lowercase).
_COLUMN_MAP = {
    "LMK_KEY":                "certificate_number",
    "ADDRESS1":               "address1",
    "ADDRESS2":               "address2",
    "ADDRESS3":               "address3",
    "POSTCODE":               "postcode",
    "LODGEMENT_DATE":         "lodgement_date",
    "TOTAL_FLOOR_AREA":       "total_floor_area",
    "NUMBER_HABITABLE_ROOMS": "habitable_rooms",
    "CURRENT_ENERGY_RATING":  "current_energy_rating",
}

_CSV_COLS = list(_COLUMN_MAP.keys())   # uppercase — read from CSV
_DB_COLS  = list(_COLUMN_MAP.values()) # lowercase — written to DB

# ---------------------------------------------------------------------------
# Phase 1: Load core_epc_domestic
# ---------------------------------------------------------------------------

def _resolve_zip_path():
    path = os.environ.get("EPC_ZIP_PATH")
    if path:
        return path
    candidate = os.path.join(_DATA_DIR, "domestic-csv.zip")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        "EPC ZIP not found. Download from "
        "https://epc.opendatacommunities.org/downloads/domestic "
        "and place at etl/data/domestic-csv.zip, or set EPC_ZIP_PATH env var."
    )


def _load_epc(conn, zip_path):
    """Load 9-column core_epc_domestic from MHCLG ZIP. Returns raw row count."""
    print(f"\n=== Phase 1: Load core_epc_domestic ===", flush=True)
    print(f"  ZIP: {zip_path} ({os.path.getsize(zip_path)/1e9:.2f} GB)", flush=True)
    t_start = time.time()

    cur = conn.cursor()

    # Recreate as UNLOGGED for fast bulk load
    cur.execute(f"DROP TABLE IF EXISTS {_EPC_TABLE}")
    col_defs = ", ".join(f"{c} TEXT" for c in _DB_COLS)
    cur.execute(f"CREATE UNLOGGED TABLE {_EPC_TABLE} ({col_defs})")
    conn.commit()
    print(f"  Created UNLOGGED {_EPC_TABLE} ({len(_DB_COLS)} columns)", flush=True)

    db_cols_sql = ", ".join(_DB_COLS)
    total_rows = 0

    with zipfile.ZipFile(zip_path) as zf:
        csv_files = sorted([
            n for n in zf.namelist()
            if n.lower().endswith(".csv") and "certificates" in n.lower()
        ])
        print(f"  {len(csv_files)} certificate CSVs in ZIP", flush=True)

        for file_idx, entry in enumerate(csv_files, 1):
            with zf.open(entry) as raw:
                reader = csv.DictReader(
                    io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
                )
                if not reader.fieldnames:
                    continue

                buf = io.StringIO()
                writer = csv.writer(buf)
                batch_count = 0

                for row in reader:
                    pc = (row.get("POSTCODE") or "").strip()
                    if not pc:
                        continue
                    writer.writerow([
                        (row.get(csv_col) or "").strip() for csv_col in _CSV_COLS
                    ])
                    batch_count += 1

                    if batch_count >= _BATCH_SIZE:
                        buf.seek(0)
                        cur.copy_expert(
                            f"COPY {_EPC_TABLE} ({db_cols_sql}) FROM STDIN "
                            "WITH (FORMAT csv, NULL '')",
                            buf,
                        )
                        conn.commit()
                        total_rows += batch_count
                        buf = io.StringIO()
                        writer = csv.writer(buf)
                        batch_count = 0

                if batch_count > 0:
                    buf.seek(0)
                    cur.copy_expert(
                        f"COPY {_EPC_TABLE} ({db_cols_sql}) FROM STDIN "
                        "WITH (FORMAT csv, NULL '')",
                        buf,
                    )
                    conn.commit()
                    total_rows += batch_count

            if file_idx % 50 == 0 or file_idx == len(csv_files):
                print(f"    [{file_idx}/{len(csv_files)}] {total_rows:,} rows", flush=True)

    print(f"  Loaded: {total_rows:,} rows ({time.time()-t_start:.0f}s)", flush=True)

    # Deduplicate (keep first occurrence per certificate_number)
    print("  Deduplicating...", flush=True)
    t0 = time.time()
    cur.execute(f"""
        DELETE FROM {_EPC_TABLE} a USING {_EPC_TABLE} b
        WHERE a.certificate_number = b.certificate_number AND a.ctid > b.ctid
    """)
    dupes = cur.rowcount
    conn.commit()
    print(f"  Removed {dupes:,} duplicates ({time.time()-t0:.0f}s)", flush=True)

    cur.execute(
        f"DELETE FROM {_EPC_TABLE} "
        "WHERE certificate_number IS NULL OR certificate_number = ''"
    )
    conn.commit()

    # Cast types
    print("  Casting types...", flush=True)
    t0 = time.time()
    cur.execute(f"""
        ALTER TABLE {_EPC_TABLE}
            ALTER COLUMN lodgement_date   TYPE DATE
                USING CASE WHEN lodgement_date   = '' THEN NULL
                           ELSE lodgement_date::date END,
            ALTER COLUMN total_floor_area TYPE REAL
                USING CASE WHEN total_floor_area = '' THEN NULL
                           ELSE total_floor_area::real END,
            ALTER COLUMN habitable_rooms  TYPE SMALLINT
                USING CASE WHEN habitable_rooms  = '' THEN NULL
                           ELSE habitable_rooms::smallint END
    """)
    conn.commit()
    print(f"  Types cast ({time.time()-t0:.0f}s)", flush=True)

    # PK + indexes
    print("  Adding PK + indexes...", flush=True)
    t0 = time.time()
    cur.execute(f"ALTER TABLE {_EPC_TABLE} ADD PRIMARY KEY (certificate_number)")
    cur.execute(f"CREATE INDEX idx_epc_postcode ON {_EPC_TABLE} (postcode)")
    cur.execute(
        f"CREATE INDEX idx_epc_postcode_date ON {_EPC_TABLE} (postcode, lodgement_date DESC)"
    )
    conn.commit()
    print(f"  Indexes ({time.time()-t0:.0f}s)", flush=True)

    # Convert UNLOGGED → LOGGED
    print("  Setting LOGGED...", flush=True)
    t0 = time.time()
    cur.execute(f"ALTER TABLE {_EPC_TABLE} SET LOGGED")
    conn.commit()
    print(f"  LOGGED ({time.time()-t0:.0f}s)", flush=True)

    cur.execute(f"SELECT COUNT(*) FROM {_EPC_TABLE}")
    final_count = cur.fetchone()[0]
    cur.close()
    print(f"  core_epc_domestic: {final_count:,} rows ({time.time()-t_start:.0f}s)", flush=True)
    return final_count


# ---------------------------------------------------------------------------
# Phase 2: SQL address-match → UPDATE master table
# ---------------------------------------------------------------------------

def _match_and_update(conn):
    """
    SQL TRANSLATE-based address match. Processes postcodes in batches of 2000.
    Returns count of transactions updated.
    """
    print(f"\n=== Phase 2: Match + UPDATE core_property_transactions ===", flush=True)
    t_start = time.time()

    cur = conn.cursor()

    # Build postcode work list: postcodes with BOTH unmatched transactions AND EPC certs
    print("  Building postcode work list...", flush=True)
    cur.execute(f"""
        SELECT DISTINCT t.postcode
        FROM {_TXN_TABLE} t
        WHERE t.postcode IS NOT NULL
          AND t.floor_area_sqm IS NULL
          AND EXISTS (
              SELECT 1 FROM {_EPC_TABLE} e
              WHERE e.postcode = t.postcode AND e.total_floor_area > 0
          )
        ORDER BY t.postcode
    """)
    postcodes = [r[0] for r in cur.fetchall()]
    conn.rollback()  # close read transaction before writes
    print(f"  {len(postcodes):,} postcodes to process", flush=True)

    if not postcodes:
        print("  Nothing to match.", flush=True)
        cur.close()
        return 0

    total_updated = 0
    batch_size = 2000  # postcodes per commit batch

    for batch_start in range(0, len(postcodes), batch_size):
        batch = postcodes[batch_start: batch_start + batch_size]

        cur.execute(f"""
            WITH txn AS (
                SELECT transaction_id, postcode, date_of_transfer, price,
                       TRANSLATE(
                           UPPER(
                               COALESCE(NULLIF(saon, 'N'), '') ||
                               COALESCE(paon, '') ||
                               COALESCE(street, '')
                           ),
                           %s, ''
                       ) AS norm
                FROM {_TXN_TABLE}
                WHERE floor_area_sqm IS NULL AND postcode = ANY(%s)
            ),
            epc AS (
                SELECT certificate_number, postcode, lodgement_date,
                       total_floor_area, habitable_rooms, current_energy_rating,
                       TRANSLATE(
                           UPPER(
                               COALESCE(address1, '') ||
                               COALESCE(address2, '') ||
                               COALESCE(address3, '')
                           ),
                           %s, ''
                       ) AS norm
                FROM {_EPC_TABLE}
                WHERE total_floor_area > 0 AND postcode = ANY(%s)
            ),
            best AS (
                SELECT DISTINCT ON (txn.transaction_id)
                    txn.transaction_id,
                    epc.certificate_number,
                    epc.total_floor_area,
                    epc.habitable_rooms,
                    epc.current_energy_rating,
                    txn.price
                FROM txn
                JOIN epc ON epc.postcode = txn.postcode AND epc.norm = txn.norm
                WHERE txn.norm <> '' AND epc.norm <> ''
                ORDER BY txn.transaction_id,
                         (epc.lodgement_date <= txn.date_of_transfer)::int DESC,
                         ABS(txn.date_of_transfer - epc.lodgement_date)
            )
            UPDATE {_TXN_TABLE} t
            SET epc_certificate_number = best.certificate_number,
                epc_match_score        = 1.0,
                floor_area_sqm         = best.total_floor_area,
                habitable_rooms        = best.habitable_rooms,
                bedrooms_estimated     = GREATEST(0, best.habitable_rooms - 1),
                epc_rating             = LEFT(best.current_energy_rating, 1),
                price_per_sqm          = CASE WHEN best.total_floor_area > 0
                                              THEN best.price::float / best.total_floor_area
                                              ELSE NULL END,
                price_per_sqft         = CASE WHEN best.total_floor_area > 0
                                              THEN best.price::float / (best.total_floor_area * 10.7639)
                                              ELSE NULL END
            FROM best
            WHERE t.transaction_id = best.transaction_id
        """, (_STRIP_CHARS, batch, _STRIP_CHARS, batch))

        total_updated += cur.rowcount
        conn.commit()

        done = min(batch_start + len(batch), len(postcodes))
        elapsed = time.time() - t_start
        rate = done / elapsed if elapsed > 0 else 0
        eta = (len(postcodes) - done) / rate if rate > 0 else 0

        if (batch_start // batch_size) % 10 == 0 or done == len(postcodes):
            print(
                f"    {done:,}/{len(postcodes):,} postcodes  "
                f"{total_updated:,} updated  "
                f"{elapsed:.0f}s  ETA {eta:.0f}s",
                flush=True,
            )

    cur.close()
    print(f"  Matched: {total_updated:,} transactions ({time.time()-t_start:.0f}s)", flush=True)
    return total_updated


# ---------------------------------------------------------------------------
# Phase 3: Recompute lsoa_month_avg_ppsm + lsoa_month_avg_ppsft
# ---------------------------------------------------------------------------

def _recompute_ppsf_aggregates(conn):
    """
    Recompute lsoa_month_avg_ppsm and lsoa_month_avg_ppsft across the master table.
    Only updates the two price-per-sqft aggregate columns — the other 10 lsoa_month_*
    columns are left unchanged (they are still correct from the last full rebuild).
    """
    print(f"\n=== Phase 3: Recompute lsoa_month ppsm/ppsft aggregates ===", flush=True)
    t_start = time.time()

    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SET work_mem = '512MB'")

    # Compute new averages into a temp table
    print("  Computing new aggregates...", flush=True)
    t0 = time.time()
    cur.execute("DROP TABLE IF EXISTS _epc_ppsf_agg")
    cur.execute(f"""
        CREATE UNLOGGED TABLE _epc_ppsf_agg AS
        SELECT
            lsoa_code,
            date_trunc('month', date_of_transfer) AS month,
            property_type,
            AVG(price::float / floor_area_sqm)
                FILTER (WHERE floor_area_sqm > 0)              AS avg_ppsm,
            AVG(price::float / (floor_area_sqm * 10.7639))
                FILTER (WHERE floor_area_sqm > 0)              AS avg_ppsft
        FROM {_TXN_TABLE}
        GROUP BY lsoa_code, date_trunc('month', date_of_transfer), property_type
    """)
    cur.execute("SELECT COUNT(*) FROM _epc_ppsf_agg")
    agg_rows = cur.fetchone()[0]
    print(f"  {agg_rows:,} groups computed ({time.time()-t0:.0f}s)", flush=True)

    cur.execute("CREATE INDEX ON _epc_ppsf_agg (lsoa_code, month, property_type)")

    # Apply back to master table
    print("  Updating master table...", flush=True)
    t0 = time.time()
    cur.execute(f"""
        UPDATE {_TXN_TABLE} t
        SET lsoa_month_avg_ppsm  = agg.avg_ppsm,
            lsoa_month_avg_ppsft = agg.avg_ppsft
        FROM _epc_ppsf_agg agg
        WHERE t.lsoa_code     = agg.lsoa_code
          AND date_trunc('month', t.date_of_transfer) = agg.month
          AND t.property_type = agg.property_type
    """)
    updated = cur.rowcount
    print(f"  {updated:,} rows updated ({time.time()-t0:.0f}s)", flush=True)

    cur.execute("DROP TABLE IF EXISTS _epc_ppsf_agg")
    conn.autocommit = False
    cur.close()
    print(f"  Aggregates recomputed ({time.time()-t_start:.0f}s)", flush=True)


# ---------------------------------------------------------------------------
# Phase 4: Verify + drop core_epc_domestic
# ---------------------------------------------------------------------------

def _verify_and_drop(conn):
    """Print floor_area coverage by year, then DROP core_epc_domestic."""
    print(f"\n=== Phase 4: Verify + drop core_epc_domestic ===", flush=True)

    cur = conn.cursor()

    # Coverage by year (2010 onwards)
    cur.execute(f"""
        SELECT
            EXTRACT(YEAR FROM date_of_transfer)::int AS yr,
            COUNT(*)                                  AS total,
            COUNT(*) FILTER (WHERE floor_area_sqm > 0) AS with_area,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE floor_area_sqm > 0) / NULLIF(COUNT(*), 0),
                1
            ) AS pct
        FROM {_TXN_TABLE}
        WHERE date_of_transfer >= '2010-01-01'
        GROUP BY 1 ORDER BY 1
    """)
    print(f"  {'Year':>6} {'Total':>10} {'With Area':>10} {'Coverage':>8}")
    print(f"  {'----':>6} {'-----':>10} {'---------':>10} {'--------':>8}")
    for row in cur.fetchall():
        print(f"  {row[0]:>6} {row[1]:>10,} {row[2]:>10,} {row[3]:>7.1f}%")

    # Total with floor area
    cur.execute(
        f"SELECT COUNT(*) FROM {_TXN_TABLE} WHERE floor_area_sqm IS NOT NULL AND floor_area_sqm > 0"
    )
    total_matched = cur.fetchone()[0]
    print(f"\n  Total transactions with floor_area_sqm: {total_matched:,}", flush=True)

    # Drop core_epc_domestic — no longer needed, GDrive backup is the archive
    print(f"\n  Dropping {_EPC_TABLE}...", flush=True)
    t0 = time.time()
    cur.execute(f"DROP TABLE IF EXISTS {_EPC_TABLE}")
    conn.commit()
    print(f"  {_EPC_TABLE} dropped ({time.time()-t0:.0f}s)", flush=True)

    cur.close()
    return total_matched


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Full EPC pipeline:
      1. Load core_epc_domestic (9 cols, ~23M rows)
      2. SQL address-match → UPDATE core_property_transactions
      3. Recompute lsoa_month_avg_ppsm / lsoa_month_avg_ppsft
      4. Verify coverage + DROP core_epc_domestic
    Returns count of transactions updated with floor_area_sqm.
    """
    zip_path = _resolve_zip_path()
    t_total = time.time()

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    try:
        _load_epc(conn, zip_path)
        updated = _match_and_update(conn)
        _recompute_ppsf_aggregates(conn)
        total_matched = _verify_and_drop(conn)
    finally:
        conn.close()

    print(
        f"\n=== epc_domestic complete: {updated:,} transactions updated "
        f"({time.time()-t_total:.0f}s total) ===",
        flush=True,
    )
    return updated
