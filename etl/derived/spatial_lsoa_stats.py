"""
derived/spatial_lsoa_stats.py — Pre-compute per-LSOA spatial statistics

Populates:
    core_lsoa_green_space  — nearest park, parks within 1km, green cover %, sports/rec count
    core_lsoa_transport    — nearest rail/metro/tram station

These enable parent comparisons for spatial metrics (nearest_station, nearest_park,
parks_1km, green_cover, sports_recreation) via:
    AVG(metric) FROM core_lsoa_X JOIN core_lsoa_boundaries WHERE lad_code = ANY(:parent_lads)

Run from etl/ directory:
    python3 -m derived.spatial_lsoa_stats
"""

from __future__ import annotations

import os
import sys
import time

import psycopg2


DB_URL = os.environ.get("DATABASE_URL", "postgresql:///ukproperty")

# Green space types matching tab_environment.py
PARK_TYPES = ("Public Park Or Garden",)
SPORT_TYPES = (
    "Golf Course", "Tennis Court", "Bowling Green",
    "Other Sports Facility", "Play Space", "Playing Field",
)

# Rail/metro/tram stop types matching tab_lifestyle.py
STATION_TYPES = ("RLY", "RSE", "RPL", "MET", "PLT", "TMU", "STR")


def compute_green_space(conn):
    """Compute per-LSOA green space metrics using LSOA centroids."""
    cur = conn.cursor()

    print("  Computing nearest park per LSOA...", flush=True)
    t0 = time.time()

    # Use LATERAL join: for each LSOA centroid, find nearest park
    cur.execute("""
        INSERT INTO core_lsoa_green_space (lsoa_code, nearest_park_m, parks_1km, green_cover_pct, sports_rec_1km)
        SELECT
            lb.lsoa_code,
            np.distance_m,
            pk.park_count,
            pk.green_cover_pct,
            sr.sport_count
        FROM core_lsoa_boundaries lb
        CROSS JOIN LATERAL (
            SELECT ST_Distance(
                gs.geom::geography,
                ST_Centroid(lb.geom)::geography
            )::int AS distance_m
            FROM core_green_space gs
            WHERE gs.geom IS NOT NULL
              AND gs.site_type = ANY(%s)
            ORDER BY gs.geom <-> ST_Centroid(lb.geom)
            LIMIT 1
        ) np
        CROSS JOIN LATERAL (
            SELECT
                COUNT(*) AS park_count,
                ROUND(
                    (COALESCE(SUM(ST_Area(gs.geom::geography) / 10000), 0) / 314.16 * 100)::numeric,
                    2
                )::numeric(5,2) AS green_cover_pct
            FROM core_green_space gs
            WHERE gs.geom IS NOT NULL
              AND gs.site_type = ANY(%s)
              AND ST_DWithin(
                  gs.geom::geography,
                  ST_Centroid(lb.geom)::geography,
                  1000
              )
        ) pk
        CROSS JOIN LATERAL (
            SELECT COUNT(*) AS sport_count
            FROM core_green_space gs
            WHERE gs.geom IS NOT NULL
              AND gs.site_type = ANY(%s)
              AND ST_DWithin(
                  gs.geom::geography,
                  ST_Centroid(lb.geom)::geography,
                  1000
              )
        ) sr
        WHERE lb.geom IS NOT NULL
        ON CONFLICT (lsoa_code) DO UPDATE SET
            nearest_park_m = EXCLUDED.nearest_park_m,
            parks_1km = EXCLUDED.parks_1km,
            green_cover_pct = EXCLUDED.green_cover_pct,
            sports_rec_1km = EXCLUDED.sports_rec_1km
    """, (list(PARK_TYPES), list(PARK_TYPES), list(SPORT_TYPES)))
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_lsoa_green_space")
    count = cur.fetchone()[0]
    cur.close()
    elapsed = time.time() - t0
    print(f"  core_lsoa_green_space: {count:,} rows ({elapsed:.0f}s)", flush=True)
    return count


def compute_transport(conn):
    """Compute per-LSOA nearest station distance."""
    cur = conn.cursor()

    print("  Computing nearest station per LSOA...", flush=True)
    t0 = time.time()

    cur.execute("""
        INSERT INTO core_lsoa_transport (lsoa_code, nearest_station_m)
        SELECT
            lb.lsoa_code,
            ns.distance_m
        FROM core_lsoa_boundaries lb
        CROSS JOIN LATERAL (
            SELECT ST_Distance(
                ts.geom::geography,
                ST_Centroid(lb.geom)::geography
            )::int AS distance_m
            FROM core_transport_stops ts
            WHERE ts.geom IS NOT NULL
              AND ts.stop_type = ANY(%s)
            ORDER BY ts.geom <-> ST_Centroid(lb.geom)
            LIMIT 1
        ) ns
        WHERE lb.geom IS NOT NULL
        ON CONFLICT (lsoa_code) DO UPDATE SET
            nearest_station_m = EXCLUDED.nearest_station_m
    """, (list(STATION_TYPES),))
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_lsoa_transport")
    count = cur.fetchone()[0]
    cur.close()
    elapsed = time.time() - t0
    print(f"  core_lsoa_transport: {count:,} rows ({elapsed:.0f}s)", flush=True)
    return count


def main() -> int:
    print(f"DATABASE_URL={DB_URL}", flush=True)
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False

    compute_green_space(conn)
    compute_transport(conn)

    # Quick validation
    cur = conn.cursor()
    cur.execute("""
        SELECT
            ROUND(AVG(nearest_park_m)) AS avg_park_m,
            ROUND(AVG(parks_1km)::numeric, 1) AS avg_parks,
            ROUND(AVG(green_cover_pct)::numeric, 1) AS avg_cover,
            ROUND(AVG(sports_rec_1km)::numeric, 1) AS avg_sports
        FROM core_lsoa_green_space
    """)
    row = cur.fetchone()
    print(f"  Green space averages: park={row[0]}m, parks_1km={row[1]}, cover={row[2]}%, sports={row[3]}", flush=True)

    cur.execute("SELECT ROUND(AVG(nearest_station_m)) FROM core_lsoa_transport")
    avg_station = cur.fetchone()[0]
    print(f"  Transport averages: station={avg_station}m", flush=True)

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
