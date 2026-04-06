-- UK Property Portal — Remaining Data Tables
-- Per Build Bible Part 3: Data Sources Registry
-- Per Build Bible Part 4: 5-Tab Information Architecture

-- ============================================================
-- TAB 1: PROPERTY & MARKET (additional tables)
-- ============================================================

-- ONS UK House Price Index (LAD level, monthly)
CREATE TABLE IF NOT EXISTS core_hpi_lad (
    lad_code            TEXT NOT NULL,
    date                DATE NOT NULL,
    average_price       NUMERIC(12,2),
    index_value         NUMERIC(8,2),
    sales_volume        INTEGER,
    detached_price      NUMERIC(12,2),
    semi_detached_price NUMERIC(12,2),
    terraced_price      NUMERIC(12,2),
    flat_price          NUMERIC(12,2),
    yearly_change_pct   NUMERIC(6,2),
    PRIMARY KEY (lad_code, date)
);

-- VOA Private Rental Market Statistics (LAD level)
CREATE TABLE IF NOT EXISTS core_voa_rents_lad (
    lad_code            TEXT NOT NULL,
    period              TEXT NOT NULL,
    median_rent_all     NUMERIC(8,2),
    median_rent_1bed    NUMERIC(8,2),
    median_rent_2bed    NUMERIC(8,2),
    median_rent_3bed    NUMERIC(8,2),
    median_rent_4bed    NUMERIC(8,2),
    PRIMARY KEY (lad_code, period)
);

-- ============================================================
-- TAB 2: LIFESTYLE & CONNECTIVITY
-- ============================================================

-- DfT NaPTAN Transport Stops
CREATE TABLE IF NOT EXISTS core_transport_stops (
    atco_code           TEXT PRIMARY KEY,
    stop_name           TEXT,
    stop_type           TEXT,        -- 'RSE' (rail), 'BCE' (bus), 'MET' (metro), etc.
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    geom                GEOMETRY(Point, 4326),
    lad_code            TEXT
);
CREATE INDEX IF NOT EXISTS idx_transport_geom ON core_transport_stops USING GIST (geom);

-- OZEV EV Chargepoints
CREATE TABLE IF NOT EXISTS core_ev_chargers (
    id                  SERIAL PRIMARY KEY,
    reference_id        TEXT,
    name                TEXT,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    geom                GEOMETRY(Point, 4326),
    connector_count     INTEGER,
    max_power_kw        NUMERIC(8,2),
    operator            TEXT
);
CREATE INDEX IF NOT EXISTS idx_ev_geom ON core_ev_chargers USING GIST (geom);

-- Ofcom Broadband Coverage (postcode level)
CREATE TABLE IF NOT EXISTS core_broadband_postcode (
    postcode            TEXT PRIMARY KEY,
    avg_download_mbps   NUMERIC(8,2),
    avg_upload_mbps     NUMERIC(8,2),
    superfast_pct       NUMERIC(5,2),
    ultrafast_pct       NUMERIC(5,2),
    gigabit_pct         NUMERIC(5,2),
    fttp_pct            NUMERIC(5,2)
);

-- OSM Amenities (15-Minute Neighbourhood) — per Bible Section 3.1
CREATE TABLE IF NOT EXISTS core_osm_amenities (
    id                  SERIAL PRIMARY KEY,
    osm_id              BIGINT,
    name                TEXT,
    amenity_type        TEXT NOT NULL,  -- supermarket, cafe, restaurant, pub, gym, park, pharmacy, dentist, hospital, doctors
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    geom                GEOMETRY(Point, 4326)
);
CREATE INDEX IF NOT EXISTS idx_osm_amenities_geom ON core_osm_amenities USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_osm_amenities_type ON core_osm_amenities (amenity_type);

-- ============================================================
-- TAB 3: ENVIRONMENT & SAFETY
-- ============================================================

