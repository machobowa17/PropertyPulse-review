"""
sources/crime.py — Police.uk crime data → core_crime_lsoa

Two-phase ingestion:
  Phase 1 — National bulk ZIP (all forces except GMP, Sussex, Gwent, BTP)
             Reads all months from the local police_latest.zip.
  Phase 2 — GMP via police.uk API
             Greater Manchester Police is excluded from the national ZIP;
             we query the crimes-street API per LSOA polygon.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_crime_lsoa)

Data files required in etl/data/ (or set CRIME_ZIP_PATH env var):
    police_latest.zip — national bulk ZIP from https://data.police.uk/data/

GMP data is fetched live from the police.uk API.
"""

import csv
import io
import json
import os
import time
import zipfile
from collections import defaultdict

import psycopg2
import requests
from psycopg2.extras import execute_values

from constants import GMP_LAD_CODES, SCHEDULE_MONTHLY, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "crime",
    "description": (
        "Police.uk bulk ZIP (national) + Police.uk API (GMP only) → core_crime_lsoa."
    ),
    "schedule":           SCHEDULE_MONTHLY,
    "depends_on":         ["boundaries"],
    "tables_written":     [TABLE_NAMES["crime_lsoa"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (4_000_000, 8_000_000),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR      = os.path.join(os.path.dirname(__file__), "..", "data")
_ZIP_PATH      = os.environ.get("CRIME_ZIP_PATH",
                                os.path.join(_DATA_DIR, "police_latest.zip"))
_API_BASE      = "https://data.police.uk/api"


# ---------------------------------------------------------------------------
# Phase 1 — National bulk ZIP
# ---------------------------------------------------------------------------

def _ingest_bulk(conn, zip_path):
    """Truncate crime table and load all months from the bulk ZIP."""
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['crime_lsoa']} CASCADE")
    conn.commit()

    with zipfile.ZipFile(zip_path, "r") as zf:
        all_street    = [n for n in zf.namelist() if n.endswith("-street.csv")]
        target_months = sorted(set(n.split("/")[0] for n in all_street))
        print(f"  Bulk ZIP: {len(target_months)} months "
              f"({target_months[0]} → {target_months[-1]})", flush=True)

        all_rows = []
        for target in target_months:
            target_files = [n for n in all_street if n.startswith(target + "/")]
            counts = defaultdict(int)
            for fname in target_files:
                with zf.open(fname) as f:
                    reader = csv.DictReader(
                        io.TextIOWrapper(f, encoding="utf-8", errors="replace")
                    )
                    for r in reader:
                        lsoa       = r.get("LSOA code", "").strip()
                        crime_type = r.get("Crime type", "").strip()
                        if lsoa.startswith("E") and crime_type:
                            counts[(lsoa, crime_type)] += 1

            month_date = target + "-01"
            for (lsoa, crime_type), cnt in counts.items():
                all_rows.append((lsoa, month_date, crime_type, cnt))
            print(f"    {target}: {len(counts):,} LSOA×type combos", flush=True)

    if all_rows:
        execute_values(
            cur,
            f"""INSERT INTO {TABLE_NAMES['crime_lsoa']}
                    (lsoa_code, month, crime_type, crime_count)
                VALUES %s
                ON CONFLICT DO NOTHING""",
            all_rows,
            page_size=10_000,
        )
        conn.commit()

    cur.close()
    print(f"  Bulk load complete: {len(all_rows):,} rows inserted", flush=True)


# ---------------------------------------------------------------------------
# Phase 2 — GMP via API
# ---------------------------------------------------------------------------

def _get_available_months():
    resp = requests.get(f"{_API_BASE}/crimes-street-dates", timeout=10)
    resp.raise_for_status()
    return [d["date"] for d in resp.json()]


def _get_gmp_lsoa_polygons(conn):
    """Return list of (lsoa_code, simplified_polygon_json) for GMP LSOAs."""
    cur = conn.cursor()
    cur.execute(f"""
        SELECT b.lsoa_code,
               ST_AsGeoJSON(ST_Simplify(b.geom, 0.001)) AS poly_json
        FROM {TABLE_NAMES['lsoa_boundaries']} b
        JOIN {TABLE_NAMES['postcodes']} p ON p.lsoa_code = b.lsoa_code
        WHERE p.lad_code = ANY(%s)
        GROUP BY b.lsoa_code, b.geom
        ORDER BY b.lsoa_code
    """, (list(GMP_LAD_CODES),))
    rows = cur.fetchall()
    cur.close()
    return rows


def _polygon_to_api_param(poly_json):
    """Convert GeoJSON polygon to the police.uk poly= query parameter format."""
    geom = json.loads(poly_json)
    if geom["type"] == "Polygon":
        coords = geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        coords = max(geom["coordinates"], key=lambda r: len(r[0]))[0]
    else:
        return None
    # API hard limit: 100 vertices
    if len(coords) > 99:
        step   = len(coords) / 99
        coords = [coords[int(i * step)] for i in range(99)] + [coords[0]]
    # Format: lat,lng:lat,lng (exclude closing duplicate)
    return ":".join(f"{c[1]:.5f},{c[0]:.5f}" for c in coords[:-1])


def _fetch_crimes(poly_param, month, retries=5):
    """Fetch crimes for an LSOA polygon + month from police.uk API."""
    url = f"{_API_BASE}/crimes-street/all-crime"
    for attempt in range(retries):
        try:
            resp = requests.get(
                url, params={"poly": poly_param, "date": month}, timeout=30
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 30))
                wait = max(wait, 2 ** (attempt + 2))
                print(f"    429 rate limit — waiting {wait}s", flush=True)
                time.sleep(wait)
            elif resp.status_code == 503:
                time.sleep(2 ** attempt)
            else:
                return []
        except Exception:
            time.sleep(2 ** attempt)
    return []


