"""
sources/place_boundaries.py — OSM place boundary polygons → core_place_boundaries

Downloads suburb/town/village/neighbourhood boundary relations from the
Overpass API and ingests them into core_place_boundaries.  After load,
backfills lad_code via ST_Within against core_lad_boundaries.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_place_boundaries)

No local data files required — data is fetched live from the Overpass API.
"""

import json

import psycopg2
import requests

from constants import SCHEDULE_FOUNDATION, TABLE_NAMES, supported_overpass_bboxes

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "place_boundaries",
    "description": "OSM place boundary polygons → core_place_boundaries.",
    "schedule":           SCHEDULE_FOUNDATION,
    "depends_on":         ["boundaries"],
    "tables_written":     [TABLE_NAMES["place_boundaries"]],
    "cache_key_patterns": ["boundary:*", "choropleth:*"],
    "expected_row_range": (10_000, 50_000),
}

# ---------------------------------------------------------------------------
# Overpass query
# ---------------------------------------------------------------------------

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

_SUPPORTED_BBOXES = supported_overpass_bboxes()


def _build_overpass_query() -> str:
    if not _SUPPORTED_BBOXES:
        raise RuntimeError("No supported country Overpass bounding boxes configured.")

    clauses = []
    for bbox in _SUPPORTED_BBOXES:
        clauses.append(f'  relation["boundary"="place"]({bbox});')
        clauses.append(f'  relation["boundary"="administrative"]["admin_level"="10"]({bbox});')

    return "\n".join([
        "[out:json][timeout:600];",
        "(",
        *clauses,
        ");",
        "out geom;",
    ])

# ---------------------------------------------------------------------------
# Geometry conversion
# ---------------------------------------------------------------------------

def _relation_to_multipolygon(element):
    """
    Convert an Overpass relation (with inline geometry) to a GeoJSON
    MultiPolygon dict, or None if the geometry can't be built.
    """
    if "members" not in element:
        return None

    outer_rings = []
    inner_rings = []

    for member in element["members"]:
        if member.get("type") != "way" or "geometry" not in member:
            continue
        role   = member.get("role", "")
        coords = [(pt["lon"], pt["lat"]) for pt in member["geometry"]]
        if len(coords) < 4:
            continue
        # Ensure ring closure
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        if role in ("outer", ""):
            outer_rings.append(coords)
        elif role == "inner":
            inner_rings.append(coords)

    if not outer_rings:
        return None

    polygons = []
    for i, outer in enumerate(outer_rings):
        # Assign inner rings to the first outer only
        polygons.append([outer] + (inner_rings if i == 0 else []))

    return {"type": "MultiPolygon", "coordinates": polygons}


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Fetch OSM place boundaries → core_place_boundaries.
    Returns final row count.
    """
    query = _build_overpass_query()
    print("  Downloading place boundaries from Overpass API for supported countries...", flush=True)
    resp = requests.post(
        _OVERPASS_URL,
        data={"data": query},
        timeout=660,
    )
    resp.raise_for_status()
    elements = resp.json().get("elements", [])
    print(f"  Downloaded {len(elements)} elements", flush=True)

    # Parse relations into place boundary records
    places = []
    for el in elements:
        if el.get("type") != "relation":
            continue
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        place_type = tags.get("place") or tags.get("boundary", "place")
        geom = _relation_to_multipolygon(el)
        if not geom:
            continue
        places.append({
            "osm_id":     el["id"],
            "name":       name,
            "name_lower": name.lower(),
            "place_type": place_type,
            "geom":       json.dumps(geom),
        })

    print(f"  Parsed {len(places)} place boundaries with geometry", flush=True)
    if not places:
        raise RuntimeError("No place boundaries parsed from Overpass response — aborting.")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    # Recreate table (cleaner than partial upsert for geometry)
    cur.execute(f"DROP TABLE IF EXISTS {TABLE_NAMES['place_boundaries']} CASCADE")
    cur.execute(f"""
        CREATE TABLE {TABLE_NAMES['place_boundaries']} (
            id               SERIAL PRIMARY KEY,
            osm_id           BIGINT UNIQUE NOT NULL,
            place_name       TEXT NOT NULL,
            place_name_lower TEXT NOT NULL,
            place_type       TEXT,
            lad_code         TEXT,
            geom             GEOMETRY(MultiPolygon, 4326) NOT NULL
        )
    """)
    conn.commit()

    inserted = 0
    skipped  = 0
    batch_size = 100

    for i in range(0, len(places), batch_size):
        batch = places[i : i + batch_size]
        for p in batch:
            try:
                cur.execute(
                    f"""INSERT INTO {TABLE_NAMES['place_boundaries']}
                            (osm_id, place_name, place_name_lower, place_type, geom)
                        VALUES (%s, %s, %s, %s,
                                ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                        ON CONFLICT (osm_id) DO NOTHING""",
                    (p["osm_id"], p["name"], p["name_lower"],
                     p["place_type"], p["geom"]),
                )
                inserted += 1
            except Exception as exc:
                conn.rollback()
                skipped += 1
                if skipped <= 5:
                    print(f"    Skipped {p['name']} (osm_id={p['osm_id']}): {exc}", flush=True)
        conn.commit()
        print(f"    Inserted {min(i + batch_size, len(places))}/{len(places)}...", flush=True)

    print(f"  Inserted {inserted} place boundaries, skipped {skipped}", flush=True)

    # Indexes
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_place_boundaries_name
        ON {TABLE_NAMES['place_boundaries']}(place_name_lower)
    """)
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_place_boundaries_geom
        ON {TABLE_NAMES['place_boundaries']} USING GIST(geom)
    """)
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_place_boundaries_lad
        ON {TABLE_NAMES['place_boundaries']}(lad_code)
    """)
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_place_boundaries_trgm
        ON {TABLE_NAMES['place_boundaries']}
        USING GIN(place_name_lower gin_trgm_ops)
    """)
    conn.commit()

    # Backfill lad_code via spatial join
    print("  Populating lad_code via spatial join...", flush=True)
    cur.execute(f"""
        UPDATE {TABLE_NAMES['place_boundaries']} pb
        SET lad_code = lb.lad_code
        FROM {TABLE_NAMES['lad_boundaries']} lb
        WHERE ST_Within(ST_Centroid(pb.geom), lb.geom)
          AND pb.lad_code IS NULL
    """)
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['place_boundaries']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_place_boundaries: {count:,} rows", flush=True)
    return count
