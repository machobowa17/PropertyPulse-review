-- 010_lad_materialized_views.sql
-- Pre-computed LAD-level aggregates for metrics that are too slow at county scale.
-- These eliminate spatial joins and large LSOA-array queries for LAD/county searches.
-- Refreshed as part of the ETL pipeline (etl/pipeline.py).

-- ============================================================
-- 1. Crime stats per LAD per month per type
--    ~315 LADs × 36 months × 15 types ≈ 170K rows
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_lad_crime_stats CASCADE;

CREATE MATERIALIZED VIEW mv_lad_crime_stats AS
SELECT
    lb.lad_code,
    c.month,
    c.crime_type,
    SUM(c.crime_count) AS crime_count
FROM core_crime_lsoa c
JOIN core_lsoa_boundaries lb ON lb.lsoa_code = c.lsoa_code
GROUP BY lb.lad_code, c.month, c.crime_type;

CREATE INDEX idx_mv_lad_crime_lad ON mv_lad_crime_stats(lad_code);
CREATE INDEX idx_mv_lad_crime_lad_month ON mv_lad_crime_stats(lad_code, month);


-- ============================================================
-- 2. Amenity counts per LAD per amenity type
--    ~315 LADs × 10 types ≈ 3,150 rows
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_lad_amenity_counts CASCADE;

CREATE MATERIALIZED VIEW mv_lad_amenity_counts AS
SELECT
    l.lad_code,
    a.amenity_type,
    COUNT(*) AS cnt
FROM core_osm_amenities a
JOIN core_lad_boundaries l ON ST_Intersects(a.geom, l.geom)
WHERE a.amenity_type IS NOT NULL
GROUP BY l.lad_code, a.amenity_type;

CREATE INDEX idx_mv_lad_amenity_lad ON mv_lad_amenity_counts(lad_code);


-- ============================================================
-- 3. Transport mode counts per LAD
--    ~315 LADs × 7 categories ≈ 2,200 rows
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_lad_transport_mode_counts CASCADE;

CREATE MATERIALIZED VIEW mv_lad_transport_mode_counts AS
SELECT
    lb.lad_code,
    cat,
    SUM(cnt) AS cnt
FROM (
    SELECT
        lb.lad_code,
        CASE
            WHEN t.stop_type IN ('RSE','RLY','RPL') THEN 'rail'
            WHEN t.atco_code LIKE '%ZZLU%'          THEN 'underground'
            WHEN t.atco_code LIKE '%ZZDL%'          THEN 'dlr'
            WHEN t.atco_code LIKE '%ZZLO%'          THEN 'overground'
            WHEN t.stop_type IN ('MET','PLT','STR') THEN 'tram'
            WHEN t.stop_type = 'TMU'
                 AND t.atco_code LIKE '%ZZ%'        THEN 'tram'
            WHEN t.stop_type IN ('FER','FTD')       THEN 'ferry'
            WHEN t.stop_type IN ('BCT','BCS','BCE','BCQ','BST','FBT') THEN 'bus'
        END AS cat,
        1 AS cnt
    FROM core_transport_stops t
    JOIN core_lad_boundaries lb ON ST_Within(t.geom, lb.geom)
    WHERE t.geom IS NOT NULL
) sub
WHERE cat IS NOT NULL
GROUP BY lb.lad_code, cat;

CREATE INDEX idx_mv_lad_transport_lad ON mv_lad_transport_mode_counts(lad_code);


-- ============================================================
-- 4. Green space stats per LAD per site type
--    ~315 LADs × 7 types ≈ 2,200 rows
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_lad_green_space_stats CASCADE;

CREATE MATERIALIZED VIEW mv_lad_green_space_stats AS
SELECT
    lb.lad_code,
    gs.site_type,
    COUNT(*) AS cnt,
    SUM(ST_Area(gs.geom::geography) / 10000.0) AS total_ha
FROM core_green_space gs
JOIN core_lad_boundaries lb ON ST_Intersects(gs.geom, lb.geom)
WHERE gs.geom IS NOT NULL
  AND gs.site_type IS NOT NULL
GROUP BY lb.lad_code, gs.site_type;

CREATE INDEX idx_mv_lad_green_lad ON mv_lad_green_space_stats(lad_code);
