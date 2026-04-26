#!/usr/bin/env python3
"""Load historical Ofsted inspections from year-to-date CSVs.

Downloads end-of-year "all inspections" CSVs from 2020-2025.
Each CSV has inspections published that year.
Loads them into schools.inspections with UPSERT.
Then recomputes previous_rating from chronological order.
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

# End-of-year "all inspections YTD" CSVs (one per academic year)
HISTORY_CSVS = [
    # Each year's Jul/Aug/Sep CSV captures the full year of inspections
    ("2024-25", "https://assets.publishing.service.gov.uk/media/69c526cb23fcbcd838a6f743/Management_information_-_state-funded_schools_-_all_inspections_-_year_to_date_published_by_28_Feb_2026.csv"),
    ("2024-25b", "https://assets.publishing.service.gov.uk/media/68ee0f87a8398380cb4ad014/Management_information_-_state-funded_schools_-_all_inspections_-_year_to_date_published_by_30_Sep_2025.csv"),
    ("2023-24", "https://assets.publishing.service.gov.uk/media/66b330df49b9c0597fdb0bdb/Management_information_-_state-funded_schools_-_all_inspections_-_year_to_date_published_by_31_July_2024.csv"),
    ("2022-23", "https://assets.publishing.service.gov.uk/media/64d610a3742749000dde0667/Management_information_-_state-funded_schools_-_all_inspections_-_year_to_date_published_by_31_Jul_2023.csv"),
    ("2021-22", "https://assets.publishing.service.gov.uk/media/62f23565d3bf7f4fe8f0ba0c/Management_information_-_state-funded_schools_-_all_inspections_-_year_to_date_published_by_31_July_2022.csv"),
    ("2020-21", "https://assets.publishing.service.gov.uk/media/610d517ce90e0706c8fedeb5/Management_information_-_state-funded_schools_-_all_inspections_-_year_to_date_published_by_31_Jul_2021.csv"),
    ("2019-20", "https://assets.publishing.service.gov.uk/media/5f5891b18fa8f51061921e7c/Management_information_-_state-funded_schools_-_all_inspections_-_year_to_date_published_by_31_August_2020.csv"),
]

RATING_MAP = {
    "1": 1, "Outstanding": 1,
    "2": 2, "Good": 2,
    "3": 3, "Requires improvement": 3, "Requires Improvement": 3, "Satisfactory": 3,
    "4": 4, "Inadequate": 4, "Special Measures": 4, "Serious Weaknesses": 4,
    "9": None, "NULL": None, "": None, "N/A": None, "Not applicable": None,
}

BOOL_MAP = {
    "yes": True, "y": True, "true": True, "1": True, "met": True,
    "no": False, "n": False, "false": False, "0": False, "not met": False,
}


def _parse_rating(s):
    if s is None:
        return None
    s = s.strip()
    if s in RATING_MAP:
        return RATING_MAP[s]
    try:
        v = int(s)
        return v if 1 <= v <= 4 else None
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


def _parse_int(s):
    if not s or not s.strip() or s.strip() in ("NULL", "N/A", ""):
        return None
    try:
        return int(s.strip())
    except (ValueError, TypeError):
        return None


def _parse_bool(s):
    if not s or not s.strip() or s.strip() in ("NULL", "N/A", ""):
        return None
    return BOOL_MAP.get(s.strip().lower())


def _find_col(fieldnames, candidates):
    for c in candidates:
        for f in fieldnames:
            if c.lower() == f.lower():  # Exact match first
                return f
        for f in fieldnames:
            if c.lower() in f.lower():  # Substring match
                return f
    return None


def parse_all_inspections_csv(csv_text, label):
    """Parse an 'all inspections YTD' CSV which has one row per inspection."""
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    logger.info("[%s] Columns (%d): %s", label, len(fieldnames), fieldnames[:15])

    # Detect column names
    urn_col = _find_col(fieldnames, ["URN"])
    date_col = _find_col(fieldnames, ["Inspection start date"])
    type_col = _find_col(fieldnames, ["Inspection type"])
    web_col = _find_col(fieldnames, ["Web Link"])

    # New framework (OEIF) columns
    oe_col = _find_col(fieldnames, ["Overall effectiveness"])
    qoe_col = _find_col(fieldnames, ["Quality of education"])
    ba_col = _find_col(fieldnames, ["Behaviour and attitudes"])
    pd_col = _find_col(fieldnames, ["Personal development"])
    lm_col = _find_col(fieldnames, ["Leadership and management", "Leadership and governance"])
    ey_col = _find_col(fieldnames, ["Early years"])
    sf_col = _find_col(fieldnames, ["Sixth form provision", "Post-16 provision"])
    sg_col = _find_col(fieldnames, ["Safeguarding is effective", "Safeguarding standards"])

    logger.info("[%s] OE=%s, type=%s, date=%s", label, oe_col, type_col, date_col)

    rows = []
    for record in reader:
        urn = _parse_int(record.get(urn_col)) if urn_col else None
        if not urn:
            continue

        inspection_date = _parse_date(record.get(date_col)) if date_col else None
        if not inspection_date:
            continue

        overall = _parse_rating(record.get(oe_col)) if oe_col else None
        category = record.get(type_col, "").strip() if type_col else None
        if category in ("NULL", "N/A", ""):
            category = None

        report_url = record.get(web_col, "").strip() if web_col else None
        if report_url in ("NULL", "N/A", ""):
            report_url = None

        # Sub-judgements (may not exist in old-format CSVs)
        qoe = _parse_rating(record.get(qoe_col)) if qoe_col else None
        ba = _parse_rating(record.get(ba_col)) if ba_col else None
        pd_val = _parse_rating(record.get(pd_col)) if pd_col else None
        lm = _parse_rating(record.get(lm_col)) if lm_col else None
        ey = _parse_rating(record.get(ey_col)) if ey_col else None
        sf = _parse_rating(record.get(sf_col)) if sf_col else None

        # Safeguarding
        sg_raw = record.get(sg_col, "").strip() if sg_col else ""
        sg = _parse_bool(sg_raw)

        # Old framework: try to get overall from sub-judgements if missing
        # Old framework used "Achievement", "Behaviour", etc. with number ratings
        if overall is None:
            # Try old-style "Overall effectiveness" or compute from sub-judgements
            ach_col = _find_col(fieldnames, ["Achievement"])
            if ach_col:
                overall = _parse_rating(record.get(ach_col))

        rows.append((
            urn, "Ofsted", inspection_date, overall,
            record.get(oe_col, "").strip() if oe_col else None,  # rating_text
            category, report_url,
            qoe, ba, pd_val, lm, ey, sf, sg,
            None,  # previous_rating — computed later
        ))

    logger.info("[%s] Parsed %d inspection records", label, len(rows))
    return rows


def load_inspections(all_rows, conn):
    """Upsert all inspection rows into schools.inspections."""
    if not all_rows:
        return

    # Filter to valid URNs
    with conn.cursor() as cur:
        cur.execute("SELECT urn FROM schools.institutions")
        valid_urns = {r[0] for r in cur.fetchall()}

    filtered = [r for r in all_rows if r[0] in valid_urns]
    logger.info("After FK filter: %d of %d rows", len(filtered), len(all_rows))

    if not filtered:
        return

    with conn.cursor() as cur:
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
                overall_rating = COALESCE(EXCLUDED.overall_rating, schools.inspections.overall_rating),
                rating_text = COALESCE(EXCLUDED.rating_text, schools.inspections.rating_text),
                category = COALESCE(EXCLUDED.category, schools.inspections.category),
                report_url = COALESCE(EXCLUDED.report_url, schools.inspections.report_url),
                quality_of_education = COALESCE(EXCLUDED.quality_of_education, schools.inspections.quality_of_education),
                behaviour_attitudes = COALESCE(EXCLUDED.behaviour_attitudes, schools.inspections.behaviour_attitudes),
                personal_development = COALESCE(EXCLUDED.personal_development, schools.inspections.personal_development),
                leadership_management = COALESCE(EXCLUDED.leadership_management, schools.inspections.leadership_management),
                early_years = COALESCE(EXCLUDED.early_years, schools.inspections.early_years),
                sixth_form = COALESCE(EXCLUDED.sixth_form, schools.inspections.sixth_form),
                safeguarding = COALESCE(EXCLUDED.safeguarding, schools.inspections.safeguarding)
            """,
            filtered,
            page_size=5000,
        )
        conn.commit()
        logger.info("Upserted %d inspection rows", len(filtered))


