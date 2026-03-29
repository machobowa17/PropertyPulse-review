"""
GET /api/v1/commute?origin_lat=&origin_lon=&destination=
Haversine + mode speed factors → structured commute estimate.
"""
import math
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.geo_resolver import resolve_search
from app.cache import cache_get, cache_set

router = APIRouter()

# Mode config: (speed_kmh, road_factor, fixed_wait_mins, label)
# road_factor: multiplier on straight-line distance to approximate road/path distance
# walking uses 1.15 (pedestrian routes shorter than road routes)
MODES = {
    "driving": {"speed": 50,  "road_factor": 1.30, "wait": 0,  "label": "Driving"},
    "transit": {"speed": 30,  "road_factor": 1.30, "wait": 10, "label": "Transit"},
    "cycling": {"speed": 18,  "road_factor": 1.20, "wait": 0,  "label": "Cycling"},
    "walking": {"speed": 5,   "road_factor": 1.15, "wait": 0,  "label": "Walking"},
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_mode(straight_km: float, mode: dict) -> dict:
    route_km = round(straight_km * mode["road_factor"], 1)
    travel_mins = (route_km / mode["speed"]) * 60
    total_mins = round(travel_mins + mode["wait"])
    h, m = divmod(total_mins, 60)
    label = f"{h}h {m}m" if h > 0 and m > 0 else (f"{h}h" if h > 0 else f"{total_mins} min")
    return {
        "route_km": route_km,
        "mins": total_mins,
        "label": label,
    }


@router.get("/commute")
async def commute(
    origin_lat: float = Query(...),
    origin_lon: float = Query(...),
    destination: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"commute:{round(origin_lat,4)}:{round(origin_lon,4)}:{destination.strip().lower()}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    resolved = await resolve_search(db, destination.strip())
    if not resolved.get("coordinates") or not resolved["coordinates"].get("lat"):
        raise HTTPException(status_code=404, detail="Destination not found")

    dest_lat = resolved["coordinates"]["lat"]
    dest_lon = resolved["coordinates"]["lon"]
    straight_km = haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)

    dest_name = (
        destination.upper()
        if resolved.get("type") == "postcode"
        else resolved.get("query", destination)
    )

    result = {
        "destination": dest_name,
        "straight_km": round(straight_km, 1),
        "modes": {
            mode_key: {**estimate_mode(straight_km, cfg), "mode": cfg["label"]}
            for mode_key, cfg in MODES.items()
        },
    }

    await cache_set(cache_key, result, ttl=86400)
    return result
