-- Add index on dest_crs for reverse lookups and station-pair queries.
-- CONCURRENTLY avoids locking the table during creation.
CREATE INDEX CONCURRENTLY IF NOT EXISTS
    idx_station_destinations_dest_crs
    ON core_station_destinations (dest_crs);
