"""
sources/inspire_parcels.py — INSPIRE Index Polygons → core_inspire_parcels

Ingests Land Registry INSPIRE Cadastral Parcel GML files from a local directory
into core_inspire_parcels.  Each authority has a single GML file containing all
cadastral parcel polygons in EPSG:27700 (British National Grid).

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_inspire_parcels)

Data directory layout (env var INSPIRE_DIR or default path):
    <INSPIRE_DIR>/
        Adur_District_Council/
            Adur_District_Council/
                Land_Registry_Cadastral_Parcels.gml
        Amber_Valley_Borough_Council/
            ...

Download from:
    https://use-land-property-data.service.gov.uk/datasets/inspire/download
"""

import os
import re
import xml.etree.ElementTree as ET

import psycopg2
import psycopg2.extras
from pyproj import Transformer

from constants import SCHEDULE_ONE_TIME, TABLE_NAMES
from utils import blue_green_swap, create_staging_table, recreate_indexes

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "inspire_parcels",
    "description":        "Land Registry INSPIRE Cadastral Parcel GML files → core_inspire_parcels (24M polygons).",
    "schedule":           SCHEDULE_ONE_TIME,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["inspire_parcels"]],
    "cache_key_patterns": [],
    "expected_row_range": (15_000_000, 30_000_000),
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GML_FILENAME = "Land_Registry_Cadastral_Parcels.gml"

# Default data directory: /Volumes/PropertyPulse/INSPIRE Take 2
_DEFAULT_INSPIRE_DIR = os.environ.get(
    "INSPIRE_DIR",
    "/Volumes/PropertyPulse/INSPIRE Take 2",
)

# XML namespaces used in Land Registry INSPIRE GML
_NS = {
    "wfs":  "http://www.opengis.net/wfs/2.0",
    "gml":  "http://www.opengis.net/gml/3.2",
    "LR":   "www.landregistry.gov.uk",
}

# BNG → WGS84 transformer (thread-safe, reusable)
_TRANSFORMER = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

# Batch size for bulk inserts
_BATCH_SIZE = 10_000

# Commit interval (rows)
_COMMIT_INTERVAL = 50_000


# ---------------------------------------------------------------------------
# GML parsing — streaming iterparse for memory efficiency
# ---------------------------------------------------------------------------

def _parse_poslist(poslist_text):
    """
    Parse a gml:posList string of BNG coordinates into a WGS84 WKT POLYGON ring.

    Input:  "525665.05 105074.4 525667.92 105074.62 ..."
    Output: list of (lon, lat) tuples in WGS84
    """
    coords = poslist_text.split()
    if len(coords) < 6:  # Need at least 3 points (6 values)
        return None

    ring = []
    for i in range(0, len(coords) - 1, 2):
        try:
            easting = float(coords[i])
            northing = float(coords[i + 1])
        except (ValueError, IndexError):
            continue
        lon, lat = _TRANSFORMER.transform(easting, northing)
        ring.append((lon, lat))

    if len(ring) < 3:
        return None

    # Ensure ring is closed
    if ring[0] != ring[-1]:
        ring.append(ring[0])

    return ring


def _ring_to_wkt(ring):
    """Convert a list of (lon, lat) tuples to a WKT ring string."""
    return ",".join(f"{lon} {lat}" for lon, lat in ring)


