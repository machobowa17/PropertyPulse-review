-- Mart: Pre-aggregated broadband coverage by LAD
-- Replaces the slow 488ms JOIN on 1.7M row postcode table
-- Refreshed monthly when Ofcom releases new data
{{ config(materialized='table', indexes=[{'columns': ['lad_code'], 'unique': True}]) }}

SELECT
    p.lad_code,
    ROUND(AVG(b.superfast_pct)::numeric, 2) AS superfast_pct,
    ROUND(AVG(b.ultrafast_pct)::numeric, 2) AS ultrafast_pct,
    ROUND(AVG(b.gigabit_pct)::numeric, 2) AS gigabit_pct,
    ROUND(AVG(b.fttp_pct)::numeric, 2) AS full_fibre_pct,
    COUNT(DISTINCT b.postcode) AS postcode_count,
    NOW() AS refreshed_at
FROM core_broadband_postcode b
JOIN core_postcodes p ON p.postcode = b.postcode
WHERE p.lad_code LIKE 'E%'
GROUP BY p.lad_code
