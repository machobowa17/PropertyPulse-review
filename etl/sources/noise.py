"""
sources/noise.py — Defra Strategic Noise Maps → core_noise

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_noise)

Data source: Defra Round 4 Strategic Noise Maps (2022, based on 2021 data)
  - Road noise: WCS from environment.data.gov.uk (10m raster grid)
  - Rail noise: WCS from environment.data.gov.uk (10m raster grid)
  - Air noise:  Not currently ingested (limited airport-only coverage)

Approach:
  1. Tile England into 50km × 50km grid cells (BNG / EPSG:27700)
  2. Download each tile as GeoTIFF from DEFRA WCS
  3. Load into PostGIS temp raster table via raster2pgsql
  4. Sample every postcode centroid within the tile bbox
  5. Upsert into core_noise, compute noise_band from max dB
  6. Clean up temp table and file, move to next tile

Requires: PostGIS raster extension (CREATE EXTENSION postgis_raster),
          raster2pgsql on PATH.
"""

import os
import subprocess
import sys
import tempfile
import time

import psycopg2

from constants import SCHEDULE_ANNUAL, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "noise",
    "description":        "Defra Round 4 strategic noise maps (road + rail) → core_noise at postcode level.",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         ["postcodes"],
    "tables_written":     [TABLE_NAMES["noise"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (200_000, 1_500_000),
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TILE_SIZE = 25_000  # 25km tiles in BNG metres (WCS limit ~30km)

# WCS coverage IDs (dataset UUID + coverage name)
_ROAD_DATASET_UUID = "562c9d56-7c2d-4d42-83bb-578d6e97a517"
_RAIL_DATASET_UUID = "3fb3c2d7-292c-4e0a-bd5b-d8e4e1fe2947"

_ROAD_COVERAGE = f"{_ROAD_DATASET_UUID}__Road_Noise_Lden_England_Round_4_All"
_RAIL_COVERAGE = f"{_RAIL_DATASET_UUID}__Rail_Noise_Lden_England_Round_4_All"

_WCS_URL_TEMPLATE = (
    "https://environment.data.gov.uk/geoservices/datasets/{dataset_uuid}/wcs?"
    "service=WCS&version=2.0.1&request=GetCoverage"
    "&CoverageId={coverage_id}"
    "&format=image/tiff"
    "&subset=E({e_min},{e_max})&subset=N({n_min},{n_max})"
    "&subsettingCrs=http://www.opengis.net/def/crs/EPSG/0/27700"
)

# Noise band classification (Lden — day-evening-night weighted average)
# Based on WHO Environmental Noise Guidelines for the European Region (2018)
_NOISE_BANDS = [
    (75, "Very High"),
    (65, "High"),
    (55, "Moderate"),
    (40, "Low"),
    (0,  "Quiet"),
]

# raster2pgsql path
_RASTER2PGSQL = os.environ.get(
    "RASTER2PGSQL",
    "/Applications/Postgres.app/Contents/Versions/latest/bin/raster2pgsql",
)

_PSQL = os.environ.get(
    "PSQL_PATH",
    "/Applications/Postgres.app/Contents/Versions/latest/bin/psql",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify_band(road_db, rail_db, air_db):
    """Return noise band based on maximum Lden across sources."""
    values = [v for v in (road_db, rail_db, air_db) if v is not None and v > 0]
    if not values:
        return None
    max_db = max(values)
    for threshold, band in _NOISE_BANDS:
        if max_db >= threshold:
            return band
    return "Quiet"


def _download_tile(dataset_uuid, coverage_id, e_min, n_min, e_max, n_max, dest_path):
    """Download a single tile GeoTIFF from DEFRA WCS. Returns True on success."""
    url = _WCS_URL_TEMPLATE.format(
        dataset_uuid=dataset_uuid,
        coverage_id=coverage_id,
        e_min=e_min, e_max=e_max,
        n_min=n_min, n_max=n_max,
    )
    try:
        result = subprocess.run(
            ["curl", "-sL", "-o", dest_path, url],
            capture_output=True, timeout=120,
        )
        if result.returncode != 0 or not os.path.exists(dest_path):
            return False
        if os.path.getsize(dest_path) < 1000:
            return False  # Too small — likely error HTML/JSON
        # Verify it's actually a TIFF (not a JSON/HTML error)
        with open(dest_path, "rb") as f:
            magic = f.read(4)
        if magic[:2] in (b"II", b"MM"):  # TIFF byte order markers
            return True
        return False
    except Exception:
        return False


def _load_raster_to_postgis(tif_path, table_name, db_url):
    """Load a GeoTIFF into a PostGIS raster table using raster2pgsql."""
    # Parse db_url for psql connection
    # raster2pgsql outputs SQL; pipe to psql
    cmd_raster = [_RASTER2PGSQL, "-s", "27700", "-d", "-t", "100x100", "-I", tif_path, table_name]
    cmd_psql = [_PSQL, db_url, "-q"]

    p1 = subprocess.Popen(cmd_raster, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p2 = subprocess.Popen(cmd_psql, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p1.stdout.close()
    _, err = p2.communicate(timeout=120)
    return p2.returncode == 0


def _ensure_bng_table(conn):
    """Create pre-computed BNG coordinate table for postcodes (one-time)."""
    cur = conn.cursor()
    cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'tmp_postcode_bng')")
    if cur.fetchone()[0]:
        cur.close()
        return
    print("  Creating BNG lookup table (one-time)...", flush=True)
    cur.execute("""
        CREATE TABLE tmp_postcode_bng AS
        SELECT postcode,
               ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 27700) AS geom_bng,
               ST_X(ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 27700)) AS easting,
               ST_Y(ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 27700)) AS northing
        FROM core_postcodes
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude BETWEEN 49.5 AND 56.0 AND longitude BETWEEN -7.0 AND 2.5
    """)
    cur.execute("CREATE INDEX idx_tmp_postcode_bng_en ON tmp_postcode_bng (easting, northing)")
    cur.execute("CREATE INDEX idx_tmp_postcode_bng_geom ON tmp_postcode_bng USING gist (geom_bng)")
    cur.close()
    print("  BNG lookup table ready.", flush=True)


def _sample_postcodes(conn, rast_table, value_col, e_min, n_min, e_max, n_max):
    """Sample postcodes within the BNG tile from a PostGIS raster table.
    Uses pre-computed BNG coordinates (tmp_postcode_bng) to avoid per-row ST_Transform.
    Returns list of (postcode, value) tuples."""
    cur = conn.cursor()
    cur.execute(f"""
        SELECT b.postcode,
               ROUND(ST_Value(r.rast, b.geom_bng)::numeric, 1)
        FROM {rast_table} r,
             tmp_postcode_bng b
        WHERE b.easting BETWEEN {e_min} AND {e_max}
          AND b.northing BETWEEN {n_min} AND {n_max}
          AND ST_Intersects(r.rast, b.geom_bng)
    """)
    rows = cur.fetchall()
    cur.close()
    # Filter out nodata (0 or None) — noise rasters use 0 for unmapped areas
    return [(pc, float(val)) for pc, val in rows if val is not None and float(val) > 0]


def _get_tile_list(conn):
    """Get list of 50km BNG tiles that contain postcodes."""
    cur = conn.cursor()
    cur.execute(f"""
        SELECT
            (FLOOR(ST_X(ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 27700)) / {_TILE_SIZE}) * {_TILE_SIZE})::int,
            (FLOOR(ST_Y(ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 27700)) / {_TILE_SIZE}) * {_TILE_SIZE})::int,
            COUNT(*)
        FROM core_postcodes
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude BETWEEN 49.5 AND 56.0 AND longitude BETWEEN -7.0 AND 2.5
        GROUP BY 1, 2
        ORDER BY 1, 2
    """)
    tiles = [(int(r[0]), int(r[1]), int(r[2])) for r in cur.fetchall()]
    cur.close()
    return tiles


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """Download Defra noise rasters tile by tile, sample at postcodes, insert into core_noise."""
    conn = psycopg2.connect(db_url)
    conn.autocommit = True

    # Ensure PostGIS raster extension
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis_raster")
    cur.close()

    # Ensure BNG lookup table exists
    _ensure_bng_table(conn)

    # Get tile list
    tiles = _get_tile_list(conn)
    total_tiles = len(tiles)
    total_postcodes = sum(t[2] for t in tiles)
    print(f"  Noise ingest: {total_tiles} tiles, {total_postcodes:,} postcodes", flush=True)

    # --- Resume support: check which tiles already have data ---
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT
            (FLOOR(b.easting / {_TILE_SIZE}) * {_TILE_SIZE})::int,
            (FLOOR(b.northing / {_TILE_SIZE}) * {_TILE_SIZE})::int
        FROM {TABLE_NAMES['noise']} n
        JOIN tmp_postcode_bng b ON b.postcode = n.postcode
    """)
    done_tiles = set(cur.fetchall())
    cur.close()
    skipped = 0

    t0 = time.time()
    tmpdir = tempfile.mkdtemp(prefix="noise_")
    upserted_total = 0

    for idx, (e_min, n_min, pc_count) in enumerate(tiles, 1):
        e_max = e_min + _TILE_SIZE
        n_max = n_min + _TILE_SIZE
        tile_label = f"E{e_min//1000}k_N{n_min//1000}k"

        # Skip tiles already ingested (resume)
        if (e_min, n_min) in done_tiles:
            skipped += 1
            continue

        elapsed = time.time() - t0
        done_count = idx - skipped
        rate = done_count / elapsed if elapsed > 0 else 0
        remaining = total_tiles - idx
        eta = remaining / rate / 60 if rate > 0 else 0
        print(f"  [{idx}/{total_tiles}] {tile_label} ({pc_count:,} postcodes) "
              f"[{elapsed/60:.0f}m elapsed, ~{eta:.0f}m remaining]", flush=True)

        # --- Download and sample road + rail for this tile ---
        road_samples = {}
        rail_samples = {}

        road_tif = os.path.join(tmpdir, f"road_{tile_label}.tif")
        road_ok = _download_tile(_ROAD_DATASET_UUID, _ROAD_COVERAGE,
                                 e_min, n_min, e_max, n_max, road_tif)
        if road_ok:
            if _load_raster_to_postgis(road_tif, "tmp_noise_road", db_url):
                try:
                    samples = _sample_postcodes(conn, "tmp_noise_road", "road_noise_db",
                                                e_min, n_min, e_max, n_max)
                    for pc, val in samples:
                        road_samples[pc] = val
                    if samples:
                        print(f"    road: {len(samples):,} postcodes sampled", flush=True)
                except Exception as e:
                    print(f"    road sample failed: {e}", flush=True)
                    conn.rollback()
            try:
                cur = conn.cursor()
                cur.execute("DROP TABLE IF EXISTS tmp_noise_road")
                cur.close()
            except Exception:
                conn.rollback()
        if os.path.exists(road_tif):
            os.unlink(road_tif)

        rail_tif = os.path.join(tmpdir, f"rail_{tile_label}.tif")
        rail_ok = _download_tile(_RAIL_DATASET_UUID, _RAIL_COVERAGE,
                                 e_min, n_min, e_max, n_max, rail_tif)
        if rail_ok:
            if _load_raster_to_postgis(rail_tif, "tmp_noise_rail", db_url):
                try:
                    samples = _sample_postcodes(conn, "tmp_noise_rail", "rail_noise_db",
                                                e_min, n_min, e_max, n_max)
                    for pc, val in samples:
                        rail_samples[pc] = val
                    if samples:
                        print(f"    rail: {len(samples):,} postcodes sampled", flush=True)
                except Exception as e:
                    print(f"    rail sample failed: {e}", flush=True)
                    conn.rollback()
            try:
                cur = conn.cursor()
                cur.execute("DROP TABLE IF EXISTS tmp_noise_rail")
                cur.close()
            except Exception:
                conn.rollback()
        if os.path.exists(rail_tif):
            os.unlink(rail_tif)

        # --- Upsert this tile's data immediately (incremental save) ---
        tile_postcodes = set(road_samples.keys()) | set(rail_samples.keys())
        if tile_postcodes:
            rows = []
            for pc in tile_postcodes:
                road_db = road_samples.get(pc)
                rail_db = rail_samples.get(pc)
                band = _classify_band(road_db, rail_db, None)
                rows.append((
                    pc,
                    round(road_db, 1) if road_db else None,
                    round(rail_db, 1) if rail_db else None,
                    None,  # air_noise_db
                    band,
                ))
            cur = conn.cursor()
            batch_size = 5_000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                args = ",".join(
                    cur.mogrify("(%s,%s,%s,%s,%s)", r).decode() for r in batch
                )
                cur.execute(f"""
                    INSERT INTO {TABLE_NAMES['noise']}
                        (postcode, road_noise_db, rail_noise_db, air_noise_db, noise_band)
                    VALUES {args}
                    ON CONFLICT (postcode) DO UPDATE SET
                        road_noise_db = EXCLUDED.road_noise_db,
                        rail_noise_db = EXCLUDED.rail_noise_db,
                        air_noise_db  = EXCLUDED.air_noise_db,
                        noise_band    = EXCLUDED.noise_band
                """)
            conn.commit()
            upserted_total += len(rows)
            cur.close()
            print(f"    upserted {len(rows):,} postcodes (total: {upserted_total:,})", flush=True)

    # Clean up tmpdir
    try:
        os.rmdir(tmpdir)
    except OSError:
        pass

    if skipped:
        print(f"  Skipped {skipped} tiles (already ingested from previous run)", flush=True)

    # Final count
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['noise']}")
    final_count = cur.fetchone()[0]
    cur.close()

    elapsed = time.time() - t0
    print(f"  core_noise: {final_count:,} rows ({elapsed/60:.1f} minutes)", flush=True)

    # Quick stats
    cur = conn.cursor()
    cur.execute(f"""
        SELECT noise_band, COUNT(*) as cnt
        FROM {TABLE_NAMES['noise']}
        WHERE noise_band IS NOT NULL
        GROUP BY noise_band ORDER BY cnt DESC
    """)
    for row in cur.fetchall():
        print(f"    {row[0]}: {row[1]:,}", flush=True)
    cur.execute(f"""
        SELECT ROUND(AVG(road_noise_db)::numeric, 1) as avg_road,
               ROUND(AVG(rail_noise_db)::numeric, 1) as avg_rail,
               COUNT(road_noise_db) as road_count,
               COUNT(rail_noise_db) as rail_count
        FROM {TABLE_NAMES['noise']}
    """)
    row = cur.fetchone()
    print(f"    avg_road={row[0]}dB ({row[2]:,}), avg_rail={row[1]}dB ({row[3]:,})", flush=True)
    cur.close()
    conn.close()

    return final_count


if __name__ == "__main__":
    db = os.environ.get("DATABASE_URL", "postgresql:///ukproperty")
    print(f"DATABASE_URL={db}", flush=True)
    run(db)
