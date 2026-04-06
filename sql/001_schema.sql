-- UK Property Portal — Database Schema
-- Source: Build Bible Part 2, Section 2.1 (verbatim)

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- for fuzzy text search

-- ============================================================
-- GEO-RESOLUTION TABLES
-- ============================================================

-- Master postcode lookup (sourced from ONS ONSPD)
CREATE TABLE IF NOT EXISTS core_postcodes (
    postcode            TEXT PRIMARY KEY,
    postcode_compact    TEXT NOT NULL,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    geom                GEOMETRY(Point, 4326),
    lsoa_code           TEXT,
    lsoa_name           TEXT,
    msoa_code           TEXT,
    msoa_name           TEXT,
    ward_code           TEXT,
    ward_name           TEXT,
    lad_code            TEXT,
    lad_name            TEXT,
    county_code         TEXT,
    county_name         TEXT,
    region_code         TEXT,
    region_name         TEXT,
    nation              CHAR(1) DEFAULT 'E',
    is_active           BOOLEAN DEFAULT TRUE,
    last_updated        DATE DEFAULT CURRENT_DATE
);
CREATE INDEX IF NOT EXISTS idx_postcodes_geom ON core_postcodes USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_postcodes_lsoa ON core_postcodes (lsoa_code);
CREATE INDEX IF NOT EXISTS idx_postcodes_lad ON core_postcodes (lad_code);
CREATE INDEX IF NOT EXISTS idx_postcodes_compact ON core_postcodes (postcode_compact);
CREATE INDEX IF NOT EXISTS idx_postcodes_ward ON core_postcodes (ward_code);

-- LSOA boundary polygons
CREATE TABLE IF NOT EXISTS core_lsoa_boundaries (
    lsoa_code           TEXT PRIMARY KEY,
    lsoa_name           TEXT,
    msoa_code           TEXT,
    lad_code            TEXT,
    geom                GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_lsoa_geom ON core_lsoa_boundaries USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_lsoa_lad ON core_lsoa_boundaries (lad_code);

-- Ward boundary polygons
CREATE TABLE IF NOT EXISTS core_ward_boundaries (
    ward_code           TEXT PRIMARY KEY,
    ward_name           TEXT,
    lad_code            TEXT,
    geom                GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_ward_geom ON core_ward_boundaries USING GIST (geom);

-- LAD boundary polygons
CREATE TABLE IF NOT EXISTS core_lad_boundaries (
    lad_code            TEXT PRIMARY KEY,
    lad_name            TEXT,
    county_code         TEXT,
    county_name         TEXT,
    region_code         TEXT,
    region_name         TEXT,
    geom                GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_lad_geom ON core_lad_boundaries USING GIST (geom);

-- Place name alias table (Gazetteer)
CREATE TABLE IF NOT EXISTS core_place_names (
    id                  SERIAL PRIMARY KEY,
    place_name          TEXT NOT NULL,
    place_name_lower    TEXT NOT NULL,
    place_type          TEXT,
    lad_code            TEXT,
    ward_code           TEXT,
    postcode_prefix     TEXT,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    population          INTEGER
);
CREATE INDEX IF NOT EXISTS idx_place_trgm ON core_place_names USING GIN (place_name_lower gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_place_lad ON core_place_names (lad_code);

-- LAD-to-county/region lookup (for parent-level comparisons)
CREATE TABLE IF NOT EXISTS core_lad_county_lookup (
    lad_code            TEXT PRIMARY KEY,
    lad_name            TEXT,
    county_code         TEXT,
    county_name         TEXT,
    region_code         TEXT,
    region_name         TEXT,
    is_london_borough   BOOLEAN DEFAULT FALSE,
    is_metropolitan     BOOLEAN DEFAULT FALSE,
    parent_comparison   TEXT    -- the name used for parent comparison (e.g. 'Greater London')
);

-- ============================================================
-- CORE DATA TABLES (Land Registry)
-- ============================================================

-- DROPPED: core_property_prices_lsoa and core_property_prices_lad
-- Replaced by denormalized lsoa_month_* columns on core_property_transactions (migration 006).
-- See etl/migrations/006_lsoa_month_columns.sql for the replacement.
