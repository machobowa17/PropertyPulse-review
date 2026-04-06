-- Step 2 (continued): Populate EPC columns from core_transactions_epc
-- Run AFTER migration 005 is applied and Step 1 ingest is verified.
-- This copies data from the join table into the master, then the join table can be DROPped.
--
-- Expected: ~1.5M rows updated out of ~30M (only 2024-2025 transactions have EPC matches currently).
-- After the full EPC re-ingest (lower priority queue), run the derived/transactions_epc.py
-- module to match older transactions too.
--
-- Elapsed: expect ~5-10 minutes for 30M row scan + 1.5M updates.

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
WHERE t.transaction_id = te.transaction_id;

-- Verify: should show ~1,495,509
SELECT COUNT(*) AS epc_matched FROM core_property_transactions
WHERE floor_area_sqm IS NOT NULL;

-- If count looks right, run:
-- DROP TABLE core_transactions_epc;
