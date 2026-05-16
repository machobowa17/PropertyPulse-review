"""
GET /api/v1/aq-history
GET /api/v1/comparable
GET /api/v1/wiki-summary
Air quality history, comparable areas, and Wikipedia summary endpoints.
"""
import logging

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.cache import cache_get, cache_set
from app.services.session_helpers import (
    session_boundary_source,
    session_local_scope_type,
    session_entity_name,
    require_session,
)
from app.services.comparable_areas import find_comparable_lads, find_comparable_scopes

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# AQ history
# ---------------------------------------------------------------------------

@router.get("/aq-history")
async def get_aq_history(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    db: AsyncSession = Depends(get_db),
):
    """Return yearly PM2.5/NO2 averages for the resolved local scope and national benchmark."""
    sess = await require_session(session_key)
    lad_code = sess["lad_code"]
    local_lads = sorted({code for code in (sess.get("local_lads") or []) if code and code != "_"})
    boundary_source = session_boundary_source(sess)
    entity_name = session_entity_name(sess)

    if boundary_source == "county" and local_lads:
        cache_key = f"aq_history:county:{entity_name}"
    else:
        cache_key = f"aq_history:{lad_code}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Local history
    if boundary_source == "county" and local_lads:
        local_res = await db.execute(
            text("""
                SELECT a.year,
                       SUM(a.pm25_ugm3 * p.total_pop) / NULLIF(SUM(p.total_pop), 0) AS pm25_ugm3,
                       SUM(a.no2_ugm3 * p.total_pop) / NULLIF(SUM(p.total_pop), 0) AS no2_ugm3,
                       SUM(a.pm10_ugm3 * p.total_pop) / NULLIF(SUM(p.total_pop), 0) AS pm10_ugm3
                FROM core_air_quality_lad a
                LEFT JOIN mv_lad_population p ON p.lad_code = a.lad_code
                WHERE a.lad_code = ANY(:lads)
                GROUP BY a.year
                ORDER BY a.year
            """),
            {"lads": local_lads},
        )
    else:
        local_res = await db.execute(
            text("""
                SELECT year, pm25_ugm3, no2_ugm3, pm10_ugm3
                FROM core_air_quality_lad
                WHERE lad_code = :lad
                ORDER BY year
            """),
            {"lad": lad_code},
        )
    local_rows = [dict(r) for r in local_res.mappings().all()]

    # National average per year
    national_res = await db.execute(
        text("""
            SELECT a.year,
                   ROUND((SUM(a.pm25_ugm3 * p.total_pop) / NULLIF(SUM(p.total_pop), 0))::numeric, 2) AS pm25_ugm3,
                   ROUND((SUM(a.no2_ugm3 * p.total_pop) / NULLIF(SUM(p.total_pop), 0))::numeric, 2) AS no2_ugm3,
                   ROUND((SUM(a.pm10_ugm3 * p.total_pop) / NULLIF(SUM(p.total_pop), 0))::numeric, 2) AS pm10_ugm3
            FROM core_air_quality_lad a
            LEFT JOIN mv_lad_population p ON p.lad_code = a.lad_code
            GROUP BY a.year ORDER BY a.year
        """),
    )
    national_rows = [dict(r) for r in national_res.mappings().all()]

    # Display name
    if boundary_source == "county" and local_lads:
        lad_name = entity_name
    else:
        lad_name_res = await db.execute(
            text("SELECT lad_name FROM core_lad_boundaries WHERE lad_code = :lad"),
            {"lad": lad_code},
        )
        lad_name_row = lad_name_res.mappings().first()
        lad_name = lad_name_row["lad_name"] if lad_name_row else entity_name

    # Serialize numeric types
    for row in local_rows + national_rows:
        for k in ("pm25_ugm3", "no2_ugm3", "pm10_ugm3"):
            if row.get(k) is not None:
                row[k] = float(row[k])

    result = {
        "local": local_rows,
        "national": national_rows,
        "lad_name": lad_name,
    }
    await cache_set(cache_key, result, ttl=86400)
    return result


# ---------------------------------------------------------------------------
# Comparable areas
# ---------------------------------------------------------------------------

