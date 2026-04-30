-- 013_lad_population_view.sql
-- Per-LAD population and household counts for weighted averaging.
-- Used as a weight source by parent comparison queries for LAD-level tables
-- that lack their own weight column (air quality, broadband, mobile, council tax, rent, earnings).
-- ~318 rows. Refreshed alongside other MVs in pipeline.

DROP MATERIALIZED VIEW IF EXISTS mv_lad_population CASCADE;

CREATE MATERIALIZED VIEW mv_lad_population AS
SELECT
    b.lad_code,
    SUM(c.total_population) AS total_pop,
    SUM(c.total_households) AS total_hh
FROM core_census_lsoa c
JOIN core_lsoa_boundaries b ON b.lsoa_code = c.lsoa_code
GROUP BY b.lad_code;

CREATE UNIQUE INDEX idx_mv_lad_pop_lad ON mv_lad_population(lad_code);
