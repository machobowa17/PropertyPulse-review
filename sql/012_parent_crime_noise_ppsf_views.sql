-- 012_parent_crime_noise_ppsf_views.sql
-- Per-LAD materialized views for crime rate, noise, and yearly PPSF.
-- Previously created ad-hoc in the DB; now codified and keyed by lad_code
-- so all consumers use: WHERE lad_code = ANY(:parent_lad_codes)

-- ============================================================
-- 1. Crime rate per LAD per month (with population for rate calc)
--    ~315 LADs × 36 months ≈ 11K rows
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_parent_crime_rate CASCADE;

CREATE MATERIALIZED VIEW mv_parent_crime_rate AS
WITH crime_stats AS (
    SELECT
        b.lad_code,
        c.month,
        SUM(c.crime_count) AS total_crimes
    FROM core_crime_lsoa c
    JOIN core_lsoa_boundaries b ON b.lsoa_code = c.lsoa_code
    GROUP BY b.lad_code, c.month
), pop_stats AS (
    SELECT
        b.lad_code,
        SUM(d.total_population) AS total_pop
    FROM core_census_lsoa d
    JOIN core_lsoa_boundaries b ON b.lsoa_code = d.lsoa_code
    GROUP BY b.lad_code
)
SELECT
    cs.lad_code,
    cs.month,
    cs.total_crimes,
    ps.total_pop
FROM crime_stats cs
JOIN pop_stats ps ON ps.lad_code = cs.lad_code;

CREATE INDEX idx_mv_parent_crime_lad ON mv_parent_crime_rate(lad_code);
CREATE INDEX idx_mv_parent_crime_lad_month ON mv_parent_crime_rate(lad_code, month);


-- ============================================================
-- 2. Noise averages per LAD (with postcode count for weighted re-aggregation)
--    ~315 LADs, 1 row each
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_parent_noise_avg CASCADE;

CREATE MATERIALIZED VIEW mv_parent_noise_avg AS
SELECT
    p.lad_code,
    AVG(n.road_noise_db) AS avg_road,
    AVG(n.rail_noise_db) AS avg_rail,
    AVG(n.air_noise_db) AS avg_air,
    COUNT(*) AS postcode_count
FROM core_noise n
JOIN core_postcodes p ON p.postcode = n.postcode
GROUP BY p.lad_code;

CREATE INDEX idx_mv_parent_noise_lad ON mv_parent_noise_avg(lad_code);


-- ============================================================
-- 3. Yearly PPSF (price per square foot) per LAD
--    ~315 LADs × ~30 years ≈ 9K rows
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_parent_yearly_ppsf CASCADE;

CREATE MATERIALIZED VIEW mv_parent_yearly_ppsf AS
SELECT
    b.lad_code,
    EXTRACT(YEAR FROM t.date_of_transfer)::int AS year,
    ROUND(AVG(t.price::numeric / NULLIF(t.floor_area_sqm::numeric * 10.7639, 0)))::int AS avg_ppsf
FROM core_property_transactions t
JOIN core_lsoa_boundaries b ON b.lsoa_code = t.lsoa_code
WHERE t.property_type IN ('D','S','T','F')
  AND t.floor_area_sqm > 0
GROUP BY b.lad_code, EXTRACT(YEAR FROM t.date_of_transfer);

CREATE INDEX idx_mv_parent_ppsf_lad ON mv_parent_yearly_ppsf(lad_code);
CREATE INDEX idx_mv_parent_ppsf_lad_yr ON mv_parent_yearly_ppsf(lad_code, year);
