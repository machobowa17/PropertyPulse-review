-- Migration: core_station_destinations
-- Stores top commute destinations per National Rail station with journey time,
-- frequency, punctuality, and season ticket price.

CREATE TABLE IF NOT EXISTS core_station_destinations (
    origin_crs        TEXT NOT NULL,
    dest_crs          TEXT NOT NULL,
    dest_name         TEXT NOT NULL,
    journey_min       SMALLINT,
    trains_per_hour   NUMERIC(4,1),
    pct_on_time       NUMERIC(5,1),
    season_ticket_gbp NUMERIC(8,2),
    rank              SMALLINT NOT NULL,
    updated_at        TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (origin_crs, dest_crs)
);

CREATE INDEX IF NOT EXISTS idx_station_dest_origin ON core_station_destinations (origin_crs);