def compute_previous_rating(conn):
    """Compute previous_rating from chronological inspection order."""
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
        """)
        count = cur.rowcount
        conn.commit()
        logger.info("Computed previous_rating for %d inspections", count)


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        all_rows = []
        for label, url in HISTORY_CSVS:
            logger.info("Downloading %s...", label)
            req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
            try:
                resp = urllib.request.urlopen(req, timeout=120)
                csv_text = resp.read().decode("utf-8-sig", errors="replace")
                rows = parse_all_inspections_csv(csv_text, label)
                all_rows.extend(rows)
            except Exception as e:
                logger.warning("Failed %s: %s", label, e)
                continue

        logger.info("Total historical rows: %d", len(all_rows))
        if all_rows:
            load_inspections(all_rows, conn)
            compute_previous_rating(conn)

        # Final stats
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM schools.inspections")
            logger.info("Total inspections: %d", cur.fetchone()[0])
            cur.execute("SELECT COUNT(DISTINCT urn) FROM schools.inspections")
            logger.info("Distinct schools: %d", cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM schools.inspections WHERE previous_rating IS NOT NULL")
            logger.info("With previous_rating: %d", cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM schools.inspections WHERE category IS NOT NULL AND category != ''")
            logger.info("With category: %d", cur.fetchone()[0])
    finally:
        conn.close()
    logger.info("Historical Ofsted load complete")


if __name__ == "__main__":
    main()
