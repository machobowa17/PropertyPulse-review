-- Migration: Add TfL Journey Planner detail columns to core_station_destinations
-- Supports multi-modal journey data (legs, modes, fares, interchanges).

ALTER TABLE core_station_destinations
  ADD COLUMN IF NOT EXISTS journey_type TEXT DEFAULT 'direct',
  ADD COLUMN IF NOT EXISTS num_changes SMALLINT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS modes TEXT[],
  ADD COLUMN IF NOT EXISTS peak_fare_pence INTEGER,
  ADD COLUMN IF NOT EXISTS offpeak_fare_pence INTEGER,
  ADD COLUMN IF NOT EXISTS fare_zones TEXT,
  ADD COLUMN IF NOT EXISTS legs JSONB,
  ADD COLUMN IF NOT EXISTS fare_caveats TEXT[];
