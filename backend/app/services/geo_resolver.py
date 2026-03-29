"""
Geo-Resolution Service
Implements Build Bible Part 2, Section 2.2 — Rules 1-4

Rule 1: Postcode Search — match postcode_compact in core_postcodes
Rule 2: Place Name Search — trigram similarity on core_place_names
Rule 3: Parent Comparison — lookup core_lad_county_lookup for parent_comparison
Rule 4: Data Querying Hierarchy — returns resolved codes for downstream queries
"""
import re
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Regex patterns for classifying search input
POSTCODE_RE = re.compile(
    r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}$", re.IGNORECASE
)
# Outward-code-only (district) postcode: e.g. E1W, SW9, EC2A, LS1
DISTRICT_POSTCODE_RE = re.compile(
    r"^[A-Z]{1,2}[0-9][0-9A-Z]?$", re.IGNORECASE
)

# Place types we consider "area" types for place-name resolution
AREA_PLACE_TYPES = (
    'City', 'Town', 'Suburban Area', 'Village', 'Other Settlement', 'Hamlet'
)


async def resolve_search(db: AsyncSession, query: str) -> dict:
    """
    Resolve a user search query into geographic codes.

    Returns the exact response shape from Bible Part 6, Section 6.1:
    {
      "query": "CR5 1RA",
      "type": "postcode",
      "resolved_codes": {
        "lsoa": "E01001024",
        "ward": "E05011445",
        "lad": "E09000008",
        "parent": "Greater London"
      },
      "coordinates": {"lat": 51.320, "lon": -0.135}
    }
    """
    q = query.strip()

    # Rule 1a: Full postcode (e.g. CR5 1RA)
    if POSTCODE_RE.match(q):
        return await _resolve_postcode(db, q)

    # Rule 1b: District/outward-code-only postcode (e.g. E1W, SW9, EC2A)
    if DISTRICT_POSTCODE_RE.match(q):
        return await _resolve_district_postcode(db, q)

    # Rule 2: Place Name Search
    return await _resolve_place_name(db, q)


async def _fuzzy_suggestions(db: AsyncSession, query: str) -> list:
    """Return up to 5 fuzzy place-name suggestions for a failed query."""
    q_lower = query.strip().lower()
    await db.execute(text("SET LOCAL pg_trgm.similarity_threshold = 0.5"))
    result = await db.execute(
        text("""
            SELECT pn.place_name AS label, pn.place_type AS type,
                   COALESCE(lb.lad_name, pn.lad_code) AS area
            FROM core_place_names pn
            LEFT JOIN core_lad_boundaries lb ON pn.lad_code = lb.lad_code
            WHERE pn.place_name_lower % :q
              AND pn.place_type = ANY(:types)
            ORDER BY
                CASE
                    WHEN pn.place_type IN ('City','Town') AND similarity(pn.place_name_lower, :q) >= 0.9 THEN 0
                    WHEN pn.place_type IN ('City','Town') THEN 1
                    WHEN pn.place_type = 'Suburban Area' AND similarity(pn.place_name_lower, :q) >= 0.9 THEN 2
                    WHEN pn.place_type = 'Other Settlement' AND similarity(pn.place_name_lower, :q) >= 0.9 THEN 3
                    WHEN pn.place_type = 'Village' AND similarity(pn.place_name_lower, :q) >= 0.9 THEN 4
                    WHEN pn.place_type = 'Hamlet' AND similarity(pn.place_name_lower, :q) >= 0.9 THEN 5
                    ELSE 6
                END ASC,
                similarity(pn.place_name_lower, :q) DESC
            LIMIT 5
        """),
        {"q": q_lower, "types": list(AREA_PLACE_TYPES)},
    )
    return [dict(r) for r in result.mappings().all()]


