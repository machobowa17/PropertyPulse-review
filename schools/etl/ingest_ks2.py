#!/usr/bin/env python3
"""Ingest KS2 school-level performance data into schools.ks2_results.

Downloads from DfE Explore Education Statistics — institution-level KS2 data.
CSV contains multi-year data with rows per school × subject × year.
We aggregate per (school, year):
  - Reading expected% + scaled score + progress
  - Maths expected% + scaled score + progress
  - Writing expected% + progress
  - Combined RWM expected% + higher%
"""

import csv
import io
import logging
import os
import urllib.request
from collections import defaultdict

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property",
)

KS2_DATASET_ID = "b361b4c3-21b9-46fd-9126-b8060c6a40e2"
BASE_URL = "https://explore-education-statistics.service.gov.uk/data-catalogue/data-set"

YEAR_MAP = {
    "202324": "2023-24",
    "202223": "2022-23",
    "202122": "2021-22",
    "202021": "2020-21",
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
    url = f"{BASE_URL}/{KS2_DATASET_ID}/csv"
    logger.info("Downloading KS2 from %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=600)
    csv_text = resp.read().decode("utf-8-sig", errors="replace")

    reader = csv.DictReader(io.StringIO(csv_text))
    # Key: (urn, academic_year) → dict of aggregated fields
    school_data = defaultdict(dict)

    for record in reader:
        if record.get("geographic_level") != "School":
            continue
        if record.get("breakdown_topic") != "All pupils":
            continue

        urn = _int(record.get("school_urn"))
        if not urn:
            continue

        time_period = record.get("time_period", "").strip()
        academic_year = YEAR_MAP.get(time_period)
        if not academic_year:
            continue

        subject = record.get("subject", "").strip()
        exp_pct = _float(record.get("expected_standard_pupil_percent"))
        higher_pct = _float(record.get("higher_standard_pupil_percent"))
        scaled_score = _float(record.get("average_scaled_score"))
        progress = _float(record.get("progress_measure_score"))

        key = (urn, academic_year)
        d = school_data[key]
        d["urn"] = urn
        d["academic_year"] = academic_year

        if subject == "Reading":
            d["pct_reading_expected"] = exp_pct
            d["reading_scaled_score"] = scaled_score
            d["reading_progress"] = progress
        elif subject == "Writing":
            d["pct_writing_expected"] = exp_pct
            d["writing_progress"] = progress
        elif subject == "Maths":
            d["pct_maths_expected"] = exp_pct
            d["maths_scaled_score"] = scaled_score
            d["maths_progress"] = progress
        elif "reading" in subject.lower() and "writing" in subject.lower() and "maths" in subject.lower():
            d["pct_rwm_expected"] = exp_pct
            d["pct_rwm_higher"] = higher_pct

    # Build rows
    rows = []
    for (urn, year), d in school_data.items():
        if not any(d.get(k) is not None for k in ("pct_reading_expected", "pct_maths_expected", "pct_rwm_expected")):
            continue
        rows.append((
            urn, year,
            d.get("reading_scaled_score"),
            d.get("maths_scaled_score"),
            d.get("pct_reading_expected"),
            d.get("pct_maths_expected"),
            d.get("pct_writing_expected"),
            d.get("pct_rwm_expected"),
            d.get("pct_rwm_higher"),
            d.get("reading_progress"),
            d.get("writing_progress"),
            d.get("maths_progress"),
            None,  # cohort_size
            None,  # pct_disadvantaged
        ))

    logger.info("Parsed %d school-year KS2 results", len(rows))
    return rows


def load_ks2(rows, conn):
    valid_urns = _get_valid_urns(conn)
    rows = [r for r in rows if r[0] in valid_urns]
    logger.info("After FK filter: %d rows with valid URNs", len(rows))
    if not rows:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO schools.ks2_results (
                urn, academic_year,
                reading_scaled_score, maths_scaled_score,
                pct_reading_expected, pct_maths_expected, pct_writing_expected,
                pct_rwm_expected, pct_rwm_higher,
                reading_progress, writing_progress, maths_progress,
                cohort_size, pct_disadvantaged
            ) VALUES %s
            ON CONFLICT (urn, academic_year) DO UPDATE SET
                reading_scaled_score = EXCLUDED.reading_scaled_score,
                maths_scaled_score = EXCLUDED.maths_scaled_score,
                pct_reading_expected = EXCLUDED.pct_reading_expected,
                pct_maths_expected = EXCLUDED.pct_maths_expected,
                pct_writing_expected = EXCLUDED.pct_writing_expected,
                pct_rwm_expected = EXCLUDED.pct_rwm_expected,
                pct_rwm_higher = EXCLUDED.pct_rwm_higher,
                reading_progress = EXCLUDED.reading_progress,
                writing_progress = EXCLUDED.writing_progress,
                maths_progress = EXCLUDED.maths_progress
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d KS2 results", len(rows))


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        rows = download_and_parse()
        if rows:
            load_ks2(rows, conn)
    finally:
        conn.close()
    logger.info("KS2 ingestion complete")


if __name__ == "__main__":
    main()
