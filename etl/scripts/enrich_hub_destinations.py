"""Add major hub destinations to branch-line stations via MOTIS.

The CIF timetable parser only captures DIRECT services. Branch-line stations
(Tattenham Corner line, Isle of Wight, rural branches) may only show local
stops as destinations, missing the major hubs reachable with one change.

This script:
1. Identifies stations where NO destination is a major employment hub
2. Finds the nearest hubs by haversine distance
3. Queries MOTIS for multi-modal journey times
4. Inserts the best hub destinations (keeping existing local ones)

Usage (inside API container):
  MOTIS_BASE_URL=http://128.140.103.160:8080 \
  python3 enrich_hub_destinations.py

Env: DATABASE_URL_SYNC, MOTIS_BASE_URL, CRS_MAPPING_PATH
"""
import json
import math
import os
import sys
import time

import psycopg2

# Add etl/ to path for shared lib imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib.motis import motis_journey, MOTIS_BASE_URL  # noqa: E402

DB_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://ukproperty:ukproperty_dev@db:5432/ukproperty",
)

_MAPPING_PATH = os.environ.get(
    "CRS_MAPPING_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "crs_naptan_mapping.json"),
)

# Major employment hubs across GB — stations that branch-line commuters
# would typically travel to. Grouped by region for nearest-hub matching.
HUBS = {
    # London terminals + key interchanges
    "LBG": "London Bridge",
    "VIC": "London Victoria",
    "WAT": "London Waterloo",
    "PAD": "London Paddington",
    "KGX": "King's Cross",
    "EUS": "London Euston",
    "CHX": "Charing Cross",
    "CST": "Cannon Street",
    "LST": "Liverpool Street",
    "STP": "St Pancras",
    "CLJ": "Clapham Junction",
    "ECR": "East Croydon",
    "SRA": "Stratford",
    # Regional hubs
    "MAN": "Manchester Piccadilly",
    "MCO": "Manchester Oxford Road",
    "BHM": "Birmingham New Street",
    "LDS": "Leeds",
    "EDB": "Edinburgh",
    "GLC": "Glasgow Central",
    "GLQ": "Glasgow Queen Street",
    "LIV": "Liverpool Lime Street",
    "BRI": "Bristol Temple Meads",
    "NCL": "Newcastle",
    "CDF": "Cardiff Central",
    "SHF": "Sheffield",
    "NTG": "Nottingham",
    "LEI": "Leicester",
    "CBG": "Cambridge",
    "OXF": "Oxford",
    "RDG": "Reading",
    "SOT": "Southampton Central",
    "COV": "Coventry",
    "PLY": "Plymouth",
    "EXD": "Exeter St Davids",
    "YRK": "York",
    "ABD": "Aberdeen",
    "IVR": "Inverness",
    "SWA": "Swansea",
    "NWP": "Newport (South Wales)",
    "PBO": "Peterborough",
    "NRW": "Norwich",
    "IPW": "Ipswich",
    "BRH": "Brighton",
}

MAX_JOURNEY_MIN = 120
MAX_HUB_DESTS = 5


