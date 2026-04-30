"""
GET /api/v1/aq-history
GET /api/v1/comparable
Air quality history and comparable areas endpoints.
"""
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
