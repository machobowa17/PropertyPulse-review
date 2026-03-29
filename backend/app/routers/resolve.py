"""
GET /api/v1/resolve?q={search_key}
GET /api/v1/search/suggest?q={partial}
Build Bible Part 6, Section 6.1 — Geo-Resolution + Autocomplete
"""
import re
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.geo_resolver import resolve_search
from app.cache import cache_get, cache_set

router = APIRouter()

POSTCODE_RE = re.compile(r"^[A-Z]{1,2}[0-9]", re.IGNORECASE)


@router.get("/resolve")
async def resolve(
    q: str = Query(..., min_length=2, max_length=100, description="Search key: postcode or place name"),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"resolve:{q.strip().lower()}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    result = await resolve_search(db, q)
    await cache_set(cache_key, result, ttl=86400)
    return result


@router.get("/search/suggest")
async def suggest(
    q: str = Query(..., min_length=2, max_length=100, description="Partial search query"),
    db: AsyncSession = Depends(get_db),
):
    """Return up to 8 suggestions as the user types."""
    cache_key = f"suggest:{q.strip().lower()}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    q_clean = q.strip()
    if not q_clean:
        return {"suggestions": []}
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
            # Extract district portion: 3 chars for 1-letter areas (E1W→3), 4 chars for 2-letter (SW1A→4)
            # Filter: district must start exactly with our input prefix
            dist_len = 4 if len(compact) >= 2 and compact[0].isalpha() and compact[1].isalpha() else 3
            # For a partial input ending in a digit (e.g. "SW1", "E1"), we want districts
            # where the next character after the input is a LETTER (SW1A not SW10).
            # If input already ends in a letter (e.g. "SW1A"), just prefix-match normally.
            ends_in_digit = compact[-1].isdigit()
            if ends_in_digit:
                # Prefer districts where input is followed by a LETTER (SW1A not SW10).
                # Fall back to numeric-suffix districts (M1, LS1 etc.) if no letter-suffix found.
                letter_pat = f"^{compact}[A-Z]"
                digit_pat  = f"^{compact}[0-9]"
                sql = sa_text(f"""
                    WITH candidates AS (
                        SELECT
                            SUBSTRING(postcode_compact FROM 1 FOR {dist_len}) AS label,
                            CASE WHEN postcode_compact SIMILAR TO '{compact}[A-Z]%' THEN 0 ELSE 1 END AS pref,
                            lad_name,
                            COUNT(*) AS cnt
                        FROM core_postcodes
                        WHERE postcode_compact SIMILAR TO '{compact}[A-Z0-9]%'
                        GROUP BY 1, 2, lad_name
                    ),
                    dominant AS (
                        SELECT DISTINCT ON (label) label, pref, lad_name AS area
                        FROM candidates ORDER BY label, pref, cnt DESC
                    )
                    SELECT label, 'postcode_district' AS type, area
                    FROM dominant
                    ORDER BY pref, label
                    LIMIT 6
                """)
                res = await db.execute(sql)
            else:
                sql = sa_text(f"""
                    WITH candidates AS (
                        SELECT
                            SUBSTRING(postcode_compact FROM 1 FOR {dist_len}) AS label,
                            lad_name, COUNT(*) AS cnt
                        FROM core_postcodes
                        WHERE postcode_compact LIKE :prefix
                        GROUP BY 1, lad_name
                    ),
                    dominant AS (
                        SELECT DISTINCT ON (label) label, lad_name AS area
                        FROM candidates ORDER BY label, cnt DESC
                    )
                    SELECT label, 'postcode_district' AS type, area
                    FROM dominant ORDER BY label LIMIT 6
                """)
                res = await db.execute(sql, {"prefix": compact + "%"})
        else:
            res = await db.execute(
                sa_text("""
                    SELECT postcode AS label, 'postcode' AS type, lad_name AS area
                    FROM core_postcodes
                    WHERE postcode_compact LIKE :prefix
                    LIMIT 5
                """),
                {"prefix": compact + "%"},
            )
        results += [dict(r) for r in res.mappings().all()]

    AREA_TYPES = ['Town','City','Suburban Area','Village','Other Settlement','Hamlet']

    # 2. Prefix match on place names (fast, catches partial typing)
    if len(results) < 8:
        res = await db.execute(
            sa_text("""
                SELECT pn.place_name AS label, pn.place_type AS type,
                       COALESCE(lb.lad_name, pn.lad_code) AS area
                FROM core_place_names pn
                LEFT JOIN core_lad_boundaries lb ON pn.lad_code = lb.lad_code
                WHERE pn.place_name_lower LIKE :prefix ESCAPE '\'
                  AND pn.place_type = ANY(:types)
                ORDER BY
                    -- Exact name match wins, but only for City/Town/Suburban Area/Other Settlement.
                    -- Village/Hamlet exact matches must NOT outrank a City/Town prefix match.
                    CASE WHEN pn.place_name_lower = :exact
                              AND pn.place_type IN ('City','Town','Suburban Area','Other Settlement')
                         THEN 0 ELSE 1 END,
                    CASE pn.place_type
                        WHEN 'City' THEN 1 WHEN 'Town' THEN 2
                        WHEN 'Suburban Area' THEN 3 WHEN 'Other Settlement' THEN 4
                        WHEN 'Village' THEN 5 ELSE 6
                    END,
                    LENGTH(pn.place_name) ASC
                LIMIT :lim
            """),
            {"prefix": q_like + "%", "exact": q_lower, "lim": 8 - len(results), "types": AREA_TYPES},
        )
        results += [dict(r) for r in res.mappings().all()]

    # 3. Trigram fuzzy match (catches typos) — skip if we already have an exact name match
    has_exact = any(r["label"].lower() == q_lower for r in results)
    if len(results) < 4 and not has_exact:
        res = await db.execute(
            sa_text("""
                SELECT pn.place_name AS label, pn.place_type AS type,
                       COALESCE(lb.lad_name, pn.lad_code) AS area
                FROM core_place_names pn
                LEFT JOIN core_lad_boundaries lb ON pn.lad_code = lb.lad_code
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

    # Re-sort place-name results (prefix + fuzzy combined) by type priority so that
    # a City from fuzzy is not buried below a Hamlet from prefix.
    # Postcode results (step 1) always stay first.
    TYPE_RANK = {'City': 1, 'Town': 2, 'Suburban Area': 3, 'Other Settlement': 4, 'Village': 5}
    postcode_results = [r for r in results if r.get("type") in ("postcode", "postcode_district")]
    place_results = [r for r in results if r.get("type") not in ("postcode", "postcode_district")]
    place_results.sort(key=lambda r: (TYPE_RANK.get(r["type"], 6), len(r["label"])))
    results = postcode_results + place_results

    # Deduplicate by label
    seen = set()
    unique = []
    for r in results:
        if r["label"] not in seen:
            seen.add(r["label"])
            unique.append(r)

    response = {"suggestions": unique[:8]}
    await cache_set(cache_key, response, ttl=3600)
    return response
