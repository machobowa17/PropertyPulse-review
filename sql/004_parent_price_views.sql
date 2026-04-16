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


-- ============================================================
-- 3. LAD-level comparable features: price, rent, earnings, AQ, HPI
--    Used by comparable_areas.py — refreshed alongside parent views.
-- ============================================================
DROP MATERIALIZED VIEW IF EXISTS mv_lad_comparable_features CASCADE;

CREATE MATERIALIZED VIEW mv_lad_comparable_features AS
WITH price_agg AS (
    SELECT lad_code, AVG(price) AS avg_price
    FROM core_property_transactions
    WHERE date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
      AND property_type IN ('D','S','T','F')
    GROUP BY lad_code
),
rent_latest AS (
    SELECT DISTINCT ON (lad_code) lad_code, median_rent_all
    FROM core_voa_rents_lad
    ORDER BY lad_code, period DESC
),
hpi_latest AS (
    SELECT DISTINCT ON (lad_code) lad_code, yearly_change_pct
    FROM core_hpi_lad
    ORDER BY lad_code, date DESC
),
aq_latest AS (
    SELECT DISTINCT ON (lad_code) lad_code, pm25_ugm3
    FROM core_air_quality_lad
    ORDER BY lad_code, year DESC
)
SELECT
    lb.lad_code,
    lb.lad_name,
    p.avg_price,
    r.median_rent_all AS median_rent,
    e.median_annual_earnings AS earnings,
    aq.pm25_ugm3 AS pm25,
    h.yearly_change_pct AS hpi_yoy
FROM core_lad_boundaries lb
JOIN price_agg p ON p.lad_code = lb.lad_code
LEFT JOIN rent_latest r ON r.lad_code = lb.lad_code
LEFT JOIN core_earnings_lad e ON e.lad_code = lb.lad_code
LEFT JOIN aq_latest aq ON aq.lad_code = lb.lad_code
LEFT JOIN hpi_latest h ON h.lad_code = lb.lad_code;

CREATE UNIQUE INDEX idx_mv_lad_comparable_lad_code ON mv_lad_comparable_features (lad_code);
