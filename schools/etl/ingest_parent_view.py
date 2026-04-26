#!/usr/bin/env python3
"""Ingest Ofsted Parent View survey data into schools.parent_view.

Downloads school-level CSV from gov.uk assets.
Computes % positive (Strongly Agree + Agree) for each survey question.
Latest available: April 2020 (CSV format discontinued after this).
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

# Parent View school-level CSVs (latest available in CSV format)
PARENT_VIEW_URLS = [
    ("2019-20", "https://assets.publishing.service.gov.uk/media/5f467191d3bf7f3d6eb4594e/Parent_View_Management_Information_School_Level_Data_as_at_6_April_2020.csv"),
    ("2018-19", "https://assets.publishing.service.gov.uk/media/5f467115d3bf7f3d6eb4594d/Parent_View_Management_Information_School_Level_Data_as_at_2_September_2019.csv"),
]


def _pct(val):
    """Parse a percentage string like '46%' → 46."""
    if not val or val.strip() in ("", "z", "x", "c", "k", "u", "ne", "supp", "na", "low", "-"):
        return None
    val = val.strip().rstrip("%")
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _int(val):
    if not val or val.strip() in ("", "z", "x", "c", "k", "u", "ne", "supp", "na", "low", "-"):
        return None
    val = val.strip().replace(",", "")
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _add_pcts(a, b):
    """Sum two percentage values, handling None."""
    if a is None and b is None:
        return None
    return (a or 0) + (b or 0)


def _get_valid_urns(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT urn FROM schools.institutions")
        return {r[0] for r in cur.fetchall()}


def download_and_parse():
    all_rows = []

    for academic_year, url in PARENT_VIEW_URLS:
        logger.info("Downloading Parent View %s from %s", academic_year, url)
        req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
        try:
            resp = urllib.request.urlopen(req, timeout=120)
        except Exception as e:
            logger.warning("Failed to download %s: %s", academic_year, e)
            continue
        csv_text = resp.read().decode("utf-8-sig", errors="replace")

        reader = csv.DictReader(io.StringIO(csv_text))
        count = 0

        for record in reader:
            urn = _int(record.get("URN"))
            if not urn:
                continue

            submissions = _int(record.get("Submissions"))

            # Compute % positive (Strongly Agree + Agree) for each question
            # Column names use the question text prefix
            def positive(q_prefix):
                sa = _pct(record.get(f"{q_prefix} Strongly Agree"))
                a = _pct(record.get(f"{q_prefix} Agree"))
                return _add_pcts(sa, a)

            happy = positive("Q1. My child is happy at this school.")
            safe = positive("Q2. My child feels safe at this school.")
            behaviour = positive("Q3. The school makes sure its pupils are well behaved.")
            bullying = positive("Q4. My child has been bullied and the school dealt with the bullying effectively.")
            informed = positive("Q5. The school makes me aware of what my child will learn during the year.")
            concerns = positive("Q6. When I have raised concerns with the school they have been dealt with properly.")
            expectations = positive("Q8. The school has high expectations for my child.")
            doing_well = positive("Q9. My child does well at this school.")
            communication = positive("Q10. The school lets me know how my child is doing.")
            curriculum = positive("Q11. There is a good range of subjects available to my child at this school.")
            activities = positive("Q12. My child can take part in clubs and activities at this school.")
            development = positive("Q13. The school supports my child's wider personal development.")

            # Q14 is Yes/No, not Strongly Agree/Agree
            recommend = _pct(record.get("Q14. I would recommend this school to another parent. Yes"))

            all_rows.append((
                urn, academic_year, submissions,
                happy, safe, behaviour, bullying,
                expectations, doing_well, communication,
                curriculum, recommend,
                concerns, development,
                activities,
            ))
            count += 1

        logger.info("Parsed %d Parent View rows for %s", count, academic_year)

    logger.info("Total Parent View rows: %d", len(all_rows))
    return all_rows


def load_parent_view(rows, conn):
    valid_urns = _get_valid_urns(conn)
    rows = [r for r in rows if r[0] in valid_urns]
    logger.info("After FK filter: %d rows with valid URNs", len(rows))
    if not rows:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO schools.parent_view (
                urn, academic_year, total_responses,
                happy_at_school, feels_safe, good_behaviour, tackled_bullying,
                challenging_work, well_taught, good_communication,
                wide_curriculum, would_recommend,
                well_looked_after, supported_sen,
                good_leadership
            ) VALUES %s
            ON CONFLICT (urn, academic_year) DO UPDATE SET
                total_responses = EXCLUDED.total_responses,
                happy_at_school = EXCLUDED.happy_at_school,
                feels_safe = EXCLUDED.feels_safe,
                good_behaviour = EXCLUDED.good_behaviour,
                tackled_bullying = EXCLUDED.tackled_bullying,
                challenging_work = EXCLUDED.challenging_work,
                well_taught = EXCLUDED.well_taught,
                good_communication = EXCLUDED.good_communication,
                wide_curriculum = EXCLUDED.wide_curriculum,
                would_recommend = EXCLUDED.would_recommend,
                well_looked_after = EXCLUDED.well_looked_after,
                supported_sen = EXCLUDED.supported_sen,
                good_leadership = EXCLUDED.good_leadership
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d Parent View rows", len(rows))


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        rows = download_and_parse()
        if rows:
            load_parent_view(rows, conn)
    finally:
        conn.close()
    logger.info("Parent View ingestion complete")


if __name__ == "__main__":
    main()
