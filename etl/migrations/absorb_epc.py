#!/usr/bin/env python3
"""
Absorb EPC data from core_transactions_epc into core_property_transactions.
Uses batched updates by PK to avoid 29M-row sequential scan.
Commits every BATCH_SIZE rows so progress is visible and disk-safe.
"""
import os
import psycopg2
import time
import sys

BATCH_SIZE = 10_000
DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")

def main():
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    cur = conn.cursor()

    # Get all transaction_ids from EPC table
    print("Loading EPC transaction IDs...")
    cur.execute("SELECT transaction_id FROM core_transactions_epc")
    all_ids = [r[0] for r in cur.fetchall()]
    total = len(all_ids)
    print(f"  {total:,} EPC records to absorb")
    conn.rollback()  # close read transaction

    done = 0
    t0 = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = all_ids[i : i + BATCH_SIZE]
        cur.execute("""
            UPDATE core_property_transactions t
            SET
                epc_certificate_number = te.certificate_number,
                epc_match_score        = te.match_score::float,
                floor_area_sqm         = te.total_floor_area::float,
                habitable_rooms        = te.number_habitable_rooms::integer,
                bedrooms_estimated     = te.bedrooms_estimated::integer,
                epc_rating             = te.current_energy_rating,
                price_per_sqm          = CASE
                                             WHEN te.total_floor_area > 0
                                             THEN t.price::float / te.total_floor_area::float
                                             ELSE NULL
                                         END,
                price_per_sqft         = CASE
                                             WHEN te.total_floor_area > 0
                                             THEN t.price::float / (te.total_floor_area::float * 10.7639)
                                             ELSE NULL
                                         END
            FROM core_transactions_epc te
            WHERE t.transaction_id = te.transaction_id
              AND t.transaction_id = ANY(%s)
        """, (batch,))
        conn.commit()
        done += len(batch)
        elapsed = time.time() - t0
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        print(f"  {done:>9,} / {total:,}  ({100*done/total:5.1f}%)  "
              f"{rate:,.0f} rows/s  ETA {eta:.0f}s", flush=True)

    elapsed = time.time() - t0
    print(f"\nDone: {done:,} rows absorbed in {elapsed:.1f}s")

    # Verify
    cur.execute("SELECT COUNT(*) FROM core_property_transactions WHERE floor_area_sqm IS NOT NULL")
    matched = cur.fetchone()[0]
    print(f"Verification: {matched:,} rows have floor_area_sqm")
    conn.close()

if __name__ == "__main__":
    main()
