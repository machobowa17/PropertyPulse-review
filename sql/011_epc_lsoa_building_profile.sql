-- P59: Add building profile columns to core_epc_lsoa
-- Heating columns already exist (added previously) but are NULL.
-- These ALTER statements add only NEW columns.

ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS avg_energy_consumption NUMERIC(10,1);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS avg_heating_cost NUMERIC(8,0);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS avg_hotwater_cost NUMERIC(8,0);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS avg_lighting_cost NUMERIC(8,0);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS pct_mains_gas NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS pct_solar NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS age_pre1900_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS age_1900_1929_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS age_1930_1949_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS age_1950_1966_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS age_1967_1982_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS age_1983_2002_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS age_post2002_pct NUMERIC(5,2);

-- D21: Glazing & insulation quality columns (session 62)
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS windows_good_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS windows_vpoor_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS windows_poor_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS windows_avg_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS walls_good_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS walls_vpoor_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS roof_good_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS roof_vpoor_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS glaze_single_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS glaze_double_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS glaze_triple_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS avg_multi_glaze_pct NUMERIC(5,1);

-- D22: Built form distribution columns (session 62)
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS form_detached_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS form_semi_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS form_terrace_pct NUMERIC(5,2);
ALTER TABLE core_epc_lsoa ADD COLUMN IF NOT EXISTS form_end_terrace_pct NUMERIC(5,2);
