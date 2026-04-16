-- Mart: LAD-level summary with latest metrics for each LAD
-- Used for comparable areas, dashboards, and monitoring
{{ config(materialized='table', indexes=[{'columns': ['lad_code'], 'unique': True}]) }}

WITH latest_prices AS (
    SELECT
        lad_code,
        AVG(price) FILTER (WHERE date_of_transfer >= DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year')) AS avg_price_latest,
        AVG(price) FILTER (WHERE date_of_transfer >= DATE_TRUNC('year', CURRENT_DATE - INTERVAL '2 year')
                                AND date_of_transfer < DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year')) AS avg_price_prev,
        COUNT(*) FILTER (WHERE date_of_transfer >= DATE_TRUNC('year', CURRENT_DATE - INTERVAL '1 year')) AS transactions_ytd
    FROM core_property_transactions
    WHERE property_type IN ('D','S','T','F')
      AND lad_code IS NOT NULL
    GROUP BY lad_code
),
epc_summary AS (
    SELECT
        lb.lad_code,
        AVG(e.avg_energy_score) AS avg_epc_score,
        AVG(e.pct_rating_e_g) AS pct_low_epc
    FROM core_epc_lsoa e
    JOIN core_lsoa_boundaries lb ON lb.lsoa_code = e.lsoa_code
    GROUP BY lb.lad_code
),
crime_summary AS (
    SELECT
        lb.lad_code,
        SUM(c.crime_count) AS total_crimes,
        SUM(c.crime_count)::float / NULLIF(MAX(dem.total_population), 0) * 1000 AS crime_rate_per_1k
    FROM core_crime_lsoa c
    JOIN core_lsoa_boundaries lb ON lb.lsoa_code = c.lsoa_code
    JOIN (SELECT lsoa_code, SUM(total_population) AS total_population
          FROM core_census_lsoa GROUP BY lsoa_code) dem ON dem.lsoa_code = c.lsoa_code
    GROUP BY lb.lad_code
)
SELECT
    l.lad_code,
    l.lad_name,
    p.avg_price_latest,
    p.avg_price_prev,
    CASE WHEN p.avg_price_prev > 0
         THEN ROUND(((p.avg_price_latest - p.avg_price_prev) / p.avg_price_prev * 100)::numeric, 2)
         ELSE NULL END AS price_yoy_pct,
    p.transactions_ytd,
    e.avg_epc_score,
    e.pct_low_epc,
    cr.crime_rate_per_1k,
    NOW() AS refreshed_at
FROM core_lad_boundaries l
LEFT JOIN latest_prices p ON p.lad_code = l.lad_code
LEFT JOIN epc_summary e ON e.lad_code = l.lad_code
LEFT JOIN crime_summary cr ON cr.lad_code = l.lad_code
WHERE l.lad_code LIKE 'E%'
