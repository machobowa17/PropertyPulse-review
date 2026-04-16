#!/usr/bin/env python3
"""
Batch EPC→Transaction matching using SQL TRANSLATE normalization.

Strategy:
  1. Get all postcodes with BOTH unmatched transactions AND EPC certs with floor area.
  2. For each batch of postcodes (500 at a time):
     a. CTE normalises addresses (TRANSLATE strips non-alnum) on both sides
     b. JOIN on (postcode, norm_addr) — uses postcode index, norm match is per-postcode
     c. DISTINCT ON picks best EPC cert (prefer lodgement before transfer, closest date)
     d. UPDATE core_property_transactions with matched data
  3. Commit each batch — safe to resume.

Usage:
    python3 backfill_epc_matching.py
    python3 backfill_epc_matching.py --dry-run    # SELECT only, no UPDATE
"""

import os
import sys
import time
import psycopg2
import psycopg2.extras

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
BATCH_SIZE = 2000  # postcodes per batch


def main():
    dry_run = "--dry-run" in sys.argv

    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    cur = conn.cursor()

    # Step 1: Get work list — postcodes with unmatched txns AND EPC certs with floor area
    print("Building postcode work list...", flush=True)
    t0 = time.time()
    cur.execute("""
        SELECT DISTINCT t.postcode
        FROM core_property_transactions t
        WHERE t.floor_area_sqm IS NULL
          AND t.postcode IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM core_epc_domestic e
              WHERE e.postcode = t.postcode AND e.total_floor_area > 0
          )
        ORDER BY t.postcode
    """)
    postcodes = [r[0] for r in cur.fetchall()]
    conn.rollback()  # close read transaction
    print(f"  {len(postcodes):,} postcodes to process ({time.time()-t0:.1f}s)", flush=True)

    if not postcodes:
        print("Nothing to do.")
        conn.close()
        return

    # Step 2: Process in batches
    total_matched = 0
    t_start = time.time()

    # The TRANSLATE string removes: space, hyphen, period, comma, slash, semicolon,
    # colon, apostrophe, hash, parens, ampersand, at, underscore, double-quote, backslash
    # This covers all common address punctuation
    STRIP_CHARS = " -.,/;:'#()&@_" + '"' + "\\"

    for batch_start in range(0, len(postcodes), BATCH_SIZE):
        batch = postcodes[batch_start: batch_start + BATCH_SIZE]

        if dry_run:
            # Just count matches
            cur.execute("""
                WITH txn AS (
                    SELECT transaction_id, postcode, date_of_transfer, price,
                           TRANSLATE(
                               UPPER(COALESCE(NULLIF(saon,'N'),'')||COALESCE(paon,'')||COALESCE(street,'')),
                               %s, ''
                           ) AS norm
                    FROM core_property_transactions
                    WHERE floor_area_sqm IS NULL AND postcode = ANY(%s)
                ),
                epc AS (
                    SELECT certificate_number, postcode, lodgement_date, total_floor_area,
                           habitable_rooms, current_energy_rating,
                           TRANSLATE(
                               UPPER(COALESCE(address1,'')||COALESCE(address2,'')||COALESCE(address3,'')),
                               %s, ''
                           ) AS norm
                    FROM core_epc_domestic
                    WHERE total_floor_area > 0 AND postcode = ANY(%s)
                )
                SELECT COUNT(*)
                FROM (
                    SELECT DISTINCT ON (txn.transaction_id)
                        txn.transaction_id
                    FROM txn
                    JOIN epc ON epc.postcode = txn.postcode AND epc.norm = txn.norm
                    WHERE txn.norm <> '' AND epc.norm <> ''
                    ORDER BY txn.transaction_id,
                             (epc.lodgement_date <= txn.date_of_transfer)::int DESC,
                             ABS(txn.date_of_transfer - epc.lodgement_date)
                ) sub
            """, (STRIP_CHARS, batch, STRIP_CHARS, batch))
            count = cur.fetchone()[0]
            total_matched += count
            conn.rollback()
        else:
            # Real UPDATE
            cur.execute("""
                WITH txn AS (
                    SELECT transaction_id, postcode, date_of_transfer, price,
                           TRANSLATE(
                               UPPER(COALESCE(NULLIF(saon,'N'),'')||COALESCE(paon,'')||COALESCE(street,'')),
                               %s, ''
                           ) AS norm
                    FROM core_property_transactions
                    WHERE floor_area_sqm IS NULL AND postcode = ANY(%s)
                ),
                epc AS (
                    SELECT certificate_number, postcode, lodgement_date, total_floor_area,
                           habitable_rooms, current_energy_rating,
                           TRANSLATE(
                               UPPER(COALESCE(address1,'')||COALESCE(address2,'')||COALESCE(address3,'')),
                               %s, ''
                           ) AS norm
                    FROM core_epc_domestic
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
                UPDATE core_property_transactions t
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
            """, (STRIP_CHARS, batch, STRIP_CHARS, batch))
            count = cur.rowcount
            total_matched += count
            conn.commit()

        done = min(batch_start + len(batch), len(postcodes))
        elapsed = time.time() - t_start
        rate = done / elapsed if elapsed > 0 else 0
        eta = (len(postcodes) - done) / rate if rate > 0 else 0

        if (batch_start // BATCH_SIZE) % 10 == 0 or done == len(postcodes):
            print(f"  {done:,}/{len(postcodes):,} postcodes  "
                  f"{total_matched:,} matched  "
                  f"{elapsed:.0f}s  ETA {eta:.0f}s",
                  flush=True)

    cur.close()

    # Step 3: Verify
    print("\n=== Verification ===", flush=True)
    cur = conn.cursor()
    cur.execute("""
        SELECT
            EXTRACT(YEAR FROM date_of_transfer)::int AS yr,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE floor_area_sqm > 0) AS with_area,
            ROUND(100.0 * COUNT(*) FILTER (WHERE floor_area_sqm > 0) / NULLIF(COUNT(*), 0), 1) AS pct
        FROM core_property_transactions
        WHERE date_of_transfer >= '2010-01-01'
        GROUP BY 1 ORDER BY 1
    """)
    print(f"  {'Year':>6} {'Total':>10} {'With Area':>10} {'Coverage':>8}")
    print(f"  {'----':>6} {'-----':>10} {'---------':>10} {'--------':>8}")
    for row in cur.fetchall():
        print(f"  {row[0]:>6} {row[1]:>10,} {row[2]:>10,} {row[3]:>7.1f}%")

    cur.close()
    conn.close()

    elapsed = time.time() - t_start
    print(f"\n{'DRY RUN ' if dry_run else ''}Complete: {total_matched:,} transactions matched in {elapsed:.0f}s")


if __name__ == "__main__":
    main()
