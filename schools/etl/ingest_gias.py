#!/usr/bin/env python3
"""Ingest GIAS (Get Information About Schools) register into schools.institutions.

Downloads the daily edubasealldata CSV and loads it into PostgreSQL.
Source: https://ea-edubase-api-prod.azurewebsites.net/edubase/edubasealldata{YYYYMMDD}.csv
~35,000 open schools in England & Wales.
"""

import csv
import io
import logging
import os
import sys
import urllib.request
from datetime import date

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property")

# GIAS column mapping: CSV column name -> our column name
COLUMN_MAP = {
    "URN": "urn",
    "EstablishmentName": "name",
    "TypeOfEstablishment (name)": "type_code",
    "PhaseOfEducation (name)": "phase",
    "Gender (name)": "gender",
    "ReligiousCharacter (name)": "religious_char",
    "StatutoryLowAge": "age_low",
    "StatutoryHighAge": "age_high",
    "SchoolCapacity": "capacity",
    "NumberOfPupils": "pupil_count",
    "HeadTitle (name)": "head_title",
    "HeadFirstName": "head_first",
    "HeadLastName": "head_last",
    "Street": "address_street",
    "Locality": "address_locality",
    "Address3": "address3",
    "Town": "address_town",
    "County (name)": "address_county",
    "Postcode": "postcode",
    "SchoolWebsite": "website",
    "TelephoneNum": "phone",
    "EstablishmentStatus (name)": "status",
    "OpenDate": "open_date",
    "CloseDate": "close_date",
    "LA (name)": "la_name",
    "LA (code)": "la_code",
    "GOR (name)": "region",
    "DistrictAdministrative (code)": "lad_code",
    "Easting": "easting",
    "Northing": "northing",
    "UPRN": "uprn",
    "SEN1 (name)": "sen1",
    "SEN2 (name)": "sen2",
    "SEN3 (name)": "sen3",
    "SEN4 (name)": "sen4",
    "TypeOfResourcedProvision (name)": "resourced_provision_type",
    "ResourcedProvisionOnRoll": "resourced_provision_count",
    "ResourcedProvisionCapacity": "resourced_provision_capacity",
    "SENStat": "sen_stat",
    "SENNoStat": "sen_no_stat",
    "BoardingEstablishment (name)": "boarding",
    "NurseryProvision (name)": "nursery_provision",
    "OfficialSixthForm (name)": "sixth_form",
    "AdmissionsPolicy (name)": "admissions_policy",
    "Ofsted (name)": "ofsted_rating_text",
    "OfstedRating (name)": "ofsted_rating",
    "LastChangedDate": "last_changed",
    "FurtherEducationType (name)": "fe_type",
}


def _parse_date(s):
    """Parse dd-mm-yyyy date string."""
    if not s or s.strip() == "":
        return None
    try:
        parts = s.strip().split("-")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except Exception:
        pass
    return None


def _parse_int(s):
    if not s or s.strip() == "":
        return None
    try:
        return int(s.strip())
    except (ValueError, TypeError):
        return None


def _parse_float(s):
    if not s or s.strip() == "":
        return None
    try:
        return float(s.strip())
    except (ValueError, TypeError):
        return None


