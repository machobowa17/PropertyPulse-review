#!/usr/bin/env python3
"""Ingest DfE SEN2 returns (LA-level EHCP statistics) into schools.sen2_la_stats.

Sources: 5 CSVs from DfE 'Education, health and care plans' publication:
  1. timeliness.csv         — % plans issued within 20 weeks
  2. assessment_requests.csv — requests, refusals, tribunals
  3. assessments_outcomes.csv — assessments completed, plan issued/not issued, tribunals
  4. caseload.csv           — total EHCPs, placement breakdown
  5. caseload_primary_need.csv — primary need breakdown

All CSVs from: https://explore-education-statistics.service.gov.uk/find-statistics/education-health-and-care-plans/2025

Schema: One row per LA per year, denormalised from all 5 sources.
"""

import csv
import logging
import os

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property",
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "sen2")

# DfE uses "x", "z", "c", "k", "u", "ne", "supp", "na", "low" for suppressed/missing
SUPPRESSED = {"", "z", "x", "c", "k", "u", "ne", "supp", "na", "low", ".", "-"}


def _float(val):
    if not val or val.strip() in SUPPRESSED:
        return None
    try:
        return float(val.strip().rstrip("%"))
    except (ValueError, TypeError):
        return None


def _int(val):
    if not val or val.strip() in SUPPRESSED:
        return None
    try:
        return int(float(val.strip().replace(",", "")))
    except (ValueError, TypeError):
        return None


def _read_csv(filename):
    """Read CSV with BOM handling, return list of dicts."""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        logger.warning("File not found: %s", path)
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _la_rows(rows, time_period, breakdown_value):
    """Filter to LA-level rows for a given year and breakdown."""
    return {
        r["new_la_code"]: r
        for r in rows
        if r["geographic_level"] == "Local authority"
        and r["time_period"] == time_period
        and r["breakdown"] == breakdown_value
    }


def _national_row(rows, time_period, breakdown_value):
    """Get the national-level row for a given year and breakdown."""
    for r in rows:
        if (r["geographic_level"] == "National"
                and r["time_period"] == time_period
                and r["breakdown"] == breakdown_value):
            return r
    return None


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS schools.sen2_la_stats (
    id              SERIAL PRIMARY KEY,
    la_code         TEXT NOT NULL,          -- ONS E-code (e.g. E08000037)
    old_la_code     TEXT,                   -- DfE 3-digit code (e.g. 390)
    la_name         TEXT,
    year            TEXT NOT NULL,          -- Calendar year for flow data (e.g. '2024')
    academic_year   TEXT,                   -- Academic year for stock data (e.g. '2024-25')

    -- Timeliness (from timeliness.csv)
    plans_issued_total          INT,
    plans_issued_within_20wk    INT,
    pct_within_20wk             REAL,       -- % of plans issued within 20 weeks
    pct_within_20wk_excl        REAL,       -- % excluding exceptions
    plans_issued_20wk_to_1yr    INT,
    plans_issued_over_1yr       INT,

    -- Assessment requests (from assessment_requests.csv)
    requests_received           INT,
    requests_assessed           INT,
    requests_refused            INT,
    pct_refused                 REAL,       -- % of requests refused assessment
    requests_withdrawn          INT,
    mediation_on_request        INT,        -- mediations related to request decision
    tribunal_on_request         INT,        -- tribunals related to request decision

    -- Assessments & outcomes (from assessments_outcomes.csv)
    assessments_completed       INT,
    plans_issued                INT,
    pct_plan_issued             REAL,       -- % of assessments that resulted in plan
    plans_not_issued            INT,
    pct_plan_not_issued         REAL,
    tribunal_on_assessment      INT,        -- tribunals on assessment outcome
    tribunal_other              INT,        -- other tribunals (e.g. content, placement)
    mediation_on_assessment     INT,
    mediation_other             INT,

    -- Caseload (from caseload.csv)
    total_ehcps                 INT,
    mainstream_total            INT,
    mainstream_pct              REAL,
    special_total               INT,
    special_pct                 REAL,
    ap_pru_total                INT,
    ap_pru_pct                  REAL,
    fe_total                    INT,
    fe_pct                      REAL,
    elective_home_ed            INT,
    neet                        INT,

    -- Primary need breakdown (from caseload_primary_need.csv)
    need_asd                    INT,
    need_asd_pct                REAL,
    need_slcn                   INT,
    need_slcn_pct               REAL,
    need_semh                   INT,
    need_semh_pct               REAL,
    need_mld                    INT,
    need_mld_pct                REAL,
    need_sld                    INT,
    need_sld_pct                REAL,
    need_pmld                   INT,
    need_pmld_pct               REAL,
    need_spld                   INT,
    need_spld_pct               REAL,
    need_pd                     INT,
    need_pd_pct                 REAL,
    need_hi                     INT,
    need_hi_pct                 REAL,
    need_vi                     INT,
    need_vi_pct                 REAL,

    -- National averages (for comparison)
    nat_pct_within_20wk         REAL,
    nat_pct_refused             REAL,
    nat_pct_plan_issued         REAL,
    nat_mainstream_pct          REAL,
    nat_special_pct             REAL,
    nat_need_asd_pct            REAL,
    nat_need_slcn_pct           REAL,
    nat_need_semh_pct           REAL,

    ingested_at     TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (la_code, year)
);

