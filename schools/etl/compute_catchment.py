#!/usr/bin/env python3
"""Pre-compute catchment probability model: school→LSOA matrix.

For each school, find all LSOAs within a reasonable distance and compute
an estimated admission probability based on:
  1. Distance from school to LSOA (approximated via other schools' postcodes)
  2. School capacity vs pupil count (utilisation)
  3. Admissions data (oversubscription ratio)
  4. Last Distance Offered (if available)

Uses postcode_lsoa + school coordinates to derive school→LSOA pairs.
No core_lsoa_boundaries geometry required.

The result is stored in schools.catchment_model (urn, lsoa_code, distance_m,
admission_probability, is_within_ldo).

This runs server-side on Hetzner where PostGIS is available.
"""

import logging
import math
import os

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://property:tbFDrBtIM8wQRkPN2luJo21q@localhost:5432/property",
)

# Max radius for catchment search (metres)
PRIMARY_RADIUS_M = 3000
SECONDARY_RADIUS_M = 8000
ALLTHROUGH_RADIUS_M = 6000
DEFAULT_RADIUS_M = 5000


def get_phase_radius(phase):
    if phase == "Primary":
        return PRIMARY_RADIUS_M
    if phase == "Secondary":
        return SECONDARY_RADIUS_M
    if phase == "All-through":
        return ALLTHROUGH_RADIUS_M
    return DEFAULT_RADIUS_M


def distance_decay_probability(distance_m, max_radius_m):
    """Exponential distance decay. At 0m → ~1.0, at max_radius → ~0.05."""
    if distance_m <= 0:
        return 1.0
    if distance_m >= max_radius_m:
        return 0.0
    k = 3.0 / max_radius_m
    return math.exp(-k * distance_m)


def compute_catchment(conn):
    """Build the catchment probability matrix using postcode→LSOA mapping."""
    with conn.cursor() as cur:
        # Step 1: Build a postcode→LSOA lookup that also has geometry from institutions
        # We'll use each distinct LSOA's centroid (avg lat/lon of schools in that LSOA) as a proxy
        logger.info("Building LSOA centroid estimates from school postcodes...")
        cur.execute("""
            SELECT pl.lsoa_code,
                   AVG(i.latitude) AS centroid_lat,
                   AVG(i.longitude) AS centroid_lon
            FROM schools.institutions i
            JOIN postcode_lsoa pl ON REPLACE(UPPER(pl.postcode), ' ', '') = REPLACE(UPPER(i.postcode), ' ', '')
            WHERE i.latitude IS NOT NULL AND i.longitude IS NOT NULL
            GROUP BY pl.lsoa_code
        """)
        lsoa_centroids = {}
        for row in cur.fetchall():
            lsoa_centroids[row[0]] = (row[1], row[2])
        logger.info("Found %d LSOAs with school-derived centroids", len(lsoa_centroids))

        if not lsoa_centroids:
            logger.error("No LSOA centroids could be derived — aborting")
            return

        # Step 2: Get all open schools with coordinates
        cur.execute("""
            SELECT i.urn, i.phase, i.capacity, i.pupil_count,
                   i.latitude, i.longitude
            FROM schools.institutions i
            WHERE i.is_open = true
              AND i.latitude IS NOT NULL AND i.longitude IS NOT NULL
              AND i.phase IN ('Primary', 'Secondary', 'All-through', '16 plus')
        """)
        schools = cur.fetchall()
        logger.info("Processing %d schools", len(schools))

        # Step 3: Get admissions data
        cur.execute("""
            SELECT DISTINCT ON (urn) urn, applications_received, offers_made,
                   is_oversubscribed, last_distance_offered
            FROM schools.admissions
            ORDER BY urn, academic_year DESC
        """)
        admissions = {r[0]: {
            "applications": r[1],
            "offers": r[2],
            "oversubscribed": r[3],
            "ldo": r[4],
        } for r in cur.fetchall()}
        logger.info("Loaded admissions data for %d schools", len(admissions))

        # Step 4: For each school, find nearby LSOAs using Haversine distance
        all_rows = []
        for idx, school in enumerate(schools):
            urn, phase, capacity, pupil_count, lat, lon = school
            radius_m = get_phase_radius(phase)

            adm = admissions.get(urn, {})
            ldo = adm.get("ldo")
            apps = adm.get("applications")
            offers = adm.get("offers")

            # Oversubscription pressure factor
            pressure = 1.0
            if apps and offers and offers > 0:
                ratio = apps / offers
                if ratio > 2.0:
                    pressure = 0.4
                elif ratio > 1.5:
                    pressure = 0.6
                elif ratio > 1.0:
                    pressure = 0.8

            # Capacity utilisation factor
            cap_factor = 1.0
            if capacity and pupil_count and capacity > 0:
                util = pupil_count / capacity
                if util >= 1.0:
                    cap_factor = 0.5
                elif util >= 0.95:
                    cap_factor = 0.7

            effective_radius = radius_m
            if ldo and ldo > 0:
                effective_radius = min(ldo * 1.2, radius_m)

            # Find LSOAs within radius using Haversine
            for lsoa_code, (c_lat, c_lon) in lsoa_centroids.items():
                dist = _haversine(lat, lon, c_lat, c_lon)
                if dist > radius_m:
                    continue

                base_prob = distance_decay_probability(dist, effective_radius)
                adj_prob = base_prob * pressure * cap_factor
                adj_prob = max(0.0, min(1.0, adj_prob))

                within_ldo = None
                if ldo and ldo > 0:
                    within_ldo = dist <= ldo

                if adj_prob > 0.01:
                    all_rows.append((
                        urn, lsoa_code, int(dist),
                        round(adj_prob, 4), within_ldo,
                    ))

            if (idx + 1) % 1000 == 0:
                logger.info("Processed %d / %d schools (%d rows so far)",
                            idx + 1, len(schools), len(all_rows))

        logger.info("Total catchment rows: %d", len(all_rows))

        if all_rows:
            cur.execute("TRUNCATE schools.catchment_model")
            batch = 10000
            for i in range(0, len(all_rows), batch):
                execute_values(
                    cur,
                    """
                    INSERT INTO schools.catchment_model (
                        urn, lsoa_code, distance_m,
                        admission_probability, is_within_ldo
                    ) VALUES %s
                    """,
                    all_rows[i:i+batch],
                    page_size=5000,
                )
            conn.commit()
            logger.info("Loaded %d catchment rows", len(all_rows))
        else:
            logger.warning("No catchment rows to load")


def _haversine(lat1, lon1, lat2, lon2):
    """Return distance in metres between two lat/lon points."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        compute_catchment(conn)
    finally:
        conn.close()
    logger.info("Catchment model computation complete")


if __name__ == "__main__":
    main()