def _osgb36_to_wgs84(easting, northing):
    """Approximate OSGB36 to WGS84 conversion."""
    if easting is None or northing is None:
        return None, None
    try:
        import math
        e = float(easting)
        n = float(northing)
        if e < 1 or n < 1:
            return None, None

        a, b = 6377563.396, 6356256.909
        e0, n0, f0 = 400000, -100000, 0.9996012717
        phi0, lam0 = math.radians(49), math.radians(-2)

        e2 = 1 - (b * b) / (a * a)
        n_calc = (a - b) / (a + b)

        phi = (n - n0) / (a * f0) + phi0
        for _ in range(10):
            M = b * f0 * (
                (1 + n_calc + 1.25 * n_calc**2 + 1.25 * n_calc**3) * (phi - phi0)
                - (3 * n_calc + 3 * n_calc**2 + 2.625 * n_calc**3) * math.sin(phi - phi0) * math.cos(phi + phi0)
                + (1.875 * n_calc**2 + 1.875 * n_calc**3) * math.sin(2 * (phi - phi0)) * math.cos(2 * (phi + phi0))
                - (35.0 / 24 * n_calc**3) * math.sin(3 * (phi - phi0)) * math.cos(3 * (phi + phi0))
            )
            phi = (n - n0 - M) / (a * f0) + phi

        nu = a * f0 / math.sqrt(1 - e2 * math.sin(phi)**2)
        rho = a * f0 * (1 - e2) / (1 - e2 * math.sin(phi)**2)**1.5
        eta2 = nu / rho - 1

        VII = math.tan(phi) / (2 * rho * nu)
        VIII = math.tan(phi) / (24 * rho * nu**3) * (5 + 3 * math.tan(phi)**2 + eta2 - 9 * math.tan(phi)**2 * eta2)
        IX = math.tan(phi) / (720 * rho * nu**5) * (61 + 90 * math.tan(phi)**2 + 45 * math.tan(phi)**4)
        X = 1 / (math.cos(phi) * nu)
        XI = 1 / (math.cos(phi) * 6 * nu**3) * (nu / rho + 2 * math.tan(phi)**2)
        XII = 1 / (math.cos(phi) * 120 * nu**5) * (5 + 28 * math.tan(phi)**2 + 24 * math.tan(phi)**4)

        dE = e - e0
        lat = phi - VII * dE**2 + VIII * dE**4 - IX * dE**6
        lon = lam0 + X * dE - XI * dE**3 + XII * dE**5

        lat_deg = math.degrees(lat)
        lon_deg = math.degrees(lon)

        # Helmert transform OSGB36 -> WGS84
        lat_deg += 0.00045
        lon_deg -= 0.00015

        return round(lat_deg, 6), round(lon_deg, 6)
    except Exception:
        return None, None


def download_gias():
    """Download today's GIAS extract."""
    today = date.today().strftime("%Y%m%d")
    url = f"https://ea-edubase-api-prod.azurewebsites.net/edubase/edubasealldata{today}.csv"
    logger.info("Downloading GIAS from %s", url)

    req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        return resp.read().decode("utf-8-sig", errors="replace")
    except Exception as e:
        logger.warning("Today's file not available (%s), trying yesterday", e)
        from datetime import timedelta
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
        url = f"https://ea-edubase-api-prod.azurewebsites.net/edubase/edubasealldata{yesterday}.csv"
        req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
        resp = urllib.request.urlopen(req, timeout=120)
        return resp.read().decode("utf-8-sig", errors="replace")


