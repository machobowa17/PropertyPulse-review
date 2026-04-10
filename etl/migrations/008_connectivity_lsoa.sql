-- Official Department for Transport Transport Connectivity Metric (2025)
-- Phase-two commuter-connectivity context layer for England-first PropertyPulse.

CREATE TABLE IF NOT EXISTS core_connectivity_lsoa (
    lsoa_code                           TEXT PRIMARY KEY,
    overall_score                       NUMERIC(5,2),
    overall_walking                     NUMERIC(5,2),
    overall_cycling                     NUMERIC(5,2),
    overall_public_transport            NUMERIC(5,2),
    overall_driving                     NUMERIC(5,2),
    employment_overall                  NUMERIC(5,2),
    education_overall                   NUMERIC(5,2),
    healthcare_overall                  NUMERIC(5,2),
    leisure_community_overall           NUMERIC(5,2),
    shopping_overall                    NUMERIC(5,2),
    residential_overall                 NUMERIC(5,2),
    business_public_transport           NUMERIC(5,2),
    education_public_transport          NUMERIC(5,2),
    healthcare_public_transport         NUMERIC(5,2),
    leisure_community_public_transport  NUMERIC(5,2),
    shopping_public_transport           NUMERIC(5,2),
    residential_public_transport        NUMERIC(5,2),
    source_release                      TEXT
);
