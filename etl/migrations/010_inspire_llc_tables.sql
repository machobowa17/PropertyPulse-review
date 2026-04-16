-- 010_inspire_llc_tables.sql
-- INSPIRE Cadastral Parcels + HM Land Registry Local Land Charges tables

-- ============================================================
-- INSPIRE Index Polygons (Cadastral Parcels)
-- Source: Land Registry INSPIRE WFS per-authority GML downloads
-- 24.3M parcels across 318 authorities, EPSG:27700 → 4326
-- ============================================================

CREATE TABLE IF NOT EXISTS core_inspire_parcels (
    inspire_id          TEXT        NOT NULL,
    authority           TEXT        NOT NULL,
    geom                GEOMETRY(Geometry, 4326) NOT NULL,
    valid_from          TIMESTAMPTZ,
    begin_lifespan      TIMESTAMPTZ,
    PRIMARY KEY (inspire_id)
);

CREATE INDEX IF NOT EXISTS idx_inspire_parcels_geom
    ON core_inspire_parcels USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_inspire_parcels_authority
    ON core_inspire_parcels (authority);

-- ============================================================
-- Local Land Charges (LLC)
-- Source: HM Land Registry LLC WFS per-authority GML downloads
-- 8.3M features across 141 authorities, 4 charge types
-- ============================================================

CREATE TABLE IF NOT EXISTS core_llc_charges (
    id                  SERIAL      PRIMARY KEY,
    inspire_id          TEXT,
    authority           TEXT        NOT NULL,
    charge_type         TEXT        NOT NULL,   -- LU_Residential, LU_Forestry, Protected_Sites, Area_Management
    geom                GEOMETRY(Geometry, 4326) NOT NULL,
    valid_from          TIMESTAMPTZ,
    begin_lifespan      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_llc_charges_geom
    ON core_llc_charges USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_llc_charges_authority
    ON core_llc_charges (authority);

CREATE INDEX IF NOT EXISTS idx_llc_charges_type
    ON core_llc_charges (charge_type);

CREATE INDEX IF NOT EXISTS idx_llc_charges_inspire_id
    ON core_llc_charges (inspire_id);
