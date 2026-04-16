"""
sources/air_quality.py — Defra PCM Air Quality → core_air_quality + core_air_quality_lad

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_air_quality)

Data files required in etl/data/air_quality/ (or set env vars to override):
    AQ_DIR   — directory containing Defra PCM CSVs:
                mapno2{year}.csv, mappm25{year}g.csv, mappm10{year}g.csv

Historical data (2018-2023) is downloaded directly from Defra if not cached locally.
Current year data must be pre-downloaded and placed in AQ_DIR.

Download from:
    https://uk-air.defra.gov.uk/data/pcm-data
"""

import os
import urllib.request

from psycopg2.extras import execute_values
import psycopg2

from constants import SCHEDULE_ANNUAL, TABLE_NAMES
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":               "air_quality",
    "description":        "Defra PCM 1km grid (NO2, PM2.5, PM10) → core_air_quality; spatial aggregation to LAD → core_air_quality_lad.",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         ["boundaries"],
    "tables_written":     [TABLE_NAMES["air_quality"], TABLE_NAMES["air_quality_lad"]],
    "cache_key_patterns": [],
    "expected_row_range": (200_000, 600_000),
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFRA_BASE = "https://uk-air.defra.gov.uk/datastore/pcm"

# Years to aggregate to core_air_quality_lad (spatial join, cumulative)
_HISTORY_YEARS = [2018, 2019, 2020, 2021, 2022, 2023]

# File name patterns for each pollutant
_FILE_PATTERNS = {
    "no2":  "mapno2{year}.csv",
    "pm25": "mappm25{year}g.csv",
    "pm10": "mappm10{year}g.csv",
}

# ---------------------------------------------------------------------------
# Helper: resolve data directory
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_aq_dir():
    path = os.environ.get("AQ_DIR")
    if path:
        return path
    return os.path.join(_ETL_DATA_DIR, "air_quality")


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _parse_grid_csv_content(content):
    """Parse Defra 1km grid CSV content. Returns dict of {(x, y): value}."""
    points = {}
    lines = content.splitlines()
    data_start = False
    for line in lines:
        stripped = line.strip().lower()
        if stripped.startswith("gridcode") or stripped.startswith("ukgridcode"):
            data_start = True
            continue
        if not data_start:
            continue
        parts = line.split(",")
        try:
            x   = float(parts[1])
            y   = float(parts[2])
            val = float(parts[3])
            points[(x, y)] = val
        except (ValueError, IndexError):
            continue
    return points


def _parse_grid_csv_file(filepath):
    """Parse a local Defra 1km grid CSV file. Returns dict of {(x, y): value}."""
    points = {}
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        data_start = False
        for line in f:
            stripped = line.strip().lower()
            if stripped.startswith("gridcode") or stripped.startswith("ukgridcode"):
                data_start = True
                continue
            if not data_start:
                continue
            parts = line.split(",")
            try:
                x   = float(parts[1])
                y   = float(parts[2])
                val = float(parts[3])
                points[(x, y)] = val
            except (ValueError, IndexError):
                continue
    return points