def _ingest_gmp(conn):
    """Fetch GMP crime data via API and append to core_crime_lsoa."""
    months = _get_available_months()
    print(f"  GMP API: {len(months)} months available "
          f"({months[0]} → {months[-1]})", flush=True)

    lsoas = _get_gmp_lsoa_polygons(conn)
    print(f"  GMP LSOAs: {len(lsoas)}", flush=True)

    # Skip LSOAs that already have data
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT lsoa_code FROM {TABLE_NAMES['crime_lsoa']}
        WHERE lsoa_code IN (
            SELECT b.lsoa_code
            FROM {TABLE_NAMES['lsoa_boundaries']} b
            JOIN {TABLE_NAMES['postcodes']} p ON p.lsoa_code = b.lsoa_code
            WHERE p.lad_code = ANY(%s)
        )
    """, (list(GMP_LAD_CODES),))
    already_loaded = {r[0] for r in cur.fetchall()}
    cur.close()

    missing = [(code, poly) for code, poly in lsoas if code not in already_loaded]
    print(f"  GMP LSOAs needing API fetch: {len(missing)}", flush=True)

    total_inserted = 0
    for i, (lsoa_code, poly_json) in enumerate(missing):
        poly_param = _polygon_to_api_param(poly_json)
        if not poly_param:
            continue

        month_rows = []
        for month in months:
            crimes = _fetch_crimes(poly_param, month)
            counts = defaultdict(int)
            for crime in crimes:
                crime_type = crime.get("category", "").replace("-", " ").title()
                if crime_type:
                    counts[crime_type] += 1
            for crime_type, cnt in counts.items():
                month_rows.append((lsoa_code, month + "-01", crime_type, cnt))
            time.sleep(0.5)   # stay within ~2 req/s for polygon endpoint

        if month_rows:
            cur = conn.cursor()
            execute_values(
                cur,
                f"""INSERT INTO {TABLE_NAMES['crime_lsoa']}
                        (lsoa_code, month, crime_type, crime_count)
                    VALUES %s
                    ON CONFLICT DO NOTHING""",
                month_rows,
                page_size=1000,
            )
            conn.commit()
            cur.close()
            total_inserted += len(month_rows)

        if (i + 1) % 10 == 0:
            print(f"    GMP: {i+1}/{len(missing)} LSOAs processed, "
                  f"{total_inserted:,} rows inserted", flush=True)

    print(f"  GMP ingestion complete: {total_inserted:,} rows", flush=True)


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest crime data from national ZIP + GMP API.
    Returns final row count in core_crime_lsoa.
    """
    if not os.path.exists(_ZIP_PATH):
        raise FileNotFoundError(
            f"Crime ZIP not found: {_ZIP_PATH}. "
            "Download from https://data.police.uk/data/ and place in etl/data/, "
            "or set CRIME_ZIP_PATH env var."
        )

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    print("  Phase 1: loading national bulk ZIP...", flush=True)
    _ingest_bulk(conn, _ZIP_PATH)

    print("  Phase 2: fetching GMP data via API...", flush=True)
    _ingest_gmp(conn)

    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['crime_lsoa']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_crime_lsoa: {count:,} rows", flush=True)
    return count