def _haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance in km between two points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def main():
    print("Hub destination enrichment for branch-line stations")
    print(f"  MOTIS: {MOTIS_BASE_URL}")

    # Load CRS mapping
    if not os.path.exists(_MAPPING_PATH):
        print(f"  ERROR: CRS mapping not found at {_MAPPING_PATH}")
        return
    with open(_MAPPING_PATH) as f:
        crs_mapping = json.load(f)
    print(f"  CRS mapping: {len(crs_mapping):,} stations")

    # Build hub coords
    hub_coords = {}
    for hub_crs in HUBS:
        entry = crs_mapping.get(hub_crs, {})
        if entry.get("lat") and entry.get("lon"):
            hub_coords[hub_crs] = (entry["lat"], entry["lon"])
    print(f"  Hub stations with coords: {len(hub_coords)}")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Find stations where NO destination is a major hub
    hub_crs_list = list(HUBS.keys())
    cur.execute("""
        SELECT sd.origin_crs, ARRAY_AGG(sd.dest_crs) as existing_dests
        FROM core_station_destinations sd
        GROUP BY sd.origin_crs
        HAVING NOT bool_or(sd.dest_crs = ANY(%s))
    """, (hub_crs_list,))
    no_hub_stations = cur.fetchall()
    print(f"  Stations with no hub destinations: {len(no_hub_stations):,}")

    # Also find stations that ARE hubs themselves (skip those)
    hub_set = set(HUBS.keys())
    candidates = [(crs, dests) for crs, dests in no_hub_stations if crs not in hub_set]
    print(f"  Candidates (excluding hub stations themselves): {len(candidates):,}")

    added_total = 0
    skipped = 0
    no_route = 0

    for i, (origin_crs, existing_dests) in enumerate(candidates):
        origin_entry = crs_mapping.get(origin_crs, {})
        origin_lat = origin_entry.get("lat")
        origin_lon = origin_entry.get("lon")
        if not origin_lat or not origin_lon:
            skipped += 1
            continue

        # Find nearest hubs by haversine (try closest 10, keep best by journey time)
        hub_distances = []
        for hub_crs, (hub_lat, hub_lon) in hub_coords.items():
            if hub_crs in existing_dests:
                continue  # Already a destination
            dist_km = _haversine_km(origin_lat, origin_lon, hub_lat, hub_lon)
            if dist_km < 200:  # Only consider hubs within 200km
                hub_distances.append((hub_crs, dist_km))

        hub_distances.sort(key=lambda x: x[1])
        nearest_hubs = hub_distances[:10]  # Try top 10 nearest

        if not nearest_hubs:
            skipped += 1
            continue

        # Query MOTIS for each candidate hub
        hub_results = []
        for hub_crs, dist_km in nearest_hubs:
            hub_entry = crs_mapping.get(hub_crs, {})
            result = motis_journey(origin_lat, origin_lon, hub_entry["lat"], hub_entry["lon"])
            if result and result["journey_min"] <= MAX_JOURNEY_MIN:
                hub_results.append((hub_crs, result))
            else:
                no_route += 1
            time.sleep(0.3)

        # Sort by journey time, keep best N
        hub_results.sort(key=lambda x: x[1]["journey_min"])
        best_hubs = hub_results[:MAX_HUB_DESTS]

        if not best_hubs:
            continue

        # Get current max rank for this origin
        cur.execute(
            "SELECT COALESCE(MAX(rank), 0) FROM core_station_destinations WHERE origin_crs = %s",
            (origin_crs,)
        )
        max_rank = cur.fetchone()[0]

        # Insert hub destinations
        for j, (hub_crs, result) in enumerate(best_hubs, 1):
            # Check for existing row (shouldn't exist, but be safe)
            cur.execute(
                "SELECT 1 FROM core_station_destinations WHERE origin_crs = %s AND dest_crs = %s",
                (origin_crs, hub_crs)
            )
            if cur.fetchone():
                continue

            cur.execute("""
                INSERT INTO core_station_destinations
                    (origin_crs, dest_crs, dest_name, journey_min, trains_per_hour,
                     rank, journey_type, num_changes, modes, legs)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                origin_crs,
                hub_crs,
                HUBS[hub_crs],
                result["journey_min"],
                None,  # No direct trains_per_hour for these routes
                max_rank + j,
                result["journey_type"],
                result["num_changes"],
                result["modes"],
                json.dumps(result["legs"]),
            ))
            added_total += 1

        conn.commit()

        done = i + 1
        if done % 50 == 0:
            print(f"  [{done:,}/{len(candidates):,}] added={added_total} skipped={skipped} no_route={no_route}", flush=True)

    conn.close()

    print(f"\nDone!")
    print(f"  Hub destinations added: {added_total:,}")
    print(f"  Skipped (no coords/no nearby hubs): {skipped:,}")
    print(f"  No MOTIS route: {no_route:,}")


if __name__ == "__main__":
    main()
