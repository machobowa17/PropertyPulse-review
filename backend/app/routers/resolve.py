"""
GET /api/v1/resolve?q={search_key}
GET /api/v1/search/suggest?q={partial}
Build Bible Part 6, Section 6.1 — Geo-Resolution + Autocomplete
"""
import hashlib
import re
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.errors import http_error
from app.services.geo_resolver import resolve_search
from app.services.helpers import make_lsoa_session, get_lsoa_session
from app.cache import cache_get, cache_set
from app.rate_limit import limiter

router = APIRouter()

POSTCODE_RE = re.compile(r"^[A-Z]{1,2}[0-9]", re.IGNORECASE)
# Only allow printable ASCII + common accented chars (place names); reject junk input early
_SAFE_QUERY_RE = re.compile(r"^[\w\s\-',./()&àáâãäåèéêëìíîïòóôõöùúûüýÿñçšžœæ]+$", re.IGNORECASE | re.UNICODE)

# Statement timeout for search queries (milliseconds) — prevents CPU-intensive regex/trigram abuse
_SEARCH_STATEMENT_TIMEOUT_MS = 3000


def _safe_cache_key(prefix: str, q: str) -> str:
    """Produce a bounded cache key. Short queries use the literal value for readability;
    longer or unusual ones are hashed to cap Redis key cardinality."""
    normalised = q.strip().lower()
    if len(normalised) <= 30 and _SAFE_QUERY_RE.match(normalised):
        return f"{prefix}:{normalised}"
    return f"{prefix}:h:{hashlib.sha256(normalised.encode()).hexdigest()[:16]}"


TYPE_LABELS = {
    "postcode": "Postcode",
    "postcode_district": "Postcode area",
    "place": "Place",
    "ward": "Ward",
    "borough": "Borough",
    "district": "District",
    "county": "County",
}


def _type_label(type_name: str | None) -> str:
    if not type_name:
        return "Area"
    return TYPE_LABELS.get(type_name, type_name.replace("_", " ").title())


def _coverage_metadata() -> dict:
    return {
        "live_countries": ["England"],
        "partial_countries": ["Wales"],
        "planned_countries": ["Scotland"],
        "parked_countries": ["Northern Ireland"],
        "coverage_message": (
            "England remains the only fully live end-to-end country today. Wales now has live support for council tax plus selected England-and-Wales census and market datasets, but wider Wales coverage is still partial and some search and dataset paths remain staged. "
            "Scotland remains in an earlier staged rollout through shared geography and selected authority-level sources. Northern Ireland remains parked pending a production-safe postcode and boundary source."
        ),
    }


def _format_suggestion(row: dict) -> dict:
    label = row.get("label")
    type_name = row.get("type")
    area = row.get("area")
    comparison = row.get("comparison")
    secondary = row.get("secondary") or _type_label(type_name)

    breadcrumb_parts = []
    for part in (secondary, area, comparison):
        if part and part not in breadcrumb_parts:
            breadcrumb_parts.append(part)

    return {
        "label": label,
        "type": type_name,
        "area": area,
        "comparison": comparison,
        "secondary": secondary,
        "display_label": label,
        "display_type": _type_label(type_name),
        "display_context": " — ".join(breadcrumb_parts),
        "selection_value": label,
    }


@router.get("/resolve")
async def resolve(
    q: str = Query(..., min_length=2, max_length=100, description="Search key: postcode or place name"),
    db: AsyncSession = Depends(get_db),
):
    # Sanitise: strip null bytes and control characters that break PostgreSQL text columns
    q = q.replace("\x00", "").strip()
    if len(q) < 2:
        raise http_error(422, "INVALID_QUERY", "Query too short after sanitisation")
    if not _SAFE_QUERY_RE.match(q):
        raise http_error(422, "INVALID_QUERY", "Query contains unsupported characters")
    cache_key = _safe_cache_key("resolve", q)
    cached = await cache_get(cache_key)
    if cached:
        # Re-populate the session in Redis in case it expired (TTL refresh).
        # Session is mandatory for all downstream endpoints, so this must succeed.
        if cached.get("session_key") and cached.get("resolved_codes"):
            codes = cached["resolved_codes"]
            _, _, session = await _build_and_store_session(db, cached, codes)  # TTL refresh only
            if session and session.get("geo") and not cached.get("geo"):
                cached = {**cached, "geo": session["geo"]}
        if not cached.get("coverage"):
            cached = {**cached, "coverage": _coverage_metadata()}
        return cached
    result = await resolve_search(db, q)
    # Compute the LSOA set and store under a session key so every subsequent
    # data endpoint uses the exact same LSOA set, parent comparison, and
    # boundary info without re-deriving them.
    if result.get("resolved_codes"):
        session_key, lsoa_codes, session = await _build_and_store_session(db, result, result["resolved_codes"])
        lsoa_count = len(lsoa_codes)
        result = {
            **result,
            "session_key": session_key,
            "lsoa_count": lsoa_count,
            "lsoa_codes": lsoa_codes if lsoa_count <= 8 else [],
            "geo": session.get("geo") if session else None,
        }
    result = {**result, "coverage": _coverage_metadata()}
    await cache_set(cache_key, result, ttl=86400)
    return result


