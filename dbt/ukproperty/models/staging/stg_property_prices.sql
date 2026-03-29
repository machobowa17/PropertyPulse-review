-- Staging: Property prices from core tables → clean intermediate view
-- Aggregates LSOA-level prices to LAD level with YoY change
{{ config(materialized='view') }}

SELECT
    lad_code,
    year_month,
    property_type,
    AVG(avg_price) AS avg_price,
    AVG(median_price) AS median_price,
    SUM(transaction_count) AS transaction_count,
    SUM(new_build_count) AS new_build_count
FROM core_property_prices_lsoa pp
JOIN core_lsoa_boundaries lb ON lb.lsoa_code = pp.lsoa_code
GROUP BY lad_code, year_month, property_type