def parse_and_load(csv_text, conn):
    """Parse GIAS CSV and load into schools.institutions."""
    reader = csv.DictReader(io.StringIO(csv_text))

    rows = []
    for record in reader:
        urn = _parse_int(record.get("URN"))
        if not urn:
            continue

        status = record.get("EstablishmentStatus (name)", "").strip()
        is_open = status == "Open"

        # Build address
        addr_parts = [
            record.get("Street", "").strip(),
            record.get("Locality", "").strip(),
            record.get("Address3", "").strip(),
            record.get("Town", "").strip(),
        ]
        address = ", ".join(p for p in addr_parts if p)

        # Build headteacher name
        head_parts = [
            record.get("HeadTitle (name)", "").strip(),
            record.get("HeadFirstName", "").strip(),
            record.get("HeadLastName", "").strip(),
        ]
        headteacher = " ".join(p for p in head_parts if p) or None

        # Coordinates
        easting = _parse_float(record.get("Easting"))
        northing = _parse_float(record.get("Northing"))
        lat, lon = _osgb36_to_wgs84(easting, northing)

        # Country
        region = record.get("GOR (name)", "").strip()
        country = "W" if region == "Wales" else "E"

        # Phase normalization
        phase = record.get("PhaseOfEducation (name)", "").strip()
        if phase == "Not applicable":
            phase = record.get("TypeOfEstablishment (name)", "").strip()

        postcode = record.get("Postcode", "").strip()
        if not postcode:
            continue

        rows.append((
            urn,
            record.get("EstablishmentName", "").strip(),
            record.get("TypeOfEstablishment (name)", "").strip(),
            phase,
            record.get("Gender (name)", "").strip() or None,
            record.get("ReligiousCharacter (name)", "").strip() or None,
            _parse_int(record.get("StatutoryLowAge")),
            _parse_int(record.get("StatutoryHighAge")),
            _parse_int(record.get("SchoolCapacity")),
            _parse_int(record.get("NumberOfPupils")),
            headteacher,
            address,
            postcode,
            lat,
            lon,
            record.get("DistrictAdministrative (code)", "").strip() or None,
            record.get("LA (name)", "").strip() or None,
            record.get("SchoolWebsite", "").strip() or None,
            record.get("TelephoneNum", "").strip() or None,
            is_open,
            _parse_date(record.get("OpenDate")),
            _parse_date(record.get("CloseDate")),
            country,
            record.get("AdmissionsPolicy (name)", "").strip() or None,
            record.get("BoardingEstablishment (name)", "").strip() or None,
            record.get("NurseryProvision (name)", "").strip() or None,
            record.get("OfficialSixthForm (name)", "").strip() or None,
        ))

    logger.info("Parsed %d schools from GIAS", len(rows))

    with conn.cursor() as cur:
        # Create schools schema if not exists
        cur.execute("CREATE SCHEMA IF NOT EXISTS schools")

        # Create staging table
        cur.execute("""
            DROP TABLE IF EXISTS schools.institutions_staging;
            CREATE UNLOGGED TABLE schools.institutions_staging (
                urn              INTEGER PRIMARY KEY,
                name             TEXT NOT NULL,
                type_code        TEXT,
                phase            TEXT,
                gender           TEXT,
                religious_char   TEXT,
                age_low          SMALLINT,
                age_high         SMALLINT,
                capacity         INTEGER,
                pupil_count      INTEGER,
                headteacher      TEXT,
                address          TEXT,
                postcode         TEXT NOT NULL,
                latitude         DOUBLE PRECISION,
                longitude        DOUBLE PRECISION,
                lad_code         TEXT,
                la_name          TEXT,
                website          TEXT,
                phone            TEXT,
                is_open          BOOLEAN DEFAULT TRUE,
                open_date        DATE,
                close_date       DATE,
                country          CHAR(1),
                admissions_policy TEXT,
                boarding         TEXT,
                nursery_provision TEXT,
                sixth_form       TEXT,
                geom             GEOMETRY(Point, 4326),
                updated_at       TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Bulk insert
        execute_values(
            cur,
            """
            INSERT INTO schools.institutions_staging (
                urn, name, type_code, phase, gender, religious_char,
                age_low, age_high, capacity, pupil_count, headteacher,
                address, postcode, latitude, longitude, lad_code, la_name,
                website, phone, is_open, open_date, close_date, country,
                admissions_policy, boarding, nursery_provision, sixth_form
            ) VALUES %s
            ON CONFLICT (urn) DO NOTHING
            """,
            rows,
            page_size=5000,
        )
        logger.info("Inserted %d rows into staging", len(rows))

        # Update geometry column
        cur.execute("""
            UPDATE schools.institutions_staging
            SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """)

        # Create indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inst_stg_geom ON schools.institutions_staging USING GIST (geom)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inst_stg_postcode ON schools.institutions_staging (postcode)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inst_stg_lad ON schools.institutions_staging (lad_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inst_stg_phase ON schools.institutions_staging (phase)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_inst_stg_open ON schools.institutions_staging (is_open)")

        # Swap tables
        cur.execute("DROP TABLE IF EXISTS schools.institutions_old")
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='schools' AND tablename='institutions') THEN
                    ALTER TABLE schools.institutions RENAME TO institutions_old;
                END IF;
            END $$
        """)
        cur.execute("ALTER TABLE schools.institutions_staging RENAME TO institutions")
        cur.execute("ALTER TABLE schools.institutions SET LOGGED")
        cur.execute("DROP TABLE IF EXISTS schools.institutions_old")

        conn.commit()

    # Verify
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM schools.institutions WHERE is_open = true")
        count = cur.fetchone()[0]
        logger.info("schools.institutions: %d open schools", count)
        cur.execute("SELECT COUNT(*) FROM schools.institutions WHERE latitude IS NOT NULL")
        geo_count = cur.fetchone()[0]
        logger.info("schools.institutions: %d with coordinates", geo_count)


def main():
    csv_text = download_gias()
    conn = psycopg2.connect(DATABASE_URL)
    try:
        parse_and_load(csv_text, conn)
    finally:
        conn.close()
    logger.info("GIAS ingestion complete")


if __name__ == "__main__":
    main()
