-- Migration: Add NaPTAN + enrichment columns to core_transport_stops
-- Run on EC2 after deploying code changes

ALTER TABLE core_transport_stops
  ADD COLUMN IF NOT EXISTS short_name       TEXT,
  ADD COLUMN IF NOT EXISTS landmark         TEXT,
  ADD COLUMN IF NOT EXISTS street           TEXT,
  ADD COLUMN IF NOT EXISTS indicator        TEXT,
  ADD COLUMN IF NOT EXISTS locality_name    TEXT,
  ADD COLUMN IF NOT EXISTS parent_locality  TEXT,
  ADD COLUMN IF NOT EXISTS suburb           TEXT,
  ADD COLUMN IF NOT EXISTS status           TEXT,
  ADD COLUMN IF NOT EXISTS crs_code         TEXT,
  ADD COLUMN IF NOT EXISTS tiploc_code      TEXT,
  ADD COLUMN IF NOT EXISTS lines            TEXT,
  ADD COLUMN IF NOT EXISTS operator         TEXT,
  ADD COLUMN IF NOT EXISTS zone             TEXT,
  ADD COLUMN IF NOT EXISTS step_free        BOOLEAN,
  ADD COLUMN IF NOT EXISTS facilities       JSONB;

-- Index on CRS code for reverse lookups
CREATE INDEX IF NOT EXISTS idx_transport_crs ON core_transport_stops (crs_code) WHERE crs_code IS NOT NULL;
