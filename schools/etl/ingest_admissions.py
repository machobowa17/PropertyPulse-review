#!/usr/bin/env python3
"""Ingest school admissions data into schools.admissions.

Source: DfE 'Secondary and primary school applications and offers' (EES).
Downloads ZIP containing school-level supporting data CSV.
Uses LAEstab (LA code + Estab number) to match to URN via institutions table.
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

# EES release for secondary and primary school applications and offers
RELEASE_ID = "5ed40264-1835-4848-a29b-446ed6c075c2"
ZIP_URL = f"https://content.explore-education-statistics.service.gov.uk/api/releases/{RELEASE_ID}/files?fromPage=ReleaseDownloads"

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


def _build_laestab_to_urn():
    """Build LAEstab → URN mapping from GIAS daily extract."""
    from datetime import datetime, timedelta
    gias_base = "https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public/edubasealldata{date}.csv"
    for days_back in range(5):
        target_date = datetime.now() - timedelta(days=days_back)
        date_str = target_date.strftime("%Y%m%d")
        url = gias_base.format(date=date_str)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
            resp = urllib.request.urlopen(req, timeout=300)
            data = resp.read().decode("utf-8-sig", errors="replace")
            break
        except Exception:
            continue
    else:
        logger.warning("Could not download GIAS CSV for LAEstab mapping")
        return {}

    reader = csv.DictReader(io.StringIO(data))
    mapping = {}
    for record in reader:
        urn = _int(record.get("URN"))
        la_code = (record.get("LA (code)") or "").strip()
        estab = (record.get("EstablishmentNumber") or "").strip()
        if urn and la_code and estab:
            laestab = f"{la_code}{estab}"
            mapping[laestab] = urn
    logger.info("Built LAEstab→URN mapping: %d entries", len(mapping))
    return mapping


def download_zip():
    """Download the admissions ZIP from EES."""
    logger.info("Downloading admissions ZIP from %s", ZIP_URL)
    req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=600)
    data = resp.read()
    logger.info("Downloaded %.1f MB", len(data) / 1e6)
    return data


def find_school_level_csv(zip_data):
    """Find the school-level CSV inside the ZIP."""
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        names = zf.namelist()
        logger.info("ZIP contains %d files: %s", len(names), names[:10])

        # Look for school-level supporting data file
        candidates = [
            n for n in names
            if "school" in n.lower() and n.endswith(".csv")
        ]
        if not candidates:
            candidates = [
                n for n in names
                if "supporting" in n.lower() and n.endswith(".csv")
            ]
        if not candidates:
            candidates = [n for n in names if n.endswith(".csv")]

        if not candidates:
            raise RuntimeError(f"No CSV found in ZIP. Files: {names}")

        # Prefer the largest CSV (likely the school-level one)
        best = None
        best_size = 0
        for c in candidates:
            info = zf.getinfo(c)
            if info.file_size > best_size:
                best = c
                best_size = info.file_size

        logger.info("Using CSV: %s (%.1f MB)", best, best_size / 1e6)
        with zf.open(best) as f:
            return f.read().decode("utf-8-sig", errors="replace")


def parse_admissions(csv_text, valid_urns, laestab_to_urn):
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    logger.info("CSV has %d columns. Sample: %s", len(fieldnames), fieldnames[:20])

    rows = []
    seen = set()
    urn_found = 0
    urn_missing = 0

    for record in reader:
        # Filter to school level
        geo_level = record.get("geographic_level", "").strip()
        if geo_level and geo_level != "School":
            continue

        # Try URN first
        urn = _int(record.get("urn") or record.get("URN") or record.get("school_urn"))

        # If no URN, try LAEstab mapping
        if not urn:
            laestab = (
                record.get("school_laestab_as_used")
                or record.get("laestab")
                or record.get("school_laestab")
                or ""
            ).strip()
            if laestab:
                urn = laestab_to_urn.get(laestab)

        if not urn:
            urn_missing += 1
            continue

        if urn not in valid_urns:
            continue

        urn_found += 1

        time_period = record.get("time_period", "").strip()
        academic_year = YEAR_MAP.get(time_period)
        if not academic_year:
            continue

        # Year group from school_phase (primary = Reception, secondary = Year 7)
        school_phase = (record.get("school_phase") or "").strip()
        year_group = (
            record.get("year_group")
            or record.get("admission_year")
            or ""
        ).strip() or None
        if not year_group and school_phase:
            if "primary" in school_phase.lower():
                year_group = "Reception"
            elif "secondary" in school_phase.lower():
                year_group = "Year 7"

        key = (urn, academic_year, year_group or "")
        if key in seen:
            continue
        seen.add(key)

        # Applications (total number of times school was listed as any preference)
        apps = _int(
            record.get("times_put_as_any_preferred_school")
            or record.get("number_of_applications")
            or record.get("applications_received")
        )
        first_pref = _int(
            record.get("number_1st_preference_offers")
            or record.get("number_of_first_preferences")
        )
        second_pref = _int(
            record.get("number_2nd_preference_offers")
            or record.get("number_of_second_preferences")
        )
        third_pref = _int(
            record.get("number_3rd_preference_offers")
            or record.get("number_of_third_preferences")
        )

        # Offers
        offers = _int(
            record.get("total_number_places_offered")
            or record.get("number_preferred_offers")
            or record.get("offers_made")
        )

        # Oversubscribed
        is_oversubscribed = None
        if apps and offers:
            is_oversubscribed = apps > offers

        rows.append((
            urn, academic_year, year_group or "",
            apps, first_pref, second_pref, third_pref,
            offers, is_oversubscribed,
            None,  # last_distance_offered — from LA data, not in EES
        ))

    logger.info("Parsed %d admissions rows (URN found: %d, missing: %d)", len(rows), urn_found, urn_missing)
    return rows


def load_admissions(rows, conn):
    if not rows:
        return
    with conn.cursor() as cur:
        cur.execute("DELETE FROM schools.admissions")
        execute_values(
            cur,
            """
            INSERT INTO schools.admissions (
                urn, academic_year, year_group,
                applications_received, first_preference, second_preference, third_preference,
                offers_made, is_oversubscribed, last_distance_offered
            ) VALUES %s
            ON CONFLICT (urn, academic_year, year_group) DO UPDATE SET
                applications_received = EXCLUDED.applications_received,
                first_preference = EXCLUDED.first_preference,
                second_preference = EXCLUDED.second_preference,
                third_preference = EXCLUDED.third_preference,
                offers_made = EXCLUDED.offers_made,
                is_oversubscribed = EXCLUDED.is_oversubscribed,
                last_distance_offered = EXCLUDED.last_distance_offered
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d admissions rows", len(rows))


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        valid_urns = _get_valid_urns(conn)
        logger.info("Have %d valid URNs", len(valid_urns))
        laestab_to_urn = _build_laestab_to_urn()
        zip_data = download_zip()
        csv_text = find_school_level_csv(zip_data)
        rows = parse_admissions(csv_text, valid_urns, laestab_to_urn)
        if rows:
            load_admissions(rows, conn)
    finally:
        conn.close()
    logger.info("Admissions ingestion complete")


if __name__ == "__main__":
    main()
