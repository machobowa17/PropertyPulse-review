#!/usr/bin/env python3
"""Backfill Ofsted inspections with category and previous_rating.

The Ofsted MI "latest inspections" CSV has two inspection sections per row:
1. "Latest full inspection" (older framework columns)
2. "Latest OEIF graded inspection" (current framework columns)

The original ingest_ofsted.py only reads one section. This script reads the
correct OEIF columns and backfills missing data:
- category (from "Inspection type of latest OEIF graded inspection")
- previous_rating (computed by ordering inspections chronologically)
- report_url (from "Web Link" column)
"""

import csv
import io
import logging
import os
import re
import urllib.request

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property",
)

OFSTED_MI_PAGE = "https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes"


def _parse_int(s):
    if not s or not s.strip() or s.strip() in ("NULL", "N/A", ""):
        return None
    try:
        return int(s.strip())
    except (ValueError, TypeError):
        return None


def _parse_date(s):
    if not s or not s.strip() or s.strip() in ("NULL", "N/A", ""):
        return None
    s = s.strip()
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return s
    return None


def download_latest_csv():
    """Download the 'latest inspections' CSV from Ofsted MI page."""
    logger.info("Fetching Ofsted MI page...")
    req = urllib.request.Request(OFSTED_MI_PAGE, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=60)
    html = resp.read().decode("utf-8", errors="replace")

    csv_links = re.findall(r'href="(https://assets[^"]*\.csv)"', html)
    # First link is typically the "latest inspections" CSV
    latest_links = [l for l in csv_links if "latest" in l.lower()]
    if not latest_links:
        latest_links = csv_links

    if not latest_links:
        raise RuntimeError("No CSV links found on Ofsted MI page")

    csv_url = latest_links[0]
    logger.info("Downloading: %s", csv_url)
    req = urllib.request.Request(csv_url, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=120)
    return resp.read().decode("utf-8-sig", errors="replace")


def backfill_category_and_url(csv_text, conn):
    """Backfill category and report_url from latest inspections CSV."""
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []

    # Collect updates for category and report_url
    updates = []
    for record in reader:
        urn = _parse_int(record.get("URN"))
        if not urn:
            continue

        # Get inspection date — try OEIF section first, then full inspection
        inspection_date = _parse_date(
            record.get("Inspection start date of latest OEIF graded inspection")
        ) or _parse_date(
            record.get("Inspection start date")
        )
        if not inspection_date:
            continue

        # Category from OEIF section or full inspection section
        category = (
            record.get("Inspection type of latest OEIF graded inspection", "").strip()
            or record.get("Inspection type", "").strip()
        ) or None
        if category == "NULL":
            category = None

        # Report URL
        report_url = (record.get("Web Link (opens in new window)") or "").strip() or None
        if report_url == "NULL":
            report_url = None

        if category or report_url:
            updates.append((category, report_url, urn, inspection_date))

    logger.info("Collected %d category/URL updates", len(updates))

    if updates:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TEMP TABLE _ofsted_backfill (
                    category TEXT,
                    report_url TEXT,
                    urn INTEGER,
                    inspection_date DATE
                ) ON COMMIT DROP
            """)
            execute_values(
                cur,
                "INSERT INTO _ofsted_backfill (category, report_url, urn, inspection_date) VALUES %s",
                updates,
                page_size=5000,
            )
            # Update category where it's NULL
            cur.execute("""
                UPDATE schools.inspections i
                SET category = b.category
                FROM _ofsted_backfill b
                WHERE i.urn = b.urn AND i.inspection_date = b.inspection_date
                AND b.category IS NOT NULL AND (i.category IS NULL OR i.category = '')
            """)
            cat_count = cur.rowcount
            logger.info("Updated %d rows with category", cat_count)

            # Update report_url where it's NULL
            cur.execute("""
                UPDATE schools.inspections i
                SET report_url = b.report_url
                FROM _ofsted_backfill b
                WHERE i.urn = b.urn AND i.inspection_date = b.inspection_date
                AND b.report_url IS NOT NULL AND (i.report_url IS NULL OR i.report_url = '')
            """)
            url_count = cur.rowcount
            logger.info("Updated %d rows with report_url", url_count)

            conn.commit()


def backfill_previous_rating(conn):
    """Compute previous_rating by looking at chronologically earlier inspections."""
    with conn.cursor() as cur:
        cur.execute("""
            WITH ranked AS (
                SELECT
                    urn,
                    inspection_date,
                    overall_rating,
                    LAG(overall_rating) OVER (PARTITION BY urn ORDER BY inspection_date) AS prev_rating
                FROM schools.inspections
                WHERE overall_rating IS NOT NULL
            )
            UPDATE schools.inspections i
            SET previous_rating = r.prev_rating
            FROM ranked r
            WHERE i.urn = r.urn AND i.inspection_date = r.inspection_date
            AND r.prev_rating IS NOT NULL
            AND i.previous_rating IS NULL
        """)
        count = cur.rowcount
        conn.commit()
        logger.info("Updated %d rows with previous_rating (from earlier inspections)", count)


def backfill_report_url_pattern(conn):
    """Construct report_url from URN for any remaining NULL report_urls."""
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE schools.inspections
            SET report_url = 'https://reports.ofsted.gov.uk/provider/16/' || urn
            WHERE report_url IS NULL AND inspection_body = 'Ofsted'
        """)
        count = cur.rowcount
        conn.commit()
        logger.info("Constructed %d report_urls from URN pattern", count)


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        csv_text = download_latest_csv()
        backfill_category_and_url(csv_text, conn)
        backfill_previous_rating(conn)
        backfill_report_url_pattern(conn)

        # Stats
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM schools.inspections WHERE category IS NOT NULL AND category != ''")
            logger.info("Category populated: %d", cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM schools.inspections WHERE previous_rating IS NOT NULL")
            logger.info("Previous rating populated: %d", cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM schools.inspections WHERE report_url IS NOT NULL")
            logger.info("Report URL populated: %d", cur.fetchone()[0])
    finally:
        conn.close()
    logger.info("Ofsted backfill complete")


if __name__ == "__main__":
    main()
