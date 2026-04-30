#!/usr/bin/env python3
"""
PropertyPulse Data Pipeline — Central Orchestrator

Single entry point for all data ingestion and derived table builds.
Every data source and derived computation is registered here.

Usage:
    python3 pipeline.py --source <name>          # run one source
    python3 pipeline.py --schedule monthly       # run all monthly sources
    python3 pipeline.py --all                    # run everything in dependency order
    python3 pipeline.py --dry-run --all          # show execution order without running
    python3 pipeline.py --list                   # list all registered sources
    python3 pipeline.py --status                 # show last run result per source

Architecture:
    Sources  (etl/sources/)  — ingest one authoritative external data source
    Derived  (etl/derived/)  — build pre-computed tables from existing core_* tables
    Both follow the same interface: METADATA dict + run(db_url: str) -> int

    The pipeline:
    1. Runs migrate.py to apply any pending DB schema migrations
    2. Resolves execution order via topological sort of depends_on chains
    3. For each source: records start, calls run(), validates row counts,
       invalidates only the declared Redis key patterns, records result
    4. On failure of a non-critical source: logs error and continues
    5. Foundation sources (postcodes, boundaries) are critical — failure aborts

Design rules (never violate):
    - API endpoints NEVER query source files or external APIs directly.
      All data is consumed from core_* Postgres tables.
    - The ONLY parameter passed from the user to data endpoints is session_key.
      session_key resolves to {lsoa_codes, local_lads, lad_code, ...} which
      are the JOIN keys to core_* tables.
    - Adding a new data source = create etl/sources/<name>.py + register below.
    - Adding a new derived table = create etl/derived/<name>.py + register below.
"""

import argparse
import importlib
import os
import sys
import time
from datetime import datetime, timezone

import psycopg2
import redis as redis_lib

from constants import SCHEDULE_FOUNDATION, SCHEDULE_MONTHLY, SCHEDULE_QUARTERLY, SCHEDULE_ANNUAL, SCHEDULE_ONE_TIME

DB_DSN   = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# Source Registry
#
# Each entry:
#   module          — Python import path relative to etl/ (e.g. "sources.postcodes")
#   schedule        — one of SCHEDULE_* constants
#   depends_on      — list of source names that must run first
#   description     — human-readable description of what this source does
#   tables_written  — list of core_* tables this source writes to
#   cache_key_patterns — Redis key patterns to invalidate after a run
#                        (NOT FLUSHDB — only the keys affected by this source)
#   expected_row_range — (min, max) for the primary table; validation fails
#                        if row count outside this range after run
#   critical        — if True, pipeline aborts on failure; if False, logs and continues
# ---------------------------------------------------------------------------

