"""
sources/station_enrichment.py — Enrich core_transport_stops with TfL + NR data

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns number of rows enriched)

Data files required in etl/data/:
    rail_references.csv — NaPTAN ATCO ↔ TIPLOC ↔ CRS mapping

External APIs used:
    TfL Unified API — lines, zones, accessibility, facilities for London stops (no key)
    National Rail KnowledgeBase — operator, step-free, toilets, WiFi, car park (auth required)

Run AFTER naptan source to enrich existing core_transport_stops rows.
"""

import csv
import json
import os
import ssl
import time
import urllib.request

import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ANNUAL, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "station_enrichment",
    "description":        "Enrich core_transport_stops with CRS codes, TfL lines/zones/facilities",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         ["naptan"],
    "tables_written":     [TABLE_NAMES["transport_stops"]],
    "cache_key_patterns": [],
    "expected_row_range": (500, 10_000),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load_rail_references():
    """Load ATCO → (CRS, TIPLOC) mapping from rail_references.csv."""
    path = os.path.join(_ETL_DATA_DIR, "rail_references.csv")
    if not os.path.exists(path):
        print("  WARN: rail_references.csv not found — skipping CRS/TIPLOC enrichment")
        return {}

    mapping = {}  # atco_code → {"crs": ..., "tiploc": ...}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            atco = r.get("AtcoCode", "").strip()
            crs = r.get("CrsCode", "").strip()
            tiploc = r.get("TiplocCode", "").strip()
            if atco and (crs or tiploc):
                mapping[atco] = {"crs": crs or None, "tiploc": tiploc or None}

    print(f"  Loaded {len(mapping):,} rail reference entries")
    return mapping


