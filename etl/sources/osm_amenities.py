"""
sources/osm_amenities.py — OpenStreetMap POIs → core_osm_amenities

Fetches the 10 Bible-defined amenity types from the Overpass API and
ingests them into core_osm_amenities.  Results are cached in
etl/data/osm_bible_pois.json between runs (delete to force a fresh fetch).

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_osm_amenities)

No local data files required — data is fetched live from Overpass API
and cached in etl/data/.
"""

import json
import os
import time

import psycopg2
import requests
from psycopg2.extras import execute_values

from constants import AMENITY_OSM_TAGS, AMENITY_TYPES, ENGLAND_BBOX, SCHEDULE_QUARTERLY, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "osm_amenities",
    "description": "OpenStreetMap Overpass API (Bible Section 3.1 POI types) → core_osm_amenities.",
    "schedule":           SCHEDULE_QUARTERLY,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["osm_amenities"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (100_000, 400_000),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR     = os.path.join(os.path.dirname(__file__), "..", "data")
_CACHE_PATH   = os.path.join(_DATA_DIR, "osm_bible_pois.json")
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# ---------------------------------------------------------------------------
# Fetch from Overpass
# ---------------------------------------------------------------------------

def _fetch_osm_pois():
    """
    Fetch all Bible-defined POI types from Overpass API.
    Returns list of element dicts with '_amenity_type' key added.
    Uses local cache if available — delete etl/data/osm_bible_pois.json to refresh.
    """
    if os.path.exists(_CACHE_PATH):
        print(f"  Loading cached OSM data from {_CACHE_PATH}", flush=True)
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)

    print("  Fetching from Overpass API...", flush=True)
    all_elements = []

    for i, (amenity_type, key, value) in enumerate(AMENITY_OSM_TAGS):
        query = (
            f'[out:json][timeout:300];\n'
            f'(\n'
            f'  node["{key}"="{value}"]({ENGLAND_BBOX});\n'
            f'  way["{key}"="{value}"]({ENGLAND_BBOX});\n'
            f');\n'
            f'out center;\n'
        )
        print(f"  Fetching {amenity_type} ({key}={value})...", flush=True)
        for attempt in range(3):
            try:
                resp = requests.post(
                    _OVERPASS_URL,
                    data={"data": query},
                    timeout=360,
                )
                resp.raise_for_status()
                elements = resp.json().get("elements", [])
                for el in elements:
                    el["_amenity_type"] = amenity_type
                all_elements.extend(elements)
                print(f"    {len(elements):,} elements", flush=True)
                break
            except Exception as exc:
                print(f"    Attempt {attempt + 1} failed: {exc}", flush=True)
                if attempt < 2:
                    time.sleep(15)

        if i < len(AMENITY_OSM_TAGS) - 1:
            time.sleep(5)   # stay within Overpass rate limit

    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(all_elements, f)
    print(f"  Cached {len(all_elements):,} elements to {_CACHE_PATH}", flush=True)
    return all_elements


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Fetch OSM amenities → core_osm_amenities.
    Returns final row count.
    """
    elements = _fetch_osm_pois()

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['osm_amenities']} CASCADE")
    conn.commit()

    rows = []
    for el in elements:
        amenity_type = el.get("_amenity_type")
        if amenity_type not in set(AMENITY_TYPES):
            continue

        lat = el.get("lat")
        lon = el.get("lon")
        # Way elements have coordinates in 'center'
        if lat is None and "center" in el:
            lat = el["center"].get("lat")
            lon = el["center"].get("lon")
        if lat is None or lon is None:
            continue

        osm_id = el.get("id")
        name   = el.get("tags", {}).get("name", "")
        rows.append((osm_id, name, amenity_type, float(lat), float(lon)))

    print(f"  Collected {len(rows):,} amenities", flush=True)

    if rows:
        execute_values(
            cur,
            f"""INSERT INTO {TABLE_NAMES['osm_amenities']}
                    (osm_id, name, amenity_type, latitude, longitude)
                VALUES %s""",
            rows,
            page_size=10_000,
        )
        conn.commit()

    cur.execute(f"""
        UPDATE {TABLE_NAMES['osm_amenities']}
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL
    """)
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['osm_amenities']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_osm_amenities: {count:,} rows", flush=True)
    return count