SOURCE_REGISTRY = {

    # ── Foundation (run first, in strict dependency order) ──────────────────

    "postcodes": {
        "module":       "sources.postcodes",
        "schedule":     SCHEDULE_FOUNDATION,
        "depends_on":   [],
        "description":  "ONS Postcode Directory (ONSPD) → core_postcodes. Foundation for all geographic joins.",
        "tables_written": ["core_postcodes"],
        "cache_key_patterns": ["lsoa_sess:*", "area:*", "resolve:*"],
        "expected_row_range": (1_400_000, 2_800_000),
        "critical":     True,
    },

    "boundaries": {
        "module":       "sources.boundaries",
        "schedule":     SCHEDULE_FOUNDATION,
        "depends_on":   ["postcodes"],
        "description":  "ONS Open Geography LSOA/ward/LAD boundaries + derived county boundaries → core_lsoa_boundaries, core_ward_boundaries, core_lad_boundaries, core_county_boundaries.",
        "tables_written": ["core_lsoa_boundaries", "core_ward_boundaries", "core_lad_boundaries", "core_county_boundaries"],
        "cache_key_patterns": ["lsoa_sess:*", "area:*", "boundary:*", "choropleth:*"],
        "expected_row_range": (33_000, 35_000),   # core_lsoa_boundaries
        "critical":     True,
    },

    "lad_county_lookup": {
        "module":       "sources.lad_county_lookup",
        "schedule":     SCHEDULE_FOUNDATION,
        "depends_on":   ["postcodes"],
        "description":  "LAD → county/region parent mapping per Build Bible Rule 3 → core_lad_county_lookup.",
        "tables_written": ["core_lad_county_lookup"],
        "cache_key_patterns": ["lsoa_sess:*", "area:*"],
        "expected_row_range": (280, 350),
        "critical":     True,
    },

    "place_names": {
        "module":       "sources.place_names",
        "schedule":     SCHEDULE_FOUNDATION,
        "depends_on":   ["postcodes"],
        "description":  "OS Open Names → core_place_names. Powers place-name search.",
        "tables_written": ["core_place_names"],
        "cache_key_patterns": ["resolve:*"],
        "expected_row_range": (1, 500_000),
        "critical":     True,
    },

    "place_boundaries": {
        "module":       "sources.place_boundaries",
        "schedule":     SCHEDULE_FOUNDATION,
        "depends_on":   ["boundaries"],
        "description":  "OSM place boundary polygons → core_place_boundaries.",
        "tables_written": ["core_place_boundaries"],
        "cache_key_patterns": ["boundary:*", "choropleth:*"],
        "expected_row_range": (10_000, 50_000),
        "critical":     True,
    },

    # ── Monthly ─────────────────────────────────────────────────────────────

    "land_registry_full": {
        "module":       "sources.land_registry_full",
        "schedule":     SCHEDULE_MONTHLY,
        "depends_on":   ["postcodes"],
        "description":  "Full PPD ingest (all years 1995–present, incl. district/county/ppd_category) → core_property_transactions.",
        "tables_written": ["core_property_transactions"],
        "cache_key_patterns": ["area:*", "price_history:*", "price_by_type:*", "pois:*"],
        "expected_row_range": (20_000_000, 40_000_000),
        "critical":     False,
    },

    "hpi": {
        "module":       "sources.hpi",
        "schedule":     SCHEDULE_MONTHLY,
        "depends_on":   ["boundaries"],
        "description":  "ONS/Land Registry House Price Index → core_hpi_lad.",
        "tables_written": ["core_hpi_lad"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (80_000, 200_000),
        "critical":     False,
    },

    "crime": {
        "module":       "sources.crime",
        "schedule":     SCHEDULE_MONTHLY,
        "depends_on":   ["boundaries"],
        "description":  "Police.uk bulk ZIP (national) + Police.uk API (GMP only) → core_crime_lsoa.",
        "tables_written": ["core_crime_lsoa"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (4_000_000, 8_000_000),
        "critical":     False,
    },

    "schools": {
        "module":       "sources.schools",
        "schedule":     SCHEDULE_MONTHLY,
        "depends_on":   ["postcodes"],
        "description":  "DfE GIAS + Ofsted ratings + KS2/KS4 scores → core_schools.",
        "tables_written": ["core_schools"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (20_000, 35_000),
        "critical":     False,
    },

    "epc_domestic": {
        "module":       "sources.epc_domestic",
        "schedule":     SCHEDULE_MONTHLY,
        "depends_on":   [],
        "description":  (
            "MHCLG EPC bulk ZIP → load 9-col core_epc_domestic → SQL address-match "
            "→ UPDATE core_property_transactions (floor_area_sqm, habitable_rooms, "
            "epc_rating, ppsm, ppsft) → recompute lsoa_month ppsm/ppsft → DROP epc table."
        ),
        "tables_written": ["core_property_transactions"],
        "cache_key_patterns": ["area:*", "price_history:*"],
        "expected_row_range": (1_000_000, 10_000_000),
        "critical":     False,
    },

    # ── Quarterly ────────────────────────────────────────────────────────────

    "epc_lsoa": {
        "module":       "sources.epc_lsoa",
        "schedule":     SCHEDULE_QUARTERLY,
        "depends_on":   [],
        "description":  "ONS/Nomis Energy Efficiency of Housing (NM_2401_1) → core_epc_lsoa.",
        "tables_written": ["core_epc_lsoa"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (30_000, 36_000),
        "critical":     False,
    },

    "osm_amenities": {
        "module":       "sources.osm_amenities",
        "schedule":     SCHEDULE_QUARTERLY,
        "depends_on":   [],
        "description":  "OpenStreetMap Overpass API (Bible Section 3.1 POI types) → core_osm_amenities.",
        "tables_written": ["core_osm_amenities"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (100_000, 400_000),
        "critical":     False,
    },

    "ev_chargers": {
        "module":       "sources.ev_chargers",
        "schedule":     SCHEDULE_QUARTERLY,
        "depends_on":   [],
        "description":  "OZEV Open Charge Point Registry → core_ev_chargers.",
        "tables_written": ["core_ev_chargers"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (10_000, 60_000),
        "critical":     False,
    },

    "governance": {
        "module":       "sources.governance",
        "schedule":     SCHEDULE_QUARTERLY,
        "depends_on":   ["boundaries"],
        "description":  "Council political control + S114 notices → core_council_control_lad, core_s114_notices.",
        "tables_written": ["core_council_control_lad", "core_s114_notices"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (250, 400),   # core_council_control_lad
        "critical":     False,
    },

    "mobile_coverage": {
        "module":       "sources.mobile_coverage",
        "schedule":     SCHEDULE_QUARTERLY,
        "depends_on":   [],
        "description":  "Ofcom Connected Nations mobile 4G/5G coverage by LAD → core_mobile_coverage_lad.",
        "tables_written": ["core_mobile_coverage_lad"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (250, 400),
        "critical":     False,
    },

    # ── Annual ───────────────────────────────────────────────────────────────

    "voa_rents": {
        "module":       "sources.voa_rents",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   [],
        "description":  "VOA Private Rental Market Statistics (XLS) → core_voa_rents_lad.",
        "tables_written": ["core_voa_rents_lad"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (200, 500),
        "critical":     False,
    },

    "ashe": {
        "module":       "sources.ashe",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   [],
        "description":  "ONS ASHE median earnings by LAD → core_earnings_lad.",
        "tables_written": ["core_earnings_lad"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (250, 400),
        "critical":     False,
    },

    "broadband": {
        "module":       "sources.broadband",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   [],
        "description":  "Ofcom Connected Nations postcode + LAD broadband coverage → core_broadband_postcode, core_broadband_lad.",
        "tables_written": ["core_broadband_postcode", "core_broadband_lad"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (1_500_000, 2_000_000),   # core_broadband_postcode
        "critical":     False,
    },

    "noise": {
        "module":       "sources.noise",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   ["postcodes"],
        "description":  "Defra Round 4 strategic noise maps (road + rail Lden) → core_noise at postcode level.",
        "tables_written": ["core_noise"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (200_000, 1_500_000),
        "critical":     False,
    },

    "air_quality": {
        "module":       "sources.air_quality",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   ["boundaries"],
        "description":  "Defra PCM annual grid (2024) + historical LAD aggregates (2018-2023) → core_air_quality, core_air_quality_lad.",
        "tables_written": ["core_air_quality", "core_air_quality_lad"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (200_000, 400_000),   # core_air_quality
        "critical":     False,
    },

    "flood": {
        "module":       "sources.flood",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   [],
        "description":  "Environment Agency Historic Flood Map (GeoPackage) → core_flood_zones.",
        "tables_written": ["core_flood_zones"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (10_000, 60_000),
        "critical":     False,
    },

    "green_space": {
        "module":       "sources.green_space",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   [],
        "description":  "OS Open Greenspace (GeoPackage) → core_green_space.",
        "tables_written": ["core_green_space"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (100_000, 300_000),
        "critical":     False,
    },

    "nhs": {
        "module":       "sources.nhs",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   ["postcodes"],
        "description":  "NHS ODS (GP, hospital, dentist) geocoded via postcodes → core_nhs_facilities.",
        "tables_written": ["core_nhs_facilities"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (40_000, 80_000),
        "critical":     False,
    },

    "naptan": {
        "module":       "sources.naptan",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   [],
        "description":  "DfT NaPTAN transport stop registry → core_transport_stops.",
        "tables_written": ["core_transport_stops"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (200_000, 500_000),
        "critical":     False,
    },

    "station_enrichment": {
        "module":       "sources.station_enrichment",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   ["naptan"],
        "description":  "Enrich core_transport_stops with CRS codes, TfL lines/zones/facilities.",
        "tables_written": [],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (500, 10_000),
        "critical":     False,
    },

    "nr_destinations": {
        "module":       "sources.nr_destinations",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   ["station_enrichment"],
        "description":  "Top commute destinations per NR station (timetable + HSP punctuality).",
        "tables_written": ["core_station_destinations"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (5_000, 20_000),
        "critical":     False,
    },

    "council_tax": {
        "module":       "sources.council_tax",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   [],
        "description":  "VOA Council Tax Bands A-H by LAD → core_council_tax_lad.",
        "tables_written": ["core_council_tax_lad"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (250, 400),
        "critical":     False,
    },

    "water": {
        "module":       "sources.water",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   ["boundaries"],
        "description":  "Ofwat water company service area polygons → core_water_company_lad.",
        "tables_written": ["core_water_company_lad"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (250, 400),
        "critical":     False,
    },

    "cycling_ptal": {
        "module":       "sources.cycling_ptal",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   [],
        "description":  "Census TS061 cycling/WFH (core_cycling_lsoa) + TfL PTAL 2015 London scores (core_ptal_lsoa).",
        "tables_written": ["core_cycling_lsoa", "core_ptal_lsoa"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (30_000, 36_000),   # core_cycling_lsoa
        "critical":     False,
    },

    "connectivity_metric": {
        "module":       "sources.connectivity_metric",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   [],
        "description":  "DfT Transport Connectivity Metric 2025 ODS → core_connectivity_lsoa.",
        "tables_written": ["core_connectivity_lsoa"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (30_000, 36_000),
        "critical":     False,
    },

    # ── One-time ─────────────────────────────────────────────────────────────

    "census": {
        "module":       "sources.census",
        "schedule":     SCHEDULE_ONE_TIME,
        "depends_on":   [],
        "description":  "ONS Census 2021 → core_census_lsoa (consolidated wide table) + core_census_ethnicity_ward.",
        "tables_written": ["core_census_lsoa", "core_census_ethnicity_ward"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (33_000, 36_000),
        "critical":     False,
    },

    "imd": {
        "module":       "sources.imd",
        "schedule":     SCHEDULE_ONE_TIME,
        "depends_on":   [],
        "description":  "MHCLG Index of Multiple Deprivation 2025 → core_imd_lsoa.",
        "tables_written": ["core_imd_lsoa"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (32_000, 34_500),
        "critical":     False,
    },

    "price_sqm": {
        "module":       "sources.price_sqm",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   ["postcodes"],
        "description":  "UCL House Price per Square Metre → core_price_sqm_lad, core_price_sqm_lsoa.",
        "tables_written": ["core_price_sqm_lsoa", "core_price_sqm_lad"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (30_000, 36_000),
        "critical":     False,
    },

    "inspire_parcels": {
        "module":       "sources.inspire_parcels",
        "schedule":     SCHEDULE_ONE_TIME,
        "depends_on":   [],
        "description":  "Land Registry INSPIRE Cadastral Parcel GML files → core_inspire_parcels (24M polygons).",
        "tables_written": ["core_inspire_parcels"],
        "cache_key_patterns": [],
        "expected_row_range": (15_000_000, 30_000_000),
        "critical":     False,
    },

    "llc": {
        "module":       "sources.llc",
        "schedule":     SCHEDULE_ONE_TIME,
        "depends_on":   [],
        "description":  "HM Land Registry Local Land Charges GML files → core_llc_charges (8.3M features, 4 charge types).",
        "tables_written": ["core_llc_charges"],
        "cache_key_patterns": [],
        "expected_row_range": (5_000_000, 12_000_000),
        "critical":     False,
    },

    # ── Derived (computed from core_* tables, no external downloads) ─────────

    "place_lsoa_mapping": {
        "module":       "derived.place_lsoa_mapping",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   ["place_names", "boundaries"],
        "description":  "Spatial join core_place_names × core_lsoa_boundaries → core_place_lsoa_mapping + core_place_lsoa_mapping_town.",
        "tables_written": ["core_place_lsoa_mapping", "core_place_lsoa_mapping_town"],
        "cache_key_patterns": ["lsoa_sess:*", "resolve:*"],
        "expected_row_range": (45_000, 65_000),
        "critical":     True,
    },

    "nhs_lsoa": {
        "module":       "derived.nhs_lsoa",
        "schedule":     SCHEDULE_ANNUAL,
        "depends_on":   ["nhs", "boundaries"],
        "description":  "Aggregate core_nhs_facilities to LSOA-level counts within 2km → core_nhs_lsoa.",
        "tables_written": ["core_nhs_lsoa"],
        "cache_key_patterns": ["area:*"],
        "expected_row_range": (30_000, 36_000),
        "critical":     False,
    },

    "price_by_bedrooms": {
        "module":       "derived.price_by_bedrooms",
        "schedule":     SCHEDULE_MONTHLY,
        "depends_on":   ["land_registry_full"],
        "description":  "Aggregate master table by LAD/year/type/bedrooms → core_price_by_bedrooms_lad.",
        "tables_written": ["core_price_by_bedrooms_lad"],
        "cache_key_patterns": ["price_history:*", "area:*"],
        "expected_row_range": (1_000, 100_000),
        "critical":     False,
    },
}

# Schedule groups for --schedule flag
SCHEDULE_GROUPS = {
    SCHEDULE_FOUNDATION: [SCHEDULE_FOUNDATION],
    SCHEDULE_MONTHLY:    [SCHEDULE_FOUNDATION, SCHEDULE_MONTHLY],
    SCHEDULE_QUARTERLY:  [SCHEDULE_FOUNDATION, SCHEDULE_MONTHLY, SCHEDULE_QUARTERLY],
    SCHEDULE_ANNUAL:     [SCHEDULE_FOUNDATION, SCHEDULE_MONTHLY, SCHEDULE_QUARTERLY, SCHEDULE_ANNUAL],
    "all":               [SCHEDULE_FOUNDATION, SCHEDULE_MONTHLY, SCHEDULE_QUARTERLY, SCHEDULE_ANNUAL, SCHEDULE_ONE_TIME],
}


# ---------------------------------------------------------------------------
# Dependency resolution
# ---------------------------------------------------------------------------

def topological_sort(names):
    """
    Return list of source names in dependency order (dependencies first).
    Raises ValueError if circular dependency detected.
    """
    visited = set()
    in_stack = set()
    result = []

    def visit(name):
        if name in in_stack:
            raise ValueError(f"Circular dependency detected involving '{name}'")
        if name in visited:
            return
        in_stack.add(name)
        for dep in SOURCE_REGISTRY[name]["depends_on"]:
            if dep not in SOURCE_REGISTRY:
                raise ValueError(f"Source '{name}' depends on unknown source '{dep}'")
            visit(dep)
        in_stack.discard(name)
        visited.add(name)
        result.append(name)

    for name in names:
        visit(name)
    return result


# ---------------------------------------------------------------------------
# Redis cache invalidation
# ---------------------------------------------------------------------------

def invalidate_cache(redis_url, cache_key_patterns):
    """Delete only the Redis keys matching the declared patterns for a source."""
    if not cache_key_patterns:
        return 0
    try:
        r = redis_lib.from_url(redis_url, decode_responses=True)
        deleted = 0
        for pattern in cache_key_patterns:
            keys = r.keys(pattern)
            if keys:
                deleted += r.delete(*keys)
        return deleted
    except Exception as e:
        print(f"    [cache] WARNING: Redis invalidation failed: {e}", flush=True)
        return 0


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def get_table_count(conn, table_name):
    """Return row count for a table, or None if table doesn't exist."""
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cur.fetchone()[0]
    except Exception:
        conn.rollback()
        return None


def run_source(name, db_url, redis_url, dry_run=False):
    """
    Execute one source/derived module:
    1. Record start in core_pipeline_runs
    2. Call module.run(db_url)
    3. Validate row count in expected_row_range
    4. Invalidate declared Redis key patterns
    5. Record result in core_pipeline_runs
    Returns True on success, False on failure.
    """
    entry = SOURCE_REGISTRY[name]
    module_path = entry["module"]
    primary_table = entry["tables_written"][0] if entry["tables_written"] else None
    expected_min, expected_max = entry["expected_row_range"]

    print(f"\n{'='*60}", flush=True)
    print(f"  {name}", flush=True)
    print(f"  {entry['description']}", flush=True)
    print(f"{'='*60}", flush=True)

    if dry_run:
        print(f"  [DRY RUN] Would run: {module_path}.run(db_url)", flush=True)
        return True

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    # Record start
    run_id = None
    rows_before = get_table_count(conn, primary_table) if primary_table else None
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO core_pipeline_runs
               (source_name, started_at, status, rows_before, source_url)
               VALUES (%s, %s, 'running', %s, %s)
               RETURNING id""",
            (name, datetime.now(timezone.utc), rows_before, entry.get("source_url")),
        )
        run_id = cur.fetchone()[0]
    conn.commit()

    t0 = time.time()
    success = False
    error_msg = None
    rows_after = None
    validation_notes = None
    final_status = "failed"

    try:
        # Import and run the module
        mod = importlib.import_module(module_path)
        rows_affected = mod.run(db_url)

        # Validate row count
        rows_after = get_table_count(conn, primary_table) if primary_table else rows_affected
        print(f"  Rows in {primary_table}: {rows_after:,}", flush=True)

        if rows_after is not None and not (expected_min <= rows_after <= expected_max):
            validation_notes = (
                f"Row count {rows_after:,} outside expected range "
                f"[{expected_min:,}, {expected_max:,}]"
            )
            print(f"  [VALIDATION FAILED] {validation_notes}", flush=True)
            final_status = "validation_failed"
        else:
            final_status = "success"
            success = True
            print(f"  [OK] {name} completed in {time.time()-t0:.1f}s", flush=True)

        # Invalidate Redis cache (only declared patterns)
        deleted = invalidate_cache(redis_url, entry["cache_key_patterns"])
        if deleted:
            print(f"  [cache] Invalidated {deleted} Redis keys", flush=True)

    except Exception as exc:
        error_msg = str(exc)
        print(f"  [ERROR] {name} failed: {error_msg}", flush=True)
        conn.rollback()

    finally:
        # Record result
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE core_pipeline_runs
                       SET finished_at=%s, status=%s, rows_after=%s,
                           validation_notes=%s, error_msg=%s
                       WHERE id=%s""",
                    (
                        datetime.now(timezone.utc),
                        final_status,
                        rows_after,
                        validation_notes,
                        error_msg,
                        run_id,
                    ),
                )
            conn.commit()
        except Exception:
            pass
        conn.close()

    return success


def run_migrate(db_url):
    """Run pending schema migrations before any pipeline work."""
    migrate_path = os.path.join(os.path.dirname(__file__), "migrate.py")
    import subprocess
    result = subprocess.run(
        [sys.executable, migrate_path],
        env={**os.environ, "DATABASE_URL": db_url},
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        print(result.stdout.strip(), flush=True)
    if result.returncode != 0:
        print(f"[ERROR] Migration failed:\n{result.stderr}", flush=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_list():
    """Print all registered sources with schedule, dependencies, tables."""
    print(f"\n{'Source':<25} {'Schedule':<12} {'Depends On':<30} {'Tables Written'}")
    print("-" * 110)
    for name, entry in SOURCE_REGISTRY.items():
        deps = ", ".join(entry["depends_on"]) or "—"
        tables = ", ".join(entry["tables_written"])
        print(f"{name:<25} {entry['schedule']:<12} {deps:<30} {tables}")
    print(f"\nTotal: {len(SOURCE_REGISTRY)} sources/derived modules registered.")


def cmd_status(db_url):
    """Show last run result per source from core_pipeline_runs."""
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (source_name)
                source_name, status, started_at, finished_at,
                rows_before, rows_after, validation_notes, error_msg
            FROM core_pipeline_runs
            ORDER BY source_name, started_at DESC
        """)
        rows = cur.fetchall()
    conn.close()

    if not rows:
        print("No pipeline runs recorded yet.")
        return

    print(f"\n{'Source':<25} {'Status':<20} {'Last Run':<25} {'Rows After':<15} {'Notes'}")
    print("-" * 110)
    for source_name, status, started_at, finished_at, rows_before, rows_after, notes, error in rows:
        note_str = (notes or error or "")[:40]
        rows_str = f"{rows_after:,}" if rows_after is not None else "—"
        print(f"{source_name:<25} {status:<20} {str(started_at)[:19]:<25} {rows_str:<15} {note_str}")


def cmd_dry_run(ordered):
    """Print execution order without running anything. ordered is already sorted."""
    print("\nExecution order (dry run):")
    for i, name in enumerate(ordered, 1):
        entry = SOURCE_REGISTRY[name]
        deps = ", ".join(entry["depends_on"]) or "none"
        print(f"  {i:2d}. {name:<25} [{entry['schedule']}] depends_on: {deps}")
    print(f"\nTotal: {len(ordered)} sources would run.")


def main():
    parser = argparse.ArgumentParser(
        description="PropertyPulse Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 pipeline.py --source postcodes
  python3 pipeline.py --schedule monthly
  python3 pipeline.py --all
  python3 pipeline.py --dry-run --all
  python3 pipeline.py --list
  python3 pipeline.py --status
        """,
    )
    parser.add_argument("--source",   help="Run a single source by name")
    parser.add_argument("--schedule", choices=list(SCHEDULE_GROUPS.keys()), help="Run all sources for a given schedule tier")
    parser.add_argument("--all",      action="store_true", help="Run all sources in dependency order")
    parser.add_argument("--dry-run",  action="store_true", help="Show what would run without executing")
    parser.add_argument("--list",     action="store_true", help="List all registered sources")
    parser.add_argument("--status",   action="store_true", help="Show last run result per source")
    args = parser.parse_args()

    if args.list:
        cmd_list()
        return

    if args.status:
        cmd_status(DB_DSN)
        return

    # Determine which sources to run
    if args.source:
        if args.source not in SOURCE_REGISTRY:
            print(f"Unknown source '{args.source}'. Use --list to see available sources.")
            sys.exit(1)
        names_to_run = [args.source]
    elif args.schedule:
        schedules = SCHEDULE_GROUPS[args.schedule]
        names_to_run = [n for n, e in SOURCE_REGISTRY.items() if e["schedule"] in schedules]
    elif args.all:
        names_to_run = list(SOURCE_REGISTRY.keys())
    else:
        parser.print_help()
        return

    # Resolve dependency order.
    # --source runs ONLY the named module (dependencies assumed already populated).
    # --schedule / --all expands the full transitive dependency chain.
    if args.source:
        ordered = names_to_run
    else:
        try:
            ordered = topological_sort(names_to_run)
        except ValueError as e:
            print(f"[ERROR] {e}")
            sys.exit(1)

    if args.dry_run:
        cmd_dry_run(ordered)
        return

    # Run migrations first
    print("\n--- Running schema migrations ---", flush=True)
    run_migrate(DB_DSN)

    # Execute sources in order
    print(f"\n--- Pipeline: {len(ordered)} sources to run ---", flush=True)
    t_start = time.time()
    failed = []

    for name in ordered:
        success = run_source(name, DB_DSN, REDIS_URL)
        if not success:
            entry = SOURCE_REGISTRY[name]
            if entry["critical"]:
                print(f"\n[ABORT] Critical source '{name}' failed. Pipeline aborted.", flush=True)
                sys.exit(1)
            else:
                failed.append(name)

    # Refresh materialized views (all per-LAD MVs for parent comparison + LAD-level aggregates)
    print("\n--- Refreshing materialized views ---", flush=True)
    try:
        conn = psycopg2.connect(DB_DSN)
        conn.autocommit = True
        cur = conn.cursor()
        for view in (
            "mv_parent_yearly_price_stats", "mv_parent_rolling_price_stats", "mv_parent_yearly_ppsf",
            "mv_parent_crime_rate", "mv_parent_noise_avg",
            "mv_lad_comparable_features",
            "mv_lad_crime_stats", "mv_lad_amenity_counts", "mv_lad_transport_mode_counts", "mv_lad_green_space_stats",
        ):
            t_mv = time.time()
            print(f"  REFRESH {view} ...", end=" ", flush=True)
            cur.execute(f"REFRESH MATERIALIZED VIEW {view}")
            print(f"done ({time.time() - t_mv:.0f}s)", flush=True)
        cur.close()
        conn.close()
    except Exception as e:
        print(f"  [WARN] Materialized view refresh failed: {e}", flush=True)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}", flush=True)
    print(f"Pipeline complete in {elapsed:.0f}s", flush=True)
    if failed:
        print(f"Non-critical failures: {', '.join(failed)}", flush=True)
    else:
        print("All sources completed successfully.", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
