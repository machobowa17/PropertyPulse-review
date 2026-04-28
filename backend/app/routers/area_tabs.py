"""
GET /api/v1/area?session_key=&tab=
Tab data endpoint — dispatches to the 5 tab service handlers.
Post-processes flat metrics into the nested Metric contract via enrich_metrics().
"""
import asyncio

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.errors import http_error
from app.cache import cache_get, cache_set
from app.services.session_helpers import (
    session_centroid,
    session_boundary_source,
    session_parent_lads,
    session_parent_name,
    area_scope_cache_key as _area_scope_cache_key_fn,
    require_session,
)
from app.services.helpers import enrich_metrics
from app.services.tab_property import fetch_property_market
from app.services.tab_lifestyle import fetch_lifestyle_connectivity
from app.services.tab_environment import fetch_environment_safety
from app.services.tab_community import fetch_community_education
from app.services.tab_governance import fetch_local_governance

router = APIRouter()

AREA_CACHE_VERSION = "v26"  # bumped: LAD pre-aggregation MVs for county/LAD searches

TAB_HANDLERS = {
    "Property & Market": fetch_property_market,
    "Lifestyle & Connectivity": fetch_lifestyle_connectivity,
    "Environment & Safety": fetch_environment_safety,
    "Community & Education": fetch_community_education,
    "Local Governance": fetch_local_governance,
}


def _area_scope_cache_key(sess: dict, tab: str) -> str:
    return _area_scope_cache_key_fn(sess, tab, cache_version=AREA_CACHE_VERSION)


@router.get("/area")
async def get_area_data(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    tab: str = Query("Property & Market", description="Tab name"),
    db: AsyncSession = Depends(get_db),
):
    handler = TAB_HANDLERS.get(tab)
    if not handler:
        raise http_error(400, "INVALID_TAB", f"Unknown tab: {tab}. Valid tabs: {list(TAB_HANDLERS.keys())}")

    cache_key = f"area:{AREA_CACHE_VERSION}:{session_key}:{tab}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    sess = await require_session(session_key)
    scope_cache_key = _area_scope_cache_key(sess, tab)
    shared_cached = await cache_get(scope_cache_key)
    if shared_cached:
        await cache_set(cache_key, shared_cached, ttl=3600)
        return shared_cached

    centroid_lat, centroid_lon = session_centroid(sess)
    parent_name = session_parent_name(sess)
    flat_metrics = await handler(
        db,
        lad_code=sess["lad_code"],
        ward_code=sess["ward_code"],
        lsoa_codes=sess["lsoa_codes"],
        centroid_lat=centroid_lat,
        centroid_lon=centroid_lon,
        search_mode=sess.get("search_mode", "postcode"),
        local_lads=sess.get("local_lads", []),
        parent_lads=session_parent_lads(sess),
        parent_name=parent_name,
        boundary_source=session_boundary_source(sess),
    )
    # Post-process: enrich flat metrics into nested contract
    metrics = enrich_metrics(flat_metrics, parent_name=parent_name)
    result = {"tab": tab, "metrics": metrics}
    await asyncio.gather(
        cache_set(cache_key, result, ttl=3600),
        cache_set(scope_cache_key, result, ttl=3600),
    )
    return result
