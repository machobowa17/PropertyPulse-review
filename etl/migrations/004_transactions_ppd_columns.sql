-- Add missing PPD columns to core_property_transactions
-- These are columns 13-15 of the Land Registry pp-complete.csv that were
-- not included in the original partial (2024-2025) import.
ALTER TABLE core_property_transactions ADD COLUMN IF NOT EXISTS district TEXT;
ALTER TABLE core_property_transactions ADD COLUMN IF NOT EXISTS county TEXT;
ALTER TABLE core_property_transactions ADD COLUMN IF NOT EXISTS ppd_category CHAR(1);

-- Composite index for LAD-level historical price queries
CREATE INDEX IF NOT EXISTS idx_transactions_lsoa_date_type
    ON core_property_transactions (lsoa_code, date_of_transfer, property_type);
