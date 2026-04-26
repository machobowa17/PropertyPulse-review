#!/usr/bin/env python3
"""Ingest SEN provision details from GIAS into schools.sen_provisions.

Source: GIAS daily extract CSV (Edubase).
Extracts SEN unit / resource base information and specialisms.
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

# GIAS daily extract — date-stamped URL
GIAS_BASE_URL = "https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public/edubasealldata{date}.csv"


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


def download_gias_csv():
    """Download GIAS daily extract. Try today's date, then yesterday's."""
    for days_back in range(5):
        from datetime import timedelta
        target_date = datetime.now() - timedelta(days=days_back)
        date_str = target_date.strftime("%Y%m%d")
        url = GIAS_BASE_URL.format(date=date_str)
        logger.info("Trying GIAS CSV: %s", url)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
            resp = urllib.request.urlopen(req, timeout=300)
            data = resp.read()
            logger.info("Downloaded %.1f MB (date=%s)", len(data) / 1e6, date_str)
            return data.decode("utf-8-sig", errors="replace")
        except Exception as e:
            logger.warning("Failed for date %s: %s", date_str, e)
            continue
    raise RuntimeError("Could not download GIAS CSV for any recent date")


def parse_sen(csv_text):
    """Parse SEN provision data from GIAS extract."""
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    logger.info("GIAS CSV has %d columns", len(fieldnames))

    # Find SEN-related columns
    sen_cols = [c for c in fieldnames if "sen" in c.lower() or "SEN" in c]
    resource_cols = [c for c in fieldnames if "resource" in c.lower()]
    logger.info("SEN-related columns: %s", sen_cols[:20])
    logger.info("Resource-related columns: %s", resource_cols[:10])

    rows = []
    seen = set()

    for record in reader:
        urn = _int(record.get("URN"))
        if not urn:
            continue

        # Check for SEN unit
        sen_unit = record.get("TypeOfResourcedProvision (name)", "").strip()
        sen_specialism_str = record.get("SEN1 (name)", "").strip()

        # Also check for dedicated SEN columns
        has_sen_unit = False
        has_resource_base = False

        # GIAS uses "TypeOfResourcedProvision" or similar
        if sen_unit:
            if "SEN" in sen_unit.upper() or "UNIT" in sen_unit.upper():
                has_sen_unit = True
            elif "RESOURCE" in sen_unit.upper():
                has_resource_base = True
            else:
                # Any non-empty value means some provision
                has_resource_base = True

        # Collect specialisms from SEN1-SEN13 columns
        specialisms = []
        for i in range(1, 14):
            col_name = f"SEN{i} (name)"
            val = record.get(col_name, "").strip()
            if val and val.lower() not in ("not applicable", "none", ""):
                specialisms.append(val)

        if not specialisms and not has_sen_unit and not has_resource_base:
            # Also check ResourcedProvisionOnRoll and ResourcedProvisionCapacity
            rp_capacity = _int(record.get("ResourcedProvisionCapacity"))
            su_capacity = _int(record.get("SENUnitCapacity"))
            if rp_capacity and rp_capacity > 0:
                has_resource_base = True
            elif su_capacity and su_capacity > 0:
                has_sen_unit = True
            else:
                continue

        rp_capacity = _int(record.get("ResourcedProvisionCapacity"))
        su_capacity = _int(record.get("SENUnitCapacity"))

        # Create rows for each provision type
        if has_sen_unit or (su_capacity and su_capacity > 0):
            key = (urn, "SEN unit")
            if key not in seen:
                seen.add(key)
                rows.append((
                    urn,
                    "SEN unit",
                    specialisms if specialisms else None,
                    su_capacity,
                ))

        if has_resource_base or (rp_capacity and rp_capacity > 0):
            key = (urn, "Resourced provision")
            if key not in seen:
                seen.add(key)
                rows.append((
                    urn,
                    "Resourced provision",
                    specialisms if specialisms else None,
                    rp_capacity,
                ))

        # If we only have specialisms but no provision type identified
        if specialisms and not has_sen_unit and not has_resource_base:
            if not rp_capacity and not su_capacity:
                key = (urn, "SEN support")
                if key not in seen:
                    seen.add(key)
                    rows.append((
                        urn,
                        "SEN support",
                        specialisms,
                        None,
                    ))

    logger.info("Parsed %d SEN provision rows", len(rows))
    return rows


def load_sen(rows, conn):
    valid_urns = _get_valid_urns(conn)
    rows = [r for r in rows if r[0] in valid_urns]
    logger.info("After FK filter: %d rows with valid URNs", len(rows))
    if not rows:
        return
    with conn.cursor() as cur:
        cur.execute("DELETE FROM schools.sen_provisions")
        execute_values(
            cur,
            """
            INSERT INTO schools.sen_provisions (
                urn, provision_type, sen_specialisms, capacity
            ) VALUES %s
            ON CONFLICT (urn, provision_type) DO UPDATE SET
                sen_specialisms = EXCLUDED.sen_specialisms,
                capacity = EXCLUDED.capacity
            """,
            rows,
            page_size=5000,
        )
        conn.commit()
        logger.info("Loaded %d SEN provision rows", len(rows))


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        csv_text = download_gias_csv()
        rows = parse_sen(csv_text)
        if rows:
            load_sen(rows, conn)
    finally:
        conn.close()
    logger.info("SEN provisions ingestion complete")


if __name__ == "__main__":
    main()
