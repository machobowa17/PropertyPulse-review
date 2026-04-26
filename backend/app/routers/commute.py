"""
GET /api/v1/commute/station-pair?origin_crs=X&dest_crs=Y
GET /api/v1/commute/stations?q=search
GET /api/v1/commute/journey?origin_crs=X&dest_crs=Y&time=0800

Station pair endpoint returns pre-computed destination data (journey time,
frequency, punctuality, season ticket price, legs) for a custom
origin->destination pair.

Station search endpoint returns matching station names (all types: rail,
metro, tram, ferry) for the destination dropdown.

Journey endpoint fetches a live MOTIS result for a custom departure time.
MOTIS is self-hosted on Hetzner (env: MOTIS_BASE_URL).
"""
import json
import logging
import os
import sys

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import TABLE_NAMES
from app.database import get_db

# Shared MOTIS client (mounted from etl/lib via docker-compose)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from etl_lib.motis import motis_journey  # noqa: E402

logger = logging.getLogger(__name__)
router = APIRouter()

# CRS -> {atco, lat, lon} mapping for routing API calls (loaded once at import)
_CRS_MAPPING = {}
_MAPPING_PATH = os.environ.get(
    "CRS_MAPPING_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "etl_data", "crs_naptan_mapping.json"),
)
# Fallback: check etl/data path for local dev without docker
if not os.path.exists(_MAPPING_PATH):
    _MAPPING_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "etl", "data", "crs_naptan_mapping.json"
    )
if os.path.exists(_MAPPING_PATH):
    with open(_MAPPING_PATH) as _f:
        _CRS_MAPPING = json.load(_f)


@router.get("/commute/station-pair")
async def station_pair(
    origin_crs: str = Query(..., min_length=3, max_length=3),
    dest_crs: str = Query(..., min_length=3, max_length=3),
    db: AsyncSession = Depends(get_db),
):
    """Return pre-computed commute data for a specific origin->destination pair."""
    result = await db.execute(
        text(f"""
            SELECT dest_name, journey_min, trains_per_hour, pct_on_time,
                   season_ticket_gbp, journey_type, num_changes, modes,
                   peak_fare_pence, offpeak_fare_pence, fare_zones, legs,
                   fare_caveats,
                   COALESCE(is_travelcard, FALSE) AS is_travelcard,
                   travelcard_zones
            FROM {TABLE_NAMES['station_destinations']}
            WHERE origin_crs = :origin AND dest_crs = :dest
        """),
        {"origin": origin_crs.upper(), "dest": dest_crs.upper()},
    )
    row = result.mappings().first()
    if row:
        resp = {
            "dest_crs": dest_crs.upper(),
            "dest_name": row["dest_name"],
            "journey_min": int(row["journey_min"]) if row["journey_min"] else None,
            "trains_per_hour": float(row["trains_per_hour"]) if row["trains_per_hour"] else None,
            "pct_on_time": float(row["pct_on_time"]) if row["pct_on_time"] else None,
            "season_ticket_gbp": float(row["season_ticket_gbp"]) if row["season_ticket_gbp"] else None,
            "journey_type": row["journey_type"] or "direct",
            "num_changes": int(row["num_changes"]) if row["num_changes"] else 0,
            "modes": list(row["modes"]) if row["modes"] else [],
            "peak_fare_pence": int(row["peak_fare_pence"]) if row["peak_fare_pence"] else None,
            "offpeak_fare_pence": int(row["offpeak_fare_pence"]) if row["offpeak_fare_pence"] else None,
            "fare_zones": row["fare_zones"],
            "legs": row["legs"],
            "fare_caveats": list(row["fare_caveats"]) if row["fare_caveats"] else [],
        }
        if row["is_travelcard"]:
            resp["is_travelcard"] = True
            if row["travelcard_zones"]:
                resp["travelcard_zones"] = row["travelcard_zones"]
        return resp
    # No pre-computed data — return nulls
    return {
        "dest_crs": dest_crs.upper(),
        "dest_name": None,
        "journey_min": None,
        "trains_per_hour": None,
        "pct_on_time": None,
        "season_ticket_gbp": None,
        "journey_type": "direct",
        "num_changes": 0,
        "modes": [],
        "peak_fare_pence": None,
        "offpeak_fare_pence": None,
        "fare_zones": None,
        "legs": None,
        "fare_caveats": [],
    }


