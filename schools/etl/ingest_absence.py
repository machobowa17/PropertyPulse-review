#!/usr/bin/env python3
"""Ingest school-level absence rates into schools.absence.

Source: DfE 'Pupil absence in schools in England' publication (EES).
Downloads CSV directly from the EES data catalogue API.
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

# EES data set for pupil absence
DATA_SET_ID = "1ef1689a-070a-4e0b-9314-512db23a3cc9"
CSV_URL = f"https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/{DATA_SET_ID}/csv"

YEAR_MAP = {
    "202425": "2024-25",
    "202324": "2023-24",
    "202223": "2022-23",
    "202122": "2021-22",
    "202021": "2020-21",
}


def _float(val):
    if not val or val.strip() in ("", "z", "x", "c", "k", "u", "ne", "supp", "na", "low", ".", "-"):
        return None
    try:
        return float(val.strip().rstrip("%"))
    except (ValueError, TypeError):
        return None


def _int(val):
    if not val or val.strip() in ("", "z", "x", "c", "k", "u", "ne", "supp", "na", "low", ".", "-"):
        return None
    try:
        return int(float(val.strip().replace(",", "")))
    except (ValueError, TypeError):
        return None


def _get_valid_urns(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT urn FROM schools.institutions")
        return {r[0] for r in cur.fetchall()}


def download_csv():
    """Download absence CSV from EES."""
    logger.info("Downloading absence CSV from %s", CSV_URL)
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=600)
    data = resp.read()
    logger.info("Downloaded %.1f MB", len(data) / 1e6)
    return data.decode("utf-8-sig", errors="replace")


def parse_absence(csv_text):
    reader = csv.DictReader(io.StringIO(csv_text))

    # Log available columns for debugging
    fieldnames = reader.fieldnames or []
    logger.info("CSV has %d columns. First 10: %s", len(fieldnames), fieldnames[:10])

    rows = []
    seen = set()

    for record in reader:
        if record.get("geographic_level") != "School":
            continue

        urn = _int(record.get("school_urn") or record.get("urn"))
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

        overall_absence = _float(record.get("sess_overall_percent"))
        authorised_absence = _float(record.get("sess_authorised_percent"))
        unauthorised_absence = _float(record.get("sess_unauthorised_percent"))
        persistent_absence = _float(record.get("enrolments_pa_10_exact_percent"))
        severe_absence = _float(record.get("enrolments_pa_50_exact_percent"))
        possible_sessions = _int(record.get("sess_possible"))
        overall_sessions = _int(record.get("sess_overall"))

        rows.append((
            urn, academic_year,
            overall_absence,
            authorised_absence,
            unauthorised_absence,
            persistent_absence,
            severe_absence,
            possible_sessions,
            overall_sessions,
        ))

    logger.info("Parsed %d absence rows", len(rows))
    return rows


def ensure_table(conn):
    """Create the absence table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schools.absence (
                urn                    INTEGER NOT NULL REFERENCES schools.institutions(urn),
                academic_year          TEXT NOT NULL,
                overall_absence_pct    REAL,
                authorised_absence_pct REAL,
                unauthorised_absence_pct REAL,
                persistent_absence_pct REAL,
                severe_absence_pct     REAL,
                possible_sessions      INTEGER,
                overall_sessions       INTEGER,
                PRIMARY KEY (urn, academic_year)
            );
            CREATE INDEX IF NOT EXISTS idx_absence_urn ON schools.absence (urn);
        """)
        conn.commit()
    logger.info("Ensured schools.absence table exists")


def load_absence(rows, conn):
    valid_urns = _get_valid_urns(conn)
    rows = [r for r in rows if r[0] in valid_urns]
    logger.info("After FK filter: %d rows with valid URNs", len(rows))
    if not rows:
        return
    with conn.cursor() as cur:
        cur.execute("DELETE FROM schools.absence")
        execute_values(
            cur,
            """
            INSERT INTO schools.absence (
                urn, academic_year,
                overall_absence_pct, authorised_absence_pct, unauthorised_absence_pct,
                persistent_absence_pct, severe_absence_pct,
                possible_sessions, overall_sessions
            ) VALUES %s
            ON CONFLICT (urn, academic_year) DO UPDATE SET
                overall_absence_pct = EXCLUDED.overall_absence_pct,
                authorised_absence_pct = EXCLUDED.authorised_absence_pct,
                unauthorised_absence_pct = EXCLUDED.unauthorised_absence_pct,
                persistent_absence_pct = EXCLUDED.persistent_absence_pct,
                severe_absence_pct = EXCLUDED.severe_absence_pct,
                possible_sessions = EXCLUDED.possible_sessions,
                overall_sessions = EXCLUDED.overall_sessions
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d absence rows", len(rows))


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        ensure_table(conn)
        csv_text = download_csv()
        rows = parse_absence(csv_text)
        if rows:
            load_absence(rows, conn)
    finally:
        conn.close()
    logger.info("Absence ingestion complete")


if __name__ == "__main__":
    main()
