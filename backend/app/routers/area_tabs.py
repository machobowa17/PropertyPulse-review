"""
GET /api/v1/area?session_key=&tab=
GET /api/v1/area/property?session_key=&lat=&lon=&postcode=
Tab data endpoint — dispatches to the 6 tab service handlers.
Property endpoint returns property-specific data (EPC, transactions, parcel, flood, etc.).
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

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

AREA_CACHE_VERSION = "v39"  # bumped: audit cleanup (621 empty rows deleted, phase fixes, LDO fixes)

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


_hetzner_pool = ThreadPoolExecutor(max_workers=4)


def _fetch_hetzner_property(postcode, paon, saon, street, uprn):
    """Synchronous Hetzner API calls — run in thread pool from async context."""
    try:
        from etl_lib import property_api
    except ImportError:
        logger.warning("property_api unavailable — skipping Hetzner data")
        return None, None

    # 1. Transaction history by address
    transactions = None
    if postcode:
        transactions = property_api.transactions_by_address(
            postcode, paon=paon, saon=saon, street=street,
        )

    # 2. EPC data — by postcode + address match (UPRN endpoint has type-cast bug)
    epc_records = None
    if postcode:
        pc_compact = postcode.replace(" ", "")
        all_epcs = property_api.epc_by_postcode(pc_compact, limit=100)
        if all_epcs and isinstance(all_epcs, list):
            # Filter to matching address
            paon_upper = (paon or "").upper().strip()
            saon_upper = (saon or "").upper().strip()
            street_upper = (street or "").upper().strip()
            matched = []
            for epc in all_epcs:
                epc_paon = str(epc.get("building_reference_number") or epc.get("paon") or "").upper().strip()
                epc_saon = str(epc.get("saon") or "").upper().strip()
                epc_street = str(epc.get("street") or epc.get("address1") or "").upper().strip()
                # Match on PAON + street (SAON if present)
                if paon_upper and paon_upper in epc_paon:
                    if not street_upper or street_upper[:8] in epc_street or epc_street[:8] in street_upper:
                        if not saon_upper or saon_upper in epc_saon:
                            matched.append(epc)
            epc_records = matched if matched else all_epcs[:3]  # fallback: first 3

    return transactions, epc_records


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
    """Return full property data: transactions, EPC, parcel, flood, noise, broadband, LLC."""
    await require_session(session_key)

    cache_key = f"property:{AREA_CACHE_VERSION}:{lat:.6f}:{lon:.6f}:{paon}:{saon}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    geo_params = {"lat": lat, "lon": lon}

    # Start Hetzner API calls in thread pool (non-blocking)
    loop = asyncio.get_event_loop()
    hetzner_future = loop.run_in_executor(
        _hetzner_pool, _fetch_hetzner_property, postcode, paon, saon, street, uprn,
    )

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
        SELECT charge_type, authority, valid_from
        FROM core_llc_charges
        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        LIMIT 20
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

    # Parse spatial results
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
        {
            "charge_type": r["charge_type"],
            "authority": r.get("authority"),
            "valid_from": str(r["valid_from"]) if r.get("valid_from") else None,
        }
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

    # Await Hetzner results
    try:
        transactions, epc_records = await hetzner_future
    except Exception as e:
        logger.warning("Hetzner property data failed: %s", e)
        transactions, epc_records = None, None

    result = {
        "coordinates": {"lat": lat, "lon": lon},
        "address": {
            "paon": paon,
            "saon": saon,
            "street": street,
            "postcode": postcode,
            "uprn": uprn,
        },
        "transactions": transactions or [],
        "epc": epc_records[0] if epc_records else None,
        "epc_history": epc_records or [],
        "parcel": parcel,
        "flood_zone": flood_zone,
        "llc_charges": llc_charges,
        "noise": noise,
        "broadband": broadband,
    }

    await cache_set(cache_key, result, ttl=3600)
    return result
