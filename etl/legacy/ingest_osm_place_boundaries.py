"""
Ingest OSM place boundaries for England & Wales.
Uses Overpass API to download boundary=administrative + place polygons
for suburbs, towns, villages, neighbourhoods, etc.

Creates core_place_boundaries table with polygon geometries.
After loading, populates lad_code via ST_Within against core_lad_boundaries.
"""
import asyncio
import json
import sys
import time

import asyncpg
import httpx

DB = "postgresql://postgres@localhost:5432/ukproperty"

# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# England + Wales bounding box (generous)
BBOX = "49.8,-6.5,56.0,2.0"

# Query for place boundaries in England & Wales
# We want: suburbs, towns, villages, neighbourhoods, cities, hamlets
# These can be tagged as:
#   - boundary=place (modern OSM tagging)
#   - place=suburb/town/village/neighbourhood with a closed way or relation
OVERPASS_QUERY = f"""
[out:json][timeout:600];
(
  // Relations with boundary=administrative and admin_level=10 (suburbs/neighbourhoods in UK)
  relation["boundary"="administrative"]["admin_level"="10"]({BBOX});
  // Relations tagged as place boundaries
  relation["boundary"="place"]({BBOX});
  // Relations with place tag that have boundary geometry
  relation["place"~"^(suburb|neighbourhood|town|village|hamlet|city)$"]["type"="boundary"]({BBOX});
  // Closed ways tagged as place boundaries
  way["boundary"="place"]({BBOX});
);
out body;
>;
out skel qt;
"""

# Simpler query that gets relations with their geometries directly
OVERPASS_QUERY_GEOM = f"""
[out:json][timeout:600];
(
  relation["boundary"="place"]({BBOX});
  relation["boundary"="administrative"]["admin_level"="10"]({BBOX});
);
out geom;
"""


def relation_to_multipolygon(element: dict) -> dict | None:
    """Convert an Overpass relation with geometry to a GeoJSON MultiPolygon."""
    if "members" not in element:
        return None

    outer_rings = []
    inner_rings = []

    for member in element["members"]:
        if member.get("type") != "way" or "geometry" not in member:
            continue
        role = member.get("role", "")
        coords = [(pt["lon"], pt["lat"]) for pt in member["geometry"]]
        if len(coords) < 4:
            continue
        # Ensure ring is closed
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        if role == "outer" or role == "":
            outer_rings.append(coords)
        elif role == "inner":
            inner_rings.append(coords)

    if not outer_rings:
        return None

    # Simple approach: each outer ring is a polygon, inner rings assigned to first outer
    polygons = []
    for i, outer in enumerate(outer_rings):
        if i == 0:
            polygons.append([outer] + inner_rings)
        else:
            polygons.append([outer])

    return {
        "type": "MultiPolygon",
        "coordinates": [poly for poly in polygons],
    }


