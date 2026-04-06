-- Step 2: Absorb EPC data into core_property_transactions
-- Adds nullable EPC columns directly onto the master table.
-- After applying, run the UPDATE below (or the pipeline absorb step) to
-- populate from core_transactions_epc, then DROP core_transactions_epc.

ALTER TABLE core_property_transactions
    ADD COLUMN IF NOT EXISTS epc_certificate_number TEXT,
    ADD COLUMN IF NOT EXISTS epc_match_score        FLOAT,
    ADD COLUMN IF NOT EXISTS floor_area_sqm         FLOAT,
    ADD COLUMN IF NOT EXISTS habitable_rooms        INTEGER,
    ADD COLUMN IF NOT EXISTS bedrooms_estimated     INTEGER,
    ADD COLUMN IF NOT EXISTS epc_rating             CHAR(1),
    ADD COLUMN IF NOT EXISTS price_per_sqm          FLOAT,
    ADD COLUMN IF NOT EXISTS price_per_sqft         FLOAT;

-- Index on floor_area_sqm for WHERE floor_area_sqm > 0 filtering in avg_ppsf queries
CREATE INDEX IF NOT EXISTS idx_transactions_floor_area
    ON core_property_transactions (floor_area_sqm)
    WHERE floor_area_sqm IS NOT NULL AND floor_area_sqm > 0;
