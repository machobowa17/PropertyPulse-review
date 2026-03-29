-- Test: all LSOAs with property data should have census data
-- Fails if coverage drops below 95%
SELECT
    COUNT(*) AS lsoas_missing_census
FROM core_property_prices_lsoa pp
LEFT JOIN core_census_demographics_lsoa c ON c.lsoa_code = pp.lsoa_code
WHERE c.lsoa_code IS NULL
HAVING COUNT(*) > (SELECT COUNT(DISTINCT lsoa_code) * 0.05 FROM core_property_prices_lsoa)