async def main():
    print("=== OSM Place Boundaries Ingestion ===\n")

    # Step 1: Download from Overpass API
    print("Downloading from Overpass API (this may take a few minutes)...")
    async with httpx.AsyncClient(timeout=httpx.Timeout(660.0)) as client:
        resp = await client.post(
            OVERPASS_URL,
            data={"data": OVERPASS_QUERY_GEOM},
        )
        resp.raise_for_status()
        data = resp.json()

    elements = data.get("elements", [])
    print(f"Downloaded {len(elements)} elements from Overpass")

    # Step 2: Parse relations into place boundaries
    places = []
    for el in elements:
        if el.get("type") != "relation":
            continue

        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue

        # Determine place type
        place_type = tags.get("place") or tags.get("boundary", "place")

        # Convert to GeoJSON geometry
        geom = relation_to_multipolygon(el)
        if not geom:
            continue

        places.append({
            "osm_id": el["id"],
            "name": name,
            "name_lower": name.lower(),
            "place_type": place_type,
            "geom": json.dumps(geom),
        })

    print(f"Parsed {len(places)} place boundaries with geometry")

    if not places:
        print("ERROR: No place boundaries found. Check Overpass query.")
        sys.exit(1)

    # Step 3: Load into database
    conn = await asyncpg.connect(DB)

    await conn.execute("DROP TABLE IF EXISTS core_place_boundaries CASCADE;")
    await conn.execute("""
        CREATE TABLE core_place_boundaries (
            id          SERIAL PRIMARY KEY,
            osm_id      BIGINT UNIQUE NOT NULL,
            place_name  TEXT NOT NULL,
            place_name_lower TEXT NOT NULL,
            place_type  TEXT,
            lad_code    TEXT,
            geom        GEOMETRY(MultiPolygon, 4326) NOT NULL
        );
    """)

    # Insert in batches
    inserted = 0
    skipped = 0
    batch_size = 100
    for i in range(0, len(places), batch_size):
        batch = places[i : i + batch_size]
        for p in batch:
            try:
                await conn.execute(
                    """
                    INSERT INTO core_place_boundaries (osm_id, place_name, place_name_lower, place_type, geom)
                    VALUES ($1, $2, $3, $4, ST_SetSRID(ST_GeomFromGeoJSON($5), 4326))
                    ON CONFLICT (osm_id) DO NOTHING
                    """,
                    p["osm_id"],
                    p["name"],
                    p["name_lower"],
                    p["place_type"],
                    p["geom"],
                )
                inserted += 1
            except Exception as e:
                skipped += 1
                if skipped <= 5:
                    print(f"  Skipped {p['name']} (osm_id={p['osm_id']}): {e}")

        print(f"  Inserted {min(i + batch_size, len(places))}/{len(places)}...")

    print(f"\nInserted {inserted} boundaries, skipped {skipped}")

    # Step 4: Create indexes
    print("Creating indexes...")
    await conn.execute(
        "CREATE INDEX idx_place_boundaries_name ON core_place_boundaries(place_name_lower);"
    )
    await conn.execute(
        "CREATE INDEX idx_place_boundaries_geom ON core_place_boundaries USING GIST(geom);"
    )
    await conn.execute(
        "CREATE INDEX idx_place_boundaries_lad ON core_place_boundaries(lad_code);"
    )
    # Trigram index for fuzzy search
    await conn.execute(
        "CREATE INDEX idx_place_boundaries_trgm ON core_place_boundaries USING GIN(place_name_lower gin_trgm_ops);"
    )

    # Step 5: Populate lad_code via spatial join
    print("Populating lad_code via spatial join...")
    await conn.execute("""
        UPDATE core_place_boundaries pb
        SET lad_code = lb.lad_code
        FROM core_lad_boundaries lb
        WHERE ST_Within(ST_Centroid(pb.geom), lb.geom)
          AND pb.lad_code IS NULL
    """)
    updated = await conn.fetchval(
        "SELECT COUNT(*) FROM core_place_boundaries WHERE lad_code IS NOT NULL"
    )
    print(f"Assigned lad_code to {updated} boundaries")

    # Step 6: Verify
    total = await conn.fetchval("SELECT COUNT(*) FROM core_place_boundaries")
    by_type = await conn.fetch("""
        SELECT place_type, COUNT(*) as cnt
        FROM core_place_boundaries
        GROUP BY place_type
        ORDER BY cnt DESC
    """)
    print(f"\nTotal: {total} place boundaries")
    print("By type:")
    for r in by_type:
        print(f"  {r['place_type']:20s}  {r['cnt']}")

    # Check some known places
    print("\nSpot checks:")
    for name in ["coulsdon", "brixton", "soho", "notting hill", "didsbury", "shoreditch"]:
        rows = await conn.fetch(
            "SELECT place_name, place_type, lad_code FROM core_place_boundaries WHERE place_name_lower = $1",
            name,
        )
        if rows:
            for r in rows:
                lad_name = await conn.fetchval(
                    "SELECT lad_name FROM core_lad_boundaries WHERE lad_code = $1",
                    r["lad_code"],
                )
                print(f"  {r['place_name']:20s}  {r['place_type']:15s}  {lad_name or 'unknown'}")
        else:
            print(f"  {name:20s}  NOT FOUND")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
