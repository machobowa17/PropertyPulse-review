-- Add lad_code to core_property_transactions for faster LAD-level filtering
ALTER TABLE core_property_transactions ADD COLUMN IF NOT EXISTS lad_code TEXT;
CREATE INDEX IF NOT EXISTS idx_transactions_lad ON core_property_transactions (lad_code);