def _download_csv(url):
    """Download a CSV from Defra. Returns content string, or None on failure."""
    print(f"    Downloading {url}...", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse-ETL/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    WARNING: Failed to download {url}: {e}", flush=True)
        return None


def _load_pollutants_for_year(year, aq_dir):
    """Load all 3 pollutant files for a given year (local first, then Defra download).

    Returns dict: pollutant_name → {(x, y): value}
    """
    result = {}
    for pollutant, pattern in _FILE_PATTERNS.items():
        filename    = pattern.format(year=year)
        local_path  = os.path.join(aq_dir, filename)

        if os.path.exists(local_path):
            print(f"    {pollutant}: using local {filename}", flush=True)
            points = _parse_grid_csv_file(local_path)
        else:
            url     = f"{_DEFRA_BASE}/{filename}"
            content = _download_csv(url)
            points  = _parse_grid_csv_content(content) if content else {}

        print(f"    {pollutant}: {len(points):,} grid points", flush=True)
        result[pollutant] = points

    return result


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest Defra PCM air quality data.

    Strategy:
    1. Find the most recent local year in AQ_DIR (file presence detection).
    2. Truncate core_air_quality; load current year grid → PostGIS points.
    3. For each year in _HISTORY_YEARS + current year:
       - If already in core_air_quality_lad, skip.
       - Otherwise, load pollutant data, insert into temp grid table,
         spatial join with core_lad_boundaries, aggregate to core_air_quality_lad.
    4. Return final row count in core_air_quality.
    """
    aq_dir = _resolve_aq_dir()
    os.makedirs(aq_dir, exist_ok=True)
    print(f"  AQ data dir: {aq_dir}", flush=True)

    # Detect current year from local files (most recent year with NO2 data)
    current_year = None
    for year in range(2030, 2017, -1):
        fname = os.path.join(aq_dir, _FILE_PATTERNS["no2"].format(year=year))
        if os.path.exists(fname):
            current_year = year
            break

    if current_year is None:
        raise FileNotFoundError(
            f"No Defra PCM CSV files found in {aq_dir}. "
            "Download from https://uk-air.defra.gov.uk/data/pcm-data and place in etl/data/air_quality/."
        )

    print(f"  Current year detected: {current_year}", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    # ------------------------------------------------------------------
    # Part 1: core_air_quality — current year grid points
    # ------------------------------------------------------------------
    print(f"  Loading current year ({current_year}) grid → core_air_quality...", flush=True)
    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['air_quality']}_new (LIKE {TABLE_NAMES['air_quality']} INCLUDING ALL)")
    conn.commit()

    pollutants = _load_pollutants_for_year(current_year, aq_dir)
    no2_data   = pollutants.get("no2",  {})
    pm25_data  = pollutants.get("pm25", {})
    pm10_data  = pollutants.get("pm10", {})

    all_coords = set(no2_data.keys()) | set(pm25_data.keys()) | set(pm10_data.keys())
    print(f"    Unique grid points: {len(all_coords):,}", flush=True)

    rows = [
        (x, y,
         no2_data.get((x, y)),
         pm25_data.get((x, y)),
         pm10_data.get((x, y)),
         current_year)
        for (x, y) in all_coords
    ]

    execute_values(
        cur,
        f"""
        INSERT INTO {TABLE_NAMES['air_quality']}_new
            (grid_x, grid_y, no2_ugm3, pm25_ugm3, pm10_ugm3, year)
        VALUES %s
        """,
        rows,
        page_size=10_000,
    )

    # Build PostGIS geometry from BNG (EPSG:27700) → WGS84 (EPSG:4326)
    cur.execute(f"""
        UPDATE {TABLE_NAMES['air_quality']}_new
        SET geom = ST_Transform(ST_SetSRID(ST_MakePoint(grid_x, grid_y), 27700), 4326)
        WHERE geom IS NULL
    """)
    conn.commit()
    print(f"    Inserted {len(rows):,} current-year grid rows", flush=True)

    # ------------------------------------------------------------------
    # Part 2: core_air_quality_lad — spatial aggregate each year
    # ------------------------------------------------------------------
    all_years = _HISTORY_YEARS + [current_year]

    # Temp table for spatial join (created once, truncated per year)
    cur.execute("""
        CREATE TEMP TABLE IF NOT EXISTS tmp_aq_grid (
            grid_x    DOUBLE PRECISION,
            grid_y    DOUBLE PRECISION,
            no2_ugm3  NUMERIC(8,2),
            pm25_ugm3 NUMERIC(8,2),
            pm10_ugm3 NUMERIC(8,2),
            geom      geometry(Point, 4326)
        )
    """)
    conn.commit()

    for year in all_years:
        # Skip if already aggregated
        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAMES['air_quality_lad']} WHERE year = %s",
            (year,),
        )
        existing = cur.fetchone()[0]
        if existing > 0:
            print(f"  Year {year}: {existing} LAD rows already present — skipping.", flush=True)
            continue

        print(f"\n  Processing year {year} → core_air_quality_lad...", flush=True)

        if year == current_year:
            # Reuse already-loaded data
            y_no2  = no2_data
            y_pm25 = pm25_data
            y_pm10 = pm10_data
        else:
            y_pols = _load_pollutants_for_year(year, aq_dir)
            y_no2  = y_pols.get("no2",  {})
            y_pm25 = y_pols.get("pm25", {})
            y_pm10 = y_pols.get("pm10", {})

        y_all_coords = set(y_no2.keys()) | set(y_pm25.keys()) | set(y_pm10.keys())
        if not y_all_coords:
            print(f"    No data for year {year}, skipping.", flush=True)
            continue

        y_rows = [
            (x, y, y_no2.get((x, y)), y_pm25.get((x, y)), y_pm10.get((x, y)))
            for (x, y) in y_all_coords
        ]

        cur.execute("TRUNCATE tmp_aq_grid")
        execute_values(
            cur,
            "INSERT INTO tmp_aq_grid (grid_x, grid_y, no2_ugm3, pm25_ugm3, pm10_ugm3) VALUES %s",
            y_rows,
            page_size=10_000,
        )

        cur.execute("""
            UPDATE tmp_aq_grid
            SET geom = ST_Transform(ST_SetSRID(ST_MakePoint(grid_x, grid_y), 27700), 4326)
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_tmp_aq_geom ON tmp_aq_grid USING GIST (geom)
        """)
        conn.commit()
        print(f"    {len(y_rows):,} grid points, running spatial join...", flush=True)

        cur.execute(
            f"""
            INSERT INTO {TABLE_NAMES['air_quality_lad']}
                (lad_code, year, no2_ugm3, pm25_ugm3, pm10_ugm3)
            SELECT lb.lad_code, %s,
                   ROUND(AVG(t.no2_ugm3)::numeric,  2),
                   ROUND(AVG(t.pm25_ugm3)::numeric, 2),
                   ROUND(AVG(t.pm10_ugm3)::numeric, 2)
            FROM tmp_aq_grid t
            JOIN {TABLE_NAMES['lad_boundaries']} lb ON ST_Intersects(lb.geom, t.geom)
            GROUP BY lb.lad_code
            ON CONFLICT (lad_code, year) DO UPDATE SET
                no2_ugm3  = EXCLUDED.no2_ugm3,
                pm25_ugm3 = EXCLUDED.pm25_ugm3,
                pm10_ugm3 = EXCLUDED.pm10_ugm3
            """,
            (year,),
        )
        conn.commit()

        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAMES['air_quality_lad']} WHERE year = %s",
            (year,),
        )
        print(f"    Year {year}: {cur.fetchone()[0]} LAD rows inserted", flush=True)

    # Clean up temp table
    cur.execute("DROP TABLE IF EXISTS tmp_aq_grid")
    conn.commit()

    # Return final row count in core_air_quality
    blue_green_swap(conn, TABLE_NAMES['air_quality'])
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['air_quality']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
