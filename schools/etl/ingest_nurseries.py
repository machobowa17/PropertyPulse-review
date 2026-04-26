#!/usr/bin/env python3
"""Ingest nursery/childcare provider data into schools.nurseries.

Source: Ofsted Management Information — childcare providers and inspections.
Downloads CSV from gov.uk assets.

Note: The CSV has 2 preamble rows before the header row.
"""

import csv
import io
import logging
import os
import urllib.request
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property",
)

CSV_URL = (
    "https://assets.publishing.service.gov.uk/media/"
    "6973934c67ae94b3280137b4/"
    "Management_information_-_childcare_providers_and_inspections_"
    "-_most_recent_inspections_data_as_at_31_December_2025.csv"
)

RATING_MAP = {
    "1": "Outstanding",
    "2": "Good",
    "3": "Requires Improvement",
    "4": "Inadequate",
}


def _int(val):
    if not val or val.strip() in ("", "z", "x", "c", "k", "u", "ne", "supp", "na", "low", ".", "-", "N/A"):
        return None
    try:
        return int(float(val.strip().replace(",", "")))
    except (ValueError, TypeError):
        return None


def _date(val):
    if not val or val.strip() in ("", "N/A", "-"):
        return None
    val = val.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(val, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def download_csv():
    logger.info("Downloading nurseries CSV from %s", CSV_URL)
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "PropertyPulse/1.0"})
    resp = urllib.request.urlopen(req, timeout=600)
    data = resp.read()
    logger.info("Downloaded %.1f MB", len(data) / 1e6)
    return data.decode("utf-8-sig", errors="replace")


def parse_nurseries(csv_text):
    # Skip first 2 preamble rows
    lines = csv_text.split("\n")
    if len(lines) < 3:
        logger.error("CSV too short: %d lines", len(lines))
        return []

    # Rejoin from the header row (line index 2)
    csv_body = "\n".join(lines[2:])
    reader = csv.DictReader(io.StringIO(csv_body))
    fieldnames = reader.fieldnames or []
    logger.info("CSV has %d columns. Sample: %s", len(fieldnames), [c for c in fieldnames[:15] if c])

    rows = []
    seen = set()
    active_count = 0
    inactive_count = 0

    for record in reader:
        provider_urn = (record.get("Provider URN") or "").strip()
        if not provider_urn:
            continue

        # Only include active providers
        status = (record.get("Provider Status") or "").strip()
        if status and status.lower() != "active":
            inactive_count += 1
            continue
        active_count += 1

        if provider_urn in seen:
            continue
        seen.add(provider_urn)

        name = (record.get("Provider Name") or "").strip()
        # Childminders have REDACTED names — use type + area
        if not name or name == "REDACTED":
            town = (record.get("Provider Town") or "").strip()
            ptype = (record.get("Provider Type") or "").strip()
            name = f"{ptype} in {town}" if town else ptype or "Unnamed provider"

        provider_type = (record.get("Provider Type") or "").strip()
        postcode = (record.get("Provider Postcode") or "").strip()
        if postcode == "REDACTED":
            postcode = None

        la_name = (record.get("Local Authority") or "").strip()

        # Ofsted rating
        rating_raw = (record.get("Most Recent Full: Overall Effectiveness") or "").strip()
        ofsted_rating = RATING_MAP.get(rating_raw, None)

        # Inspection date
        last_inspection = _date(record.get("Most Recent Full: Inspection Date"))

        # Places
        max_places = _int(record.get("Places"))

        rows.append((
            provider_urn,
            name,
            provider_type,
            postcode,
            None,  # latitude
            None,  # longitude
            None,  # lad_code
            la_name,
            ofsted_rating,
            last_inspection,
            None,  # age_from
            None,  # age_to
            max_places,
        ))

    logger.info("Parsed %d nursery rows (active: %d, inactive: %d)", len(rows), active_count, inactive_count)
    return rows


def ensure_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schools.nurseries (
                urn              TEXT PRIMARY KEY,
                name             TEXT NOT NULL,
                type             TEXT,
                postcode         TEXT,
                latitude         DOUBLE PRECISION,
                longitude        DOUBLE PRECISION,
                geom             GEOMETRY(Point, 4326),
                lad_code         TEXT,
                la_name          TEXT,
                ofsted_rating    TEXT,
                last_inspection  DATE,
                age_from         SMALLINT,
                age_to           SMALLINT,
                max_places       SMALLINT,
                updated_at       TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_nurs_geom ON schools.nurseries USING GIST (geom);
            CREATE INDEX IF NOT EXISTS idx_nurs_postcode ON schools.nurseries (postcode);
        """)
        conn.commit()
    logger.info("Ensured schools.nurseries table exists")


def load_nurseries(rows, conn):
    if not rows:
        return
    with conn.cursor() as cur:
        cur.execute("DELETE FROM schools.nurseries")
        execute_values(
            cur,
            """
            INSERT INTO schools.nurseries (
                urn, name, type, postcode,
                latitude, longitude,
                lad_code, la_name,
                ofsted_rating, last_inspection,
                age_from, age_to, max_places
            ) VALUES %s
            ON CONFLICT (urn) DO UPDATE SET
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                postcode = EXCLUDED.postcode,
                la_name = EXCLUDED.la_name,
                ofsted_rating = EXCLUDED.ofsted_rating,
                last_inspection = EXCLUDED.last_inspection,
                max_places = EXCLUDED.max_places
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d nursery rows", len(rows))


def geocode_from_postcodes(conn):
    """Backfill lat/lon from institutions table postcodes."""
    with conn.cursor() as cur:
        # Use school institutions postcode coordinates as a lookup
        cur.execute("""
            UPDATE schools.nurseries n
            SET latitude = i.latitude,
                longitude = i.longitude,
                geom = i.geom
            FROM schools.institutions i
            WHERE REPLACE(UPPER(n.postcode), ' ', '') = REPLACE(UPPER(i.postcode), ' ', '')
            AND n.latitude IS NULL
            AND n.postcode IS NOT NULL
            AND i.latitude IS NOT NULL
        """)
        updated = cur.rowcount
        conn.commit()
        logger.info("Geocoded %d nurseries from institution postcodes", updated)


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        ensure_table(conn)
        csv_text = download_csv()
        rows = parse_nurseries(csv_text)
        if rows:
            load_nurseries(rows, conn)
            geocode_from_postcodes(conn)
    finally:
        conn.close()
    logger.info("Nurseries ingestion complete")


if __name__ == "__main__":
    main()
