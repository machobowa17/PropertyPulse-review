-- 007_census_lsoa_wide.sql
-- Consolidate 5 individual census LSOA tables into one wide table.
-- Phase 13 Step 5: Census consolidation.

CREATE TABLE IF NOT EXISTS core_census_lsoa (
    lsoa_code               TEXT PRIMARY KEY,
    -- Demographics (from core_census_demographics_lsoa)
    total_population        INTEGER,
    population_density      NUMERIC(8,2),
    median_age              NUMERIC(4,1),
    pct_age_0_15            NUMERIC(5,2),
    pct_age_16_64           NUMERIC(5,2),
    pct_age_65_plus         NUMERIC(5,2),
    pct_families            NUMERIC(5,2),
    pct_singles             NUMERIC(5,2),
    pct_sharers             NUMERIC(5,2),
    -- Housing (from core_census_housing_lsoa)
    total_households        INTEGER,
    pct_owned               NUMERIC(5,2),
    pct_social_rent         NUMERIC(5,2),
    pct_private_rent        NUMERIC(5,2),
    pct_detached            NUMERIC(5,2),
    pct_semi                NUMERIC(5,2),
    pct_terraced            NUMERIC(5,2),
    pct_flat                NUMERIC(5,2),
    -- Household size (from core_census_hh_size_lsoa)
    total_hh                INTEGER,
    pct_1person             NUMERIC(5,2),
    pct_2person             NUMERIC(5,2),
    pct_3_4person           NUMERIC(5,2),
    pct_5plus               NUMERIC(5,2),
    -- Commute distance (from core_census_commute_lsoa)
    total_workers           INTEGER,
    pct_lt2km               NUMERIC(5,2),
    pct_2_10km              NUMERIC(5,2),
    pct_10_30km             NUMERIC(5,2),
    pct_30plus              NUMERIC(5,2),
    pct_wfh                 NUMERIC(5,2),
    -- Extra (from core_census_extra_lsoa)
    pct_good_health         NUMERIC(5,2),
    pct_economically_active NUMERIC(5,2),
    pct_degree              NUMERIC(5,2),
    pct_no_car              NUMERIC(5,2),
    pct_born_abroad         NUMERIC(5,2)
);

-- Populate from existing 5 tables via FULL OUTER JOINs (all keyed by lsoa_code).
-- Using demographics as the base since it has the most complete LSOA coverage.
INSERT INTO core_census_lsoa
SELECT
    COALESCE(d.lsoa_code, h.lsoa_code, s.lsoa_code, c.lsoa_code, e.lsoa_code) AS lsoa_code,
    -- Demographics
    d.total_population, d.population_density, d.median_age,
    d.pct_age_0_15, d.pct_age_16_64, d.pct_age_65_plus,
    d.pct_families, d.pct_singles, d.pct_sharers,
    -- Housing
    h.total_households, h.pct_owned, h.pct_social_rent, h.pct_private_rent,
    h.pct_detached, h.pct_semi, h.pct_terraced, h.pct_flat,
    -- Household size
    s.total_hh, s.pct_1person, s.pct_2person, s.pct_3_4person, s.pct_5plus,
    -- Commute
    c.total_workers, c.pct_lt2km, c.pct_2_10km, c.pct_10_30km, c.pct_30plus, c.pct_wfh,
    -- Extra
    e.pct_good_health, e.pct_economically_active, e.pct_degree, e.pct_no_car, e.pct_born_abroad
FROM core_census_demographics_lsoa d
FULL OUTER JOIN core_census_housing_lsoa h ON h.lsoa_code = d.lsoa_code
FULL OUTER JOIN core_census_hh_size_lsoa s ON s.lsoa_code = COALESCE(d.lsoa_code, h.lsoa_code)
FULL OUTER JOIN core_census_commute_lsoa c ON c.lsoa_code = COALESCE(d.lsoa_code, h.lsoa_code, s.lsoa_code)
FULL OUTER JOIN core_census_extra_lsoa e ON e.lsoa_code = COALESCE(d.lsoa_code, h.lsoa_code, s.lsoa_code, c.lsoa_code)
ON CONFLICT (lsoa_code) DO NOTHING;