@router.get("/comparable")
async def get_comparable_areas(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    db: AsyncSession = Depends(get_db),
):
    """Find the 5 most similar LADs for single-authority sessions.

    Multi-authority scopes such as counties are intentionally marked unsupported
    until a true county-to-county comparable model is implemented.
    """
    sess = await require_session(session_key)
    lad_code = sess["lad_code"]
    local_lads = sorted({code for code in (sess.get("local_lads") or []) if code and code != "_"})
    scope_type = session_local_scope_type(sess)
    entity_name = session_entity_name(sess)

    cache_key = f"comparable:{session_key}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    if len(local_lads) > 1:
        result = await find_comparable_scopes(
            db,
            target_lad_codes=local_lads,
            target_name=entity_name,
            scope_type=scope_type,
            limit=5,
        )
        result.setdefault("target", {})["lad_count"] = len(local_lads)
    else:
        anchor_lad = local_lads[0] if local_lads else lad_code
        result = await find_comparable_lads(db, lad_code=anchor_lad, limit=5)
        result["status"] = "ok"
        result.setdefault("target", {})["scope_name"] = entity_name
        result["target"]["scope_type"] = scope_type
        result["target"]["anchor_lad_code"] = anchor_lad

    # Serialize Decimal types
    for area in result.get("comparable", []):
        for k in ("avg_price", "median_rent", "earnings", "pm25", "hpi_yoy", "distance"):
            if area.get(k) is not None:
                area[k] = float(area[k])
    for k in ("avg_price", "median_rent", "earnings", "pm25", "hpi_yoy", "distance"):
        if result.get("target", {}).get(k) is not None:
            result["target"][k] = float(result["target"][k])

    await cache_set(cache_key, result, ttl=86400)
    return result


# ---------------------------------------------------------------------------
# Wikipedia area summary
# ---------------------------------------------------------------------------

WIKI_API = "https://en.wikipedia.org/w/api.php"


async def _wiki_search(place: str, client: httpx.AsyncClient) -> dict | None:
    """Search Wikipedia for a place, return extract + image or None."""
    # Step 1: search for the page
    search_resp = await client.get(WIKI_API, params={
        "action": "query",
        "list": "search",
        "srsearch": f"{place} England",
        "srlimit": "3",
        "format": "json",
    }, timeout=5)
    search_data = search_resp.json()
    results = search_data.get("query", {}).get("search", [])
    if not results:
        return None

    # Pick the best match — prefer exact title match
    page_title = results[0]["title"]
    for r in results:
        if r["title"].lower() == place.lower():
            page_title = r["title"]
            break

    # Step 2: get extract + page image
    detail_resp = await client.get(WIKI_API, params={
        "action": "query",
        "titles": page_title,
        "prop": "extracts|pageimages|info",
        "exintro": "1",
        "explaintext": "1",
        "exsectionformat": "plain",
        "piprop": "original|thumbnail",
        "pithumbsize": "800",
        "inprop": "url",
        "format": "json",
    }, timeout=5)
    detail_data = detail_resp.json()
    pages = detail_data.get("query", {}).get("pages", {})
    if not pages:
        return None

    page = next(iter(pages.values()))
    if page.get("missing") is not None:
        return None

    extract = page.get("extract", "")
    if not extract or len(extract) < 50:
        return None

    # Truncate to ~3 paragraphs
    paragraphs = extract.split("\n")
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    extract = "\n\n".join(paragraphs[:3])

    # Image info
    image = None
    if page.get("thumbnail"):
        thumb = page["thumbnail"]
        original = page.get("original", {})
        image = {
            "url": thumb.get("source"),
            "width": thumb.get("width"),
            "height": thumb.get("height"),
            "original_url": original.get("source"),
        }

    return {
        "title": page.get("title", page_title),
        "extract": extract,
        "url": page.get("fullurl", f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"),
        "image": image,
    }


@router.get("/wiki-summary")
async def get_wiki_summary(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    db: AsyncSession = Depends(get_db),
):
    """Return a Wikipedia summary for the searched area.

    Fallback chain: place_name → LAD name → parent name.
    Results cached for 7 days (Wikipedia content rarely changes).
    """
    sess = await require_session(session_key)

    # Build search candidates: place_name, LAD name, parent comparison name
    candidates = []
    place_name = sess.get("place_name") or sess.get("entity_name")
    if place_name and place_name not in ("_", ""):
        candidates.append(place_name)

    # LAD name from DB
    lad_code = sess.get("lad_code")
    if lad_code and lad_code != "_":
        lad_res = await db.execute(
            text("SELECT lad_name FROM core_lad_boundaries WHERE lad_code = :lad LIMIT 1"),
            {"lad": lad_code},
        )
        lad_row = lad_res.mappings().first()
        if lad_row:
            lad_name = lad_row["lad_name"]
            if lad_name not in candidates:
                candidates.append(lad_name)

    # Parent comparison name (e.g. "Greater London", "Reading")
    parent_name = sess.get("parent_comparison_name") or sess.get("parent_name")
    if parent_name and parent_name not in candidates:
        candidates.append(parent_name)

    if not candidates:
        return {"summary": None}

    # Check cache — keyed on the first candidate (most specific)
    cache_key = f"wiki:{candidates[0].lower().replace(' ', '_')}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    # Try each candidate
    result = {"summary": None}
    async with httpx.AsyncClient() as client:
        for candidate in candidates:
            try:
                summary = await _wiki_search(candidate, client)
                if summary:
                    result = {"summary": summary, "search_term": candidate}
                    break
            except Exception:
                logger.warning("Wikipedia search failed for %s", candidate, exc_info=True)
                continue

    await cache_set(cache_key, result, ttl=604800)  # 7 days
    return result
