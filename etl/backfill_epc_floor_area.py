#!/usr/bin/env python3
"""
One-off EPC backfill: Load EPC domestic certificates and Jaccard-match to
ALL transactions missing floor_area_sqm on core_property_transactions.

Phase 1: Load core_epc_domestic (9 essential columns only, ~23M rows)
Phase 2: Jaccard address-match unmatched transactions → UPDATE master table
Phase 3: Verify coverage by year

Usage:
    EPC_ZIP_PATH=/Users/batty/Downloads/all-domestic-certificates.zip python3 backfill_epc_floor_area.py
"""

import csv
import io
import os
import re
import sys
import time
import zipfile
from datetime import date as dt_date

import psycopg2
import psycopg2.extras

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
EPC_TABLE = "core_epc_domestic"
TXN_TABLE = "core_property_transactions"
BATCH_SIZE = 500_000  # rows per COPY batch for EPC load
MATCH_BATCH = 500     # postcodes per matching batch

# Only the columns we need for matching + absorption
# Maps: CSV header (uppercase) → DB column name (lowercase)
COLUMN_MAP = {
    "LMK_KEY":                  "certificate_number",
    "ADDRESS1":                 "address1",
    "ADDRESS2":                 "address2",
    "ADDRESS3":                 "address3",
    "POSTCODE":                 "postcode",
    "LODGEMENT_DATE":           "lodgement_date",
    "TOTAL_FLOOR_AREA":         "total_floor_area",
    "NUMBER_HABITABLE_ROOMS":   "habitable_rooms",
    "CURRENT_ENERGY_RATING":    "current_energy_rating",
}

CSV_COLS = list(COLUMN_MAP.keys())    # uppercase keys to read from CSV
DB_COLS  = list(COLUMN_MAP.values())  # lowercase names for the DB table


# ---------------------------------------------------------------------------
# Phase 1: Load core_epc_domestic
# ---------------------------------------------------------------------------

