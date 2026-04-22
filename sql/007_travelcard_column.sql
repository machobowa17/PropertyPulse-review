-- Add is_travelcard flag and zone label for TfL Travelcard prices
ALTER TABLE core_station_destinations
  ADD COLUMN IF NOT EXISTS is_travelcard BOOLEAN DEFAULT FALSE;

ALTER TABLE core_station_destinations
  ADD COLUMN IF NOT EXISTS travelcard_zones TEXT;