async def _resolve_postcode(db: AsyncSession, query: str) -> dict:
    """Bible Rule 1: Strip spaces, uppercase, query core_postcodes by postcode_compact."""
    compact = query.replace(" ", "").upper()

    result = await db.execute(
        text("""
            SELECT postcode, lsoa_code, msoa_code, ward_code, lad_code,
                   latitude, longitude
            FROM core_postcodes
            WHERE postcode_compact = :compact
            LIMIT 1
        """),
        {"compact": compact},
    )
    row = result.mappings().first()

    if not row:
        suggestions = await _fuzzy_suggestions(db, query)
        return {
            "query": query, "type": "postcode",
            "error": "Postcode not found",
            "suggestions": suggestions,
        }

    # Rule 3: Parent Comparison
    parent = await _resolve_parent(db, row["lad_code"])

    return {
        "query": query,
        "type": "postcode",
        "resolved_codes": {
            "lsoa": row["lsoa_code"],
            "msoa": row["msoa_code"],
            "ward": row["ward_code"],
            "lad": row["lad_code"],
            "parent": parent,
        },
        "coordinates": {
            "lat": float(row["latitude"]) if row["latitude"] else None,
            "lon": float(row["longitude"]) if row["longitude"] else None,
        },
    }


async def _resolve_district_postcode(db: AsyncSession, query: str) -> dict:
    """Resolve a district (outward-only) postcode like E1W, SW9, EC2A, SW1, M1.
    Strategy:
      1. Try exact outward match: LEFT(postcode_compact, len-3) = district
         (covers M1, SW9, LS1, E1W, EC2A — districts that ARE valid outward codes)
      2. If no rows, try prefix match restricted to outwards of length len(district)+1
         (covers SW1 → SW1A/SW1E/SW1H, W1 → W1A/W1B etc. which are area prefixes)
    This correctly disambiguates SW1 (Westminster sub-districts) from SW10/SW11."""
    district = query.replace(" ", "").upper()

    # Attempt 1: exact outward match
    where_clause = "LEFT(postcode_compact, LENGTH(postcode_compact)-3) = :district"
    params: dict = {"district": district}

    result = await db.execute(
        text("""
            SELECT lad_code, COUNT(*) as cnt,
                   AVG(latitude) as lat, AVG(longitude) as lon
            FROM core_postcodes
            WHERE LEFT(postcode_compact, LENGTH(postcode_compact)-3) = :district
              AND latitude IS NOT NULL
            GROUP BY lad_code
            ORDER BY cnt DESC
            LIMIT 1
        """),
        params,
    )
    row = result.mappings().first()

    # Attempt 2: SW1-style area codes → match only letter-suffix outwards (SW1A, SW1E...)
    # to avoid SW10/SW11 etc. which are different districts entirely
    if not row:
        sub_len = len(district) + 1
        letter_after = f"{district}[A-Za-z]%"
        result2 = await db.execute(
            text("""
                SELECT lad_code, COUNT(*) as cnt,
                       AVG(latitude) as lat, AVG(longitude) as lon
                FROM core_postcodes
                WHERE postcode_compact LIKE :prefix
                  AND LENGTH(LEFT(postcode_compact, LENGTH(postcode_compact)-3)) = :sublen
                  AND SUBSTRING(postcode_compact, :pos, 1) ~ '[A-Za-z]'
                  AND latitude IS NOT NULL
                GROUP BY lad_code
                ORDER BY cnt DESC
                LIMIT 1
            """),
            {"prefix": district + "%", "sublen": sub_len, "pos": len(district) + 1},
        )
        row = result2.mappings().first()

    if not row:
        suggestions = await _fuzzy_suggestions(db, query)
        return {
            "query": query, "type": "postcode",
            "error": "Postcode district not found",
            "suggestions": suggestions,
        }

    parent = await _resolve_parent(db, row["lad_code"])
    return {
        "query": query,
        "type": "postcode_district",
        "resolved_codes": {
            "lsoa": None,
            "ward": None,
            "lad": row["lad_code"],
            "parent": parent,
        },
        "coordinates": {
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
        },
    }