def load_epc(conn, zip_path):
    """Load EPC domestic certificates from MHCLG ZIP into core_epc_domestic."""
    print("\n=== Phase 1: Loading core_epc_domestic ===", flush=True)
    t_start = time.time()

    cur = conn.cursor()

    # Create table (UNLOGGED for fast bulk load)
    cur.execute(f"DROP TABLE IF EXISTS {EPC_TABLE}")
    col_defs = ", ".join(f"{c} TEXT" for c in DB_COLS)
    cur.execute(f"CREATE UNLOGGED TABLE {EPC_TABLE} ({col_defs})")
    conn.commit()
    print(f"  Created UNLOGGED {EPC_TABLE} ({len(DB_COLS)} columns)", flush=True)

    # Find certificate CSVs in ZIP
    zf = zipfile.ZipFile(zip_path)
    csv_files = sorted([
        n for n in zf.namelist()
        if n.lower().endswith(".csv") and "certificates" in n.lower()
    ])
    print(f"  Found {len(csv_files)} certificate CSVs in ZIP", flush=True)

    db_cols_sql = ", ".join(DB_COLS)
    total_rows = 0

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
                # Skip rows without postcode
                pc = (row.get("POSTCODE") or "").strip()
                if not pc:
                    continue

                # Extract only the columns we need, mapped to DB names
                writer.writerow([
                    (row.get(csv_col) or "").strip() for csv_col in CSV_COLS
                ])
                batch_count += 1

                if batch_count >= BATCH_SIZE:
                    buf.seek(0)
                    cur.copy_expert(
                        f"COPY {EPC_TABLE} ({db_cols_sql}) FROM STDIN WITH (FORMAT csv, NULL '')",
                        buf,
                    )
                    conn.commit()
                    total_rows += batch_count
                    buf = io.StringIO()
                    writer = csv.writer(buf)
                    batch_count = 0

            # Flush remaining
            if batch_count > 0:
                buf.seek(0)
                cur.copy_expert(
                    f"COPY {EPC_TABLE} ({db_cols_sql}) FROM STDIN WITH (FORMAT csv, NULL '')",
                    buf,
                )
                conn.commit()
                total_rows += batch_count

        if file_idx % 50 == 0 or file_idx == len(csv_files):
            print(f"    [{file_idx}/{len(csv_files)}] {total_rows:,} rows loaded", flush=True)

    zf.close()
    print(f"  Total rows loaded: {total_rows:,} ({time.time() - t_start:.0f}s)", flush=True)

    # Deduplicate (keep first by ctid)
    print("  Deduplicating...", flush=True)
    t0 = time.time()
    cur.execute(f"""
        DELETE FROM {EPC_TABLE} a USING {EPC_TABLE} b
        WHERE a.certificate_number = b.certificate_number
          AND a.ctid > b.ctid
    """)
    dupes = cur.rowcount
    conn.commit()
    print(f"  Removed {dupes:,} duplicates ({time.time() - t0:.0f}s)", flush=True)

    # Remove rows with no certificate_number
    cur.execute(f"DELETE FROM {EPC_TABLE} WHERE certificate_number IS NULL OR certificate_number = ''")
    conn.commit()

    # Cast types
    print("  Casting types...", flush=True)
    t0 = time.time()
    cur.execute(f"""
        ALTER TABLE {EPC_TABLE}
            ALTER COLUMN lodgement_date TYPE DATE
                USING CASE WHEN lodgement_date = '' THEN NULL ELSE lodgement_date::date END,
            ALTER COLUMN total_floor_area TYPE REAL
                USING CASE WHEN total_floor_area = '' THEN NULL ELSE total_floor_area::real END,
            ALTER COLUMN habitable_rooms TYPE SMALLINT
                USING CASE WHEN habitable_rooms = '' THEN NULL ELSE habitable_rooms::smallint END
    """)
    conn.commit()
    print(f"  Types cast ({time.time() - t0:.0f}s)", flush=True)

    # Primary key + indexes
    print("  Adding PK and indexes...", flush=True)
    t0 = time.time()
    cur.execute(f"ALTER TABLE {EPC_TABLE} ADD PRIMARY KEY (certificate_number)")
    cur.execute(f"CREATE INDEX idx_epc_postcode ON {EPC_TABLE} (postcode)")
    cur.execute(f"CREATE INDEX idx_epc_postcode_date ON {EPC_TABLE} (postcode, lodgement_date DESC)")
    conn.commit()
    print(f"  Indexes created ({time.time() - t0:.0f}s)", flush=True)

    # Convert to LOGGED
    print("  Setting LOGGED...", flush=True)
    t0 = time.time()
    cur.execute(f"ALTER TABLE {EPC_TABLE} SET LOGGED")
    conn.commit()
    print(f"  LOGGED ({time.time() - t0:.0f}s)", flush=True)

    cur.execute(f"SELECT COUNT(*) FROM {EPC_TABLE}")
    final_count = cur.fetchone()[0]
    cur.close()
    print(f"  core_epc_domestic: {final_count:,} rows ({time.time() - t_start:.0f}s total)", flush=True)
    return final_count


# ---------------------------------------------------------------------------
# Phase 2: Jaccard address matching + UPDATE master table
# ---------------------------------------------------------------------------

_NON_ALNUM = re.compile(r"[^A-Z0-9 ]")


def _normalise_addr(s):
    if not s:
        return set()
    return set(_NON_ALNUM.sub(" ", s.upper()).split())


