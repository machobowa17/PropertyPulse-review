#!/usr/bin/env python3
"""Ingest KS4 (GCSE) school-level performance data into schools.ks4_results.

Downloads from DfE Explore Education Statistics — institution-level KS4 data.
Multi-year: downloads data for multiple academic years.
"""

import csv
import io
import logging
import os
import sys
import urllib.request

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property",
)

# KS4 institution-level performance data set IDs from EES
# These need to be updated when new releases come out
KS4_DATASETS = {
    # 2023/24 final
    "2023-24": "c8f753ef-b76f-41a3-8949-13382e131054",
}

BASE_URL = "https://explore-education-statistics.service.gov.uk/data-catalogue/data-set"


def _float(val):
    if not val or val.strip() in ("", "z", "x", "c", "k", "u", "ne", "supp", "na", "low"):
        return None
    try:
        return float(val.strip())
    except (ValueError, TypeError):
        return None


def _int(val):
    if not val or val.strip() in ("", "z", "x", "c", "k", "u", "ne", "supp", "na", "low"):
        return None
    try:
        return int(float(val.strip()))
    except (ValueError, TypeError):
        return None


def download_ks4(dataset_id):
    """Download KS4 CSV from EES."""
    url = f"{BASE_URL}/{dataset_id}/csv"
    logger.info("Downloading KS4 from %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=300)
    return resp.read().decode("utf-8-sig", errors="replace")


def parse_ks4(csv_text, academic_year):
    """Parse KS4 CSV and extract school-level performance data.

    We only want rows where:
    - geographic_level == 'School'
    - breakdown_topic == 'Total' (i.e., all pupils combined, not split by sex/disadvantage)
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    seen_urns = set()

    for record in reader:
        if record.get("geographic_level") != "School":
            continue
        if record.get("breakdown_topic") != "Total":
            continue

        urn = _int(record.get("school_urn"))
        if not urn or urn in seen_urns:
            continue
        seen_urns.add(urn)

        attainment_8 = _float(record.get("avg_att8"))
        progress_8 = _float(record.get("avg_p8score"))
        progress_8_lower = _float(record.get("p8score_ci_low"))
        progress_8_upper = _float(record.get("p8score_ci_upp"))
        pct_entering_ebacc = _float(record.get("pt_ebacc_e_ptq_ee"))
        ebacc_aps = _float(record.get("avg_ebaccaps"))
        pct_grade_5_em = _float(record.get("pt_l2basics_95"))
        pct_grade_4_em = _float(record.get("pt_l2basics_94"))
        cohort_size = _int(record.get("t_pupils"))
        pct_disadvantaged = None  # Not available in this dataset

        # Skip if no meaningful data
        if attainment_8 is None and progress_8 is None:
            continue

        rows.append((
            urn, academic_year,
            attainment_8, progress_8, progress_8_lower, progress_8_upper,
            pct_entering_ebacc, ebacc_aps,
            pct_grade_5_em, pct_grade_4_em,
            cohort_size, pct_disadvantaged,
        ))

    logger.info("Parsed %d school-level KS4 results for %s", len(rows), academic_year)
    return rows


def _get_valid_urns(conn):
    """Get set of URNs that exist in schools.institutions."""
    with conn.cursor() as cur:
        cur.execute("SELECT urn FROM schools.institutions")
        return {r[0] for r in cur.fetchall()}


def load_ks4(rows, conn):
    """Load KS4 results into the database."""
    valid_urns = _get_valid_urns(conn)
    rows = [r for r in rows if r[0] in valid_urns]
    logger.info("After FK filter: %d rows with valid URNs", len(rows))
    if not rows:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO schools.ks4_results (
                urn, academic_year,
                attainment_8, progress_8, progress_8_lower_ci, progress_8_upper_ci,
                pct_entering_ebacc, ebacc_avg_point_score,
                pct_grade_5_em, pct_grade_4_em,
                cohort_size, pct_disadvantaged
            ) VALUES %s
            ON CONFLICT (urn, academic_year) DO UPDATE SET
                attainment_8 = EXCLUDED.attainment_8,
                progress_8 = EXCLUDED.progress_8,
                progress_8_lower_ci = EXCLUDED.progress_8_lower_ci,
                progress_8_upper_ci = EXCLUDED.progress_8_upper_ci,
                pct_entering_ebacc = EXCLUDED.pct_entering_ebacc,
                ebacc_avg_point_score = EXCLUDED.ebacc_avg_point_score,
                pct_grade_5_em = EXCLUDED.pct_grade_5_em,
                pct_grade_4_em = EXCLUDED.pct_grade_4_em,
                cohort_size = EXCLUDED.cohort_size,
                pct_disadvantaged = EXCLUDED.pct_disadvantaged
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d KS4 results", len(rows))


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        for year_label, dataset_id in KS4_DATASETS.items():
            csv_text = download_ks4(dataset_id)
            rows = parse_ks4(csv_text, year_label)
            if rows:
                load_ks4(rows, conn)
    finally:
        conn.close()
    logger.info("KS4 ingestion complete")


if __name__ == "__main__":
    main()
