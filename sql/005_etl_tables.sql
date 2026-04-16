-- 005_etl_tables.sql — Tables written by ETL (missing from 001-003)
--
-- These tables are created/populated by etl/sources/ and etl/derived/ modules
-- but had no corresponding DDL in the sql/ schema files.
-- Running this after 001-004 ensures a fresh deploy can accept ETL data.
--
-- NOTE: core_epc_domestic is omitted — its 93-column schema is dynamically
-- generated from MHCLG CSV headers in epc_domestic.py.  Re-ingest creates it.
-- NOTE: core_flood_lsoa is referenced in constants.py but no ETL code
-- currently populates it; included here for forward-compatibility.

-- ============================================================
-- GEOGRAPHIC & BOUNDARY EXTENSIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS core_county_boundaries (
    county_name     TEXT PRIMARY KEY,
    lad_count       INTEGER NOT NULL,
    geom            GEOMETRY(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_county_boundaries_geom ON core_county_boundaries USING GIST(geom);

CREATE TABLE IF NOT EXISTS core_place_boundaries (
    id               SERIAL PRIMARY KEY,
    osm_id           BIGINT UNIQUE NOT NULL,
    place_name       TEXT NOT NULL,
    place_name_lower TEXT NOT NULL,
    place_type       TEXT,
    lad_code         TEXT,
    geom             GEOMETRY(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_place_boundaries_name ON core_place_boundaries(place_name_lower);
CREATE INDEX IF NOT EXISTS idx_place_boundaries_geom ON core_place_boundaries USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_place_boundaries_lad  ON core_place_boundaries(lad_code);

-- ============================================================
-- LABOUR & EARNINGS
-- ============================================================

CREATE TABLE IF NOT EXISTS core_earnings_lad (
    lad_code                TEXT PRIMARY KEY,
    lad_name                TEXT,
    median_annual_earnings  NUMERIC(10,2)
);

-- ============================================================
-- CRIME
-- ============================================================

CREATE TABLE IF NOT EXISTS core_crime_lsoa (
    lsoa_code   TEXT    NOT NULL,
    month       DATE    NOT NULL,
    crime_type  TEXT    NOT NULL,
    crime_count INTEGER,
    PRIMARY KEY (lsoa_code, month, crime_type)
);
CREATE INDEX IF NOT EXISTS idx_crime_lsoa_lsoa  ON core_crime_lsoa(lsoa_code);
CREATE INDEX IF NOT EXISTS idx_crime_lsoa_month ON core_crime_lsoa(month);

-- ============================================================
-- CENSUS
-- ============================================================

CREATE TABLE IF NOT EXISTS core_census_lsoa (
    lsoa_code               TEXT PRIMARY KEY,
    -- Demographics
    total_population        INTEGER,
    population_density      NUMERIC(8,2),
    median_age              NUMERIC(4,1),
    pct_age_0_15            NUMERIC(5,2),
    pct_age_16_64           NUMERIC(5,2),
    pct_age_65_plus         NUMERIC(5,2),
    pct_families            NUMERIC(5,2),
    pct_singles             NUMERIC(5,2),
    pct_sharers             NUMERIC(5,2),
    -- Housing
    total_households        INTEGER,
    pct_owned               NUMERIC(5,2),
    pct_social_rent         NUMERIC(5,2),
    pct_private_rent        NUMERIC(5,2),
    pct_detached            NUMERIC(5,2),
    pct_semi                NUMERIC(5,2),
    pct_terraced            NUMERIC(5,2),
    pct_flat                NUMERIC(5,2),
    -- Household size
    total_hh                INTEGER,
    pct_1person             NUMERIC(5,2),
    pct_2person             NUMERIC(5,2),
    pct_3_4person           NUMERIC(5,2),
    pct_5plus               NUMERIC(5,2),
    -- Commute distance
    total_workers           INTEGER,
    pct_lt2km               NUMERIC(5,2),
    pct_2_10km              NUMERIC(5,2),
    pct_10_30km             NUMERIC(5,2),
    pct_30plus              NUMERIC(5,2),
    pct_wfh                 NUMERIC(5,2),
    -- Extras (Census TS packs)
    pct_good_health         NUMERIC(5,2),
    pct_economically_active NUMERIC(5,2),
    pct_degree              NUMERIC(5,2),
    pct_no_car              NUMERIC(5,2),
    pct_born_abroad         NUMERIC(5,2)
);

CREATE TABLE IF NOT EXISTS core_census_ethnicity_ward (
    ward_code   TEXT PRIMARY KEY,
    total_pop   BIGINT,
    pct_white   NUMERIC(5,2),
    pct_asian   NUMERIC(5,2),
    pct_black   NUMERIC(5,2),
    pct_mixed   NUMERIC(5,2),
    pct_other   NUMERIC(5,2)
);

-- ============================================================
-- BROADBAND & MOBILE
-- ============================================================

CREATE TABLE IF NOT EXISTS core_broadband_lad (
    lad_code          VARCHAR(10) PRIMARY KEY,
    lad_name          TEXT,
    avg_download_mbps NUMERIC(8,1),
    avg_upload_mbps   NUMERIC(8,1),
    full_fibre_pct    NUMERIC(5,1),
    superfast_pct     NUMERIC(5,1),
    gigabit_pct       NUMERIC(5,1),
    ultrafast_pct     NUMERIC(5,1)
);

CREATE TABLE IF NOT EXISTS core_mobile_coverage_lad (
    lad_code       TEXT PRIMARY KEY,
    lad_name       TEXT,
    pct_4g_outdoor NUMERIC(5,1),
    pct_4g_indoor  NUMERIC(5,1),
    pct_5g_outdoor NUMERIC(5,1)
);

-- ============================================================
-- TRANSPORT & CONNECTIVITY
-- ============================================================

CREATE TABLE IF NOT EXISTS core_ptal_lsoa (
    lsoa_code TEXT PRIMARY KEY,
    avg_ptai  NUMERIC(8,2),
    ptal_band TEXT
);

CREATE TABLE IF NOT EXISTS core_cycling_lsoa (
    lsoa_code    TEXT PRIMARY KEY,
    total_workers INTEGER,
    cycling_count INTEGER,
    pct_cycling   NUMERIC(5,2),
    wfh_count     INTEGER,
    pct_wfh       NUMERIC(5,2)
);

CREATE TABLE IF NOT EXISTS core_connectivity_lsoa (
    lsoa_code                           TEXT PRIMARY KEY,
    overall_score                       NUMERIC(5,2),
    overall_walking                     NUMERIC(5,2),
    overall_cycling                     NUMERIC(5,2),
    overall_public_transport            NUMERIC(5,2),
    overall_driving                     NUMERIC(5,2),
    employment_overall                  NUMERIC(5,2),
    education_overall                   NUMERIC(5,2),
    healthcare_overall                  NUMERIC(5,2),
    leisure_community_overall           NUMERIC(5,2),
    shopping_overall                    NUMERIC(5,2),
    residential_overall                 NUMERIC(5,2),
    business_public_transport           NUMERIC(5,2),
    education_public_transport          NUMERIC(5,2),
    healthcare_public_transport         NUMERIC(5,2),
    leisure_community_public_transport  NUMERIC(5,2),
    shopping_public_transport           NUMERIC(5,2),
    residential_public_transport        NUMERIC(5,2),
    source_release                      TEXT
);

-- ============================================================
-- AIR QUALITY (LAD aggregate)
-- ============================================================

CREATE TABLE IF NOT EXISTS core_air_quality_lad (
    lad_code  TEXT        NOT NULL,
    year      SMALLINT    NOT NULL,
    no2_ugm3  NUMERIC(8,2),
    pm25_ugm3 NUMERIC(8,2),
    pm10_ugm3 NUMERIC(8,2),
    PRIMARY KEY (lad_code, year)
);

-- ============================================================
-- FLOOD (LSOA aggregate — forward-compatibility)
-- ============================================================

CREATE TABLE IF NOT EXISTS core_flood_lsoa (
    lsoa_code TEXT PRIMARY KEY,
    in_zone_2 BOOLEAN DEFAULT FALSE,
    in_zone_3 BOOLEAN DEFAULT FALSE
);

-- ============================================================
-- GOVERNANCE
-- ============================================================

CREATE TABLE IF NOT EXISTS core_council_control_lad (
    lad_code          TEXT PRIMARY KEY,
    council_name      TEXT,
    controlling_party TEXT,
    majority_seats    INTEGER,
    total_seats       INTEGER
);

CREATE TABLE IF NOT EXISTS core_s114_notices (
    lad_code     TEXT PRIMARY KEY,
    council_name TEXT,
    notice_date  DATE
);

-- ============================================================
-- UTILITIES
-- ============================================================

CREATE TABLE IF NOT EXISTS core_water_company_lad (
    lad_code            TEXT PRIMARY KEY,
    water_company       TEXT,
    water_company_type  TEXT
);

-- ============================================================
-- PRICE PER SQM (derived from master table + EPC floor area)
-- ============================================================

CREATE TABLE IF NOT EXISTS core_price_sqm_lad (
    lad_code          TEXT PRIMARY KEY,
    avg_price_per_sqm NUMERIC(10,2),
    avg_ppsm_detached NUMERIC(10,2),
    avg_ppsm_semi     NUMERIC(10,2),
    avg_ppsm_terraced NUMERIC(10,2),
    avg_ppsm_flat     NUMERIC(10,2),
    transaction_count INTEGER
);

CREATE TABLE IF NOT EXISTS core_price_sqm_lsoa (
    lsoa_code         TEXT PRIMARY KEY,
    avg_price_per_sqm NUMERIC(10,2),
    avg_ppsm_detached NUMERIC(10,2),
    avg_ppsm_semi     NUMERIC(10,2),
    avg_ppsm_terraced NUMERIC(10,2),
    avg_ppsm_flat     NUMERIC(10,2),
    transaction_count INTEGER
);

CREATE TABLE IF NOT EXISTS core_price_by_bedrooms_lad (
    lad_code          TEXT     NOT NULL,
    year              SMALLINT NOT NULL,
    property_type     CHAR(1)  NOT NULL,
    bedrooms          SMALLINT NOT NULL,
    avg_price         INTEGER,
    transaction_count INTEGER,
    PRIMARY KEY (lad_code, year, property_type, bedrooms)
);

-- ============================================================
-- DERIVED SPATIAL TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS core_nhs_lsoa (
    lsoa_code        TEXT PRIMARY KEY,
    nhs_count_2km    INTEGER DEFAULT 0,
    gp_count_2km     INTEGER DEFAULT 0,
    hospital_count_2km  INTEGER DEFAULT 0,
    dentist_count_2km   INTEGER DEFAULT 0,
    pharmacy_count_2km  INTEGER DEFAULT 0,
    optician_count_2km  INTEGER DEFAULT 0,
    care_home_count_2km INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS core_lsoa_green_space (
    lsoa_code      TEXT PRIMARY KEY,
    nearest_park_m INTEGER,
    parks_1km      INTEGER,
    green_cover_pct NUMERIC(5,2),
    sports_rec_1km INTEGER
);

CREATE TABLE IF NOT EXISTS core_lsoa_transport (
    lsoa_code        TEXT PRIMARY KEY,
    nearest_station_m INTEGER
);

-- ============================================================
-- PLACE → LSOA MAPPINGS (derived from spatial joins)
-- ============================================================

CREATE TABLE IF NOT EXISTS core_place_lsoa_mapping (
    place_name TEXT NOT NULL,
    place_type TEXT,
    lad_code   TEXT,
    lsoa_code  TEXT NOT NULL,
    method     TEXT,
    PRIMARY KEY (lsoa_code, place_name, method)
);

CREATE TABLE IF NOT EXISTS core_place_lsoa_mapping_town (
    lsoa_code  TEXT PRIMARY KEY,
    lad_code   TEXT,
    place_name TEXT NOT NULL,
    place_type TEXT
);

-- Pre-computed ST_Union per (place_name, lad_code) — avoids on-the-fly ST_Union
-- under concurrent load on the /boundary endpoint.
-- Populated by the place_lsoa_mapping derived module.
CREATE TABLE IF NOT EXISTS core_place_boundaries_union (
    place_name TEXT NOT NULL,
    lad_code   TEXT NOT NULL,
    geom       geometry(Geometry, 4326),
    PRIMARY KEY (place_name, lad_code)
);
CREATE INDEX IF NOT EXISTS idx_place_boundaries_union ON core_place_boundaries_union USING GIST (geom);

-- ============================================================
-- PIPELINE AUDIT
-- ============================================================

CREATE TABLE IF NOT EXISTS core_pipeline_runs (
    id               SERIAL PRIMARY KEY,
    source_name      TEXT        NOT NULL,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ,
    status           TEXT        NOT NULL DEFAULT 'running'
                         CHECK (status IN ('running', 'success', 'failed', 'validation_failed')),
    rows_before      BIGINT,
    rows_after       BIGINT,
    source_url       TEXT,
    source_version   TEXT,
    validation_notes TEXT,
    error_msg        TEXT
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_source
    ON core_pipeline_runs(source_name, started_at DESC);
