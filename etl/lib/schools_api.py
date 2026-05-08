"""
Shared School API client.

Single source of truth for calling the self-hosted School API on Hetzner
and returning parsed results for the EC2 backend to consume.

Follows the exact same pattern as etl/lib/motis.py.
"""

import json
import logging
import os
import ssl
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

SCHOOLS_API_BASE_URL = os.environ.get(
    "SCHOOLS_API_BASE_URL", "http://128.140.103.160:8083"
).rstrip("/")

_ssl_ctx = ssl._create_unverified_context()


def _request(method, path, body=None, timeout=30):
    """Make an HTTP request to the School API."""
    url = f"{SCHOOLS_API_BASE_URL}{path}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "PropertyPulse-EC2/1.0",
    }

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        resp = urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        logger.warning("School API HTTP %d for %s %s", e.code, method, path)
        return None
    except urllib.error.URLError as e:
        logger.warning("School API connection error for %s: %s", path, e.reason)
        return None
    except Exception as e:
        logger.warning("School API unexpected error for %s: %s", path, e)
        return None


def nearby_schools(lat, lon, radius_m=3000, phase=None, limit=50):
    """Fetch schools near a lat/lon point.

    Args:
        lat, lon: Centre point (WGS84).
        radius_m: Search radius in metres.
        phase: Comma-separated phases to filter.
        limit: Max results.

    Returns:
        Dict with keys: schools (list), count.
    """
    path = f"/schools/nearby?lat={lat}&lon={lon}&radius_m={radius_m}&limit={limit}"
    if phase:
        path += f"&phase={urllib.parse.quote(phase)}"
    return _request("GET", path, timeout=30)


def schools_by_lsoa(lsoa_codes=None, lad_codes=None, phase=None, lat=None, lon=None, limit=50):
    """Fetch schools matching LSOA codes or LAD codes (for area-mode searches).

    Args:
        lsoa_codes: List of LSOA code strings (postcode→LSOA join).
        lad_codes: List of LAD code strings (direct match, preferred).
        phase: Optional phase filter.
        lat, lon: Optional centre point for distance sorting.
        limit: Max results.

    Returns:
        Dict with keys: schools (list), count.
    """
    body = {"limit": limit}
    if lad_codes:
        body["lad_codes"] = lad_codes
    elif lsoa_codes:
        body["lsoa_codes"] = lsoa_codes
    if phase:
        body["phase"] = phase
    if lat is not None and lon is not None:
        body["lat"] = lat
        body["lon"] = lon
    return _request("POST", "/schools/by-lsoa", body, timeout=30)


def quality_summary(lat=None, lon=None, radius_m=3000, phase=None, lad_code=None):
    """Get Ofsted rating distribution summary for schools near a point or in a LAD.

    Returns:
        Dict with total_schools, primary_count, secondary_count,
        outstanding, good, requires_improvement, inadequate, avg_rating.
    """
    params = [f"radius_m={radius_m}"]
    if lat is not None and lon is not None:
        params.append(f"lat={lat}&lon={lon}")
    if lad_code:
        params.append(f"lad_code={urllib.parse.quote(lad_code)}")
    if phase:
        params.append(f"phase={urllib.parse.quote(phase)}")
    path = "/schools/quality-summary?" + "&".join(params)
    return _request("GET", path, timeout=15)


def school_detail(urn):
    """Get full school profile + inspection history.

    Args:
        urn: School URN (integer).

    Returns:
        Dict with school info + inspections list.
    """
    return _request("GET", f"/schools/{urn}", timeout=15)


def compare_schools(urns):
    """Compare up to 5 schools side-by-side.

    Args:
        urns: List of URN integers.

    Returns:
        Dict with schools list.
    """
    return _request("POST", "/schools/compare", {"urns": urns}, timeout=15)


def walk_time(urn, from_lat, from_lon):
    """Get walking time from a point to a school.

    Args:
        urn: School URN.
        from_lat, from_lon: Origin point.

    Returns:
        Dict with walk_minutes, distance_m, source.
    """
    return _request("GET", f"/schools/{urn}/walk-time?from_lat={from_lat}&from_lon={from_lon}", timeout=30)


def nearby_nurseries(lat, lon, radius_m=2000, limit=50):
    """Fetch nurseries near a lat/lon point.

    Returns:
        Dict with keys: nurseries (list), count.
    """
    return _request("GET", f"/nurseries/nearby?lat={lat}&lon={lon}&radius_m={radius_m}&limit={limit}", timeout=15)


def nursery_summary(lat=None, lon=None, radius_m=2000, la_name=None):
    """Get nursery Ofsted rating distribution.

    Returns:
        Dict with total, outstanding, good, requires_improvement, inadequate, met, not_inspected.
    """
    params = [f"radius_m={radius_m}"]
    if lat is not None and lon is not None:
        params.append(f"lat={lat}&lon={lon}")
    if la_name:
        params.append(f"la_name={urllib.parse.quote(la_name)}")
    path = "/nurseries/summary?" + "&".join(params)
    return _request("GET", path, timeout=15)


def catchment_check(lat, lon, phase=None, limit=20):
    """Which schools likely serve this location?

    Returns:
        Dict with schools (ranked by admission_probability), lsoa_code.
    """
    path = f"/schools/catchment-check?lat={lat}&lon={lon}&limit={limit}"
    if phase:
        path += f"&phase={urllib.parse.quote(phase)}"
    return _request("GET", path, timeout=15)


def school_catchment(urn):
    """Get catchment probability map for a school.

    Returns:
        Dict with urn, catchment (list of {lsoa_code, distance_m, admission_probability}).
    """
    return _request("GET", f"/schools/{urn}/catchment", timeout=15)


def feeder_schools(urn):
    """Get inferred feeder/destination schools.

    Returns:
        Dict with urn + feeder_primaries or destination_secondaries.
    """
    return _request("GET", f"/schools/{urn}/feeders", timeout=15)


def league_table(lad_code=None, phase="Secondary", sort_by="progress_8", limit=50):
    """Get a league table of schools.

    Returns:
        Dict with schools list, sort_by, phase.
    """
    params = [f"phase={urllib.parse.quote(phase)}", f"sort_by={sort_by}", f"limit={limit}"]
    if lad_code:
        params.append(f"lad_code={urllib.parse.quote(lad_code)}")
    path = "/schools/league-table?" + "&".join(params)
    return _request("GET", path, timeout=15)


def sen2_la_stats(la_code):
    """Get SEN2 EHCP statistics for a local authority.

    Args:
        la_code: ONS E-code (e.g. E09000008) or DfE 3-digit code (e.g. 306).

    Returns:
        Dict with timeliness, refusal rates, tribunal counts, caseload,
        placement breakdown, primary need breakdown, and national averages.
    """
    return _request("GET", f"/schools/sen2/{urllib.parse.quote(str(la_code))}", timeout=15)