async def _build_and_store_session(db, result: dict, codes: dict) -> tuple:
    """Derive all session fields from a resolve result, store the session, and return it."""
    lad  = codes.get("lad")  or "_"
    ward = codes.get("ward") or "_"
    lsoa = codes.get("lsoa") or "_"
    coords = result.get("coordinates") or {}

    # expand_lsoa_codes kwargs
    expand_kwargs: dict = {}
    lat = coords.get("lat")
    lon = coords.get("lon")
    if lat is not None:
        expand_kwargs["postcode_lat"] = lat
    if lon is not None:
        expand_kwargs["postcode_lon"] = lon
    if result.get("boundary_source") == "county":
        expand_kwargs["county_name"] = result.get("boundary_id")

    # Derive postcode district: "SW1A 1AA" → "SW1A"
    postcode_district = None
    if result.get("type") == "postcode":
        raw_q = (result.get("query") or "").strip().upper()
        parts = raw_q.split()
        if parts:
            postcode_district = parts[0]  # outward code = district
    elif result.get("type") == "postcode_district":
        postcode_district = (result.get("query") or "").strip().upper().replace(" ", "")

    lsoa_codes, _, _, _, _, session_key = await make_lsoa_session(
        db, lad, ward, lsoa,
        boundary_source=result.get("boundary_source", "lad"),
        boundary_id=result.get("boundary_id", ""),
        postcode_district=postcode_district,
        place_name=result.get("place_name"),
        place_lad_code=result.get("place_lad_code"),
        place_type=result.get("place_type"),
        entity_type=result.get("type"),
        entity_name=result.get("place_name") or result.get("boundary_id") or result.get("query"),
        query_text=result.get("query"),
        **expand_kwargs,
    )
    session = await get_lsoa_session(session_key)
    return session_key, lsoa_codes, session


