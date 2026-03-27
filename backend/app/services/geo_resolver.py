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

    # Rule 1: Postcode Search
    if POSTCODE_RE.match(q):
        return await _resolve_postcode(db, q)

    # Rule 2: Place Name Search
    return await _resolve_place_name(db, q)


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
        return {"query": query, "type": "postcode", "error": "Postcode not found"}

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


async def _resolve_place_name(db: AsyncSession, query: str) -> dict:
    """Bible Rule 2: Lowercase, trigram similarity on core_place_names."""
    q_lower = query.lower()

    result = await db.execute(
        text("""
            SELECT place_name, ward_code, lad_code, latitude, longitude
            FROM core_place_names
            WHERE place_name_lower % :query
            ORDER BY similarity(place_name_lower, :query) DESC
            LIMIT 1
        """),
        {"query": q_lower},
    )
    row = result.mappings().first()

    if not row:
        return {"query": query, "type": "place_name", "error": "Place not found"}

    # Rule 3: Parent Comparison
    parent = await _resolve_parent(db, row["lad_code"])

    return {
        "query": query,
        "type": "place_name",
        "resolved_codes": {
            "lsoa": None,  # Place names resolve to ward/LAD level, not LSOA
            "ward": row["ward_code"],
            "lad": row["lad_code"],
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
