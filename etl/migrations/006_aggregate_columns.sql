-- Step 3: Pre-computed aggregate columns on core_property_transactions
-- Per architecture.md: denormalized per row, same value for all rows in
-- the same (lsoa_code, month, property_type) group.
-- After populating, the 6 old price tables can be dropped.

ALTER TABLE core_property_transactions
    ADD COLUMN IF NOT EXISTS lsoa_month_avg_price          FLOAT,
    ADD COLUMN IF NOT EXISTS lsoa_month_median_price       FLOAT,
    ADD COLUMN IF NOT EXISTS lsoa_month_min_price          INTEGER,
    ADD COLUMN IF NOT EXISTS lsoa_month_max_price          INTEGER,
    ADD COLUMN IF NOT EXISTS lsoa_month_transaction_count  INTEGER,
    ADD COLUMN IF NOT EXISTS lsoa_month_new_build_count    INTEGER,
    ADD COLUMN IF NOT EXISTS lsoa_month_freehold_count     INTEGER,
    ADD COLUMN IF NOT EXISTS lsoa_month_leasehold_count    INTEGER,
    ADD COLUMN IF NOT EXISTS lsoa_month_avg_freehold_price FLOAT,
    ADD COLUMN IF NOT EXISTS lsoa_month_avg_leasehold_price FLOAT,
    ADD COLUMN IF NOT EXISTS lsoa_month_avg_ppsm           FLOAT,
    ADD COLUMN IF NOT EXISTS lsoa_month_avg_ppsft          FLOAT;
