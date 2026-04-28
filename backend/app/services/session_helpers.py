"""
backend/app/services/session_helpers.py — shared session-unpacking helpers

Extracted from area.py so that report.py, commute.py, and any future
routers can reuse the same session → field accessors without duplicating code.
"""

import hashlib
import json

from app.errors import http_error
from app.services.helpers import get_lsoa_session


# ---------------------------------------------------------------------------
# Session field accessors
# ---------------------------------------------------------------------------

def geo(sess: dict) -> dict:
    return sess.get("geo") or {}


def geo_entity(sess: dict) -> dict:
    return geo(sess).get("entity") or {}


def geo_local_scope(sess: dict) -> dict:
    return geo(sess).get("local_scope") or {}


def geo_comparison_scope(sess: dict) -> dict:
    return geo(sess).get("comparison_scope") or {}


def geo_display_geometry(sess: dict) -> dict:
    return geo(sess).get("display_geometry") or {}


def session_centroid(sess: dict) -> tuple:
    centroid = geo(sess).get("centroid") or {}
    return centroid.get("lat", sess.get("lat")), centroid.get("lon", sess.get("lon"))


def session_boundary_source(sess: dict) -> str:
    geom = geo_display_geometry(sess)
    return geom.get("type") or sess.get("boundary_source", "lad")


def session_boundary_id(sess: dict) -> str:
    geom = geo_display_geometry(sess)
    return geom.get("id") or sess.get("boundary_id", "")


def session_local_scope_type(sess: dict) -> str:
    local_scope = geo_local_scope(sess)
    return local_scope.get("type") or sess.get("local_scope_type") or ("area" if sess.get("search_mode") == "area" else "lsoa")


def session_entity_name(sess: dict) -> str:
    entity = geo_entity(sess)
    return entity.get("name") or sess.get("query") or session_boundary_id(sess) or "Selected area"


def session_parent_name(sess: dict) -> str:
    comparison = geo_comparison_scope(sess)
    return comparison.get("name") or sess.get("comparison_scope_name") or sess.get("parent_name", "England")


def session_parent_lads(sess: dict) -> list:
    comparison = geo_comparison_scope(sess)
    return comparison.get("lad_codes") or sess.get("parent_lad_codes", [])


# ---------------------------------------------------------------------------
# Session validation
# ---------------------------------------------------------------------------

async def require_session(session_key: str | None) -> dict:
    """Validate and retrieve session, raising on missing/expired."""
    if not session_key:
        raise http_error(400, "SESSION_KEY_REQUIRED", "session_key is required")
    sess = await get_lsoa_session(session_key)
    if not sess:
        raise http_error(410, "SESSION_EXPIRED", "Session expired — please search again")
    return sess


# ---------------------------------------------------------------------------
# Cache key builder
# ---------------------------------------------------------------------------

def area_scope_cache_key(sess: dict, tab: str, cache_version: str = "v26") -> str:
    local_scope = geo_local_scope(sess)
    comparison_scope = geo_comparison_scope(sess)
    display_geometry = geo_display_geometry(sess)
    lsoa_codes = sorted(sess.get("lsoa_codes") or [])
    scope_payload = {
        "tab": tab,
        "search_mode": sess.get("search_mode"),
        "local_scope": {
            "type": local_scope.get("type") or session_local_scope_type(sess),
            "id": local_scope.get("id") or sess.get("local_scope_id") or session_boundary_id(sess),
            "lad_codes": sorted(local_scope.get("lad_codes") or sess.get("local_lads") or []),
        },
        "comparison_scope": {
            "id": comparison_scope.get("id") or session_parent_name(sess),
            "lad_codes": sorted(comparison_scope.get("lad_codes") or session_parent_lads(sess)),
        },
        "display_geometry": {
            "type": display_geometry.get("type") or session_boundary_source(sess),
            "id": display_geometry.get("id") or session_boundary_id(sess),
        },
        "lsoa_codes_hash": hashlib.sha256(json.dumps(lsoa_codes).encode()).hexdigest()[:16],
    }
    scope_hash = hashlib.sha256(json.dumps(scope_payload, sort_keys=True).encode()).hexdigest()[:24]
    return f"area_scope:{cache_version}:{scope_hash}"
