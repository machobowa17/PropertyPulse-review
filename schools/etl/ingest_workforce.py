#!/usr/bin/env python3
"""Ingest school-level workforce data into schools.workforce.

Downloads pupil-to-teacher ratio data from DfE EES.
Contains: teacher FTEs, pupil FTEs, PTR ratios per school per year.
"""

import csv
import io
import logging
import os
import urllib.request

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property",
)

# School-level pupil-to-teacher ratios dataset
WORKFORCE_DATASET_ID = "f63c85d9-1c8f-4b3d-a5b5-2ef6e2dbd7ef"
BASE_URL = "https://explore-education-statistics.service.gov.uk/data-catalogue/data-set"

YEAR_MAP = {
    "202324": "2023-24",
    "202223": "2022-23",
    "202122": "2021-22",
    "202021": "2020-21",
    "201920": "2019-20",
}


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


def _get_valid_urns(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT urn FROM schools.institutions")
        return {r[0] for r in cur.fetchall()}


def download_and_parse():
    url = f"{BASE_URL}/{WORKFORCE_DATASET_ID}/csv"
    logger.info("Downloading workforce data from %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=600)
    csv_text = resp.read().decode("utf-8-sig", errors="replace")

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    seen = set()

    for record in reader:
        if record.get("geographic_level") != "School":
            continue

        urn = _int(record.get("school_urn"))
        if not urn:
            continue

        time_period = record.get("time_period", "").strip()
        academic_year = YEAR_MAP.get(time_period)
        if not academic_year:
            continue

        key = (urn, academic_year)
        if key in seen:
            continue
        seen.add(key)

        rows.append((
            urn, academic_year,
            _float(record.get("teachers_fte")),           # total_teachers_fte
            None,                                          # total_ta_fte (not in this dataset)
            _float(record.get("adults_fte")),              # total_support_fte (adults = teachers + support)
            _float(record.get("pupil_to_qual_teacher_ratio")),  # pupil_teacher_ratio
            None,                                          # mean_salary_teachers (not in this dataset)
            None,                                          # pct_teachers_qualified (not in this dataset)
            None,                                          # teacher_vacancies (not in this dataset)
            None,                                          # teacher_turnover_pct (not in this dataset)
        ))

    logger.info("Parsed %d workforce rows", len(rows))
    return rows


def load_workforce(rows, conn):
    valid_urns = _get_valid_urns(conn)
    rows = [r for r in rows if r[0] in valid_urns]
    logger.info("After FK filter: %d rows with valid URNs", len(rows))
    if not rows:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO schools.workforce (
                urn, academic_year,
                total_teachers_fte, total_ta_fte, total_support_fte,
                pupil_teacher_ratio, mean_salary_teachers,
                pct_teachers_qualified, teacher_vacancies, teacher_turnover_pct
            ) VALUES %s
            ON CONFLICT (urn, academic_year) DO UPDATE SET
                total_teachers_fte = EXCLUDED.total_teachers_fte,
                total_ta_fte = EXCLUDED.total_ta_fte,
                total_support_fte = EXCLUDED.total_support_fte,
                pupil_teacher_ratio = EXCLUDED.pupil_teacher_ratio,
                mean_salary_teachers = EXCLUDED.mean_salary_teachers,
                pct_teachers_qualified = EXCLUDED.pct_teachers_qualified,
                teacher_vacancies = EXCLUDED.teacher_vacancies,
                teacher_turnover_pct = EXCLUDED.teacher_turnover_pct
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d workforce rows", len(rows))


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        rows = download_and_parse()
        if rows:
            load_workforce(rows, conn)
    finally:
        conn.close()
    logger.info("Workforce ingestion complete")


if __name__ == "__main__":
    main()
