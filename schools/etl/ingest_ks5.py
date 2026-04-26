#!/usr/bin/env python3
"""Ingest KS5 (16-18) school-level performance data into schools.ks5_results.

Downloads from DfE Explore Education Statistics — institution-level 16-18 data.
CSV contains multi-year data with multiple cohort rows per school per year.
We aggregate Academic + A level + Applied general per (school, year).
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

# Single dataset contains multiple years
KS5_DATASET_ID = "aae22548-56ea-40db-b710-62231d3f0e0e"
BASE_URL = "https://explore-education-statistics.service.gov.uk/data-catalogue/data-set"

# Map time_period codes to our academic_year labels
YEAR_MAP = {
    "202324": "2023-24",
    "202223": "2022-23",
    "202122": "2021-22",
    "202021": "2020-21",
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
    """Download KS5 CSV and parse into rows keyed by (urn, year)."""
    url = f"{BASE_URL}/{KS5_DATASET_ID}/csv"
    logger.info("Downloading KS5 from %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=600)
    csv_text = resp.read().decode("utf-8-sig", errors="replace")

    reader = csv.DictReader(io.StringIO(csv_text))
    # Key: (urn, academic_year) → dict of aggregated fields
    school_year_data = defaultdict(dict)

    for record in reader:
        if record.get("geographic_level") != "School":
            continue
        if record.get("disadvantaged_status") != "All students":
            continue

        urn = _int(record.get("school_urn"))
        if not urn:
            continue

        time_period = record.get("time_period", "").strip()
        academic_year = YEAR_MAP.get(time_period)
        if not academic_year:
            continue

        cohort = record.get("cohort", "").strip()
        ppe = _float(record.get("points_per_entry"))
        pupil_count = _int(record.get("pupil_count"))

        key = (urn, academic_year)
        d = school_year_data[key]
        d["urn"] = urn
        d["academic_year"] = academic_year

        if cohort == "A level":
            d["avg_point_score_a"] = ppe
            d["cohort_size_a"] = pupil_count
        elif cohort == "Academic":
            d["avg_point_score_academic"] = ppe
        elif cohort == "Applied general":
            d["avg_point_score_applied"] = ppe

    # Build rows — skip entries with no meaningful data
    rows = []
    for (urn, year), d in school_year_data.items():
        if d.get("avg_point_score_a") is None and d.get("avg_point_score_academic") is None:
            continue
        rows.append((
            urn, year,
            d.get("avg_point_score_a"),
            d.get("avg_point_score_academic"),
            d.get("avg_point_score_applied"),
            d.get("cohort_size_a"),
        ))

    logger.info("Parsed %d school-year KS5 results across %d years",
                len(rows), len(YEAR_MAP))
    return rows


def load_ks5(rows, conn):
    valid_urns = _get_valid_urns(conn)
    rows = [r for r in rows if r[0] in valid_urns]
    logger.info("After FK filter: %d rows with valid URNs", len(rows))
    if not rows:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO schools.ks5_results (
                urn, academic_year,
                avg_point_score_a, avg_point_score_academic,
                avg_point_score_applied, cohort_size_a
            ) VALUES %s
            ON CONFLICT (urn, academic_year) DO UPDATE SET
                avg_point_score_a = EXCLUDED.avg_point_score_a,
                avg_point_score_academic = EXCLUDED.avg_point_score_academic,
                avg_point_score_applied = EXCLUDED.avg_point_score_applied,
                cohort_size_a = EXCLUDED.cohort_size_a
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d KS5 results", len(rows))


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        rows = download_and_parse()
        if rows:
            load_ks5(rows, conn)
    finally:
        conn.close()
    logger.info("KS5 ingestion complete")


if __name__ == "__main__":
    main()
