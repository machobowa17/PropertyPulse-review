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

from app.constants import TABLE_NAMES
from app.services.helpers import build_country_metadata, infer_country_from_geo_codes

# Regex patterns for classifying search input
POSTCODE_RE = re.compile(
    r"^[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}$", re.IGNORECASE
)
# Outward-code-only (district) postcode: e.g. E1W, SW9, EC2A, LS1
DISTRICT_POSTCODE_RE = re.compile(
    r"^[A-Z]{1,2}[0-9][0-9A-Z]?$", re.IGNORECASE
)

# Address pattern: optional flat/unit prefix, then number + street, optionally followed by comma + postcode/area
# Group 1: sub-building prefix (e.g. "Flat 2" / "Unit 3A") — optional
# Group 2: PAON number (e.g. "42", "42A", "10-12")
# Group 3: street name
# Group 4: trailing part after comma (postcode or area hint)
ADDRESS_RE = re.compile(
    r"^(?:(?:flat|unit|apt|apartment)\s+(\w+),?\s*)?(\d+(?:[a-zA-Z]|-\d+)?)\s+(.+?)(?:,\s*(.+))?$",
    re.IGNORECASE,
)

# Words that indicate the "street" part is actually a street name (not "Bed Semi")
_STREET_WORDS = frozenset({
    "street", "st", "road", "rd", "lane", "ln", "avenue", "ave", "drive", "dr",
    "close", "cl", "court", "ct", "crescent", "cres", "place", "pl", "way",
    "terrace", "gardens", "grove", "park", "hill", "rise", "row", "square",
    "mews", "walk", "green", "gate", "passage", "yard", "mount", "vale",
    "broadway", "circus", "high", "bridge", "church", "chapel", "manor",
    "field", "meadow", "wood", "heath", "common", "view", "end",
})

# Place types we consider "area" types for place-name resolution
AREA_PLACE_TYPES = (
    'City', 'Town', 'Suburban Area', 'Village', 'Other Settlement', 'Hamlet'
)


def _resolved_country_metadata(*codes, fallback: str = "England") -> dict:
    selected_country, status = infer_country_from_geo_codes(*codes, fallback=fallback)
    return build_country_metadata(selected_country, status)


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

    # Rule 1b: Address search (e.g. "42 High Street, CR5 1RA", "Flat 2, 42 High Street")
    # Must come before district postcode and place name — detected by leading number.
    addr_match = ADDRESS_RE.match(q)
    if addr_match:
        # Validate: the street part must contain at least one recognised street word
        # to avoid false positives like "3 Bed Semi" or "4 Bedroom House"
        street_part = addr_match.group(3)  # group 3 is street in updated regex
        street_words = {w.lower().rstrip(".,") for w in street_part.split()}
        if street_words & _STREET_WORDS or addr_match.group(4):
            # Has a street word or a trailing comma section (e.g. ", CR5 1RA")
            addr_result = await _resolve_address(db, q, addr_match)
            if addr_result:
                return addr_result
        # Fall through to place/ward resolution if address not found

    # Rule 1c: District/outward-code-only postcode (e.g. E1W, SW9, EC2A)
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
    parent = await _resolve_parent(db, row["lad_code"], entity_type="postcode")

    return {
        "query": query,
        "type": "postcode",
        "search_mode": "postcode",
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
        "boundary_source": "ward_lsoa",
        "boundary_id": row["ward_code"],
        "country": _resolved_country_metadata(row["lsoa_code"], row["ward_code"], row["lad_code"]),
    }