def _parse_gml_file(gml_path, authority_name):
    """
    Stream-parse an INSPIRE Cadastral Parcels GML file.

    Yields (inspire_id, authority, wkt_polygon, valid_from, begin_lifespan) tuples.

    Uses iterparse to avoid loading the entire XML into memory (files can be 500+ MB).
    """
    # Tag names with full namespace URIs (for iterparse matching)
    member_tag = "{http://www.opengis.net/wfs/2.0}member"
    predefined_tag = "{www.landregistry.gov.uk}PREDEFINED"
    geometry_tag = "{www.landregistry.gov.uk}GEOMETRY"
    inspireid_tag = "{www.landregistry.gov.uk}INSPIREID"
    validfrom_tag = "{www.landregistry.gov.uk}VALIDFROM"
    beginlifespan_tag = "{www.landregistry.gov.uk}BEGINLIFESPANVERSION"
    polygon_tag = "{http://www.opengis.net/gml/3.2}Polygon"
    exterior_tag = "{http://www.opengis.net/gml/3.2}exterior"
    interior_tag = "{http://www.opengis.net/gml/3.2}interior"
    linearring_tag = "{http://www.opengis.net/gml/3.2}LinearRing"
    poslist_tag = "{http://www.opengis.net/gml/3.2}posList"

    context = ET.iterparse(gml_path, events=("end",))

    for event, elem in context:
        if elem.tag != predefined_tag:
            continue

        # Extract fields
        inspire_id = None
        valid_from = None
        begin_lifespan = None
        exterior_ring = None
        interior_rings = []

        id_el = elem.find(inspireid_tag)
        if id_el is not None and id_el.text:
            inspire_id = id_el.text.strip()

        vf_el = elem.find(validfrom_tag)
        if vf_el is not None and vf_el.text:
            valid_from = vf_el.text.strip()

        bl_el = elem.find(beginlifespan_tag)
        if bl_el is not None and bl_el.text:
            begin_lifespan = bl_el.text.strip()

        # Parse geometry
        geom_el = elem.find(geometry_tag)
        if geom_el is not None:
            polygon_el = geom_el.find(polygon_tag)
            if polygon_el is not None:
                # Exterior ring
                ext_el = polygon_el.find(exterior_tag)
                if ext_el is not None:
                    lr_el = ext_el.find(linearring_tag)
                    if lr_el is not None:
                        pl_el = lr_el.find(poslist_tag)
                        if pl_el is not None and pl_el.text:
                            exterior_ring = _parse_poslist(pl_el.text)

                # Interior rings (holes)
                for int_el in polygon_el.findall(interior_tag):
                    lr_el = int_el.find(linearring_tag)
                    if lr_el is not None:
                        pl_el = lr_el.find(poslist_tag)
                        if pl_el is not None and pl_el.text:
                            ring = _parse_poslist(pl_el.text)
                            if ring:
                                interior_rings.append(ring)

        # Build WKT
        if inspire_id and exterior_ring:
            if interior_rings:
                rings = [_ring_to_wkt(exterior_ring)]
                rings.extend(_ring_to_wkt(r) for r in interior_rings)
                wkt = "POLYGON((" + "),(".join(rings) + "))"
            else:
                wkt = "POLYGON((" + _ring_to_wkt(exterior_ring) + "))"

            yield (inspire_id, authority_name, wkt, valid_from, begin_lifespan)

        # Free memory — critical for large files
        elem.clear()


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest all INSPIRE Cadastral Parcel GML files → core_inspire_parcels.

    Strategy:
    1. Discover all authority directories with a GML file.
    2. Create core_inspire_parcels_new staging table (full replace each run).
    3. For each authority: stream-parse GML, bulk insert with execute_values.
    4. Blue/green swap: rename _new → live table atomically.
    5. Return final row count.
    """
    inspire_dir = _DEFAULT_INSPIRE_DIR
    if not os.path.isdir(inspire_dir):
        raise FileNotFoundError(
            f"INSPIRE directory not found: {inspire_dir}. "
            "Set INSPIRE_DIR env var to the directory containing authority folders."
        )

    # Discover authority GML files (double-nested: Authority/Authority/file.gml)
    authorities = []
    for entry in sorted(os.listdir(inspire_dir)):
        outer = os.path.join(inspire_dir, entry)
        if not os.path.isdir(outer) or entry.startswith("."):
            continue
        # Double-nested structure
        inner = os.path.join(outer, entry)
        gml_path = os.path.join(inner, _GML_FILENAME)
        if os.path.isfile(gml_path):
            # Derive clean authority name from folder name
            authority_name = entry.replace("_", " ")
            authorities.append((authority_name, gml_path))
        else:
            # Try flat structure too (Authority/file.gml)
            gml_flat = os.path.join(outer, _GML_FILENAME)
            if os.path.isfile(gml_flat):
                authority_name = entry.replace("_", " ")
                authorities.append((authority_name, gml_flat))

    print(f"  Found {len(authorities)} INSPIRE authorities with GML files", flush=True)
    if not authorities:
        raise RuntimeError("No INSPIRE GML files found — aborting.")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    # Full replace — staging table WITHOUT indexes for fast bulk insert
    create_staging_table(conn, TABLE_NAMES['inspire_parcels'])

    total_count = 0
    skipped_authorities = []

    for i, (authority_name, gml_path) in enumerate(authorities, 1):
        file_size_mb = os.path.getsize(gml_path) / (1024 * 1024)
        print(f"  [{i}/{len(authorities)}] {authority_name} ({file_size_mb:.1f} MB)...", flush=True)

        batch = []
        authority_count = 0

        try:
            for row in _parse_gml_file(gml_path, authority_name):
                batch.append(row)
                authority_count += 1

                if len(batch) >= _BATCH_SIZE:
                    psycopg2.extras.execute_values(
                        cur,
                        f"""INSERT INTO {TABLE_NAMES['inspire_parcels']}_new
                                (inspire_id, authority, geom, valid_from, begin_lifespan)
                            VALUES %s
                            ON CONFLICT (inspire_id) DO NOTHING""",
                        batch,
                        template="(%s, %s, ST_MakeValid(ST_GeomFromText(%s, 4326)), %s::timestamptz, %s::timestamptz)",
                        page_size=_BATCH_SIZE,
                    )
                    batch = []

                if authority_count % _COMMIT_INTERVAL == 0:
                    conn.commit()

            # Flush remaining batch
            if batch:
                psycopg2.extras.execute_values(
                    cur,
                    f"""INSERT INTO {TABLE_NAMES['inspire_parcels']}_new
                            (inspire_id, authority, geom, valid_from, begin_lifespan)
                        VALUES %s
                        ON CONFLICT (inspire_id) DO NOTHING""",
                    batch,
                    template="(%s, %s, ST_GeomFromText(%s, 4326), %s::timestamptz, %s::timestamptz)",
                    page_size=_BATCH_SIZE,
                )
            conn.commit()

        except Exception as e:
            conn.rollback()
            print(f"    ERROR: {authority_name}: {e}", flush=True)
            skipped_authorities.append((authority_name, str(e)))
            continue

        total_count += authority_count
        print(f"    {authority_count:,} parcels ({total_count:,} cumulative)", flush=True)

    print("  Rebuilding indexes on staging table...", flush=True)
    recreate_indexes(conn, TABLE_NAMES['inspire_parcels'])

    blue_green_swap(conn, TABLE_NAMES['inspire_parcels'])

    # Vacuum analyze for query performance
    conn.autocommit = True
    cur.execute(f"ANALYZE {TABLE_NAMES['inspire_parcels']}")

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['inspire_parcels']}")
    final = cur.fetchone()[0]
    cur.close()
    conn.close()

    if skipped_authorities:
        print(f"  Skipped {len(skipped_authorities)} authorities due to errors:", flush=True)
        for name, err in skipped_authorities:
            print(f"    {name}: {err}", flush=True)

    print(f"  Final: {final:,} parcels in core_inspire_parcels", flush=True)
    return final
