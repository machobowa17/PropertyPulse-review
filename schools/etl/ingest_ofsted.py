#!/usr/bin/env python3
"""Ingest Ofsted inspection data into schools.inspections.

Downloads the Ofsted Management Information CSV (state-funded schools)
and loads full inspection history.
Source: https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes
"""

import csv
import io
import logging
import os
import re
import sys
import urllib.request
from datetime import date

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property")

# Ofsted MI page URL — we scrape it for the latest CSV link
OFSTED_MI_PAGE = "https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes"

RATING_MAP = {
    "1": 1, "Outstanding": 1,
    "2": 2, "Good": 2,
    "3": 3, "Requires improvement": 3, "Requires Improvement": 3, "Satisfactory": 3,
    "4": 4, "Inadequate": 4, "Special Measures": 4, "Serious Weaknesses": 4,
    "9": None, "NULL": None, "": None, "N/A": None,
}


def _parse_rating(s):
    if s is None:
        return None
    s = s.strip()
    if s in RATING_MAP:
        return RATING_MAP[s]
    try:
        v = int(s)
        if 1 <= v <= 4:
            return v
    except (ValueError, TypeError):
        pass
    return None


def _parse_date(s):
    """Parse various date formats."""
    if not s or not s.strip():
        return None
    s = s.strip()
    # Try dd/mm/yyyy
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    # Try yyyy-mm-dd
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return s
    # Try dd-mm-yyyy
    m = re.match(r"(\d{2})-(\d{2})-(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def _parse_int(s):
    if not s or not s.strip():
        return None
    try:
        return int(s.strip())
    except (ValueError, TypeError):
        return None


def _parse_bool(s):
    if not s or not s.strip():
        return None
    s = s.strip().lower()
    if s in ("yes", "y", "true", "1", "met"):
        return True
    if s in ("no", "n", "false", "0", "not met"):
        return False
    return None


def download_ofsted_mi():
    """Download Ofsted MI CSV from gov.uk."""
    # First try to find the CSV download link from the page
    logger.info("Fetching Ofsted MI page to find CSV link...")
    req = urllib.request.Request(OFSTED_MI_PAGE, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=60)
    html = resp.read().decode("utf-8", errors="replace")

    # Look for CSV download links
    csv_links = re.findall(r'href="([^"]*\.csv[^"]*)"', html)
    if not csv_links:
        # Try assets links
        csv_links = re.findall(r'href="(/government/uploads/[^"]*\.csv)"', html)

    if not csv_links:
        # Try the direct asset URL pattern
        csv_links = re.findall(r'href="(https://assets\.publishing\.service\.gov\.uk/[^"]*\.csv)"', html)

    if csv_links:
        # Pick the most recent / largest CSV
        csv_url = csv_links[0]
        if csv_url.startswith("/"):
            csv_url = "https://www.gov.uk" + csv_url
        logger.info("Found CSV link: %s", csv_url)
    else:
        # Fallback: try known URL patterns
        csv_url = "https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes"
        logger.warning("Could not find CSV link, using page URL")

    req = urllib.request.Request(csv_url, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=120)
    return resp.read().decode("utf-8-sig", errors="replace")


def load_from_file(filepath, conn):
    """Load from a local CSV file."""
    logger.info("Loading from local file: %s", filepath)
    with open(filepath, "r", encoding="utf-8-sig") as f:
        parse_and_load(f.read(), conn)


def parse_and_load(csv_text, conn):
    """Parse Ofsted MI CSV and load into schools.inspections."""
    reader = csv.DictReader(io.StringIO(csv_text))

    # Auto-detect column names (Ofsted changes them periodically)
    fieldnames = reader.fieldnames
    if not fieldnames:
        logger.error("No CSV headers found")
        return

    # Map common column name variants
    def _find_col(candidates):
        for c in candidates:
            for f in fieldnames:
                if c.lower() in f.lower():
                    return f
        return None

    urn_col = _find_col(["URN"])
    date_col = _find_col(["Inspection start date", "Event start date", "Inspection date"])
    overall_col = _find_col(["Overall effectiveness", "Overall judgement"])
    category_col = _find_col(["Inspection type", "Event type", "Type of inspection"])
    qoe_col = _find_col(["Quality of education"])
    ba_col = _find_col(["Behaviour and attitudes"])
    pd_col = _find_col(["Personal development"])
    lm_col = _find_col(["Leadership and management", "Effectiveness of leadership"])
    ey_col = _find_col(["Early years provision", "Effectiveness of early years"])
    sf_col = _find_col(["Sixth form provision", "16-19 study programmes"])
    safeguarding_col = _find_col(["Safeguarding is effective"])
    prev_col = _find_col(["Previous inspection number", "Previous overall effectiveness"])

    if not urn_col:
        logger.error("Cannot find URN column in: %s", fieldnames)
        return

    logger.info("Detected columns: URN=%s, date=%s, overall=%s", urn_col, date_col, overall_col)

    rows = []
    for record in reader:
        urn = _parse_int(record.get(urn_col))
        if not urn:
            continue

        inspection_date = _parse_date(record.get(date_col)) if date_col else None
        if not inspection_date:
            continue

        overall = _parse_rating(record.get(overall_col)) if overall_col else None
        rating_text = record.get(overall_col, "").strip() if overall_col else None
        category = record.get(category_col, "").strip() if category_col else None

        rows.append((
            urn,
            "Ofsted",
            inspection_date,
            overall,
            rating_text,
            category,
            None,  # report_url
            _parse_rating(record.get(qoe_col)) if qoe_col else None,
            _parse_rating(record.get(ba_col)) if ba_col else None,
            _parse_rating(record.get(pd_col)) if pd_col else None,
            _parse_rating(record.get(lm_col)) if lm_col else None,
            _parse_rating(record.get(ey_col)) if ey_col else None,
            _parse_rating(record.get(sf_col)) if sf_col else None,
            _parse_bool(record.get(safeguarding_col)) if safeguarding_col else None,
            _parse_rating(record.get(prev_col)) if prev_col else None,
        ))

    logger.info("Parsed %d inspection records", len(rows))

    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS schools")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS schools.inspections (
                id               SERIAL PRIMARY KEY,
                urn              INTEGER NOT NULL,
                inspection_body  TEXT NOT NULL DEFAULT 'Ofsted',
                inspection_date  DATE NOT NULL,
                overall_rating   SMALLINT,
                rating_text      TEXT,
                category         TEXT,
                report_url       TEXT,
                quality_of_education    SMALLINT,
                behaviour_attitudes     SMALLINT,
                personal_development    SMALLINT,
                leadership_management   SMALLINT,
                early_years             SMALLINT,
                sixth_form              SMALLINT,
                safeguarding            BOOLEAN,
                previous_rating         SMALLINT,
                UNIQUE (urn, inspection_date, inspection_body)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_insp_urn ON schools.inspections (urn)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_insp_date ON schools.inspections (urn, inspection_date DESC)")

        # Upsert
        execute_values(
            cur,
            """
            INSERT INTO schools.inspections (
                urn, inspection_body, inspection_date, overall_rating, rating_text,
                category, report_url, quality_of_education, behaviour_attitudes,
                personal_development, leadership_management, early_years,
                sixth_form, safeguarding, previous_rating
            ) VALUES %s
            ON CONFLICT (urn, inspection_date, inspection_body) DO UPDATE SET
                overall_rating = EXCLUDED.overall_rating,
                rating_text = EXCLUDED.rating_text,
                category = EXCLUDED.category,
                quality_of_education = EXCLUDED.quality_of_education,
                behaviour_attitudes = EXCLUDED.behaviour_attitudes,
                personal_development = EXCLUDED.personal_development,
                leadership_management = EXCLUDED.leadership_management,
                early_years = EXCLUDED.early_years,
                sixth_form = EXCLUDED.sixth_form,
                safeguarding = EXCLUDED.safeguarding,
                previous_rating = EXCLUDED.previous_rating
            """,
            rows,
            page_size=5000,
        )

        conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM schools.inspections")
        count = cur.fetchone()[0]
        logger.info("schools.inspections: %d total records", count)
        cur.execute("SELECT COUNT(DISTINCT urn) FROM schools.inspections")
        school_count = cur.fetchone()[0]
        logger.info("schools.inspections: %d distinct schools", school_count)


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else None
    conn = psycopg2.connect(DATABASE_URL)
    try:
        if filepath:
            load_from_file(filepath, conn)
        else:
            csv_text = download_ofsted_mi()
            parse_and_load(csv_text, conn)
    finally:
        conn.close()
    logger.info("Ofsted ingestion complete")


if __name__ == "__main__":
    main()
