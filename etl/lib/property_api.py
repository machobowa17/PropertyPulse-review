"""
Shared Property API client.

Single source of truth for calling the self-hosted Property API on Hetzner
and returning parsed results for the EC2 backend to consume.

Follows the exact same pattern as etl/lib/motis.py.
"""

import json
import logging
import os
import ssl
import urllib.request

logger = logging.getLogger(__name__)

PROPERTY_API_BASE_URL = os.environ.get(
    "PROPERTY_API_BASE_URL", "http://128.140.103.160:8082"
).rstrip("/")

# Reusable SSL context (no cert verification for internal traffic)
_ssl_ctx = ssl._create_unverified_context()


def _request(method, path, body=None, timeout=30):
    """Make an HTTP request to the Property API.

    Args:
        method: HTTP method (GET or POST).
        path: URL path (e.g., "/transactions/aggregate").
        body: Dict to JSON-encode for POST requests.
        timeout: HTTP timeout in seconds.

    Returns:
        Parsed JSON response, or None on failure.
    """
    url = f"{PROPERTY_API_BASE_URL}{path}"
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
        logger.warning("Property API HTTP %d for %s %s", e.code, method, path)
        return None
    except urllib.error.URLError as e:
        logger.warning("Property API connection error for %s: %s", path, e.reason)
        return None
    except Exception as e:
        logger.warning("Property API unexpected error for %s: %s", path, e)
        return None


def aggregate_transactions(lsoa_codes, price_types=None):
    """Fetch all transaction-based aggregations for a set of LSOA codes.

    This replaces ~10 separate SQL queries that tab_property.py previously
    ran against core_property_transactions on EC2.

    Args:
        lsoa_codes: List of LSOA code strings.
        price_types: List of property type codes (default: D,S,T,F).

    Returns:
        Dict with keys: core_recent, by_type, ppsm, prior_avg, prior_txn,
        nb_trend, price_trend, price_spread.
        Or None if the API call fails.
    """
    body = {"lsoa_codes": lsoa_codes}
    if price_types:
        body["price_types"] = price_types
    return _request("POST", "/transactions/aggregate", body, timeout=60)


def aggregate_transactions_by_lad(lad_codes, price_types=None):
    """Fetch pre-aggregated transaction stats by LAD code.

    Fast path for LAD/county searches — reads from materialized views
    instead of scanning 31M gold rows. Response shape is identical to
    aggregate_transactions() so downstream code needs no changes.

    Args:
        lad_codes: List of LAD code strings (e.g. ["E07000207"]).
        price_types: List of property type codes (default: D,S,T,F).

    Returns:
        Dict with keys: core_recent, by_type, ppsm, prior_avg, prior_txn,
        nb_trend, price_trend, price_spread.
        Or None if the API call fails.
    """
    body = {"lad_codes": lad_codes}
    if price_types:
        body["price_types"] = price_types
    return _request("POST", "/transactions/aggregate-by-lad", body, timeout=10)


def parent_aggregate_transactions(lsoa_codes, price_types=None):
    """Fetch parent-area tenure and new-build aggregations.

    Args:
        lsoa_codes: List of LSOA codes for the parent area.
        price_types: List of property type codes.

    Returns:
        Dict with keys: tenure, newbuild. Or None on failure.
    """
    body = {"lsoa_codes": lsoa_codes}
    if price_types:
        body["price_types"] = price_types
    return _request("POST", "/transactions/parent-aggregate", body, timeout=60)


def recent_transactions(lsoa_codes, limit=50, offset=0, property_type=None):
    """Fetch individual recent transactions for detail views.

    Args:
        lsoa_codes: List of LSOA code strings.
        limit: Max rows to return.
        offset: Pagination offset.
        property_type: Optional filter (D, S, T, F).

    Returns:
        Dict with keys: rows, total. Or None on failure.
    """
    codes_str = ",".join(lsoa_codes)
    path = f"/transactions/recent?lsoa_codes={codes_str}&limit={limit}&offset={offset}"
    if property_type:
        path += f"&property_type={property_type}"
    return _request("GET", path, timeout=30)


def transactions_by_uprn(uprn):
    """Fetch all transactions for a given UPRN (previous sales).

    Args:
        uprn: Integer UPRN.

    Returns:
        List of transaction dicts, or None on failure.
    """
    return _request("GET", f"/transactions/by-uprn/{uprn}", timeout=15)


def transactions_by_address(postcode, paon=None, saon=None, street=None):
    """Fetch transactions matching an address (fallback when no UPRN).

    Args:
        postcode: Postcode string.
        paon: Primary addressable object name.
        saon: Secondary addressable object name.
        street: Street name.

    Returns:
        List of transaction dicts, or None on failure.
    """
    path = f"/transactions/by-address?postcode={urllib.parse.quote(postcode)}"
    if paon:
        path += f"&paon={urllib.parse.quote(paon)}"
    if saon:
        path += f"&saon={urllib.parse.quote(saon)}"
    if street:
        path += f"&street={urllib.parse.quote(street)}"
    return _request("GET", path, timeout=15)


def epc_by_uprn(uprn):
    """Fetch full 93-column EPC data for a UPRN.

    Args:
        uprn: Integer UPRN.

    Returns:
        List of EPC record dicts, or None on failure.
    """
    return _request("GET", f"/transactions/epc/{uprn}", timeout=15)


def epc_by_postcode(postcode, limit=20):
    """Fetch EPC records for a postcode.

    Args:
        postcode: Postcode string.
        limit: Max rows.

    Returns:
        List of EPC record dicts, or None on failure.
    """
    return _request("GET", f"/transactions/epc/by-postcode/{urllib.parse.quote(postcode)}?limit={limit}", timeout=15)
