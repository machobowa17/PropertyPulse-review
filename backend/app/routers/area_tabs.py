"""
GET /api/v1/area?session_key=&tab=
GET /api/v1/area/property?session_key=&lat=&lon=&postcode=
Tab data endpoint — dispatches to the 6 tab service handlers.
Property endpoint returns property-specific data (EPC, parcel, flood, etc.).
"""
import asyncio
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text as sa_text
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
from app.services.tab_overview import fetch_overview

router = APIRouter()

AREA_CACHE_VERSION = "v37"  # bumped: weighted local multi-LAD queries (council tax, AQ)

TAB_HANDLERS = {
    "Overview": fetch_overview,
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


logger = logging.getLogger(__name__)


@router.get("/area/property")
async def get_property_data(
    session_key: str = Query(..., description="Session key from /resolve"),
    lat: float = Query(..., description="Property latitude"),
    lon: float = Query(..., description="Property longitude"),
    postcode: str = Query(None, description="Property postcode (for noise/broadband)"),
    paon: str = Query(None, description="Primary addressable object name"),
    saon: str = Query(None, description="Secondary addressable object name"),
    street: str = Query(None, description="Street name"),
    uprn: int = Query(None, description="Unique Property Reference Number"),
    db: AsyncSession = Depends(get_db),
):
    """Return property-specific data: INSPIRE parcel, flood, noise, broadband, LLC.

    Transaction history and EPC data come from the Hetzner Property API
    (called client-side or via a separate proxy endpoint), so this endpoint
    focuses on spatial lookups against EC2's PostGIS tables.
    """
    await require_session(session_key)

    cache_key = f"property:{AREA_CACHE_VERSION}:{lat:.6f}:{lon:.6f}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    geo_params = {"lat": lat, "lon": lon}

    # Run spatial queries sequentially (async sessions cannot run concurrent queries)
    parcel_result = await db.execute(sa_text("""
        SELECT inspire_id, authority,
               ST_AsGeoJSON(geom) AS geojson
        FROM core_inspire_parcels
        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        LIMIT 1
    """), geo_params)

    flood_result = await db.execute(sa_text("""
        SELECT flood_zone
        FROM core_flood_zones
        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        ORDER BY CASE flood_zone WHEN 'Flood Zone 3' THEN 0 ELSE 1 END
        LIMIT 1
    """), geo_params)

    llc_result = await db.execute(sa_text("""
        SELECT charge_type
        FROM core_llc_charges
        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        LIMIT 10
    """), geo_params)

    # Postcode-keyed lookups (noise, broadband)
    noise_result = None
    broadband_result = None
    if postcode:
        pc_clean = postcode.strip().upper()
        noise_result = await db.execute(sa_text("""
            SELECT road_noise_db, rail_noise_db
            FROM core_noise
            WHERE postcode = :pc
            LIMIT 1
        """), {"pc": pc_clean})

        broadband_result = await db.execute(sa_text("""
            SELECT avg_download_mbps, avg_upload_mbps,
                   superfast_pct, ultrafast_pct, gigabit_pct, fttp_pct
            FROM core_broadband_postcode
            WHERE postcode = :pc
            LIMIT 1
        """), {"pc": pc_clean})

    # Parse results
    parcel_row = parcel_result.mappings().first()
    parcel = None
    if parcel_row:
        import json
        parcel = {
            "inspire_id": parcel_row["inspire_id"],
            "authority": parcel_row["authority"],
            "geojson": json.loads(parcel_row["geojson"]),
        }

    flood_row = flood_result.mappings().first()
    flood_zone = flood_row["flood_zone"] if flood_row else None

    llc_rows = llc_result.mappings().all()
    llc_charges = [
        {"charge_type": r["charge_type"]}
        for r in llc_rows
    ]

    noise = None
    if noise_result:
        noise_row = noise_result.mappings().first()
        if noise_row:
            noise = {
                "road_db": float(noise_row["road_noise_db"]) if noise_row["road_noise_db"] is not None else None,
                "rail_db": float(noise_row["rail_noise_db"]) if noise_row["rail_noise_db"] is not None else None,
            }

    broadband = None
    if broadband_result:
        bb_row = broadband_result.mappings().first()
        if bb_row:
            broadband = {
                "avg_download": float(bb_row["avg_download_mbps"]) if bb_row["avg_download_mbps"] is not None else None,
                "avg_upload": float(bb_row["avg_upload_mbps"]) if bb_row["avg_upload_mbps"] is not None else None,
                "superfast_pct": float(bb_row["superfast_pct"]) if bb_row["superfast_pct"] is not None else None,
                "ultrafast_pct": float(bb_row["ultrafast_pct"]) if bb_row["ultrafast_pct"] is not None else None,
                "gigabit_pct": float(bb_row["gigabit_pct"]) if bb_row["gigabit_pct"] is not None else None,
                "fttp_pct": float(bb_row["fttp_pct"]) if bb_row["fttp_pct"] is not None else None,
            }

    result = {
        "coordinates": {"lat": lat, "lon": lon},
        "address": {
            "paon": paon,
            "saon": saon,
            "street": street,
            "postcode": postcode,
            "uprn": uprn,
        },
        "parcel": parcel,
        "flood_zone": flood_zone,
        "llc_charges": llc_charges,
        "noise": noise,
        "broadband": broadband,
    }

    await cache_set(cache_key, result, ttl=3600)
    return result
