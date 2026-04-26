#!/usr/bin/env python3
"""Backfill teacher_turnover_pct in schools.workforce from DfE teacher turnover dataset.

Source: EES 'Teacher turnover - school level' (school-level, 303K rows, 2010-2024).
Computes: turnover_pct = (left_system + left_to_other_school) / total_fte * 100
"""

import csv
import io
import logging
import os
import urllib.request

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property",
)

TURNOVER_DATASET_ID = "1df9bfbf-b573-4f1d-ba87-06a36387f2e5"
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


def download_and_compute():
    url = f"{BASE_URL}/{TURNOVER_DATASET_ID}/csv"
    logger.info("Downloading teacher turnover from %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=600)
    csv_text = resp.read().decode("utf-8-sig", errors="replace")

    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    logger.info("CSV columns: %s", fieldnames[:20])

    updates = []
    seen = set()

    for record in reader:
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

        total_fte = _float(record.get("teacher_fte_in_census_year"))
        left_system = _float(record.get("left_the_state-funded_system"))
        left_other = _float(record.get("left_to_another_state-funded_school"))

        if total_fte and total_fte > 0 and left_system is not None and left_other is not None:
            turnover_pct = round((left_system + left_other) / total_fte * 100, 1)
            updates.append((turnover_pct, urn, academic_year))

    logger.info("Computed %d turnover updates", len(updates))
    return updates


def apply_updates(updates, conn):
    if not updates:
        return
    with conn.cursor() as cur:
        # Batch update using a temp table for efficiency
        cur.execute("""
            CREATE TEMP TABLE _turnover_updates (
                turnover_pct NUMERIC,
                urn INTEGER,
                academic_year TEXT
            ) ON COMMIT DROP
        """)
        from psycopg2.extras import execute_values
        execute_values(
            cur,
            "INSERT INTO _turnover_updates (turnover_pct, urn, academic_year) VALUES %s",
            updates,
            page_size=5000,
        )
        cur.execute("""
            UPDATE schools.workforce w
            SET teacher_turnover_pct = t.turnover_pct
            FROM _turnover_updates t
            WHERE w.urn = t.urn AND w.academic_year = t.academic_year
        """)
        updated = cur.rowcount
        conn.commit()
        logger.info("Updated %d workforce rows with teacher_turnover_pct", updated)


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        updates = download_and_compute()
        if updates:
            apply_updates(updates, conn)
    finally:
        conn.close()
    logger.info("Teacher turnover backfill complete")


if __name__ == "__main__":
    main()