def _jaccard(a, b):
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _best_match(tx_saon, tx_paon, tx_street, tx_date, epc_certs):
    """Find best EPC cert for a transaction. Returns (cert_row, match_score) or (None, None)."""
    tx_addr = _normalise_addr(" ".join(p for p in [tx_saon, tx_paon, tx_street] if p))
    if not tx_addr:
        return None, None

    candidates = []
    for c in epc_certs:
        epc_addr = _normalise_addr(
            " ".join(p for p in [c["address1"], c["address2"], c["address3"]] if p)
        )
        if not epc_addr:
            continue
        score = _jaccard(tx_addr, epc_addr)
        if score >= 0.5:
            candidates.append((score, c))

    if not candidates:
        return None, None

    if isinstance(tx_date, str):
        tx_date = dt_date.fromisoformat(tx_date)

    best = None
    best_score = None
    best_tiebreak = (-1, None)

    for score, c in candidates:
        ld = c["lodgement_date"]
        if ld is None:
            continue
        if isinstance(ld, str):
            ld = dt_date.fromisoformat(ld)
        before = ld <= tx_date
        days_diff = abs((tx_date - ld).days)
        tiebreak = (score, before, -days_diff)
        if best is None or tiebreak > best_tiebreak:
            best = c
            best_score = score
            best_tiebreak = tiebreak

    return best, best_score


