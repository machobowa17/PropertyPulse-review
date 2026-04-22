"""
Shared MOTIS routing client.

Single source of truth for calling the self-hosted MOTIS API and parsing
itinerary responses into our internal journey format.

All consumers (nr_destinations, enrich_hub_destinations, commute router)
import from here instead of duplicating the logic.
"""

import datetime
import json
import logging
import os
import ssl
import urllib.request

logger = logging.getLogger(__name__)

MOTIS_BASE_URL = os.environ.get(
    "MOTIS_BASE_URL", "http://128.140.103.160:8080"
).rstrip("/") + "/api/v1/plan"

# Map MOTIS mode names -> internal mode IDs (frontend-compatible).
MODE_MAP = {
    "WALK": "walking",
    "TRANSIT": "national-rail",
    "TRAM": "tram",
    "METRO": "tube",
    "SUBWAY": "tube",
    "RAIL": "national-rail",
    "REGIONAL_RAIL": "national-rail",
    "LONG_DISTANCE": "national-rail",
    "BUS": "bus",
    "FERRY": "ferry",
    "CABLE_CAR": "dlr",
}


def _build_departure_time(depart_time="0800"):
    """Build ISO 8601 UTC departure string for MOTIS.

    Picks the next weekday from today and converts UK local time to UTC
    using a simplified BST heuristic (Apr-Oct = BST).
    """
    now = datetime.date.today()
    weekday = now.weekday()
    if weekday >= 5:
        now += datetime.timedelta(days=(7 - weekday))

    month = now.month
    is_bst = 4 <= month <= 10
    hour = int(depart_time[:2])
    minute = int(depart_time[2:])
    if is_bst:
        hour -= 1
        if hour < 0:
            hour += 24
    return f"{now.isoformat()}T{hour:02d}:{minute:02d}:00Z"


def _parse_itinerary(itinerary):
    """Extract legs, modes, and changes from a MOTIS itinerary.

    Returns dict with keys: journey_min, num_changes, modes, legs.
    """
    duration_min = itinerary["duration"] // 60
    num_changes = itinerary.get("transfers", 0)

    legs = []
    modes_set = set()
    for leg in itinerary.get("legs", []):
        raw_mode = leg.get("mode", "WALK")
        mapped_mode = MODE_MAP.get(raw_mode, "national-rail")
        if mapped_mode != "walking":
            modes_set.add(mapped_mode)

        ld = {
            "mode": mapped_mode,
            "duration": leg.get("duration", 0) // 60,
        }

        route = leg.get("routeShortName", "")
        agency = leg.get("agencyName", "")
        if route:
            ld["line"] = route
        if agency and route:
            ld["summary"] = f"{agency} {route}"
        elif agency:
            ld["summary"] = agency
        elif route:
            ld["summary"] = route
        else:
            ld["summary"] = mapped_mode.replace("-", " ").title()

        from_obj = leg.get("from", {})
        to_obj = leg.get("to", {})
        from_name = from_obj.get("name", "")
        to_name = to_obj.get("name", "")
        if from_name and from_name not in ("START", "END"):
            ld["from"] = from_name
        if to_name and to_name not in ("START", "END"):
            ld["to"] = to_name

        start_time = leg.get("startTime", "")
        end_time = leg.get("endTime", "")
        if start_time and len(start_time) >= 16:
            ld["depart"] = start_time[11:16]
        if end_time and len(end_time) >= 16:
            ld["arrive"] = end_time[11:16]

        dist = leg.get("distance", 0)
        if dist:
            ld["distance_m"] = round(dist)

        legs.append(ld)

    return {
        "journey_min": duration_min,
        "num_changes": num_changes,
        "modes": sorted(modes_set),
        "legs": legs,
    }


def motis_journey(from_lat, from_lon, to_lat, to_lon,
                  depart_time="0800", base_url=None, timeout=30):
    """Call MOTIS API and return parsed journey dict, or None on failure.

    Args:
        from_lat, from_lon: Origin coordinates (WGS84).
        to_lat, to_lon: Destination coordinates (WGS84).
        depart_time: 4-digit local UK time string, e.g. "0800".
        base_url: Override MOTIS endpoint (defaults to MOTIS_BASE_URL).
        timeout: HTTP timeout in seconds.

    Returns:
        dict with journey_min, num_changes, modes, legs, journey_type
        or None if no route found / API error.
    """
    endpoint = base_url or MOTIS_BASE_URL
    time_str = _build_departure_time(depart_time)

    url = (
        f"{endpoint}"
        f"?fromPlace={from_lat},{from_lon}"
        f"&toPlace={to_lat},{to_lon}"
        f"&time={time_str}"
        f"&numItineraries=3"
        f"&mode=TRANSIT,WALK"
    )

    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; PropertyPulse/1.0)",
        })
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        logger.warning("MOTIS HTTP %d for %s,%s → %s,%s",
                       e.code, from_lat, from_lon, to_lat, to_lon)
        return None
    except urllib.error.URLError as e:
        logger.warning("MOTIS connection error for %s,%s → %s,%s: %s",
                       from_lat, from_lon, to_lat, to_lon, e.reason)
        return None
    except Exception as e:
        logger.warning("MOTIS unexpected error for %s,%s → %s,%s: %s",
                       from_lat, from_lon, to_lat, to_lon, e)
        return None

    itineraries = data.get("itineraries", [])
    if not itineraries:
        return None

    best = min(itineraries, key=lambda it: it.get("duration", 999999))
    result = _parse_itinerary(best)
    result["journey_type"] = "multi_modal"
    return result
