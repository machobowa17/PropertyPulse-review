#!/usr/bin/env python3
"""Ingest 16-18 destination measures into schools.destinations.

Downloads institution-level data from DfE EES.
Filters: data_type='Percentage', breakdown_topic='Total', cohort_level_group='Total'
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

DESTINATIONS_DATASET_ID = "7455a8e4-3271-4cea-89bb-b0adbe88b372"
BASE_URL = "https://explore-education-statistics.service.gov.uk/data-catalogue/data-set"

YEAR_MAP = {
    "202223": "2022-23",
    "202122": "2021-22",
    "202021": "2020-21",
    "201920": "2019-20",
    "201819": "2018-19",
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
    url = f"{BASE_URL}/{DESTINATIONS_DATASET_ID}/csv"
    logger.info("Downloading destinations from %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=600)
    csv_text = resp.read().decode("utf-8-sig", errors="replace")

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    seen = set()

    for record in reader:
        if record.get("geographic_level") != "School":
            continue
        if record.get("data_type") != "Percentage":
            continue
        if record.get("breakdown_topic") != "Total":
            continue
        if record.get("cohort_level_group") != "Total":
            continue

        urn = _int(record.get("school_urn"))
        if not urn:
            continue

        time_period = record.get("time_period", "").strip()
        academic_year = YEAR_MAP.get(time_period, time_period)

        key = (urn, academic_year)
        if key in seen:
            continue
        seen.add(key)

        rows.append((
            urn, academic_year,
            "ks5",  # destination_level — this is 16-18 data
            _float(record.get("overall")),       # pct_education_employment
            _float(record.get("fe")),             # pct_further_education
            _float(record.get("he")),             # pct_higher_education
            None,                                  # pct_russell_group (not in this dataset)
            None,                                  # pct_oxbridge
            None,                                  # pct_top_third_uni
            _float(record.get("appren")),         # pct_apprenticeships
            _float(record.get("all_work")),       # pct_employment
            _float(record.get("all_notsust")),    # pct_not_sustained
        ))

    logger.info("Parsed %d destination results", len(rows))
    return rows


def load_destinations(rows, conn):
    valid_urns = _get_valid_urns(conn)
    rows = [r for r in rows if r[0] in valid_urns]
    logger.info("After FK filter: %d rows with valid URNs", len(rows))
    if not rows:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO schools.destinations (
                urn, academic_year, destination_level,
                pct_education_employment, pct_further_education,
                pct_higher_education, pct_russell_group, pct_oxbridge,
                pct_top_third_uni, pct_apprenticeships,
                pct_employment, pct_not_sustained
            ) VALUES %s
            ON CONFLICT (urn, academic_year, destination_level) DO UPDATE SET
                pct_education_employment = EXCLUDED.pct_education_employment,
                pct_further_education = EXCLUDED.pct_further_education,
                pct_higher_education = EXCLUDED.pct_higher_education,
                pct_russell_group = EXCLUDED.pct_russell_group,
                pct_oxbridge = EXCLUDED.pct_oxbridge,
                pct_top_third_uni = EXCLUDED.pct_top_third_uni,
                pct_apprenticeships = EXCLUDED.pct_apprenticeships,
                pct_employment = EXCLUDED.pct_employment,
                pct_not_sustained = EXCLUDED.pct_not_sustained
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d destination results", len(rows))


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        rows = download_and_parse()
        if rows:
            load_destinations(rows, conn)
    finally:
        conn.close()
    logger.info("Destinations ingestion complete")


if __name__ == "__main__":
    main()
