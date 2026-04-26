#!/usr/bin/env python3
"""Ingest school-level pupil demographics into schools.pupil_demographics.

Source: DfE 'Schools, pupils and their characteristics' publication.
Uses the school-level underlying data CSV from the ZIP download.

If the CSV file is not available locally, downloads the ZIP from EES.
"""

import csv
import io
import logging
import os
import urllib.request
import zipfile

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property",
)

# EES publication release ZIP
RELEASE_ID = "63491b17-2037-4533-b719-d3656aaf6ed5"
ZIP_URL = f"https://content.explore-education-statistics.service.gov.uk/api/releases/{RELEASE_ID}/files?fromPage=ReleaseDownloads"
SCHOOL_LEVEL_FILE = "supporting-files/spc_school_level_underlying_data_2025.csv"

YEAR_MAP = {
    "202425": "2024-25",
    "202324": "2023-24",
    "202223": "2022-23",
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


def get_csv_text(local_path=None):
    """Get CSV text from local file or download ZIP."""
    if local_path and os.path.exists(local_path):
        logger.info("Reading from local file: %s", local_path)
        with open(local_path, "rb") as f:
            return f.read().decode("utf-8-sig", errors="replace")

    logger.info("Downloading ZIP from %s", ZIP_URL)
    req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=600)
    zip_data = resp.read()
    logger.info("Downloaded %.1f MB", len(zip_data) / 1e6)

    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        with zf.open(SCHOOL_LEVEL_FILE) as f:
            return f.read().decode("utf-8-sig", errors="replace")


def parse_demographics(csv_text):
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = []
    seen = set()

    for record in reader:
        if record.get("geographic_level") != "School":
            continue

        urn = _int(record.get("urn"))
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

        total = _int(record.get("headcount of pupils"))
        boys = _int(record.get("headcount total male"))
        girls = _int(record.get("headcount total female"))

        pct_boys = round(boys / total * 100, 1) if boys and total else None
        pct_girls = round(girls / total * 100, 1) if girls and total else None

        # FSM
        pct_fsm = _float(record.get("% of pupils known to be eligible for free school meals"))

        # EAL
        pct_eal = _float(record.get("% of pupils whose first language is known or believed to be other than English"))

        # Ethnicity (aggregate broader groups)
        pct_white_british = _float(record.get("% of pupils classified as white British ethnic origin"))
        pct_chinese = _float(record.get("% of pupils classified as Chinese ethnic origin"))

        # Asian = Indian + Pakistani + Bangladeshi + Other Asian
        pct_indian = _float(record.get("% of pupils classified as Indian ethnic origin"))
        pct_pakistani = _float(record.get("% of pupils classified as Pakistani ethnic origin"))
        pct_bangladeshi = _float(record.get("% of pupils classified as Bangladeshi ethnic origin"))
        pct_other_asian = _float(record.get("% of pupils classified as any other Asian background ethnic origin"))
        pct_asian = None
        asian_parts = [v for v in [pct_indian, pct_pakistani, pct_bangladeshi, pct_other_asian] if v is not None]
        if asian_parts:
            pct_asian = round(sum(asian_parts), 1)

        # Black = Caribbean + African + Other Black
        pct_caribbean = _float(record.get("% of pupils classified as Caribbean ethnic origin"))
        pct_african = _float(record.get("% of pupils classified as African ethnic origin"))
        pct_other_black = _float(record.get("% of pupils classified as any other black background ethnic origin"))
        pct_black = None
        black_parts = [v for v in [pct_caribbean, pct_african, pct_other_black] if v is not None]
        if black_parts:
            pct_black = round(sum(black_parts), 1)

        # Mixed = W+BC + W+BA + W+Asian + Other Mixed
        pct_wbc = _float(record.get("% of pupils classified as white and black Caribbean ethnic origin"))
        pct_wba = _float(record.get("% of pupils classified as white and black African ethnic origin"))
        pct_w_asian = _float(record.get("% of pupils classified as white and Asian ethnic origin"))
        pct_other_mixed = _float(record.get("% of pupils classified as any other mixed background ethnic origin"))
        pct_mixed = None
        mixed_parts = [v for v in [pct_wbc, pct_wba, pct_w_asian, pct_other_mixed] if v is not None]
        if mixed_parts:
            pct_mixed = round(sum(mixed_parts), 1)

        pct_other_ethnic = _float(record.get("% of pupils classified as any other ethnic group ethnic origin"))

        rows.append((
            urn, academic_year, total,
            pct_boys, pct_girls,
            pct_fsm,
            None,  # pct_fsm_ever6 — not in this dataset
            pct_eal,
            None,  # pct_sen_support — not in this dataset
            None,  # pct_sen_ehcp — not in this dataset
            pct_white_british,
            pct_asian,
            pct_black,
            pct_mixed,
            pct_chinese,
            pct_other_ethnic,
            None,  # avg_class_size — in separate file
            None,  # pupil_teacher_ratio — in workforce dataset
        ))

    logger.info("Parsed %d demographics rows", len(rows))
    return rows


def load_demographics(rows, conn):
    valid_urns = _get_valid_urns(conn)
    rows = [r for r in rows if r[0] in valid_urns]
    logger.info("After FK filter: %d rows with valid URNs", len(rows))
    if not rows:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO schools.pupil_demographics (
                urn, academic_year, total_pupils,
                pct_boys, pct_girls,
                pct_fsm, pct_fsm_ever6,
                pct_eal,
                pct_sen_support, pct_sen_ehcp,
                pct_white_british, pct_asian, pct_black, pct_mixed,
                pct_chinese, pct_other_ethnic,
                avg_class_size, pupil_teacher_ratio
            ) VALUES %s
            ON CONFLICT (urn, academic_year) DO UPDATE SET
                total_pupils = EXCLUDED.total_pupils,
                pct_boys = EXCLUDED.pct_boys,
                pct_girls = EXCLUDED.pct_girls,
                pct_fsm = EXCLUDED.pct_fsm,
                pct_fsm_ever6 = EXCLUDED.pct_fsm_ever6,
                pct_eal = EXCLUDED.pct_eal,
                pct_sen_support = EXCLUDED.pct_sen_support,
                pct_sen_ehcp = EXCLUDED.pct_sen_ehcp,
                pct_white_british = EXCLUDED.pct_white_british,
                pct_asian = EXCLUDED.pct_asian,
                pct_black = EXCLUDED.pct_black,
                pct_mixed = EXCLUDED.pct_mixed,
                pct_chinese = EXCLUDED.pct_chinese,
                pct_other_ethnic = EXCLUDED.pct_other_ethnic,
                avg_class_size = EXCLUDED.avg_class_size,
                pupil_teacher_ratio = EXCLUDED.pupil_teacher_ratio
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d demographics rows", len(rows))


def main():
    # Check for local file first (extracted from ZIP)
    local_path = os.environ.get("DEMOGRAPHICS_CSV", "/tmp/supporting-files/spc_school_level_underlying_data_2025.csv")

    conn = psycopg2.connect(DATABASE_URL)
    try:
        csv_text = get_csv_text(local_path)
        rows = parse_demographics(csv_text)
        if rows:
            load_demographics(rows, conn)
    finally:
        conn.close()
    logger.info("Demographics ingestion complete")


if __name__ == "__main__":
    main()