@router.get("/commute/stations")
async def station_search(
    q: str = Query(..., min_length=2, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    """Search stations by name for the destination dropdown.

    Returns rail, metro/underground, tram, and ferry stations (not bus stops).
    Includes lat/lon for coordinate-based routing to non-NR stations.
    """
    result = await db.execute(
        text(f"""
            SELECT DISTINCT ON (name)
                   COALESCE(crs_code, atco_code) AS station_id,
                   crs_code,
                   REGEXP_REPLACE(
                     REGEXP_REPLACE(stop_name,
                         ' (Rail Station|Station)$', '', 'i'),
                     '^London ', '', 'i') AS name,
                   stop_type,
                   latitude AS lat,
                   longitude AS lon
            FROM {TABLE_NAMES['transport_stops']}
            WHERE stop_type IN ('RLY', 'MET', 'PLT', 'FER')
              AND stop_name ILIKE :pattern
              AND latitude IS NOT NULL
            ORDER BY name
            LIMIT 20
        """),
        {"pattern": f"%{q}%"},
    )
    rows = result.mappings().all()
    return [
        {
            "station_id": r["station_id"],
            "crs_code": r["crs_code"],
            "name": r["name"],
            "stop_type": r["stop_type"],
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
        }
        for r in rows
    ]


@router.get("/commute/journey")
async def live_journey(
    origin_crs: str = Query(..., min_length=3, max_length=3),
    dest_crs: str = Query(None, min_length=3, max_length=3),
    dest_lat: float = Query(None),
    dest_lon: float = Query(None),
    time: str = Query("0800", min_length=4, max_length=4),
):
    """Fetch live MOTIS journey for a custom departure time.

    Destination can be specified by CRS code OR by lat/lon coordinates
    (for non-NR stations like tube/tram/DLR).
    """
    from_entry = _CRS_MAPPING.get(origin_crs.upper(), {})
    from_lat = from_entry.get("lat")
    from_lon = from_entry.get("lon")

    if not from_lat:
        return {
            "error": "No coordinate mapping for origin CRS code",
            "origin_crs": origin_crs.upper(),
        }

    # Resolve destination coordinates
    to_lat = None
    to_lon = None
    if dest_crs:
        to_entry = _CRS_MAPPING.get(dest_crs.upper(), {})
        to_lat = to_entry.get("lat")
        to_lon = to_entry.get("lon")
    if to_lat is None and dest_lat is not None and dest_lon is not None:
        to_lat = dest_lat
        to_lon = dest_lon

    if not to_lat:
        return {
            "error": "No coordinates for destination (provide dest_crs or dest_lat+dest_lon)",
            "origin_crs": origin_crs.upper(),
        }

    try:
        result = motis_journey(from_lat, from_lon, to_lat, to_lon, depart_time=time, timeout=15)
    except Exception:
        logger.exception("MOTIS unexpected error: %s → %s at %s",
                         origin_crs.upper(), dest_crs or f"{dest_lat},{dest_lon}", time)
        return {
            "error": "Journey lookup failed",
            "origin_crs": origin_crs.upper(),
        }

    if not result:
        logger.info("No MOTIS route: %s → %s at %s", origin_crs.upper(),
                     dest_crs or f"{dest_lat},{dest_lon}", time)
        return {
            "error": "No journey found",
            "origin_crs": origin_crs.upper(),
        }

    result["origin_crs"] = origin_crs.upper()
    if dest_crs:
        result["dest_crs"] = dest_crs.upper()
    return result


@router.get("/school-walk")
async def school_walk_time(
    urn: int = Query(..., description="School URN"),
    from_lat: float = Query(..., description="Origin latitude"),
    from_lon: float = Query(..., description="Origin longitude"),
):
    """Proxy walk-time request to Hetzner School API (which calls MOTIS internally)."""
    try:
        from etl_lib import schools_api
    except ImportError:
        schools_api = None

    if not schools_api:
        return {"error": "School API not available"}

    result = schools_api.walk_time(urn, from_lat, from_lon)
    if not result:
        return {"error": "Walk time lookup failed", "urn": urn}
    return result


@router.get("/school-detail")
async def school_detail(
    urn: int = Query(..., description="School URN"),
):
    """Proxy detail request to Hetzner School API — returns full multi-year data."""
    try:
        from etl_lib import schools_api
    except ImportError:
        schools_api = None

    if not schools_api:
        return {"error": "School API not available"}

    result = schools_api.school_detail(urn)
    if not result:
        return {"error": "School detail lookup failed", "urn": urn}
    return result
