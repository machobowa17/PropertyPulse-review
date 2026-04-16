"""
derived/flood_lsoa.py — Compute per-LSOA flood zone exposure

Populates:
    core_flood_lsoa — (lsoa_code, in_zone_2, in_zone_3)

For each LSOA, checks whether any Flood Zone 2 or Flood Zone 3 polygon
intersects its boundary geometry.  Uses ST_Intersects with the GiST
index on core_flood_zones.geom for efficient spatial lookup.

Source tables:
    core_flood_zones    — 3.5M polygons (flood_zone = '2' | '3')
    core_lsoa_boundaries — ~35K LSOA polygons

Run from etl/ directory:
    python3 -m derived.flood_lsoa
"""

from __future__ import annotations

import os
import sys
import time

import psycopg2


DB_URL = os.environ.get("DATABASE_URL", "postgresql:///ukproperty")


def compute_flood_lsoa(conn):
    """Compute per-LSOA flood zone exposure via spatial intersection."""
    cur = conn.cursor()

    print("  Computing flood zone exposure per LSOA...", flush=True)
    t0 = time.time()

    # Use EXISTS subqueries — much faster than JOIN for boolean flags
    # because the planner can short-circuit after the first matching polygon.
    cur.execute("""
        INSERT INTO core_flood_lsoa (lsoa_code, in_zone_2, in_zone_3)
        SELECT
            lb.lsoa_code,
            EXISTS (
                SELECT 1 FROM core_flood_zones fz
                WHERE fz.flood_zone = '2'
                  AND ST_Intersects(fz.geom, lb.geom)
            ) AS in_zone_2,
            EXISTS (
                SELECT 1 FROM core_flood_zones fz
                WHERE fz.flood_zone = '3'
                  AND ST_Intersects(fz.geom, lb.geom)
            ) AS in_zone_3
        FROM core_lsoa_boundaries lb
        WHERE lb.geom IS NOT NULL
        ON CONFLICT (lsoa_code) DO UPDATE SET
            in_zone_2 = EXCLUDED.in_zone_2,
            in_zone_3 = EXCLUDED.in_zone_3
    """)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM core_flood_lsoa")
    total = cur.fetchone()[0]
    cur.execute("SELECT SUM(in_zone_2::int), SUM(in_zone_3::int) FROM core_flood_lsoa")
    z2, z3 = cur.fetchone()
    cur.close()

    elapsed = time.time() - t0
    print(f"  core_flood_lsoa: {total:,} rows ({z2:,} zone 2, {z3:,} zone 3) [{elapsed:.0f}s]", flush=True)
    return total


def main() -> int:
    print(f"DATABASE_URL={DB_URL}", flush=True)
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False

    compute_flood_lsoa(conn)

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