CREATE INDEX IF NOT EXISTS idx_sen2_la_stats_lacode ON schools.sen2_la_stats (la_code);
CREATE INDEX IF NOT EXISTS idx_sen2_la_stats_year ON schools.sen2_la_stats (year);
"""


def create_table(conn):
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE)
    conn.commit()
    logger.info("Table schools.sen2_la_stats ensured")


def load_data(conn):
    """Load all 5 CSVs, join by LA code, and upsert into sen2_la_stats."""

    # --- Read all CSVs ---
    timeliness_all = _read_csv("timeliness.csv")
    requests_all = _read_csv("assessment_requests.csv")
    outcomes_all = _read_csv("assessments_outcomes.csv")
    caseload_all = _read_csv("caseload.csv")
    needs_all = _read_csv("caseload_primary_need.csv")

    if not timeliness_all:
        logger.error("No timeliness data found — aborting")
        return 0

    # --- Determine latest year for each dataset ---
    # Flow data (timeliness, requests, outcomes) uses calendar year: '2024'
    # Stock data (caseload, needs) uses academic year: '202425'
    FLOW_YEAR = "2024"
    STOCK_YEAR = "202425"

    # --- Filter to LA level, latest year, "All" breakdown ---
    timeliness = _la_rows(timeliness_all, FLOW_YEAR, "All EHC plans issued")
    requests = _la_rows(requests_all, FLOW_YEAR, "All requests for EHC needs assessments")
    outcomes = _la_rows(outcomes_all, FLOW_YEAR, "All EHC needs assessments")
    caseload = _la_rows(caseload_all, STOCK_YEAR, "All EHC plans")
    needs = _la_rows(needs_all, STOCK_YEAR, "All EHC plans")

    logger.info("Rows per dataset — timeliness: %d, requests: %d, outcomes: %d, caseload: %d, needs: %d",
                len(timeliness), len(requests), len(outcomes), len(caseload), len(needs))

    # --- Get national averages ---
    nat_t = _national_row(timeliness_all, FLOW_YEAR, "All EHC plans issued") or {}
    nat_r = _national_row(requests_all, FLOW_YEAR, "All requests for EHC needs assessments") or {}
    nat_o = _national_row(outcomes_all, FLOW_YEAR, "All EHC needs assessments") or {}
    nat_c = _national_row(caseload_all, STOCK_YEAR, "All EHC plans") or {}
    nat_n = _national_row(needs_all, STOCK_YEAR, "All EHC plans") or {}

    nat_pct_20wk = _float(nat_t.get("pc_plans_issued_within_20_weeks"))
    nat_pct_refused = _float(nat_r.get("request_not_assess_pc"))
    nat_pct_issued = _float(nat_o.get("assess_issued_pc"))
    nat_mainstream_pct = _float(nat_c.get("mainstream_total_pc"))
    nat_special_pct = _float(nat_c.get("special_total_pc"))
    nat_asd_pct = _float(nat_n.get("asd_pc"))
    nat_slcn_pct = _float(nat_n.get("slcn_pc"))
    nat_semh_pct = _float(nat_n.get("semh_pc"))

    logger.info("National averages — 20wk: %s%%, refused: %s%%, issued: %s%%, mainstream: %s%%, special: %s%%",
                nat_pct_20wk, nat_pct_refused, nat_pct_issued, nat_mainstream_pct, nat_special_pct)

    # --- Build union of all LA codes ---
    all_la_codes = set()
    for d in (timeliness, requests, outcomes, caseload, needs):
        all_la_codes.update(d.keys())

    logger.info("Total unique LA codes: %d", len(all_la_codes))

    # --- Build rows ---
    rows = []
    for la_code in sorted(all_la_codes):
        t = timeliness.get(la_code, {})
        r = requests.get(la_code, {})
        o = outcomes.get(la_code, {})
        c = caseload.get(la_code, {})
        n = needs.get(la_code, {})

        # Get LA name from whichever source has it
        la_name = t.get("la_name") or r.get("la_name") or o.get("la_name") or c.get("la_name") or n.get("la_name")
        old_code = t.get("old_la_code") or r.get("old_la_code") or o.get("old_la_code") or c.get("old_la_code") or n.get("old_la_code")

        rows.append((
            la_code,
            old_code,
            la_name,
            FLOW_YEAR,                                    # year
            "2024-25",                                    # academic_year

            # Timeliness
            _int(t.get("plans_issued_den")),
            _int(t.get("plans_issued_within_20_weeks")),
            _float(t.get("pc_plans_issued_within_20_weeks")),
            _float(t.get("PC_plans_issued_20_weeks_ex")),
            _int(t.get("plans_issued_gt20weeks_ltYear")),
            _int(t.get("plans_issued_gt_1_year")),

            # Assessment requests
            _int(r.get("requests_received_in_year")),
            _int(r.get("requests_decided_to_assess")),
            _int(r.get("requests_decided_not_to_assess")),
            _float(r.get("request_not_assess_pc")),
            _int(r.get("requests_withdrawn")),
            _int(r.get("mediation_related_request")),
            _int(r.get("tribunal_related_request")),

            # Assessments & outcomes
            _int(o.get("assess_in_year")),
            _int(o.get("assess_issued")),
            _float(o.get("assess_issued_pc")),
            _int(o.get("assess_not_issued")),
            _float(o.get("assess_not_issued_pc")),
            _int(o.get("number_assess_tribunal")),
            _int(o.get("number_other_tribunal")),
            _int(o.get("number_assess_mediation")),
            _int(o.get("number_other_mediation")),

            # Caseload
            _int(c.get("ehcplans")),
            _int(c.get("mainstream_total")),
            _float(c.get("mainstream_total_pc")),
            _int(c.get("special_total")),
            _float(c.get("special_total_pc")),
            _int(c.get("ap_pru_total")),
            _float(c.get("AP_PRU_total_pc")),
            _int(c.get("fe_total")),
            _float(c.get("fe_total_pc")),
            _int(c.get("elective_home_education")),
            _int(c.get("neet")),

            # Primary need
            _int(n.get("number_asd")),
            _float(n.get("asd_pc")),
            _int(n.get("number_slcn")),
            _float(n.get("slcn_pc")),
            _int(n.get("number_semh")),
            _float(n.get("semh_pc")),
            _int(n.get("number_mld")),
            _float(n.get("mld_pc")),
            _int(n.get("number_sld")),
            _float(n.get("sld_pc")),
            _int(n.get("number_pmld")),
            _float(n.get("pmld_pc")),
            _int(n.get("number_spld")),
            _float(n.get("spld_pc")),
            _int(n.get("number_pd")),
            _float(n.get("pd_pc")),
            _int(n.get("number_hi")),
            _float(n.get("hi_pc")),
            _int(n.get("number_vi")),
            _float(n.get("vi_pc")),

            # National averages
            nat_pct_20wk,
            nat_pct_refused,
            nat_pct_issued,
            nat_mainstream_pct,
            nat_special_pct,
            nat_asd_pct,
            nat_slcn_pct,
            nat_semh_pct,
        ))

    if not rows:
        logger.warning("No rows to insert")
        return 0

    # --- Upsert ---
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO schools.sen2_la_stats (
                la_code, old_la_code, la_name, year, academic_year,
                plans_issued_total, plans_issued_within_20wk, pct_within_20wk, pct_within_20wk_excl,
                plans_issued_20wk_to_1yr, plans_issued_over_1yr,
                requests_received, requests_assessed, requests_refused, pct_refused,
                requests_withdrawn, mediation_on_request, tribunal_on_request,
                assessments_completed, plans_issued, pct_plan_issued, plans_not_issued, pct_plan_not_issued,
                tribunal_on_assessment, tribunal_other, mediation_on_assessment, mediation_other,
                total_ehcps, mainstream_total, mainstream_pct, special_total, special_pct,
                ap_pru_total, ap_pru_pct, fe_total, fe_pct, elective_home_ed, neet,
                need_asd, need_asd_pct, need_slcn, need_slcn_pct, need_semh, need_semh_pct,
                need_mld, need_mld_pct, need_sld, need_sld_pct, need_pmld, need_pmld_pct,
                need_spld, need_spld_pct, need_pd, need_pd_pct, need_hi, need_hi_pct,
                need_vi, need_vi_pct,
                nat_pct_within_20wk, nat_pct_refused, nat_pct_plan_issued,
                nat_mainstream_pct, nat_special_pct, nat_need_asd_pct, nat_need_slcn_pct, nat_need_semh_pct
            ) VALUES %s
            ON CONFLICT (la_code, year) DO UPDATE SET
                old_la_code = EXCLUDED.old_la_code,
                la_name = EXCLUDED.la_name,
                academic_year = EXCLUDED.academic_year,
                plans_issued_total = EXCLUDED.plans_issued_total,
                plans_issued_within_20wk = EXCLUDED.plans_issued_within_20wk,
                pct_within_20wk = EXCLUDED.pct_within_20wk,
                pct_within_20wk_excl = EXCLUDED.pct_within_20wk_excl,
                plans_issued_20wk_to_1yr = EXCLUDED.plans_issued_20wk_to_1yr,
                plans_issued_over_1yr = EXCLUDED.plans_issued_over_1yr,
                requests_received = EXCLUDED.requests_received,
                requests_assessed = EXCLUDED.requests_assessed,
                requests_refused = EXCLUDED.requests_refused,
                pct_refused = EXCLUDED.pct_refused,
                requests_withdrawn = EXCLUDED.requests_withdrawn,
                mediation_on_request = EXCLUDED.mediation_on_request,
                tribunal_on_request = EXCLUDED.tribunal_on_request,
                assessments_completed = EXCLUDED.assessments_completed,
                plans_issued = EXCLUDED.plans_issued,
                pct_plan_issued = EXCLUDED.pct_plan_issued,
                plans_not_issued = EXCLUDED.plans_not_issued,
                pct_plan_not_issued = EXCLUDED.pct_plan_not_issued,
                tribunal_on_assessment = EXCLUDED.tribunal_on_assessment,
                tribunal_other = EXCLUDED.tribunal_other,
                mediation_on_assessment = EXCLUDED.mediation_on_assessment,
                mediation_other = EXCLUDED.mediation_other,
                total_ehcps = EXCLUDED.total_ehcps,
                mainstream_total = EXCLUDED.mainstream_total,
                mainstream_pct = EXCLUDED.mainstream_pct,
                special_total = EXCLUDED.special_total,
                special_pct = EXCLUDED.special_pct,
                ap_pru_total = EXCLUDED.ap_pru_total,
                ap_pru_pct = EXCLUDED.ap_pru_pct,
                fe_total = EXCLUDED.fe_total,
                fe_pct = EXCLUDED.fe_pct,
                elective_home_ed = EXCLUDED.elective_home_ed,
                neet = EXCLUDED.neet,
                need_asd = EXCLUDED.need_asd,
                need_asd_pct = EXCLUDED.need_asd_pct,
                need_slcn = EXCLUDED.need_slcn,
                need_slcn_pct = EXCLUDED.need_slcn_pct,
                need_semh = EXCLUDED.need_semh,
                need_semh_pct = EXCLUDED.need_semh_pct,
                need_mld = EXCLUDED.need_mld,
                need_mld_pct = EXCLUDED.need_mld_pct,
                need_sld = EXCLUDED.need_sld,
                need_sld_pct = EXCLUDED.need_sld_pct,
                need_pmld = EXCLUDED.need_pmld,
                need_pmld_pct = EXCLUDED.need_pmld_pct,
                need_spld = EXCLUDED.need_spld,
                need_spld_pct = EXCLUDED.need_spld_pct,
                need_pd = EXCLUDED.need_pd,
                need_pd_pct = EXCLUDED.need_pd_pct,
                need_hi = EXCLUDED.need_hi,
                need_hi_pct = EXCLUDED.need_hi_pct,
                need_vi = EXCLUDED.need_vi,
                need_vi_pct = EXCLUDED.need_vi_pct,
                nat_pct_within_20wk = EXCLUDED.nat_pct_within_20wk,
                nat_pct_refused = EXCLUDED.nat_pct_refused,
                nat_pct_plan_issued = EXCLUDED.nat_pct_plan_issued,
                nat_mainstream_pct = EXCLUDED.nat_mainstream_pct,
                nat_special_pct = EXCLUDED.nat_special_pct,
                nat_need_asd_pct = EXCLUDED.nat_need_asd_pct,
                nat_need_slcn_pct = EXCLUDED.nat_need_slcn_pct,
                nat_need_semh_pct = EXCLUDED.nat_need_semh_pct,
                ingested_at = NOW()
            """,
            rows,
            page_size=200,
        )

    conn.commit()
    logger.info("Upserted %d LA rows into schools.sen2_la_stats", len(rows))
    return len(rows)


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        create_table(conn)
        count = load_data(conn)
        logger.info("Done — %d rows loaded", count)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