def match_and_update(conn):
    """Jaccard-match unmatched transactions against EPC, UPDATE master table directly."""
    print("\n=== Phase 2: Matching & updating ===", flush=True)
    t_start = time.time()

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get postcodes that have BOTH: unmatched transactions AND EPC certs
    print("  Building postcode work list...", flush=True)
    cur.execute(f"""
        SELECT DISTINCT t.postcode
        FROM {TXN_TABLE} t
        WHERE t.postcode IS NOT NULL
          AND t.floor_area_sqm IS NULL
          AND EXISTS (
              SELECT 1 FROM {EPC_TABLE} e WHERE e.postcode = t.postcode
          )
        ORDER BY t.postcode
    """)
    postcodes = [r["postcode"] for r in cur.fetchall()]
    print(f"  {len(postcodes):,} postcodes with unmatched transactions + EPC data", flush=True)

    total_matched = 0
    total_updated = 0

    # Use a plain cursor for UPDATEs (faster than RealDictCursor)
    update_cur = conn.cursor()

    for batch_start in range(0, len(postcodes), MATCH_BATCH):
        batch = postcodes[batch_start: batch_start + MATCH_BATCH]

        # Load EPC certs for this batch
        cur.execute(f"""
            SELECT certificate_number, address1, address2, address3, postcode,
                   lodgement_date, total_floor_area, habitable_rooms, current_energy_rating
            FROM {EPC_TABLE}
            WHERE postcode = ANY(%s)
        """, (batch,))
        epc_by_pc = {}
        for row in cur.fetchall():
            pc = row["postcode"]
            if pc not in epc_by_pc:
                epc_by_pc[pc] = []
            epc_by_pc[pc].append(dict(row))

        # Load unmatched transactions for this batch
        cur.execute(f"""
            SELECT transaction_id, postcode, saon, paon, street, date_of_transfer
            FROM {TXN_TABLE}
            WHERE postcode = ANY(%s)
              AND floor_area_sqm IS NULL
        """, (batch,))
        tx_rows = cur.fetchall()

        # Match and collect UPDATEs
        updates = []
        for tx in tx_rows:
            pc = tx["postcode"]
            certs = epc_by_pc.get(pc, [])
            if not certs:
                continue

            best, score = _best_match(
                tx["saon"] or "", tx["paon"] or "", tx["street"] or "",
                tx["date_of_transfer"], certs,
            )
            if best is None:
                continue

            habitable = best.get("habitable_rooms")
            habitable = int(habitable) if habitable is not None else None
            bedrooms = max(0, habitable - 1) if habitable is not None else None
            floor_area = best.get("total_floor_area")
            floor_area = float(floor_area) if floor_area is not None else None

            if floor_area is None or floor_area <= 0:
                continue

            price_per_sqm = None
            price_per_sqft = None
            # We don't have price in this query, so we'll compute it in a final pass
            # Actually let's include price — simpler to do it here

            updates.append((
                best["certificate_number"],
                round(score, 3),
                floor_area,
                habitable,
                bedrooms,
                (best.get("current_energy_rating") or "")[:1] or None,
                tx["transaction_id"],
            ))

        if updates:
            psycopg2.extras.execute_batch(
                update_cur,
                f"""
                UPDATE {TXN_TABLE}
                SET epc_certificate_number = %s,
                    epc_match_score        = %s,
                    floor_area_sqm         = %s,
                    habitable_rooms        = %s,
                    bedrooms_estimated     = %s,
                    epc_rating             = %s,
                    price_per_sqm          = CASE WHEN %s > 0 THEN price::float / %s ELSE NULL END,
                    price_per_sqft         = CASE WHEN %s > 0 THEN price::float / (%s * 10.7639) ELSE NULL END
                WHERE transaction_id = %s
                """,
                [
                    (cert, score, fa, hab, bed, rating, fa, fa, fa, fa, tid)
                    for cert, score, fa, hab, bed, rating, tid in updates
                ],
                page_size=500,
            )
            total_matched += len(updates)

        conn.commit()

        done = min(batch_start + len(batch), len(postcodes))
        if (batch_start // MATCH_BATCH) % 50 == 0 or done == len(postcodes):
            elapsed = time.time() - t_start
            rate = done / elapsed if elapsed > 0 else 0
            eta = (len(postcodes) - done) / rate if rate > 0 else 0
            print(f"    {done:,}/{len(postcodes):,} postcodes "
                  f"({total_matched:,} matched, {elapsed:.0f}s, ETA {eta:.0f}s)", flush=True)

    update_cur.close()
    cur.close()
    print(f"  Done: {total_matched:,} transactions matched ({time.time() - t_start:.0f}s)", flush=True)
    return total_matched


# ---------------------------------------------------------------------------
# Phase 3: Verify
# ---------------------------------------------------------------------------

def verify(conn):
    """Show floor_area_sqm coverage by year."""
    print("\n=== Phase 3: Verification ===", flush=True)
    cur = conn.cursor()
    cur.execute(f"""
        SELECT
            EXTRACT(YEAR FROM date_of_transfer) AS yr,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE floor_area_sqm > 0) AS with_area,
            ROUND(100.0 * COUNT(*) FILTER (WHERE floor_area_sqm > 0) / NULLIF(COUNT(*), 0), 1) AS pct
        FROM {TXN_TABLE}
        WHERE date_of_transfer >= '2015-01-01'
        GROUP BY 1 ORDER BY 1
    """)
    print(f"  {'Year':>6} {'Total':>10} {'With Area':>10} {'Coverage':>8}")
    print(f"  {'----':>6} {'-----':>10} {'---------':>10} {'--------':>8}")
    for row in cur.fetchall():
        print(f"  {int(row[0]):>6} {row[1]:>10,} {row[2]:>10,} {row[3]:>7.1f}%")
    cur.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    skip_load = "--skip-load" in sys.argv

    conn = psycopg2.connect(DSN)
    conn.autocommit = False

    try:
        if skip_load:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {EPC_TABLE}")
            epc_count = cur.fetchone()[0]
            cur.close()
            print(f"Skipping Phase 1: {EPC_TABLE} already has {epc_count:,} rows")
        else:
            zip_path = os.environ.get("EPC_ZIP_PATH", "/Users/batty/Downloads/all-domestic-certificates.zip")
            if not os.path.exists(zip_path):
                print(f"ERROR: EPC ZIP not found at {zip_path}", file=sys.stderr)
                sys.exit(1)
            print(f"EPC ZIP: {zip_path} ({os.path.getsize(zip_path) / 1e9:.1f} GB)")
            epc_count = load_epc(conn, zip_path)

        matched = match_and_update(conn)
        verify(conn)
    finally:
        conn.close()

    print(f"\n=== Complete: {epc_count:,} EPC certs loaded, {matched:,} transactions matched ===")


if __name__ == "__main__":
    main()
