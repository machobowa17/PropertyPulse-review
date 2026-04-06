-- 004_parent_price_views.sql
-- Pre-computed parent-level price statistics (true median via PERCENTILE_CONT).
-- Refreshed weekly after Land Registry data loads.
-- "parent_comparison" = county/region grouping from core_lad_county_lookup (42 groups).

-- ============================================================
-- 1. Yearly stats: per (parent, year, type) + (parent, year, ALL)
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_parent_yearly_price_stats CASCADE;

CREATE MATERIALIZED VIEW mv_parent_yearly_price_stats AS

-- Per property type
SELECT
    l.parent_comparison,
    EXTRACT(YEAR FROM t.date_of_transfer)::int AS year,
    t.property_type,
    ROUND(AVG(t.price))::int AS avg_price,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.price))::int AS median_price,
    COUNT(*) AS transactions
FROM core_property_transactions t
JOIN core_lsoa_boundaries b ON b.lsoa_code = t.lsoa_code
JOIN core_lad_county_lookup l ON l.lad_code = b.lad_code
WHERE t.property_type IN ('D','S','T','F')
GROUP BY l.parent_comparison, EXTRACT(YEAR FROM t.date_of_transfer), t.property_type

UNION ALL

-- All types combined
SELECT
    l.parent_comparison,
    EXTRACT(YEAR FROM t.date_of_transfer)::int AS year,
    'ALL' AS property_type,
    ROUND(AVG(t.price))::int AS avg_price,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.price))::int AS median_price,
    COUNT(*) AS transactions
FROM core_property_transactions t
JOIN core_lsoa_boundaries b ON b.lsoa_code = t.lsoa_code
JOIN core_lad_county_lookup l ON l.lad_code = b.lad_code
WHERE t.property_type IN ('D','S','T','F')
GROUP BY l.parent_comparison, EXTRACT(YEAR FROM t.date_of_transfer);

CREATE INDEX idx_mv_parent_yr_pc ON mv_parent_yearly_price_stats(parent_comparison);
CREATE INDEX idx_mv_parent_yr_pc_yr ON mv_parent_yearly_price_stats(parent_comparison, year);
CREATE INDEX idx_mv_parent_yr_pc_yr_pt ON mv_parent_yearly_price_stats(parent_comparison, year, property_type);


-- ============================================================
-- 2. Rolling 13-month stats: per (parent, type) + (parent, ALL)
--    Includes avg_ppsf for headline metric.
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_parent_rolling_price_stats CASCADE;

CREATE MATERIALIZED VIEW mv_parent_rolling_price_stats AS

-- Per property type
SELECT
    l.parent_comparison,
    t.property_type,
    ROUND(AVG(t.price))::int AS avg_price,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.price))::int AS median_price,
    COUNT(*) AS transactions,
    AVG(t.price::numeric / NULLIF(t.floor_area_sqm::numeric * 10.7639, 0)) AS avg_ppsf
FROM core_property_transactions t
JOIN core_lsoa_boundaries b ON b.lsoa_code = t.lsoa_code
JOIN core_lad_county_lookup l ON l.lad_code = b.lad_code
WHERE t.property_type IN ('D','S','T','F')
  AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
GROUP BY l.parent_comparison, t.property_type

UNION ALL

-- All types combined
SELECT
    l.parent_comparison,
    'ALL' AS property_type,
    ROUND(AVG(t.price))::int AS avg_price,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.price))::int AS median_price,
    COUNT(*) AS transactions,
    AVG(t.price::numeric / NULLIF(t.floor_area_sqm::numeric * 10.7639, 0)) AS avg_ppsf
FROM core_property_transactions t
JOIN core_lsoa_boundaries b ON b.lsoa_code = t.lsoa_code
JOIN core_lad_county_lookup l ON l.lad_code = b.lad_code
WHERE t.property_type IN ('D','S','T','F')
  AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
GROUP BY l.parent_comparison;

CREATE INDEX idx_mv_parent_roll_pc ON mv_parent_rolling_price_stats(parent_comparison);
CREATE INDEX idx_mv_parent_roll_pc_pt ON mv_parent_rolling_price_stats(parent_comparison, property_type);