-- Environment Agency Flood Zones 2 & 3
CREATE TABLE IF NOT EXISTS core_flood_zones (
    id                  SERIAL PRIMARY KEY,
    flood_zone          TEXT NOT NULL,   -- '2' or '3'
    geom                GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_flood_geom ON core_flood_zones USING GIST (geom);

-- Defra Air Quality (NO2, PM2.5 grid)
CREATE TABLE IF NOT EXISTS core_air_quality (
    id                  SERIAL PRIMARY KEY,
    grid_x              DOUBLE PRECISION,
    grid_y              DOUBLE PRECISION,
    geom                GEOMETRY(Point, 4326),
    no2_ugm3            NUMERIC(8,2),
    pm25_ugm3           NUMERIC(8,2),
    pm10_ugm3           NUMERIC(8,2),
    year                SMALLINT
);
CREATE INDEX IF NOT EXISTS idx_airqual_geom ON core_air_quality USING GIST (geom);

-- Defra Strategic Noise Mapping
CREATE TABLE IF NOT EXISTS core_noise (
    postcode            TEXT PRIMARY KEY,
    road_noise_db       NUMERIC(5,1),
    rail_noise_db       NUMERIC(5,1),
    air_noise_db        NUMERIC(5,1),
    noise_band          TEXT
);

-- Natural England Green Space
CREATE TABLE IF NOT EXISTS core_green_space (
    id                  SERIAL PRIMARY KEY,
    site_name           TEXT,
    site_type           TEXT,
    area_hectares       NUMERIC(12,2),
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    geom                GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_greenspace_geom ON core_green_space USING GIST (geom);

-- EPC Energy Performance (aggregated LSOA level)
CREATE TABLE IF NOT EXISTS core_epc_lsoa (
    lsoa_code           TEXT PRIMARY KEY,
    total_certs         INTEGER,
    avg_energy_score    NUMERIC(5,1),
    pct_rating_a_b      NUMERIC(5,2),
    pct_rating_c        NUMERIC(5,2),
    pct_rating_d        NUMERIC(5,2),
    pct_rating_e_g      NUMERIC(5,2),
    avg_co2_emissions   NUMERIC(8,2)
);

-- ============================================================
-- TAB 4: COMMUNITY & EDUCATION
-- ============================================================

-- DROPPED: core_census_demographics_lsoa and core_census_housing_lsoa
-- Replaced by consolidated core_census_lsoa wide table (migration 007).
-- See etl/migrations/007_census_lsoa_wide.sql for the replacement.

-- DfE Schools + Ofsted (per Bible Section 4, Tab 4)
CREATE TABLE IF NOT EXISTS core_schools (
    urn                 INTEGER PRIMARY KEY,
    school_name         TEXT,
    school_type         TEXT,
    phase               TEXT,           -- Primary, Secondary, All-through
    postcode            TEXT,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    geom                GEOMETRY(Point, 4326),
    lad_code            TEXT,
    ofsted_rating       TEXT,           -- Outstanding, Good, Requires Improvement, Inadequate
    ofsted_date         DATE,
    ks2_reading_pct     NUMERIC(5,2),
    ks2_maths_pct       NUMERIC(5,2),
    gcse_progress_8     NUMERIC(5,2),
    gcse_attainment_8   NUMERIC(5,2),
    is_open             BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_schools_geom ON core_schools USING GIST (geom);

-- IMD Deprivation (LSOA level) — per Bible Section 2.1
-- Already defined in 001_schema.sql conceptually, creating here with Bible columns
CREATE TABLE IF NOT EXISTS core_imd_lsoa (
    lsoa_code           TEXT PRIMARY KEY,
    imd_score           NUMERIC(8,4),
    imd_rank            INTEGER,
    imd_decile          SMALLINT,
    income_score        NUMERIC(8,4),
    employment_score    NUMERIC(8,4),
    education_score     NUMERIC(8,4),
    health_score        NUMERIC(8,4),
    crime_score         NUMERIC(8,4),
    barriers_score      NUMERIC(8,4),
    living_env_score    NUMERIC(8,4)
);

-- NHS Health Facilities
CREATE TABLE IF NOT EXISTS core_nhs_facilities (
    id                  SERIAL PRIMARY KEY,
    org_code            TEXT,
    name                TEXT,
    facility_type       TEXT,       -- GP, Hospital, Dentist, Pharmacy
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    geom                GEOMETRY(Point, 4326),
    postcode            TEXT
);
CREATE INDEX IF NOT EXISTS idx_nhs_geom ON core_nhs_facilities USING GIST (geom);

-- ============================================================
-- TAB 5: LOCAL GOVERNANCE
-- ============================================================

-- VOA Council Tax (LAD level)
CREATE TABLE IF NOT EXISTS core_council_tax_lad (
    lad_code            TEXT PRIMARY KEY,
    band_a              NUMERIC(8,2),
    band_b              NUMERIC(8,2),
    band_c              NUMERIC(8,2),
    band_d              NUMERIC(8,2),
    band_e              NUMERIC(8,2),
    band_f              NUMERIC(8,2),
    band_g              NUMERIC(8,2),
    band_h              NUMERIC(8,2)
);
