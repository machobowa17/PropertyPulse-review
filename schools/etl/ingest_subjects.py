#!/usr/bin/env python3
"""Ingest KS4 subject-level entries and grades into schools.subjects.

Downloads institution-level subject data from DfE EES.
Aggregates: total entries per subject per school, grade percentages.
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

# KS4 subject entries dataset
KS4_SUBJECTS_ID = "914fe46b-0626-4a8d-a7c6-da6edc40c306"
# KS5 subject entries dataset
KS5_SUBJECTS_ID = "0aa27be7-4958-4d9b-87c5-4af9ec6cd921"

BASE_URL = "https://explore-education-statistics.service.gov.uk/data-catalogue/data-set"

YEAR_MAP = {
    "202324": "2023-24",
    "202223": "2022-23",
    "202122": "2021-22",
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


def download_csv(dataset_id, label):
    url = f"{BASE_URL}/{dataset_id}/csv"
    logger.info("Downloading %s from %s", label, url)
    req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=900)
    return resp.read().decode("utf-8-sig", errors="replace")


def parse_ks4_subjects(csv_text):
    """Parse KS4 subject entries — aggregate per (school, year, subject).

    Each row is a grade level. We need:
    - 'Total exam entries' row for total entries
    - Grade '9' row for pct_grade_9
    - Grade '8' or '7' for grade_a_star proxy (grade 9 ≈ A*)
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    # Key: (urn, year, subject) → {entries, grade_9_count, etc.}
    data = defaultdict(lambda: {"entries": None, "grade_9": None, "grade_7_plus": None})

    for record in reader:
        if record.get("geographic_level") != "School":
            continue
        # Only GCSE
        if record.get("qualification_type") != "GCSE":
            continue

        urn = _int(record.get("school_urn"))
        if not urn:
            continue

        time_period = record.get("time_period", "").strip()
        academic_year = YEAR_MAP.get(time_period)
        if not academic_year:
            continue

        subject = record.get("subject", "").strip()
        if not subject:
            continue

        grade = record.get("grade", "").strip()
        count = _int(record.get("number_achieving"))

        key = (urn, academic_year, subject)

        if grade == "Total exam entries":
            data[key]["entries"] = count
        elif grade == "9":
            data[key]["grade_9"] = count
        elif grade == "7" and data[key].get("grade_7_plus") is None:
            data[key]["grade_7_plus"] = count

    # Build rows
    rows = []
    for (urn, year, subject), d in data.items():
        entries = d.get("entries")
        if not entries or entries < 1:
            continue

        grade_9 = d.get("grade_9")
        pct_9 = (grade_9 / entries * 100) if grade_9 is not None and entries else None

        rows.append((
            urn, year, "ks4", subject,
            entries,
            None,  # pct_grade_a_star — not directly available in GCSE 9-1
            None,  # pct_grade_a
            pct_9,
            None,  # avg_point_score
        ))

    logger.info("Parsed %d KS4 subject rows", len(rows))
    return rows


def load_subjects(rows, conn):
    valid_urns = _get_valid_urns(conn)
    rows = [r for r in rows if r[0] in valid_urns]
    logger.info("After FK filter: %d rows with valid URNs", len(rows))
    if not rows:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO schools.subjects (
                urn, academic_year, key_stage, subject_name,
                entries, pct_grade_a_star, pct_grade_a, pct_grade_9, avg_point_score
            ) VALUES %s
            ON CONFLICT (urn, academic_year, key_stage, subject_name) DO UPDATE SET
                entries = EXCLUDED.entries,
                pct_grade_a_star = EXCLUDED.pct_grade_a_star,
                pct_grade_a = EXCLUDED.pct_grade_a,
                pct_grade_9 = EXCLUDED.pct_grade_9,
                avg_point_score = EXCLUDED.avg_point_score
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d subject rows", len(rows))


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        # KS4 subjects
        csv_text = download_csv(KS4_SUBJECTS_ID, "KS4 subjects")
        rows = parse_ks4_subjects(csv_text)
        if rows:
            load_subjects(rows, conn)
    finally:
        conn.close()
    logger.info("Subjects ingestion complete")


if __name__ == "__main__":
    main()