async def _resolve_place_name(db: AsyncSession, query: str) -> dict:
    """Bible Rule 2: Lowercase, trigram similarity on core_place_names."""
    q_lower = query.lower()

    # Raise trigram threshold to 0.5 to avoid spurious matches for non-English cities
    await db.execute(text("SET LOCAL pg_trgm.similarity_threshold = 0.5"))

    result = await db.execute(
        text("""
            SELECT place_name, ward_code, lad_code, latitude, longitude
            FROM core_place_names
            WHERE place_name_lower % :query
              AND place_type = ANY(:types)
              -- Villages/Hamlets only qualify on near-exact name match (sim>=0.9)
              -- to prevent "Walton Cardiff" matching "Cardiff" or similar
              AND (
                  place_type NOT IN ('Village','Hamlet','Other Settlement')
                  OR similarity(place_name_lower, :query2) >= 0.9
              )
            ORDER BY
                -- Bucket 0: City/Town with sim>=0.9
                -- Bucket 1: City/Town with sim<0.9
                -- Bucket 2: Suburban Area with sim>=0.9
                -- Bucket 3: Other Settlement with sim>=0.9 (e.g. Croydon as London suburb)
                -- Bucket 4: Village with sim>=0.9
                -- Bucket 5: Hamlet with sim>=0.9
                CASE
                    WHEN place_type IN ('City','Town') AND similarity(place_name_lower, :query2) >= 0.9 THEN 0
                    WHEN place_type IN ('City','Town') THEN 1
                    WHEN place_type = 'Suburban Area' AND similarity(place_name_lower, :query2) >= 0.9 THEN 2
                    WHEN place_type = 'Other Settlement' AND similarity(place_name_lower, :query2) >= 0.9 THEN 3
                    WHEN place_type = 'Village' AND similarity(place_name_lower, :query2) >= 0.9 THEN 4
                    WHEN place_type = 'Hamlet' AND similarity(place_name_lower, :query2) >= 0.9 THEN 5
                    ELSE 6
                END ASC,
                similarity(place_name_lower, :query2) DESC
            LIMIT 1
        """),
        {"query": q_lower, "query2": q_lower, "types": list(AREA_PLACE_TYPES)},
    )
    row = result.mappings().first()

    if not row:
        suggestions = await _fuzzy_suggestions(db, query)
        return {
            "query": query, "type": "place_name",
            "error": "Place not found",
            "suggestions": suggestions,
        }

    lad_code = row["lad_code"]

    # Spatial fallback: 33% of core_place_names rows have NULL lad_code.
    # Resolve via point-in-polygon against core_lad_boundaries.
    if not lad_code and row["latitude"] and row["longitude"]:
        fallback = await db.execute(
            text("""
                SELECT lad_code
                FROM core_lad_boundaries
                WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                LIMIT 1
            """),
            {"lon": float(row["longitude"]), "lat": float(row["latitude"])},
        )
        fb_row = fallback.mappings().first()
        if fb_row:
            lad_code = fb_row["lad_code"]

    # Rule 3: Parent Comparison
    parent = await _resolve_parent(db, lad_code)

    return {
        "query": query,
        "type": "place_name",
        "resolved_codes": {
            "lsoa": None,  # Place names resolve to ward/LAD level, not LSOA
            "ward": row["ward_code"],
            "lad": lad_code,
            "parent": parent,
        },
        "coordinates": {
            "lat": float(row["latitude"]) if row["latitude"] else None,
            "lon": float(row["longitude"]) if row["longitude"] else None,
        },
    }


async def _resolve_parent(db: AsyncSession, lad_code: str) -> str:
    """Bible Rule 3: Determine parent comparison from core_lad_county_lookup."""
    if not lad_code:
        return "England"

    result = await db.execute(
        text("""
            SELECT parent_comparison
            FROM core_lad_county_lookup
            WHERE lad_code = :lad_code
        """),
        {"lad_code": lad_code},
    )
    row = result.mappings().first()

    if row and row["parent_comparison"]:
        return row["parent_comparison"]

    return "England"
