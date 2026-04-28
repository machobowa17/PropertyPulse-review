-- migrate_utilities.sql — Create tables for electricity DNO and gas GDN per LAD
-- Run once on EC2 before ETL: psql ukproperty -f sql/migrate_utilities.sql

CREATE TABLE IF NOT EXISTS core_electricity_dno_lad (
    lad_code    TEXT PRIMARY KEY,
    dno_name    TEXT NOT NULL,       -- e.g. "UK Power Networks"
    dno_region  TEXT NOT NULL,       -- e.g. "East England"
    dno_code    TEXT                 -- e.g. "_A" (NESO region code)
);

CREATE TABLE IF NOT EXISTS core_gas_gdn_lad (
    lad_code    TEXT PRIMARY KEY,
    gdn_name    TEXT NOT NULL,       -- e.g. "SGN"
    gdn_region  TEXT NOT NULL        -- e.g. "Southern"
);
