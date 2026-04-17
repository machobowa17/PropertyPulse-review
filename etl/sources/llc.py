"""
sources/llc.py — HM Land Registry Local Land Charges → core_llc_charges

Ingests LLC GML files from a local directory into core_llc_charges.
Each authority has up to 4 GML files covering different charge types:
    - LU_Residential  (land use — residential)     ~7.9M features
    - LU_Forestry     (land use — forestry)         ~123K features
    - Protected_Sites (designated sites)            ~192K features
    - Area_Management (management zones)            ~6K features

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_llc_charges)

Data directory layout (env var LLC_DIR or default path):
    <LLC_DIR>/
        Ashfield_District_Council/
            Ashfield_District_Council/
                Land_Registry_LU_Residential.gml
                Land_Registry_LU_Forestry.gml
                Land_Registry_Protected_Sites.gml
                Land_Registry_Area_Management.gml
                INSPIRE Download Licence.pdf
                Ashfield_District_Council.zip

Download from:
    https://use-land-property-data.service.gov.uk/datasets/llc/download
"""

import os
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
    "name":               "llc",
    "description":        "HM Land Registry Local Land Charges GML files → core_llc_charges (8.3M features, 4 charge types).",
    "schedule":           SCHEDULE_ONE_TIME,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["llc_charges"]],
    "cache_key_patterns": [],
    "expected_row_range": (5_000_000, 12_000_000),
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# GML file prefixes → charge_type mapping
_LLC_FILE_TYPES = {
    "Land_Registry_LU_Residential.gml":  "LU_Residential",
    "Land_Registry_LU_Forestry.gml":     "LU_Forestry",
    "Land_Registry_Protected_Sites.gml": "Protected_Sites",
    "Land_Registry_Area_Management.gml": "Area_Management",
}

_DEFAULT_LLC_DIR = os.environ.get(
    "LLC_DIR",
    "/Volumes/PropertyPulse/LLC Take 2",
)

# XML element tags vary by charge type — LLC GML uses 'inspire' namespace (not 'LR')
# Feature element names per charge type:
_FEATURE_TAGS = {
    "LU_Residential":  "{www.landregistry.gov.uk/inspire}LU.ResidentialUse",
    "LU_Forestry":     "{www.landregistry.gov.uk/inspire}LU.ForestryUse",
    "Protected_Sites": "{www.landregistry.gov.uk/inspire}PS.ProtectedSite",
    "Area_Management": "{www.landregistry.gov.uk/inspire}AM.Predefined",
}

# Common sub-element tags (lowercase in LLC GML, unlike INSPIRE which uses uppercase)
_GEOMETRY_TAG = "{www.landregistry.gov.uk/inspire}geometry"
_INSPIREID_TAG = "{www.landregistry.gov.uk/inspire}inspireid"
_VALIDFROM_TAG = "{www.landregistry.gov.uk/inspire}validfrom"
_BEGINLIFESPAN_TAG = "{www.landregistry.gov.uk/inspire}beginlifespanversion"

_POLYGON_TAG = "{http://www.opengis.net/gml/3.2}Polygon"
_MULTIPOLYGON_TAG = "{http://www.opengis.net/gml/3.2}MultiPolygon"
_EXTERIOR_TAG = "{http://www.opengis.net/gml/3.2}exterior"
_INTERIOR_TAG = "{http://www.opengis.net/gml/3.2}interior"
_LINEARRING_TAG = "{http://www.opengis.net/gml/3.2}LinearRing"
_POSLIST_TAG = "{http://www.opengis.net/gml/3.2}posList"
_SURFACEMEMBER_TAG = "{http://www.opengis.net/gml/3.2}surfaceMember"

# BNG → WGS84 transformer
_TRANSFORMER = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

_BATCH_SIZE = 10_000
_COMMIT_INTERVAL = 50_000


# ---------------------------------------------------------------------------
# GML parsing
# ---------------------------------------------------------------------------

def _parse_poslist(poslist_text):
    """Parse gml:posList of BNG coords into a WGS84 ring [(lon, lat), ...]."""
    coords = poslist_text.split()
    if len(coords) < 6:
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

    if ring[0] != ring[-1]:
        ring.append(ring[0])

    return ring


