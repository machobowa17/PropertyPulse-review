"""
derived/place_lsoa_mapping.py — Spatial join → core_place_lsoa_mapping + core_place_lsoa_mapping_town

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_place_lsoa_mapping)

Rebuilds the Voronoi+containment LSOA→place mapping tables from:
    core_place_names     — ONS place names with lat/lon and lad_code
    core_lsoa_boundaries — LSOA polygon geometries
    core_place_boundaries — OSM place polygon boundaries

Two-pass strategy per table:
    1. Containment: LSOA centroids within OSM place polygons → method='containment'
    2. Voronoi: each LSOA assigned to nearest place in same LAD → method='voronoi'

core_place_lsoa_mapping_town:
    Nearest City/Town per LSOA within same LAD (pure Voronoi).

Expected row count (verify after rebuild):
    core_place_lsoa_mapping:      ~52,476 rows
    core_place_lsoa_mapping_town: ~28,680 rows
"""

import psycopg2

from constants import SCHEDULE_ANNUAL, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":           "place_lsoa_mapping",
    "description":    "Spatial join core_place_names × core_lsoa_boundaries → core_place_lsoa_mapping + _town.",
    "schedule":       SCHEDULE_ANNUAL,
    "depends_on":     ["place_names", "boundaries"],
    "tables_written": [TABLE_NAMES["place_lsoa_mapping"], TABLE_NAMES["place_lsoa_mapping_town"]],
    "cache_key_patterns": ["lsoa_sess:*", "area:*", "resolve:*"],
    "expected_row_range": (45_000, 65_000),
}

# Place types treated as searchable area names (matches geo_resolver AREA_PLACE_TYPES)
_AREA_TYPES = ["City", "Town", "Suburban Area", "Village", "Hamlet", "Other Settlement"]
_TOWN_TYPES = ["City", "Town"]

# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Rebuild core_place_lsoa_mapping and core_place_lsoa_mapping_town.

    Steps:
    1. Truncate both tables.
    2. Containment pass: LSOA centroids within core_place_boundaries polygons → method='containment'.
    3. Voronoi pass: nearest core_place_names entry per LSOA in same LAD → method='voronoi'.
    4. Town table: nearest City/Town per LSOA in same LAD.
    5. Return row count in core_place_lsoa_mapping.
    """
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    # ------------------------------------------------------------------
    # Truncate
    # ------------------------------------------------------------------
    print("  Truncating place LSOA mapping tables...", flush=True)
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['place_lsoa_mapping']}")
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['place_lsoa_mapping_town']}")
    conn.commit()

    # ------------------------------------------------------------------
    # Pass 1 — Containment: LSOA centroid within OSM place boundary
    # ------------------------------------------------------------------
    print("  Containment pass (LSOA centroid within OSM place polygon)...", flush=True)
    cur.execute(
        f"""
        INSERT INTO {TABLE_NAMES['place_lsoa_mapping']} (place_name, place_type, lad_code, lsoa_code, method)
        SELECT DISTINCT
            pb.place_name,
            COALESCE(pn.place_type, pb.place_type)  AS place_type,
            lb.lad_code,
            lb.lsoa_code,
            'containment'
        FROM {TABLE_NAMES['lsoa_boundaries']} lb
        JOIN {TABLE_NAMES['place_boundaries']} pb
            ON ST_Within(ST_Centroid(lb.geom), pb.geom)
           AND (pb.lad_code IS NULL OR pb.lad_code = lb.lad_code)
        LEFT JOIN {TABLE_NAMES['place_names']} pn
            ON pn.place_name = pb.place_name
           AND pn.lad_code = lb.lad_code
           AND pn.place_type = ANY(%s)
        WHERE COALESCE(pn.place_type, pb.place_type) = ANY(%s)
        """,
        (_AREA_TYPES, _AREA_TYPES),
    )
    containment_count = cur.rowcount
    conn.commit()
    print(f"    Inserted {containment_count:,} containment rows", flush=True)

    # ------------------------------------------------------------------
    # Pass 2 — Voronoi: nearest place in same LAD per LSOA
    # ------------------------------------------------------------------
    print("  Voronoi pass (nearest place in LAD per LSOA)...", flush=True)
    cur.execute(
        f"""
        INSERT INTO {TABLE_NAMES['place_lsoa_mapping']} (place_name, place_type, lad_code, lsoa_code, method)
        SELECT DISTINCT ON (lb.lsoa_code)
            pn.place_name,
            pn.place_type,
            lb.lad_code,
            lb.lsoa_code,
            'voronoi'
        FROM {TABLE_NAMES['lsoa_boundaries']} lb
        JOIN {TABLE_NAMES['place_names']} pn
            ON pn.lad_code = lb.lad_code
           AND pn.place_type = ANY(%s)
           AND pn.latitude  IS NOT NULL
           AND pn.longitude IS NOT NULL
        ORDER BY lb.lsoa_code,
            ST_Distance(
                ST_Centroid(lb.geom),
                ST_SetSRID(ST_MakePoint(pn.longitude, pn.latitude), 4326)
            )
        """,
        (_AREA_TYPES,),
    )
    voronoi_count = cur.rowcount
    conn.commit()
    print(f"    Inserted {voronoi_count:,} voronoi rows", flush=True)

    # ------------------------------------------------------------------
    # Town mapping: nearest City/Town in same LAD per LSOA
    # ------------------------------------------------------------------
    print("  Building town/city LSOA mapping (core_place_lsoa_mapping_town)...", flush=True)
    cur.execute(
        f"""
        INSERT INTO {TABLE_NAMES['place_lsoa_mapping_town']} (lsoa_code, lad_code, place_name, place_type)
        SELECT DISTINCT ON (lb.lsoa_code)
            lb.lsoa_code,
            lb.lad_code,
            pn.place_name,
            pn.place_type
        FROM {TABLE_NAMES['lsoa_boundaries']} lb
        JOIN {TABLE_NAMES['place_names']} pn
            ON pn.lad_code = lb.lad_code
           AND pn.place_type = ANY(%s)
           AND pn.latitude  IS NOT NULL
           AND pn.longitude IS NOT NULL
        ORDER BY lb.lsoa_code,
            ST_Distance(
                ST_Centroid(lb.geom),
                ST_SetSRID(ST_MakePoint(pn.longitude, pn.latitude), 4326)
            )
        """,
        (_TOWN_TYPES,),
    )
    town_count = cur.rowcount
    conn.commit()
    print(f"    Inserted {town_count:,} town mapping rows", flush=True)

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['place_lsoa_mapping']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
