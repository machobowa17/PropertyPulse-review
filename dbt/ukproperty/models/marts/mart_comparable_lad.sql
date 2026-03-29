-- Mart: Comparable LADs feature vector (used by similarity search)
-- Pre-computed so similarity queries are fast
{{ config(materialized='table', indexes=[{'columns': ['lad_code'], 'unique': True}]) }}

WITH price_data AS (
    SELECT lad_code,
           AVG(avg_price) FILTER (WHERE year_month >= NOW() - INTERVAL '12 months') AS avg_price
    FROM core_property_prices_lad WHERE property_type IN ('D','S','T','F') GROUP BY lad_code
),
rent_data AS (
    SELECT lad_code, median_annual_rent / 12.0 AS median_rent FROM core_voa_rents_lad
),
earn_data AS (
    SELECT lad_code, median_gross_pay AS earnings FROM core_earnings_lad
),
aq_data AS (
    SELECT lad_code, AVG(pm25_ugm3) FILTER (WHERE year >= 2020) AS pm25
    FROM core_air_quality_lad GROUP BY lad_code
),
hpi_data AS (
    SELECT lad_code, hpi_yoy FROM core_hpi_lad WHERE year_month = (SELECT MAX(year_month) FROM core_hpi_lad)
)
SELECT
    l.lad_code,
    l.lad_name,
    p.avg_price,
    r.median_rent,
    e.earnings,
    a.pm25,
    h.hpi_yoy,
    NOW() AS refreshed_at
FROM core_lad_boundaries l
LEFT JOIN price_data p ON p.lad_code = l.lad_code
LEFT JOIN rent_data r ON r.lad_code = l.lad_code
LEFT JOIN earn_data e ON e.lad_code = l.lad_code
LEFT JOIN aq_data a ON a.lad_code = l.lad_code
LEFT JOIN hpi_data h ON h.lad_code = l.lad_code
WHERE l.lad_code LIKE 'E%'