@router.get("/search/suggest")
@limiter.limit("300/minute")
async def suggest(
    request: Request,
    q: str = Query(..., min_length=2, max_length=100, description="Partial search query"),
    db: AsyncSession = Depends(get_db),
):
    """Return up to 8 suggestions as the user types."""
    q_clean = q.replace("\x00", "").strip()
    if not q_clean:
        return {"suggestions": []}
    if not _SAFE_QUERY_RE.match(q_clean):
        return {"suggestions": [], "coverage": _coverage_metadata()}

    cache_key = _safe_cache_key("suggest", q_clean)
    cached = await cache_get(cache_key)
    if cached:
        if not cached.get("coverage"):
            cached = {**cached, "coverage": _coverage_metadata()}
        return cached

    # Guard against expensive regex/trigram queries: set per-session statement timeout
    await db.execute(sa_text(f"SET LOCAL statement_timeout = '{_SEARCH_STATEMENT_TIMEOUT_MS}'"))

    q_lower = q_clean.lower()
    # Escape LIKE special characters so user input is treated as literal text
    q_like = q_lower.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    results = []

    # 1. Postcode prefix match (if input looks like a postcode)
    if POSTCODE_RE.match(q_clean):
        compact = q_clean.replace(" ", "").upper()
        # Guard: compact must be purely alphanumeric before f-string interpolation into SQL
        if not compact.isalnum():
            compact = None
    else:
        compact = None
    if compact:
        # If input is a partial district (no space, no inward code: e.g. "SW1", "EC2", "SW1A"),
        # return distinct districts rather than individual full postcodes.
        is_partial_district = " " not in q_clean and len(compact) <= 4
        if is_partial_district:
            # Use Postgres regex to extract the outward code dynamically.
            # Pattern ^[A-Z]{1,2}[0-9][A-Z]? handles all UK formats:
            #   E1, N1, M1 (1-letter + digit)
            #   SW1, EC2 (2-letter + digit)
            #   SW1A, EC2A (2-letter + digit + alpha suffix)
            #   CR5, LS1 (2-letter + digit — NOT forced to 4 chars)
            # The optional suffix is [A-Z] only (not [A-Z0-9]) because
            # the digit after the area digit is always the start of the
            # inward code (e.g. CR51RA → outward=CR5, inward=1RA).
            outward_regex = r'^[A-Z]{1,2}[0-9][A-Z]?'

            # For a partial input ending in a digit (e.g. "SW1", "E1"), we want districts
            # where the next character after the input is a LETTER (SW1A not SW10).
            # If input already ends in a letter (e.g. "SW1A"), just prefix-match normally.
            ends_in_digit = compact[-1].isdigit()
            if ends_in_digit:
                # Prefer districts where input is followed by a LETTER (SW1A not SW10).
                # Fall back to numeric-suffix districts (M1, LS1 etc.) if no letter-suffix found.
                # Build SIMILAR TO patterns as bind params (never interpolate user input into SQL)
                letter_prefix = compact + "[A-Z]%"
                alnum_prefix = compact + "[A-Z0-9]%"
                res = await db.execute(
                    sa_text("""
                        WITH candidates AS (
                            SELECT
                                SUBSTRING(postcode_compact FROM :outward_regex) AS label,
                                CASE WHEN postcode_compact SIMILAR TO :letter_prefix THEN 0 ELSE 1 END AS pref,
                                lad_name,
                                COUNT(*) AS cnt
                            FROM core_postcodes
                            WHERE postcode_compact SIMILAR TO :alnum_prefix
                            GROUP BY 1, 2, lad_name
                        ),
                        dominant AS (
                            SELECT DISTINCT ON (label) label, pref, lad_name AS area
                            FROM candidates ORDER BY label, pref, cnt DESC
                        )
                        SELECT label, 'postcode_district' AS type, area,
                               NULL AS comparison, 'Postcode area' AS secondary
                        FROM dominant
                        ORDER BY pref, label
                        LIMIT 6
                    """),
                    {"outward_regex": outward_regex, "letter_prefix": letter_prefix, "alnum_prefix": alnum_prefix},
                )
            else:
                res = await db.execute(
                    sa_text("""
                        WITH candidates AS (
                            SELECT
                                SUBSTRING(postcode_compact FROM :outward_regex) AS label,
                                lad_name, COUNT(*) AS cnt
                            FROM core_postcodes
                            WHERE postcode_compact LIKE :prefix
                            GROUP BY 1, lad_name
                        ),
                        dominant AS (
                            SELECT DISTINCT ON (label) label, lad_name AS area
                            FROM candidates ORDER BY label, cnt DESC
                        )
                        SELECT label, 'postcode_district' AS type, area,
                               NULL AS comparison, 'Postcode area' AS secondary
                        FROM dominant ORDER BY label LIMIT 6
                    """),
                    {"outward_regex": outward_regex, "prefix": compact + "%"},
                )
        else:
            res = await db.execute(
                sa_text("""
                    SELECT postcode AS label, 'postcode' AS type, lad_name AS area,
                           NULL AS comparison, 'Postcode' AS secondary
                    FROM core_postcodes
                    WHERE postcode_compact LIKE :prefix
                    LIMIT 5
                """),
                {"prefix": compact + "%"},
            )
        results += [dict(r) for r in res.mappings().all()]

    AREA_TYPES = ['Town','City','Suburban Area','Village','Other Settlement','Hamlet']

    # 2. LAD/Borough names (prefix match)
    if len(results) < 8:
        res = await db.execute(
            sa_text("""
                SELECT lb.lad_name AS label,
                       CASE WHEN cl.is_london_borough THEN 'borough' ELSE 'district' END AS type,
                       cl.parent_comparison AS area,
                       cl.parent_comparison AS comparison,
                       CASE WHEN cl.is_london_borough THEN 'Borough' ELSE 'District' END AS secondary
                FROM core_lad_boundaries lb
                JOIN core_lad_county_lookup cl ON lb.lad_code = cl.lad_code
                WHERE LOWER(lb.lad_name) LIKE :prefix ESCAPE '\'
                ORDER BY
                    CASE WHEN LOWER(lb.lad_name) = :exact THEN 0 ELSE 1 END,
                    LENGTH(lb.lad_name) ASC
                LIMIT :lim
            """),
            {"prefix": q_like + "%", "exact": q_lower, "lim": 8 - len(results)},
        )
        results += [dict(r) for r in res.mappings().all()]

    # 3. County names (prefix match) — before places to ensure counties rank higher
    if len(results) < 8:
        res = await db.execute(
            sa_text("""
                SELECT county_name AS label, 'county' AS type,
                       NULL AS area,
                       'England' AS comparison,
                       'County' AS secondary
                FROM core_county_boundaries
                WHERE LOWER(county_name) LIKE :prefix ESCAPE '\'
                   OR LOWER(county_name) LIKE 'greater ' || :prefix ESCAPE '\'
                ORDER BY
                    CASE WHEN LOWER(county_name) LIKE :prefix ESCAPE '\' THEN 0 ELSE 1 END,
                    LENGTH(county_name) ASC
                LIMIT :lim
            """),
            {"prefix": q_like + "%", "lim": 8 - len(results)},
        )
        results += [dict(r) for r in res.mappings().all()]

    # 4. Place names from core_place_names (prefix match — places with Voronoi mapping)
    if len(results) < 8:
        res = await db.execute(
            sa_text("""
                SELECT DISTINCT ON (pn.place_name, pn.lad_code)
                       pn.place_name AS label, 'place' AS type,
                       COALESCE(lb.lad_name, pn.lad_code) AS area,
                       cl.parent_comparison AS comparison,
                       pn.place_type AS secondary
                FROM core_place_names pn
                LEFT JOIN core_lad_boundaries lb ON pn.lad_code = lb.lad_code
                LEFT JOIN core_lad_county_lookup cl ON pn.lad_code = cl.lad_code
                WHERE pn.place_name_lower LIKE :prefix ESCAPE '\'
                  AND pn.place_type = ANY(:types)
                  AND pn.lad_code IS NOT NULL
                ORDER BY pn.place_name, pn.lad_code,
                    CASE WHEN pn.place_name_lower = :exact THEN 0 ELSE 1 END,
                    CASE pn.place_type
                        WHEN 'City' THEN 1 WHEN 'Town' THEN 2
                        WHEN 'Suburban Area' THEN 3 WHEN 'Other Settlement' THEN 4
                        WHEN 'Village' THEN 5 ELSE 6
                    END
                LIMIT :lim
            """),
            {"prefix": q_like + "%", "exact": q_lower, "lim": 8 - len(results), "types": AREA_TYPES},
        )
        results += [dict(r) for r in res.mappings().all()]

    # 5. Ward names (prefix match)
    if len(results) < 8:
        res = await db.execute(
            sa_text("""
                SELECT wb.ward_name AS label, 'ward' AS type,
                       lb.lad_name AS area,
                       cl.parent_comparison AS comparison,
                       'Ward' AS secondary
                FROM core_ward_boundaries wb
                JOIN core_lad_boundaries lb ON wb.lad_code = lb.lad_code
                LEFT JOIN core_lad_county_lookup cl ON wb.lad_code = cl.lad_code
                WHERE LOWER(wb.ward_name) LIKE :prefix ESCAPE '\'
                ORDER BY
                    CASE WHEN LOWER(wb.ward_name) = :exact THEN 0 ELSE 1 END,
                    LENGTH(wb.ward_name) ASC
                LIMIT :lim
            """),
            {"prefix": q_like + "%", "exact": q_lower, "lim": 8 - len(results)},
        )
        results += [dict(r) for r in res.mappings().all()]

    # 6b. Substring/contains match across wards, places, and ONS places
    # Catches "Old Coulsdon" when user types "Coulsdon" (query appears mid-name)
    if len(results) < 8 and len(q_lower) >= 3:
        contains_pat = "%" + q_like + "%"
        prefix_pat = q_like + "%"
        existing_contains = {(r["label"].lower(), (r.get("area") or "").lower()) for r in results}
        res = await db.execute(
            sa_text("""
                SELECT label, type, area, comparison, secondary FROM (
                    (
                        SELECT lb2.lad_name AS label,
                               CASE WHEN cl2.is_london_borough THEN 'borough' ELSE 'district' END AS type,
                               cl2.parent_comparison AS area,
                               cl2.parent_comparison AS comparison,
                               CASE WHEN cl2.is_london_borough THEN 'Borough' ELSE 'District' END AS secondary,
                               0 AS src_rank
                        FROM core_lad_boundaries lb2
                        JOIN core_lad_county_lookup cl2 ON lb2.lad_code = cl2.lad_code
                        WHERE LOWER(lb2.lad_name) LIKE :contains ESCAPE '\\'
                          AND LOWER(lb2.lad_name) NOT LIKE :prefix ESCAPE '\\'
                    )
                    UNION ALL
                    (
                        SELECT DISTINCT ON (pn.place_name, pn.lad_code)
                               pn.place_name AS label, 'place' AS type,
                               COALESCE(lb.lad_name, pn.lad_code) AS area,
                               cl.parent_comparison AS comparison,
                               pn.place_type AS secondary,
                               1 AS src_rank
                        FROM core_place_names pn
                        LEFT JOIN core_lad_boundaries lb ON pn.lad_code = lb.lad_code
                        LEFT JOIN core_lad_county_lookup cl ON pn.lad_code = cl.lad_code
                        WHERE pn.place_name_lower LIKE :contains ESCAPE '\\'
                          AND pn.place_name_lower NOT LIKE :prefix ESCAPE '\\'
                          AND pn.place_type = ANY(:types)
                          AND pn.lad_code IS NOT NULL
                        ORDER BY pn.place_name, pn.lad_code,
                            CASE pn.place_type
                                WHEN 'City' THEN 1 WHEN 'Town' THEN 2
                                WHEN 'Suburban Area' THEN 3 WHEN 'Other Settlement' THEN 4
                                WHEN 'Village' THEN 5 ELSE 6
                            END
                    )
                    UNION ALL
                    (
                        SELECT wb.ward_name AS label, 'ward' AS type,
                               lb.lad_name AS area,
                               cl.parent_comparison AS comparison,
                               'Ward' AS secondary,
                               2 AS src_rank
                        FROM core_ward_boundaries wb
                        JOIN core_lad_boundaries lb ON wb.lad_code = lb.lad_code
                        LEFT JOIN core_lad_county_lookup cl ON wb.lad_code = cl.lad_code
                        WHERE LOWER(wb.ward_name) LIKE :contains ESCAPE '\\'
                          AND LOWER(wb.ward_name) NOT LIKE :prefix ESCAPE '\\'
                    )
                ) sub
                ORDER BY src_rank, LENGTH(label) ASC
                LIMIT :lim
            """),
            {"contains": contains_pat, "prefix": prefix_pat, "lim": 8 - len(results), "types": AREA_TYPES},
        )
        for r in res.mappings().all():
            key = (r["label"].lower(), (r.get("area") or "").lower())
            if key not in existing_contains:
                existing_contains.add(key)
                results.append({
                    "label": r["label"],
                    "type": r["type"],
                    "area": r["area"],
                    "comparison": r.get("comparison"),
                    "secondary": r.get("secondary"),
                    "_contains": True,
                })

    # 7. Trigram fuzzy match (catches typos) — skip if we already have an exact name match
    has_exact = any(r["label"].lower() == q_lower for r in results)
    if len(results) < 4 and not has_exact:
        res = await db.execute(
            sa_text("""
                SELECT pn.place_name AS label, 'place' AS type,
                       COALESCE(lb.lad_name, pn.lad_code) AS area,
                       cl.parent_comparison AS comparison,
                       pn.place_type AS secondary
                FROM core_place_names pn
                LEFT JOIN core_lad_boundaries lb ON pn.lad_code = lb.lad_code
                LEFT JOIN core_lad_county_lookup cl ON pn.lad_code = cl.lad_code
                WHERE pn.place_name_lower % :q
                  AND pn.place_type = ANY(:types)
                ORDER BY
                    CASE WHEN similarity(pn.place_name_lower, :q) >= 0.9 THEN 0 ELSE 1 END ASC,
                    CASE pn.place_type
                        WHEN 'City' THEN 1 WHEN 'Town' THEN 2
                        WHEN 'Suburban Area' THEN 3 WHEN 'Other Settlement' THEN 4
                        WHEN 'Village' THEN 5 ELSE 6
                    END,
                    similarity(pn.place_name_lower, :q) DESC
                LIMIT :lim
            """),
            {"q": q_lower, "lim": 8 - len(results), "types": AREA_TYPES},
        )
        results += [dict(r) for r in res.mappings().all()]

    # Re-sort: postcodes first, then counties/LADs, then places/wards
    TYPE_RANK = {
        'postcode': 0, 'postcode_district': 0,
        'county': 1,
        'borough': 2, 'district': 2,
        'place': 3,
        'ward': 4,
    }
    # Prefix matches (no _contains flag) sort before substring matches within the same type
    results.sort(key=lambda r: (TYPE_RANK.get(r["type"], 10), 1 if r.get("_contains") else 0, len(r["label"])))

    # Deduplicate by (label_lower, area_lower) — prevents same place appearing from
    # multiple sources (step 3 place + step 7 fuzzy, or place + ward same name).
    seen = set()
    unique = []
    for r in results:
        key = (r["label"].lower(), (r.get("area") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(_format_suggestion({k: v for k, v in r.items() if k != "_contains"}))

    response = {"suggestions": unique[:8], "coverage": _coverage_metadata()}
    await cache_set(cache_key, response, ttl=3600)
    return response