def _ring_to_wkt(ring):
    return ",".join(f"{lon} {lat}" for lon, lat in ring)


def _polygon_to_wkt(polygon_el):
    """Extract a single Polygon element into WKT, or None."""
    ext_el = polygon_el.find(_EXTERIOR_TAG)
    if ext_el is None:
        return None
    lr_el = ext_el.find(_LINEARRING_TAG)
    if lr_el is None:
        return None
    pl_el = lr_el.find(_POSLIST_TAG)
    if pl_el is None or not pl_el.text:
        return None

    exterior_ring = _parse_poslist(pl_el.text)
    if not exterior_ring:
        return None

    interior_rings = []
    for int_el in polygon_el.findall(_INTERIOR_TAG):
        lr = int_el.find(_LINEARRING_TAG)
        if lr is not None:
            pl = lr.find(_POSLIST_TAG)
            if pl is not None and pl.text:
                ring = _parse_poslist(pl.text)
                if ring:
                    interior_rings.append(ring)

    if interior_rings:
        rings = [_ring_to_wkt(exterior_ring)]
        rings.extend(_ring_to_wkt(r) for r in interior_rings)
        return "POLYGON((" + "),(".join(rings) + "))"
    else:
        return "POLYGON((" + _ring_to_wkt(exterior_ring) + "))"


