-- 011_expand_comparable_features.sql
-- Expand mv_lad_comparable_features from 5D to 11D for richer comparable areas.
-- New dimensions: crime_rate, avg_imd_score, median_age, pop_density, nearest_station_m, council_tax.
-- Must be run on EC2 after deploy.

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
),
-- New CTEs for expanded dimensions
crime_agg AS (
    SELECT b.lad_code,
           SUM(c.crime_count)::float / NULLIF(SUM(cs.total_population), 0) * 1000 AS crime_rate
    FROM core_crime_lsoa c
    JOIN core_lsoa_boundaries b ON b.lsoa_code = c.lsoa_code
    JOIN core_census_lsoa cs ON cs.lsoa_code = c.lsoa_code
    WHERE c.month > (SELECT MAX(month) - INTERVAL '12 months' FROM core_crime_lsoa)
    GROUP BY b.lad_code
),
imd_agg AS (
    SELECT b.lad_code,
           SUM(cs.total_population * i.imd_score) / NULLIF(SUM(cs.total_population), 0) AS avg_imd_score
    FROM core_imd_lsoa i
    JOIN core_census_lsoa cs ON cs.lsoa_code = i.lsoa_code
    JOIN core_lsoa_boundaries b ON b.lsoa_code = i.lsoa_code
    GROUP BY b.lad_code
),
demo_agg AS (
    SELECT b.lad_code,
           SUM(cs.total_population * cs.median_age) / NULLIF(SUM(cs.total_population), 0) AS median_age,
           SUM(cs.total_population)::float / NULLIF(SUM(cs.total_population::float / NULLIF(cs.population_density, 0)), 0) AS pop_density
    FROM core_census_lsoa cs
    JOIN core_lsoa_boundaries b ON b.lsoa_code = cs.lsoa_code
    WHERE cs.population_density > 0
    GROUP BY b.lad_code
),
transport_agg AS (
    SELECT b.lad_code, AVG(t.nearest_station_m) AS nearest_station_m
    FROM core_lsoa_transport t
    JOIN core_lsoa_boundaries b ON b.lsoa_code = t.lsoa_code
    GROUP BY b.lad_code
),
council_tax_agg AS (
    SELECT lad_code, band_d AS council_tax
    FROM core_council_tax_lad
)
SELECT
    lb.lad_code,
    lb.lad_name,
    p.avg_price,
    r.median_rent_all AS median_rent,
    e.median_annual_earnings AS earnings,
    aq.pm25_ugm3 AS pm25,
    h.yearly_change_pct AS hpi_yoy,
    cr.crime_rate,
    imd.avg_imd_score,
    demo.median_age,
    demo.pop_density,
    tr.nearest_station_m,
    ct.council_tax
FROM core_lad_boundaries lb
JOIN price_agg p ON p.lad_code = lb.lad_code
LEFT JOIN rent_latest r ON r.lad_code = lb.lad_code
LEFT JOIN core_earnings_lad e ON e.lad_code = lb.lad_code
LEFT JOIN aq_latest aq ON aq.lad_code = lb.lad_code
LEFT JOIN hpi_latest h ON h.lad_code = lb.lad_code
LEFT JOIN crime_agg cr ON cr.lad_code = lb.lad_code
LEFT JOIN imd_agg imd ON imd.lad_code = lb.lad_code
LEFT JOIN demo_agg demo ON demo.lad_code = lb.lad_code
LEFT JOIN transport_agg tr ON tr.lad_code = lb.lad_code
LEFT JOIN council_tax_agg ct ON ct.lad_code = lb.lad_code;

CREATE UNIQUE INDEX idx_mv_lad_comparable_lad_code ON mv_lad_comparable_features (lad_code);