def _tfl_get(url, timeout=30):
    """Fetch JSON from TfL API using urllib (no curl dependency)."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "PropertyPulse-ETL/1.0 (station enrichment)",
    })
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_tfl_line_stops():
    """
    Fetch all TfL stop points grouped by line.
    Returns: dict[naptan_id] → {lines: [...], zone: str, step_free: bool, facilities: dict}
    """
    # Modes to query — all TfL-operated rail/metro/tram
    modes = "tube,overground,dlr,elizabeth-line,tram"
    stops = {}  # naptan_id → enrichment data

    try:
        lines = _tfl_get(f"https://api.tfl.gov.uk/Line/Mode/{modes}/Route")
        print(f"  TfL: {len(lines)} lines found")

        # Fetch stop points for each line
        for line_info in lines:
            line_id = line_info["id"]
            line_name = line_info["name"]

            time.sleep(0.3)  # rate limit courtesy

            try:
                stop_points = _tfl_get(f"https://api.tfl.gov.uk/Line/{line_id}/StopPoints")
            except Exception as e:
                print(f"    WARN: Failed to fetch stops for {line_id}: {e}")
                continue

            for sp in stop_points:
                naptan_id = sp.get("naptanId", "")
                if not naptan_id:
                    continue

                if naptan_id not in stops:
                    # Parse facilities from additionalProperties
                    props = {
                        p["key"]: p["value"]
                        for p in sp.get("additionalProperties", [])
                    }
                    facilities = {}
                    if props.get("Ticket Halls"):
                        facilities["ticket_halls"] = props["Ticket Halls"]
                    if props.get("Toilet") == "Yes" or props.get("Toilets") == "yes":
                        facilities["toilets"] = True
                    if props.get("Car park") == "yes":
                        facilities["car_park"] = True
                    if props.get("WiFi") == "yes":
                        facilities["wifi"] = True
                    if props.get("Lifts"):
                        try:
                            facilities["lifts"] = int(props["Lifts"])
                        except ValueError:
                            pass
                    if props.get("Escalators"):
                        try:
                            facilities["escalators"] = int(props["Escalators"])
                        except ValueError:
                            pass
                    if props.get("Gates"):
                        try:
                            facilities["gates"] = int(props["Gates"])
                        except ValueError:
                            pass

                    # Step-free access
                    step_free = (
                        props.get("AccessViaLift", "").lower() == "yes"
                        or "step-free" in props.get("NatRailStepFreeAccess", "").lower()
                    )

                    zone = props.get("Zone", "")

                    stops[naptan_id] = {
                        "lines": [line_name],
                        "zone": zone or None,
                        "step_free": step_free,
                        "facilities": facilities if facilities else None,
                        "operator": "TfL",
                        "modes": sp.get("modes", []),
                    }
                else:
                    # Add this line to existing entry
                    if line_name not in stops[naptan_id]["lines"]:
                        stops[naptan_id]["lines"].append(line_name)

        print(f"  TfL: enriched {len(stops):,} stations")
    except Exception as e:
        print(f"  WARN: TfL API error: {e}")

    return stops


# ---------------------------------------------------------------------------
# NR KnowledgeBase helpers
# ---------------------------------------------------------------------------

# Shared NR auth (credentials via NR_EMAIL / NR_PASSWORD env vars)
from lib.nr_auth import nr_authenticate as _nr_authenticate

# TOC code → human-readable operator name
_TOC_NAMES = {
    "AW": "Transport for Wales", "CC": "c2c", "CH": "Chiltern Railways",
    "EM": "East Midlands Railway", "ES": "Eurostar", "GN": "Great Northern",
    "GR": "LNER", "GW": "Great Western Railway", "GX": "Gatwick Express",
    "GM": "Grand Central", "HS": "Southeastern Highspeed", "HV": "Hull Trains",
    "HX": "Heathrow Express", "IL": "Island Line", "LE": "Greater Anglia",
    "LN": "London Northwestern", "LO": "London Overground", "LT": "London Underground",
    "ME": "Merseyrail", "NR": "Network Rail", "NT": "Northern Trains",
    "SE": "Southeastern", "SN": "Southern", "SR": "ScotRail",
    "SW": "South Western Railway", "TL": "Thameslink",
    "TP": "TransPennine Express", "VT": "Avanti West Coast",
    "WM": "West Midlands Trains", "XP": "CrossCountry", "XR": "Elizabeth line",
    "XS": "CrossCountry",
}


def _nr_fetch_stations(token):
    """
    Download NR KnowledgeBase stations XML feed and parse into dict[CRS] → enrichment data.
    Returns: dict with keys = CRS code, values = {operator, step_free, facilities}
    """
    import xml.etree.ElementTree as ET

    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(
        "https://opendata.nationalrail.co.uk/api/staticfeeds/3.0/stations",
        headers={"X-Auth-Token": token},
    )
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        raw = resp.read()

    print(f"  NR KB: downloaded {len(raw):,} bytes")
    root = ET.fromstring(raw)

    ns = "{http://nationalrail.co.uk/xml/station}"
    com = "{http://nationalrail.co.uk/xml/common}"

    stations = {}
    for station_elem in root:
        crs_elem = station_elem.find(f"{ns}CrsCode")
        if crs_elem is None or not crs_elem.text:
            continue
        crs = crs_elem.text.strip()

        # Operator
        op_elem = station_elem.find(f"{ns}StationOperator")
        op_code = op_elem.text.strip() if op_elem is not None and op_elem.text else None
        operator = _TOC_NAMES.get(op_code, op_code) if op_code else None

        # Step-free access
        acc = station_elem.find(f"{ns}Accessibility")
        step_free = False
        if acc is not None:
            sfa = acc.find(f"{ns}StepFreeAccess")
            if sfa is not None:
                cov = sfa.find(f"{ns}Coverage")
                if cov is not None and cov.text:
                    # wholeStation or partialStation = True
                    step_free = cov.text.strip() in ("wholeStation", "partialStation")

        # Facilities
        facilities = {}
        fac = station_elem.find(f"{ns}StationFacilities")
        if fac is not None:
            toilets_elem = fac.find(f"{ns}Toilets")
            if toilets_elem is not None:
                avail = toilets_elem.find(f"{com}Available")
                if avail is not None and avail.text and avail.text.strip() == "true":
                    facilities["toilets"] = True

            wifi_elem = fac.find(f"{ns}WiFi")
            if wifi_elem is not None:
                avail = wifi_elem.find(f"{com}Available")
                if avail is not None and avail.text and avail.text.strip() == "true":
                    facilities["wifi"] = True

        # Car park (under Interchange)
        interchange = station_elem.find(f"{ns}Interchange")
        if interchange is not None:
            cp = interchange.find(f"{ns}CarPark")
            if cp is not None:
                spaces = cp.find(f"{ns}Spaces")
                if spaces is not None and spaces.text:
                    try:
                        if int(spaces.text.strip()) > 0:
                            facilities["car_park"] = True
                    except ValueError:
                        pass

        stations[crs] = {
            "operator": operator,
            "step_free": step_free,
            "facilities": facilities if facilities else None,
        }

    print(f"  NR KB: parsed {len(stations):,} stations")
    return stations


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Enrich core_transport_stops with:
    1. CRS + TIPLOC codes from rail_references.csv
    2. Lines, zones, step-free, facilities from TfL API

    Does NOT recreate the table — only UPDATEs existing rows.
    """
    rail_refs = _load_rail_references()
    tfl_stops = _fetch_tfl_line_stops()

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()
    enriched = 0

    # Step 1: CRS + TIPLOC from rail_references.csv
    if rail_refs:
        crs_rows = [
            (v["crs"], v["tiploc"], atco)
            for atco, v in rail_refs.items()
        ]
        # Batch update
        for batch_start in range(0, len(crs_rows), 5000):
            batch = crs_rows[batch_start:batch_start + 5000]
            execute_values(
                cur,
                f"""
                UPDATE {TABLE_NAMES['transport_stops']} AS t
                SET crs_code = v.crs, tiploc_code = v.tiploc
                FROM (VALUES %s) AS v(crs, tiploc, atco_code)
                WHERE t.atco_code = v.atco_code
                """,
                batch,
                template="(%s, %s, %s)",
            )
        conn.commit()
        print(f"  CRS/TIPLOC: updated {len(crs_rows):,} rail stations")
        enriched += len(crs_rows)

    # Step 2: TfL enrichment
    if tfl_stops:
        tfl_rows = []
        for naptan_id, data in tfl_stops.items():
            lines_str = ", ".join(data["lines"]) if data["lines"] else None
            facilities_json = json.dumps(data["facilities"]) if data["facilities"] else None
            # TfL uses station-group naptanIds (940G prefix) while NaPTAN ATCOCodes
            # use 9400 prefix. Replace 940G→9400 to match the platform-level codes.
            atco_prefix = naptan_id.replace("940G", "9400", 1) if naptan_id.startswith("940G") else naptan_id
            tfl_rows.append((
                lines_str,
                data.get("operator"),
                data.get("zone"),
                data.get("step_free", False),
                facilities_json,
                atco_prefix,
            ))

        for batch_start in range(0, len(tfl_rows), 1000):
            batch = tfl_rows[batch_start:batch_start + 1000]
            execute_values(
                cur,
                f"""
                UPDATE {TABLE_NAMES['transport_stops']} AS t
                SET lines = v.lines,
                    operator = v.operator,
                    zone = v.zone,
                    step_free = v.step_free::boolean,
                    facilities = v.facilities::jsonb
                FROM (VALUES %s) AS v(lines, operator, zone, step_free, facilities, atco_prefix)
                WHERE t.atco_code = v.atco_prefix
                   OR t.atco_code LIKE v.atco_prefix || '%%'
                """,
                batch,
                template="(%s, %s, %s, %s, %s, %s)",
            )
        conn.commit()
        print(f"  TfL: updated {len(tfl_rows):,} station records")
        enriched += len(tfl_rows)

    # Step 3: NR KnowledgeBase enrichment (operator, step-free, facilities)
    # Only updates rows WHERE operator IS NULL (preserves TfL data from Step 2)
    try:
        print("  NR KB: authenticating...")
        nr_token = _nr_authenticate()
        nr_stations = _nr_fetch_stations(nr_token)

        if nr_stations:
            nr_rows = []
            for crs, data in nr_stations.items():
                facilities_json = json.dumps(data["facilities"]) if data["facilities"] else None
                nr_rows.append((
                    data["operator"],
                    data["step_free"],
                    facilities_json,
                    crs,
                ))

            for batch_start in range(0, len(nr_rows), 500):
                batch = nr_rows[batch_start:batch_start + 500]
                execute_values(
                    cur,
                    f"""
                    UPDATE {TABLE_NAMES['transport_stops']} AS t
                    SET operator = v.operator,
                        step_free = v.step_free::boolean,
                        facilities = COALESCE(v.facilities::jsonb, t.facilities)
                    FROM (VALUES %s) AS v(operator, step_free, facilities, crs_code)
                    WHERE t.crs_code = v.crs_code
                      AND t.operator IS NULL
                    """,
                    batch,
                    template="(%s, %s, %s, %s)",
                )
            conn.commit()
            print(f"  NR KB: updated {len(nr_rows):,} station records")
            enriched += len(nr_rows)
    except Exception as e:
        print(f"  WARN: NR KnowledgeBase enrichment failed: {e}")
        conn.rollback()

    # Count total enriched rows
    cur.execute(
        f"SELECT COUNT(*) FROM {TABLE_NAMES['transport_stops']} "
        "WHERE crs_code IS NOT NULL OR lines IS NOT NULL OR operator IS NOT NULL"
    )
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    return total