def _parse_llc_gml(gml_path, authority_name, charge_type):
    """
    Stream-parse an LLC GML file.

    Yields (inspire_id, authority, charge_type, wkt_polygon, valid_from, begin_lifespan).
    """
    feature_tag = _FEATURE_TAGS.get(charge_type)
    if not feature_tag:
        return

    context = ET.iterparse(gml_path, events=("end",))

    for event, elem in context:
        if elem.tag != feature_tag:
            continue

        inspire_id = None
        valid_from = None
        begin_lifespan = None

        id_el = elem.find(_INSPIREID_TAG)
        if id_el is not None and id_el.text:
            inspire_id = id_el.text.strip()

        vf_el = elem.find(_VALIDFROM_TAG)
        if vf_el is not None and vf_el.text:
            valid_from = vf_el.text.strip()

        bl_el = elem.find(_BEGINLIFESPAN_TAG)
        if bl_el is not None and bl_el.text:
            begin_lifespan = bl_el.text.strip()

        # Parse geometry — can be Polygon or MultiPolygon
        geom_el = elem.find(_GEOMETRY_TAG)
        if geom_el is not None:
            # Try single Polygon first
            polygon_el = geom_el.find(_POLYGON_TAG)
            if polygon_el is not None:
                wkt = _polygon_to_wkt(polygon_el)
                if wkt and inspire_id:
                    yield (inspire_id, authority_name, charge_type, wkt, valid_from, begin_lifespan)
            else:
                # Try MultiPolygon — yield each polygon as separate row
                mp_el = geom_el.find(_MULTIPOLYGON_TAG)
                if mp_el is not None:
                    for sm_el in mp_el.findall(_SURFACEMEMBER_TAG):
                        p_el = sm_el.find(_POLYGON_TAG)
                        if p_el is not None:
                            wkt = _polygon_to_wkt(p_el)
                            if wkt and inspire_id:
                                yield (inspire_id, authority_name, charge_type, wkt, valid_from, begin_lifespan)

        elem.clear()


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest all LLC GML files → core_llc_charges.

    Strategy:
    1. Discover all authority directories with GML files.
    2. Create core_llc_charges_new staging table (full replace each run).
    3. For each authority × charge type: stream-parse, bulk insert.
    4. Blue/green swap: rename _new → live table atomically.
    5. Return final row count.
    """
    llc_dir = _DEFAULT_LLC_DIR
    if not os.path.isdir(llc_dir):
        raise FileNotFoundError(
            f"LLC directory not found: {llc_dir}. "
            "Set LLC_DIR env var to the directory containing authority folders."
        )

    # Discover authority directories (double-nested: Authority/Authority/files)
    authorities = []
    for entry in sorted(os.listdir(llc_dir)):
        outer = os.path.join(llc_dir, entry)
        if not os.path.isdir(outer) or entry.startswith("."):
            continue
        # Double-nested structure
        inner = os.path.join(outer, entry)
        if os.path.isdir(inner):
            # Check for at least one GML file
            gml_files = [f for f in os.listdir(inner) if f in _LLC_FILE_TYPES]
            if gml_files:
                authority_name = entry.replace("_", " ")
                authorities.append((authority_name, inner, gml_files))
        else:
            # Try flat structure
            gml_files = [f for f in os.listdir(outer) if f in _LLC_FILE_TYPES]
            if gml_files:
                authority_name = entry.replace("_", " ")
                authorities.append((authority_name, outer, gml_files))

    print(f"  Found {len(authorities)} LLC authorities with GML files", flush=True)
    if not authorities:
        raise RuntimeError("No LLC GML files found — aborting.")

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    # Full replace — staging table WITHOUT indexes for fast bulk insert
    create_staging_table(conn, TABLE_NAMES['llc_charges'])

    total_count = 0
    skipped = []

    for i, (authority_name, gml_dir, gml_files) in enumerate(authorities, 1):
        print(f"  [{i}/{len(authorities)}] {authority_name} ({len(gml_files)} GML files)...", flush=True)
        authority_count = 0

        for gml_filename in sorted(gml_files):
            charge_type = _LLC_FILE_TYPES[gml_filename]
            gml_path = os.path.join(gml_dir, gml_filename)
            file_size_mb = os.path.getsize(gml_path) / (1024 * 1024)

            batch = []
            file_count = 0

            try:
                for row in _parse_llc_gml(gml_path, authority_name, charge_type):
                    batch.append(row)
                    file_count += 1

                    if len(batch) >= _BATCH_SIZE:
                        psycopg2.extras.execute_values(
                            cur,
                            f"""INSERT INTO {TABLE_NAMES['llc_charges']}_new
                                    (inspire_id, authority, charge_type, geom, valid_from, begin_lifespan)
                                VALUES %s""",
                            batch,
                            template="(%s, %s, %s, ST_MakeValid(ST_GeomFromText(%s, 4326)), %s::timestamptz, %s::timestamptz)",
                            page_size=_BATCH_SIZE,
                        )
                        batch = []

                    if file_count % _COMMIT_INTERVAL == 0:
                        conn.commit()

                # Flush remaining
                if batch:
                    psycopg2.extras.execute_values(
                        cur,
                        f"""INSERT INTO {TABLE_NAMES['llc_charges']}_new
                                (inspire_id, authority, charge_type, geom, valid_from, begin_lifespan)
                            VALUES %s""",
                        batch,
                        template="(%s, %s, %s, ST_MakeValid(ST_GeomFromText(%s, 4326)), %s::timestamptz, %s::timestamptz)",
                        page_size=_BATCH_SIZE,
                    )
                conn.commit()

            except Exception as e:
                conn.rollback()
                print(f"    ERROR: {authority_name}/{charge_type}: {e}", flush=True)
                skipped.append((authority_name, charge_type, str(e)))
                continue

            authority_count += file_count
            if file_count > 0:
                print(f"    {charge_type}: {file_count:,} ({file_size_mb:.1f} MB)", flush=True)

        total_count += authority_count

    print("  Rebuilding indexes on staging table...", flush=True)
    recreate_indexes(conn, TABLE_NAMES['llc_charges'])

    blue_green_swap(conn, TABLE_NAMES['llc_charges'])

    # Vacuum analyze
    conn.autocommit = True
    cur.execute(f"ANALYZE {TABLE_NAMES['llc_charges']}")

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['llc_charges']}")
    final = cur.fetchone()[0]
    cur.close()
    conn.close()

    if skipped:
        print(f"  Skipped {len(skipped)} files due to errors:", flush=True)
        for name, ctype, err in skipped:
            print(f"    {name}/{ctype}: {err}", flush=True)

    print(f"  Final: {final:,} charges in core_llc_charges", flush=True)
    return final