async def _resolve_address(db: AsyncSession, query: str, match: re.Match) -> dict | None:
    """Resolve an address search (e.g. '42 High Street, CR5 1RA').

    Parses PAON + street from the regex match. If a postcode is present in the
    trailing group, uses it for an exact lookup. Otherwise searches by PAON + street.

    Returns a property-type resolve result, or None if no match found (caller
    should fall through to place-name resolution).
    """
    saon_raw = match.group(1)  # sub-building (Flat 2, Unit 3A) — may be None
    paon = match.group(2).upper()
    street_raw = match.group(3).strip().rstrip(",")
    trailing = (match.group(4) or "").strip()

    # Check if trailing text is a postcode
    postcode = None
    area_hint = None
    if trailing:
        if POSTCODE_RE.match(trailing):
            postcode = trailing.replace(" ", "").upper()
        else:
            area_hint = trailing.lower()

    # Build fuzzy LIKE pattern: split words and join with % to allow
    # extra characters between words (e.g. "ST%JAMES%STREET" matches "ST JAMES'S STREET")
    street_words_raw = street_raw.upper().split()
    street_parts = [w.replace("%", "\\%").replace("_", "\\_") for w in street_words_raw]
    street_like = "%" + "%".join(street_parts) + "%"

    _area_rows = None  # Set by area_hint branch when rows are pre-consumed

    if postcode:
        # Format compact postcode to standard form (e.g. "SW1A1PH" → "SW1A 1PH")
        postcode_formatted = postcode[:-3] + " " + postcode[-3:] if len(postcode) > 3 else postcode
        # Exact lookup: PAON + street + postcode (uses idx_addresses_paon_postcode)
        result = await db.execute(
            text("""
                SELECT paon, saon, street, postcode, locality, town,
                       latitude, longitude, lsoa_code
                FROM core_addresses
                WHERE postcode = :postcode
                  AND paon = :paon
                  AND street LIKE :street
                LIMIT 5
            """),
            {
                "postcode": postcode_formatted,
                "paon": paon,
                "street": street_like,
            },
        )
    elif area_hint:
        # Broader search with area filter: push town/locality into SQL WHERE so
        # LIMIT doesn't exclude the right town (e.g. "73 High Street, Barnsley"
        # must not return random towns before Barnsley).
        area_hint_upper = area_hint.upper()
        area_hint_like = "%" + area_hint_upper.replace("%", "\\%").replace("_", "\\_") + "%"
        result = await db.execute(
            text("""
                SELECT paon, saon, street, postcode, locality, town,
                       latitude, longitude, lsoa_code
                FROM core_addresses
                WHERE paon = :paon
                  AND street LIKE :street
                  AND (town LIKE :area_hint OR locality LIKE :area_hint)
                LIMIT 20
            """),
            {
                "paon": paon,
                "street": street_like,
                "area_hint": area_hint_like,
            },
        )
        # Check if area-filtered query returned results; if not, fall back to
        # unfiltered search (address might not exist in that town)
        _area_rows = result.mappings().all()
        if not _area_rows:
            result = await db.execute(
                text("""
                    SELECT paon, saon, street, postcode, locality, town,
                           latitude, longitude, lsoa_code
                    FROM core_addresses
                    WHERE paon = :paon
                      AND street LIKE :street
                    LIMIT 20
                """),
                {
                    "paon": paon,
                    "street": street_like,
                },
            )
            _area_rows = None
    else:
        # Broader search: PAON + street (uses idx_addresses_paon_street)
        result = await db.execute(
            text("""
                SELECT paon, saon, street, postcode, locality, town,
                       latitude, longitude, lsoa_code
                FROM core_addresses
                WHERE paon = :paon
                  AND street LIKE :street
                LIMIT 20
            """),
            {
                "paon": paon,
                "street": street_like,
            },
        )

    rows = _area_rows if _area_rows is not None else result.mappings().all()
    if not rows:
        return None

    # If SAON was specified (e.g. "Flat 2"), filter results to matching sub-address
    if saon_raw:
        saon_upper = saon_raw.upper()
        saon_filtered = [
            r for r in rows
            if saon_upper in (r["saon"] or "").upper()
            or (r["saon"] or "").upper().endswith(saon_upper)
        ]
        if saon_filtered:
            rows = saon_filtered

    # Deduplicate by (postcode, paon, street) to get unique addresses
    seen = set()
    unique_addresses = []
    for r in rows:
        key = (r["postcode"], r["paon"], r["street"])
        if key not in seen:
            seen.add(key)
            unique_addresses.append(dict(r))

    # If area hint provided and no postcode (area_hint was already pushed into
    # SQL WHERE clause above), do a secondary Python filter only as a tiebreaker
    # when multiple results still remain from the SQL query.
    if area_hint and not postcode and len(unique_addresses) > 1:
        # Prefer exact town/locality match over partial
        exact_filtered = [
            a for a in unique_addresses
            if area_hint == (a.get("town") or "").lower()
            or area_hint == (a.get("locality") or "").lower()
        ]
        if exact_filtered:
            unique_addresses = exact_filtered

    if len(unique_addresses) == 0:
        return None

    # Use the first (most recent) match
    prop = unique_addresses[0]

    # Clean PPD saon="N" (means "no sub-address") to null
    for addr in unique_addresses:
        if addr.get("saon") == "N":
            addr["saon"] = None

    # Resolve LSOA → LAD → parent for this property
    lsoa_code = prop.get("lsoa_code")
    if not lsoa_code and prop["latitude"] and prop["longitude"]:
        # Spatial lookup if lsoa_code not on transaction
        lsoa_result = await db.execute(
            text("""
                SELECT lsoa_code FROM core_lsoa_boundaries
                WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                LIMIT 1
            """),
            {"lon": float(prop["longitude"]), "lat": float(prop["latitude"])},
        )
        lsoa_row = lsoa_result.mappings().first()
        if lsoa_row:
            lsoa_code = lsoa_row["lsoa_code"]

    if not lsoa_code:
        return None

    # Get LAD + MSOA from core_lsoa_boundaries (single query)
    lsoa_info = await db.execute(
        text("SELECT lad_code, msoa_code FROM core_lsoa_boundaries WHERE lsoa_code = :lsoa LIMIT 1"),
        {"lsoa": lsoa_code},
    )
    lsoa_info_row = lsoa_info.mappings().first()
    if not lsoa_info_row:
        return None
    lad_code = lsoa_info_row["lad_code"]
    msoa_code = lsoa_info_row["msoa_code"]

    if not lad_code:
        return None

    # Get ward from core_postcodes (postcode-keyed)
    ward_code = None
    if prop.get("postcode"):
        pc_compact = prop["postcode"].replace(" ", "").upper()
        ward_result = await db.execute(
            text("SELECT ward_code FROM core_postcodes WHERE postcode_compact = :pc LIMIT 1"),
            {"pc": pc_compact},
        )
        ward_row = ward_result.mappings().first()
        if ward_row:
            ward_code = ward_row["ward_code"]

    parent = await _resolve_parent(db, lad_code, entity_type="address")

    # Build address display string
    parts = [prop["paon"]]
    if prop.get("saon"):
        parts.insert(0, prop["saon"])
    if prop.get("street"):
        parts.append(prop["street"].title())
    if prop.get("postcode"):
        parts.append(prop["postcode"])
    address_display = ", ".join(parts)

    return {
        "query": query,
        "type": "address",
        "search_mode": "property",
        "resolved_codes": {
            "lsoa": lsoa_code,
            "msoa": msoa_code,
            "ward": ward_code,
            "lad": lad_code,
            "parent": parent,
        },
        "coordinates": {
            "lat": float(prop["latitude"]),
            "lon": float(prop["longitude"]),
        },
        "boundary_source": "ward_lsoa",
        "boundary_id": lsoa_code,
        "country": _resolved_country_metadata(lsoa_code, lad_code),
        # Property-specific fields
        "property": {
            "paon": prop["paon"],
            "saon": prop.get("saon"),
            "street": prop.get("street"),
            "postcode": prop.get("postcode"),
            "uprn": None,
            "lat": float(prop["latitude"]),
            "lon": float(prop["longitude"]),
            "address_display": address_display,
        },
        # Disambiguation: if multiple addresses matched, include alternatives
        "alternatives": [
            {
                "paon": a["paon"],
                "saon": a.get("saon"),
                "street": a.get("street"),
                "postcode": a.get("postcode"),
                "lat": float(a["latitude"]) if a.get("latitude") else None,
                "lon": float(a["longitude"]) if a.get("longitude") else None,
            }
            for a in unique_addresses[1:5]  # Up to 4 alternatives
        ] if len(unique_addresses) > 1 else [],
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

    parent = await _resolve_parent(db, row["lad_code"], entity_type="postcode_district")
    return {
        "query": query,
        "type": "postcode_district",
        "search_mode": "area",
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
        "boundary_source": "lad",
        "boundary_id": row["lad_code"],
        "country": _resolved_country_metadata(row["lad_code"]),
    }


async def _resolve_place_name(db: AsyncSession, query: str) -> dict:
    """Bible Rule 2: Resolve non-postcode input.

    Resolution order (largest to smallest):
    1. County (core_county_boundaries)
    2. LAD/Borough (core_lad_boundaries)
    3. Ward — exact match only (core_ward_boundaries)
    4. Place name — Voronoi mapping (core_place_names)
    5. Ward — fuzzy match (core_ward_boundaries)
    """
    q_lower = query.lower().strip()

    # 1. County match
    county_row = await _try_county(db, q_lower)
    if county_row:
        return county_row

    # 2. LAD/Borough match
    lad_row = await _try_lad(db, q_lower, query)
    if lad_row:
        return lad_row

    # 3. Exact ward match (before fuzzy place-name match to prevent
    #    "Coulsdon Town" ward matching "Old Coulsdon" place via trigram)
    ward_row = await _try_ward(db, q_lower, query, exact_only=True)
    if ward_row:
        return ward_row

    # 4. Place name match (Voronoi mapping via core_place_names)
    place_row = await _try_place_name(db, q_lower, query)
    if place_row:
        return place_row

    # 5. Fuzzy ward match
    ward_row = await _try_ward(db, q_lower, query)
    if ward_row:
        return ward_row

    # 5. Not found — return fuzzy suggestions
    suggestions = await _fuzzy_suggestions(db, query)
    return {
        "query": query, "type": "place_name",
        "error": "Place not found",
        "suggestions": suggestions,
    }


async def _try_county(db: AsyncSession, q_lower: str) -> dict | None:
    """Check if input matches a county name.

    Also matches common short names (e.g. "london" → "Greater London")
    so users don't need to type the full formal name.
    """
    result = await db.execute(
        text("""
            SELECT county_name,
                   ST_Y(ST_Centroid(geom)) AS lat,
                   ST_X(ST_Centroid(geom)) AS lon
            FROM core_county_boundaries
            WHERE LOWER(county_name) = :q
               OR LOWER(county_name) = 'greater ' || :q
            ORDER BY CASE WHEN LOWER(county_name) = :q THEN 0 ELSE 1 END
            LIMIT 1
        """),
        {"q": q_lower},
    )
    row = result.mappings().first()
    if not row:
        return None

    return {
        "query": q_lower,
        "type": "county",
        "search_mode": "area",
        "resolved_codes": {
            "lsoa": None,
            "ward": None,
            "lad": None,
            "parent": None,
        },
        "coordinates": {"lat": float(row["lat"]), "lon": float(row["lon"])},
        "boundary_source": "county",
        "boundary_id": row["county_name"],
        "country": build_country_metadata("England", "live"),
    }


async def _try_lad(db: AsyncSession, q_lower: str, query: str) -> dict | None:
    """Check if input matches a LAD/Borough name (exact or trigram)."""
    await db.execute(text("SET LOCAL pg_trgm.similarity_threshold = 0.5"))
    result = await db.execute(
        text("""
            SELECT lad_code, lad_name,
                   ST_Y(ST_Centroid(geom)) AS lat,
                   ST_X(ST_Centroid(geom)) AS lon,
                   similarity(LOWER(lad_name), :q) AS sim
            FROM core_lad_boundaries
            WHERE LOWER(lad_name) % :q
               OR LOWER(lad_name) LIKE :q || '%'
            ORDER BY
                CASE WHEN LOWER(lad_name) = :q THEN 0 ELSE 1 END,
                similarity(LOWER(lad_name), :q) DESC
            LIMIT 1
        """),
        {"q": q_lower},
    )
    row = result.mappings().first()
    # Accept trigram matches with sim >= 0.6, or prefix matches (name starts with query)
    if not row or (row["sim"] < 0.6 and not row["lad_name"].lower().startswith(q_lower)):
        return None

    parent = await _resolve_parent(db, row["lad_code"], entity_type="lad")

    # Determine display type: borough for London, district otherwise
    cl_result = await db.execute(
        text("SELECT is_london_borough FROM core_lad_county_lookup WHERE lad_code = :code"),
        {"code": row["lad_code"]},
    )
    cl_row = cl_result.mappings().first()
    display_type = "lad"

    return {
        "query": query,
        "type": display_type,
        "search_mode": "area",
        "resolved_codes": {
            "lsoa": None,
            "ward": None,
            "lad": row["lad_code"],
            "parent": parent,
        },
        "coordinates": {"lat": float(row["lat"]), "lon": float(row["lon"])},
        "boundary_source": "lad",
        "boundary_id": row["lad_code"],
        "country": _resolved_country_metadata(row["lad_code"]),
    }


async def _try_place_name(db: AsyncSession, q_lower: str, query: str) -> dict | None:
    """Check if input matches a place name with Voronoi LSOA mapping.

    Looks up core_place_names (ONS) and verifies a mapping exists in either
    core_place_lsoa_mapping (suburb-level) or core_place_lsoa_mapping_town
    (town/city-level).
    """
    await db.execute(text("SET LOCAL pg_trgm.similarity_threshold = 0.5"))

    # Join with mapping tables to count LSOAs — used as a tiebreaker for
    # duplicate place names (e.g. Soho in Westminster vs Soho in Sandwell).
    # More LSOAs = more prominent area = preferred.
    result = await db.execute(
        text("""
            SELECT pn.place_name, pn.place_type, pn.lad_code,
                   pn.latitude, pn.longitude,
                   similarity(pn.place_name_lower, :q) AS sim,
                   COALESCE(m_cnt.cnt, 0) AS mapping_count
            FROM core_place_names pn
            LEFT JOIN (
                SELECT place_name, lad_code, COUNT(*) AS cnt
                FROM core_place_lsoa_mapping
                GROUP BY place_name, lad_code
            ) m_cnt ON m_cnt.place_name = pn.place_name AND m_cnt.lad_code = pn.lad_code
            WHERE (pn.place_name_lower % :q OR pn.place_name_lower LIKE :q || '%')
              AND pn.place_type = ANY(:types)
              AND (
                  pn.place_type NOT IN ('Village','Hamlet','Other Settlement')
                  OR similarity(pn.place_name_lower, :q2) >= 0.9
              )
            ORDER BY
                CASE
                    -- Exact match City/Town — absolute top priority
                    WHEN pn.place_name_lower = :q AND pn.place_type IN ('City','Town') THEN 0
                    -- City/Town whose name starts with the query (e.g. "Brighton" → "Brighton and Hove")
                    WHEN pn.place_type IN ('City','Town') AND pn.place_name_lower LIKE :q || '%' THEN 1
                    -- Exact match Suburban Area / Other Settlement
                    WHEN pn.place_name_lower = :q AND pn.place_type IN ('Suburban Area','Other Settlement') THEN 2
                    -- Exact match Village / Hamlet
                    WHEN pn.place_name_lower = :q THEN 3
                    -- High-similarity City/Town (non-exact)
                    WHEN pn.place_type IN ('City','Town') AND similarity(pn.place_name_lower, :q2) >= 0.9 THEN 4
                    WHEN pn.place_type IN ('City','Town') THEN 5
                    -- Fuzzy Suburban Area
                    WHEN pn.place_type = 'Suburban Area' AND similarity(pn.place_name_lower, :q2) >= 0.9 THEN 6
                    -- Fuzzy Other Settlement / Village / Hamlet (only shown if sim >= 0.9)
                    WHEN pn.place_type = 'Other Settlement' AND similarity(pn.place_name_lower, :q2) >= 0.9 THEN 7
                    WHEN pn.place_type = 'Village' AND similarity(pn.place_name_lower, :q2) >= 0.9 THEN 8
                    WHEN pn.place_type = 'Hamlet' AND similarity(pn.place_name_lower, :q2) >= 0.9 THEN 9
                    ELSE 10
                END ASC,
                similarity(pn.place_name_lower, :q2) DESC,
                COALESCE(m_cnt.cnt, 0) DESC
            LIMIT 1
        """),
        {"q": q_lower, "q2": q_lower, "types": list(AREA_PLACE_TYPES)},
    )
    row = result.mappings().first()
    if not row:
        return None

    place_name = row["place_name"]
    place_type = row["place_type"]
    lad_code = row["lad_code"]

    # Spatial fallback for NULL lad_code
    if not lad_code and row["latitude"] and row["longitude"]:
        fb = await db.execute(
            text("""
                SELECT lad_code FROM core_lad_boundaries
                WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                LIMIT 1
            """),
            {"lon": float(row["longitude"]), "lat": float(row["latitude"])},
        )
        fb_row = fb.mappings().first()
        if fb_row:
            lad_code = fb_row["lad_code"]

    if not lad_code:
        return None

    # Determine mapping table: towns/cities use town-level Voronoi, others suburb-level
    use_town = place_type in ('City', 'Town')
    primary_table = TABLE_NAMES["place_lsoa_mapping_town"] if use_town else TABLE_NAMES["place_lsoa_mapping"]
    fallback_table = TABLE_NAMES["place_lsoa_mapping"] if use_town else TABLE_NAMES["place_lsoa_mapping_town"]

    check = await db.execute(
        text(f"SELECT 1 FROM {primary_table} WHERE place_name = :name AND lad_code = :lad LIMIT 1"),
        {"name": place_name, "lad": lad_code},
    )
    if not check.first():
        check2 = await db.execute(
            text(f"SELECT 1 FROM {fallback_table} WHERE place_name = :name AND lad_code = :lad LIMIT 1"),
            {"name": place_name, "lad": lad_code},
        )
        if not check2.first():
            return None

    parent = await _resolve_parent(db, lad_code, entity_type="place")

    return {
        "query": query,
        "type": "place",
        "search_mode": "area",
        "resolved_codes": {
            "lsoa": None,
            "ward": None,
            "lad": lad_code,
            "parent": parent,
        },
        "coordinates": {
            "lat": float(row["latitude"]) if row["latitude"] else None,
            "lon": float(row["longitude"]) if row["longitude"] else None,
        },
        "boundary_source": "place",
        "boundary_id": place_name,
        "place_name": place_name,
        "place_lad_code": lad_code,
        "place_type": place_type,
        "country": _resolved_country_metadata(lad_code),
    }


async def _try_ward(db: AsyncSession, q_lower: str, query: str, *, exact_only: bool = False) -> dict | None:
    """Check if input matches a ward name (exact or trigram)."""
    if exact_only:
        result = await db.execute(
            text("""
                SELECT wb.ward_code, wb.ward_name, wb.lad_code,
                       ST_Y(ST_Centroid(wb.geom)) AS lat,
                       ST_X(ST_Centroid(wb.geom)) AS lon,
                       1.0 AS sim
                FROM core_ward_boundaries wb
                WHERE LOWER(wb.ward_name) = :q
                LIMIT 1
            """),
            {"q": q_lower},
        )
    else:
        await db.execute(text("SET LOCAL pg_trgm.similarity_threshold = 0.5"))
        result = await db.execute(
            text("""
                SELECT wb.ward_code, wb.ward_name, wb.lad_code,
                       ST_Y(ST_Centroid(wb.geom)) AS lat,
                       ST_X(ST_Centroid(wb.geom)) AS lon,
                       similarity(LOWER(wb.ward_name), :q) AS sim
                FROM core_ward_boundaries wb
                WHERE LOWER(wb.ward_name) % :q
                ORDER BY
                    CASE WHEN LOWER(wb.ward_name) = :q THEN 0 ELSE 1 END,
                    similarity(LOWER(wb.ward_name), :q) DESC
                LIMIT 1
            """),
            {"q": q_lower},
        )
    row = result.mappings().first()
    if not row or row["sim"] < 0.7:
        return None

    parent = await _resolve_parent(db, row["lad_code"], entity_type="ward")
    return {
        "query": query,
        "type": "ward",
        "search_mode": "area",
        "resolved_codes": {
            "lsoa": None,
            "ward": row["ward_code"],
            "lad": row["lad_code"],
            "parent": parent,
        },
        "coordinates": {"lat": float(row["lat"]), "lon": float(row["lon"])},
        "boundary_source": "ward",
        "boundary_id": row["ward_code"],
        "country": _resolved_country_metadata(row["ward_code"], row["lad_code"]),
    }



async def _resolve_parent(db: AsyncSession, lad_code: str, entity_type: str | None = None) -> str:
    """Bible Rule 3: Determine parent comparison from core_lad_county_lookup.

    Delegates to get_parent_lad_info() which handles:
    - Sub-LAD searches (postcode/ward/place) → parent is the LAD itself
      (except London boroughs → Greater London)
    - LAD searches → county peer group (singletons escalate to region)
    """
    from app.services.helpers import get_parent_lad_info

    if not lad_code:
        return "England"

    _, parent_name = await get_parent_lad_info(db, lad_code, entity_type=entity_type)
    return parent_name
