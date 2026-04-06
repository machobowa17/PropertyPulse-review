#!/usr/bin/env python3
"""
Step 3, Option B: Rebuild core_property_transactions with aggregate columns.

Creates a new table with pre-computed lsoa_month_* aggregates joined in,
then swaps it for the original. Avoids 29M-row UPDATE entirely.

Estimated: ~15 min table creation + ~45 min index rebuilds = ~1 hour.
Disk: needs ~10 GB for new table while old (~7 GB data) still exists.
"""
import psycopg2
import time
import sys

DSN = "dbname=ukproperty user=postgres"

def step(msg):
    print(f"\n{'='*60}\n  {msg}\n{'='*60}", flush=True)
    return time.time()

def done(t0, detail=""):
    s = f"   {time.time() - t0:.1f}s"
    if detail:
        s += f" — {detail}"
    print(s, flush=True)

def main():
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET maintenance_work_mem = '2GB'")
    cur.execute("SET work_mem = '512MB'")

    # ── 1. Verify current table ──────────────────────────────────
    t0 = step("1/7  Verify current table")
    cur.execute("SELECT COUNT(*) FROM core_property_transactions")
    original_count = cur.fetchone()[0]
    print(f"   {original_count:,} rows")
    if original_count < 28_000_000:
        sys.exit("ABORT: expected ~29M rows")

    # Get base columns (exclude lsoa_month_* — we'll replace them)
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'core_property_transactions'
          AND column_name NOT LIKE 'lsoa_month_%%'
        ORDER BY ordinal_position
    """)
    base_cols = [r[0] for r in cur.fetchall()]
    print(f"   {len(base_cols)} base columns + 12 aggregate columns to add")
    done(t0)

    # ── 2. Compute aggregates ────────────────────────────────────
    t0 = step("2/7  Compute aggregates (GROUP BY lsoa, month, type)")
    cur.execute("DROP TABLE IF EXISTS _tx_agg")
    cur.execute("""
        CREATE UNLOGGED TABLE _tx_agg AS
        SELECT
            lsoa_code,
            date_trunc('month', date_of_transfer)  AS month,
            property_type,
            AVG(price)::float                       AS avg_price,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price)::float AS median_price,
            MIN(price)::integer                     AS min_price,
            MAX(price)::integer                     AS max_price,
            COUNT(*)::integer                       AS transaction_count,
            COUNT(*) FILTER (WHERE old_new = 'Y')::integer  AS new_build_count,
            COUNT(*) FILTER (WHERE duration = 'F')::integer AS freehold_count,
            COUNT(*) FILTER (WHERE duration = 'L')::integer AS leasehold_count,
            AVG(price) FILTER (WHERE duration = 'F')::float AS avg_freehold_price,
            AVG(price) FILTER (WHERE duration = 'L')::float AS avg_leasehold_price,
            AVG(price::float / floor_area_sqm)
                FILTER (WHERE floor_area_sqm > 0)   AS avg_ppsm,
            AVG(price::float / (floor_area_sqm * 10.7639))
                FILTER (WHERE floor_area_sqm > 0)   AS avg_ppsft
        FROM core_property_transactions
        GROUP BY lsoa_code, date_trunc('month', date_of_transfer), property_type
    """)
    cur.execute("SELECT COUNT(*) FROM _tx_agg")
    agg_count = cur.fetchone()[0]
    print(f"   {agg_count:,} groups")
    done(t0)

    print("   Indexing temp table...", flush=True)
    t1 = time.time()
    cur.execute("CREATE INDEX ON _tx_agg (lsoa_code, month, property_type)")
    done(t1, "indexed")

    # ── 3. Build new table ───────────────────────────────────────
    t0 = step("3/7  Build new table (SELECT ... LEFT JOIN aggregates)")
    cur.execute("DROP TABLE IF EXISTS core_property_transactions_new")
    col_list = ", ".join(f"t.{c}" for c in base_cols)
    cur.execute(f"""
        CREATE TABLE core_property_transactions_new AS
        SELECT
            {col_list},
            agg.avg_price           AS lsoa_month_avg_price,
            agg.median_price        AS lsoa_month_median_price,
            agg.min_price           AS lsoa_month_min_price,
            agg.max_price           AS lsoa_month_max_price,
            agg.transaction_count   AS lsoa_month_transaction_count,
            agg.new_build_count     AS lsoa_month_new_build_count,
            agg.freehold_count      AS lsoa_month_freehold_count,
            agg.leasehold_count     AS lsoa_month_leasehold_count,
            agg.avg_freehold_price  AS lsoa_month_avg_freehold_price,
            agg.avg_leasehold_price AS lsoa_month_avg_leasehold_price,
            agg.avg_ppsm            AS lsoa_month_avg_ppsm,
            agg.avg_ppsft           AS lsoa_month_avg_ppsft
        FROM core_property_transactions t
        LEFT JOIN _tx_agg agg
            ON  t.lsoa_code = agg.lsoa_code
            AND date_trunc('month', t.date_of_transfer) = agg.month
            AND t.property_type = agg.property_type
    """)
    cur.execute("SELECT COUNT(*) FROM core_property_transactions_new")
    new_count = cur.fetchone()[0]
    print(f"   {new_count:,} rows")
    done(t0)

    if new_count != original_count:
        sys.exit(f"ABORT: count mismatch! old={original_count:,} new={new_count:,}")

    # ── 4. Swap tables ───────────────────────────────────────────
    t0 = step("4/7  Swap tables (rename old → drop, rename new → live)")
    cur.execute("ALTER TABLE core_property_transactions RENAME TO core_property_transactions_old")
    cur.execute("ALTER TABLE core_property_transactions_new RENAME TO core_property_transactions")
    cur.execute("DROP TABLE core_property_transactions_old")
    cur.execute("DROP TABLE IF EXISTS _tx_agg")
    done(t0, "swapped + old table dropped")

    # ── 5. Primary key ───────────────────────────────────────────
    t0 = step("5/7  Rebuild primary key")
    cur.execute("ALTER TABLE core_property_transactions ADD PRIMARY KEY (transaction_id)")
    done(t0)

    # ── 6. Rebuild indexes ───────────────────────────────────────
    t0 = step("6/7  Rebuild indexes")
    indexes = [
        ("idx_transactions_date",
         "CREATE INDEX idx_transactions_date ON core_property_transactions (date_of_transfer)"),
        ("idx_transactions_lad",
         "CREATE INDEX idx_transactions_lad ON core_property_transactions (lad_code)"),
        ("idx_transactions_postcode",
         "CREATE INDEX idx_transactions_postcode ON core_property_transactions (postcode)"),
        ("idx_transactions_lsoa_date_type",
         "CREATE INDEX idx_transactions_lsoa_date_type ON core_property_transactions (lsoa_code, date_of_transfer, property_type)"),
        ("idx_transactions_floor_area",
         "CREATE INDEX idx_transactions_floor_area ON core_property_transactions (floor_area_sqm) WHERE floor_area_sqm IS NOT NULL AND floor_area_sqm > 0"),
        ("idx_transactions_geom",
         "CREATE INDEX idx_transactions_geom ON core_property_transactions USING GIST (geom)"),
        ("idx_transactions_geom_geog",
         "CREATE INDEX idx_transactions_geom_geog ON core_property_transactions USING GIST ((geom::geography))"),
    ]
    for name, sql in indexes:
        t1 = time.time()
        print(f"   {name}...", end=" ", flush=True)
        cur.execute(sql)
        print(f"{time.time()-t1:.1f}s", flush=True)
    done(t0, "all indexes built")

    # ── 7. Verify ────────────────────────────────────────────────
    t0 = step("7/7  Final verification")
    cur.execute("SELECT COUNT(*) FROM core_property_transactions")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM core_property_transactions WHERE lsoa_month_avg_price IS NOT NULL")
    populated = cur.fetchone()[0]
    cur.execute("""
        SELECT pg_size_pretty(pg_relation_size('core_property_transactions')) AS data,
               pg_size_pretty(pg_total_relation_size('core_property_transactions')) AS total
    """)
    data_sz, total_sz = cur.fetchone()
    print(f"   {total:,} rows total")
    print(f"   {populated:,} rows with aggregates ({100*populated/total:.1f}%)")
    print(f"   Size: {data_sz} data, {total_sz} with indexes")

    # Spot check
    cur.execute("""
        SELECT lsoa_month_avg_price, lsoa_month_median_price,
               lsoa_month_transaction_count, lsoa_month_avg_ppsft
        FROM core_property_transactions
        WHERE lsoa_month_avg_price IS NOT NULL
        LIMIT 1
    """)
    row = cur.fetchone()
    print(f"   Sample: avg={row[0]:.0f} median={row[1]:.0f} txns={row[2]} ppsft={row[3]}")
    done(t0)

    # Record migration version
    cur.execute("INSERT INTO schema_migrations (version) VALUES (6) ON CONFLICT DO NOTHING")

    conn.close()
    print(f"\n  DONE. Table rebuilt with 12 aggregate columns.\n")

if __name__ == "__main__":
    main()
