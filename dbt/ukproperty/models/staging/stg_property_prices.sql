-- Staging: Property prices from master table → clean intermediate view
-- Aggregates transaction-level prices to LAD level with counts
{{ config(materialized='view') }}

SELECT
    lad_code,
    DATE_TRUNC('month', date_of_transfer)::DATE AS year_month,
    property_type,
    AVG(price) AS avg_price,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) AS median_price,
    COUNT(*) AS transaction_count
FROM core_property_transactions
WHERE lad_code IS NOT NULL
  AND property_type IN ('D','S','T','F')
GROUP BY lad_code, DATE_TRUNC('month', date_of_transfer)::DATE, property_type
