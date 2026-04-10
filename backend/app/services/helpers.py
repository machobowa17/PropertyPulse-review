"""Shared helpers for tab services. Bible Part 6 response shape."""
import hashlib
import json as _json

from app.constants import TABLE_NAMES
from app.metric_registry import METRIC_REGISTRY


def _normalize_scalar(value, fallback="_"):
    """Return a stable scalar placeholder for cache/session storage."""
    return fallback if value in (None, "") else value


COUNTRY_COVERAGE = {
    "live": ["England"],
    "partial": ["Wales"],
    "planned": ["Scotland"],
    "parked": ["Northern Ireland"],
}

COUNTRY_STATUS = {
    "England": "live",
    "Scotland": "planned",
    "Wales": "partial",
    "Northern Ireland": "parked",
}

COUNTRY_CODE_PREFIXES = {
    "E": "England",
    "S": "Scotland",
    "W": "Wales",
    "N": "Northern Ireland",
}

NATIONAL_PARENT_NAMES = frozenset(COUNTRY_STATUS)


def infer_country_from_geo_codes(*codes, fallback: str = "England") -> tuple[str, str]:
    """Infer country/status from resolved geography codes.

    This is intentionally additive and conservative. Existing England sessions keep
    their current behaviour, while future federated-country rollouts can pass
    Scotland or Northern Ireland coded identifiers through the same canonical geo
    contract before full downstream data coverage is available.
    """
    for raw_code in codes:
        code = str(raw_code).strip().upper() if raw_code not in (None, "") else ""
        if not code or code == "_":
            continue
        country = COUNTRY_CODE_PREFIXES.get(code[:1])
        if country:
            return country, COUNTRY_STATUS.get(country, "live")
    return fallback, COUNTRY_STATUS.get(fallback, "live")


def build_country_metadata(selected_country: str = "England", status: str = "live") -> dict:
    """Return stable country coverage metadata for geo/session contracts.

    The live platform currently treats England as fully live, Wales as partial,
    Scotland as planned, and Northern Ireland as parked. The session contract is
    kept additive so richer country metadata can evolve without breaking existing
    cached sessions or frontend assumptions.
    """
    return {
        "selected": selected_country,
        "status": status,
        "live": COUNTRY_COVERAGE["live"],
        "partial": COUNTRY_COVERAGE["partial"],
        "planned": COUNTRY_COVERAGE["planned"],
        "parked": COUNTRY_COVERAGE["parked"],
    }


def comparison_flag(local, parent):
    """Return comparison_flag per Bible: lower_than_parent / higher_than_parent / equal_to_parent."""
    if local is None or parent is None:
        return None
    if local < parent:
        return "lower_than_parent"
    elif local > parent:
        return "higher_than_parent"
    return "equal_to_parent"


def metric(id: str, name: str, local_value, parent_value, unit: str, details=None):
    """Build a single metric dict matching Bible Section 6.1 response shape.

    Enriches the response with comparison_status, trend_status, and map_binding
    from the formal metric registry (metric_registry.py).
    """
    reg = METRIC_REGISTRY.get(id, {})

    # Comparison status: runtime truth + registry intent
    if parent_value is not None:
        comp_status = "comparable"
    elif not reg.get("supports_parent", True):
        comp_status = "not_comparable"
    else:
        comp_status = "not_modelled_yet"

    # Trend status: check if details contain trend data
    has_trend = bool(details and (
        "trend" in details
        or "yoy_change_pct" in details
        or "nb_trend" in details
    ))
    if has_trend:
        trend_status = "trended"
    elif not reg.get("supports_trend", False):
        trend_status = "no_history"
    else:
        trend_status = "not_modelled_yet"

    return {
        "id": id,
        "name": name,
        "local_value": local_value,
        "parent_value": parent_value,
        "unit": unit,
        "comparison_flag": comparison_flag(local_value, parent_value),
        "comparison_status": comp_status,
        "trend_status": trend_status,
        "map_binding": reg.get("map_binding", "none"),
        "decision_question": reg.get("decision_question"),
        "interpretation_direction": reg.get("interpretation_direction", "neutral"),
        "quality_notes": reg.get("quality_notes"),
        "details": details,
    }


async def get_lsoa_centroid(db, lsoa_code: str):
    """Get lat/lon centroid of an LSOA boundary for spatial queries."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT ST_Y(ST_Centroid(geom)) as lat, ST_X(ST_Centroid(geom)) as lon
            FROM core_lsoa_boundaries WHERE lsoa_code = :lsoa
        """),
        {"lsoa": lsoa_code},
    )
    row = result.mappings().first()
    if row:
        return float(row["lat"]), float(row["lon"])
    return None, None


async def expand_lsoa_codes(
    db,
    lad_code: str,
    ward_code: str,
    lsoa_code: str,
    *,
    postcode_lat: float | None = None,
    postcode_lon: float | None = None,
    county_name: str | None = None,
    place_name: str | None = None,
    place_lad_code: str | None = None,
    place_type: str | None = None,
):
    """Bible Rule 4 — Data Querying Hierarchy.

    Expand search key to all applicable LSOAs and compute area centroid.

    Returns (lsoa_codes, centroid_lat, centroid_lon, search_mode, local_lads)
    where local_lads is the list of LAD codes for LAD-level metric queries.
    """
    from sqlalchemy import text

    # Case 1: Single LSOA (postcode search) — use actual postcode coordinates
    if lsoa_code and lsoa_code != '_':
        if postcode_lat is not None and postcode_lon is not None:
            lat, lon = postcode_lat, postcode_lon
        else:
            lat, lon = await get_lsoa_centroid(db, lsoa_code)
        local_lads = [lad_code] if lad_code and lad_code != '_' else []
        return [lsoa_code], lat, lon, "postcode", local_lads

    # Case 5: Place name — LSOAs from Voronoi mapping tables
    if place_name is not None and place_lad_code is not None:
        use_town = place_type in ('City', 'Town')
        primary = TABLE_NAMES["place_lsoa_mapping_town"] if use_town else TABLE_NAMES["place_lsoa_mapping"]
        fallback = TABLE_NAMES["place_lsoa_mapping"] if use_town else TABLE_NAMES["place_lsoa_mapping_town"]

        result = await db.execute(
            text(f"SELECT lsoa_code FROM {primary} WHERE place_name = :name AND lad_code = :lad"),
            {"name": place_name, "lad": place_lad_code},
        )
        codes = [r["lsoa_code"] for r in result.mappings().all()]
        if not codes:
            result = await db.execute(
                text(f"SELECT lsoa_code FROM {fallback} WHERE place_name = :name AND lad_code = :lad"),
                {"name": place_name, "lad": place_lad_code},
            )
            codes = [r["lsoa_code"] for r in result.mappings().all()]

        # Centroid from core_place_names
        centroid = await db.execute(
            text("""
                SELECT latitude AS lat, longitude AS lon FROM core_place_names
                WHERE place_name = :name AND lad_code = :lad LIMIT 1
            """),
            {"name": place_name, "lad": place_lad_code},
        )
        crow = centroid.mappings().first()
        lat = float(crow["lat"]) if crow and crow["lat"] else None
        lon = float(crow["lon"]) if crow and crow["lon"] else None
        return codes, lat, lon, "area", [place_lad_code]

    # Case 4: County search — all LSOAs across all LADs in the county
    if county_name:
        # LAD codes from authoritative county lookup (not derived from LSOAs)
        lad_result = await db.execute(
            text("SELECT lad_code FROM core_lad_county_lookup WHERE parent_comparison = :county"),
            {"county": county_name},
        )
        county_lads = [r["lad_code"] for r in lad_result.mappings().all()]

        # Use already-fetched county_lads as a bound array so the planner uses
        # idx_postcodes_lad (bitmap index scan) instead of a full seq scan join
        result = await db.execute(
            text("""
                SELECT DISTINCT lsoa_code
                FROM core_postcodes
                WHERE lad_code = ANY(:lad_codes)
                  AND lsoa_code IS NOT NULL
            """),
            {"lad_codes": county_lads},
        )
        codes = [r["lsoa_code"] for r in result.mappings().all()]
        centroid = await db.execute(
            text("""
                SELECT ST_Y(ST_Centroid(geom)) as lat, ST_X(ST_Centroid(geom)) as lon
                FROM core_county_boundaries WHERE county_name = :county
            """),
            {"county": county_name},
        )
        crow = centroid.mappings().first()
        lat = float(crow["lat"]) if crow else None
        lon = float(crow["lon"]) if crow else None
        return codes, lat, lon, "area", county_lads

    # Case 2: Ward-level search — all LSOAs in ward
    if ward_code and ward_code != '_':
        result = await db.execute(
            text("""
                SELECT DISTINCT lsoa_code
                FROM core_postcodes
                WHERE ward_code = :ward
                  AND lsoa_code IS NOT NULL
            """),
            {"ward": ward_code},
        )
        codes = [r["lsoa_code"] for r in result.mappings().all()]
        ward_local_lads = [lad_code] if lad_code and lad_code != '_' else []

        centroid = await db.execute(
            text("""
                SELECT ST_Y(ST_Centroid(geom)) as lat, ST_X(ST_Centroid(geom)) as lon
                FROM core_ward_boundaries WHERE ward_code = :ward
            """),
            {"ward": ward_code},
        )
        crow = centroid.mappings().first()
        if crow and crow["lat"]:
            return codes, float(crow["lat"]), float(crow["lon"]), "area", ward_local_lads

        centroid2 = await db.execute(
            text("""
                SELECT AVG(latitude) as lat, AVG(longitude) as lon
                FROM core_postcodes WHERE ward_code = :ward
            """),
            {"ward": ward_code},
        )
        crow2 = centroid2.mappings().first()
        if crow2 and crow2["lat"]:
            return codes, float(crow2["lat"]), float(crow2["lon"]), "area", ward_local_lads
        return codes, None, None, "area", ward_local_lads

    # Case 3: LAD/borough-level search — all LSOAs in LAD
    lad_local_lads = [lad_code] if lad_code and lad_code != '_' else []
    result = await db.execute(
        text("""
            SELECT DISTINCT lsoa_code
            FROM core_postcodes
            WHERE lad_code = :lad
              AND lsoa_code IS NOT NULL
        """),
        {"lad": lad_code},
    )
    codes = [r["lsoa_code"] for r in result.mappings().all()]

    centroid = await db.execute(
        text("""
            SELECT ST_Y(ST_Centroid(geom)) as lat, ST_X(ST_Centroid(geom)) as lon
            FROM core_lad_boundaries WHERE lad_code = :lad
        """),
        {"lad": lad_code},
    )
    crow = centroid.mappings().first()
    if crow and crow["lat"]:
        return codes, float(crow["lat"]), float(crow["lon"]), "area", lad_local_lads

    centroid2 = await db.execute(
        text("""
            SELECT AVG(latitude) as lat, AVG(longitude) as lon
            FROM core_postcodes WHERE lad_code = :lad
        """),
        {"lad": lad_code},
    )
    crow2 = centroid2.mappings().first()
    if crow2 and crow2["lat"]:
        return codes, float(crow2["lat"]), float(crow2["lon"]), "area", lad_local_lads
    return codes, None, None, "area", lad_local_lads


async def make_lsoa_session(
    db,
    lad_code,
    ward_code,
    lsoa_code,
    *,
    boundary_source: str = "lad",
    boundary_id: str = "",
    postcode_district: str | None = None,
    place_name: str | None = None,
    place_lad_code: str | None = None,
    place_type: str | None = None,
    display_name: str = "",
    display_lad_name: str | None = None,
    **expand_kwargs,
) -> tuple:
    """Call expand_lsoa_codes and store comprehensive session in Redis.

    Returns (lsoa_codes, lat, lon, search_mode, local_lads, session_key).
    The session_key is the single canonical search token — pass it to every
    subsequent data endpoint so they all operate on exactly the same LSOA set
    and share parent comparison data without redundant DB queries.
    """
    # Pass place fields through to expand_lsoa_codes
    if place_name is not None:
        expand_kwargs["place_name"] = place_name
    if place_lad_code is not None:
        expand_kwargs["place_lad_code"] = place_lad_code
    if place_type is not None:
        expand_kwargs["place_type"] = place_type

    lsoa_codes, lat, lon, mode, local_lads = await expand_lsoa_codes(
        db, lad_code, ward_code, lsoa_code, **expand_kwargs
    )

    # Compute parent comparison info once (eliminates 5 redundant DB queries per page load)
    primary_lad = lad_code if lad_code and lad_code != "_" else (local_lads[0] if local_lads else "_")
    parent_lad_codes, parent_name = await get_parent_lad_info(db, primary_lad)

    # County self-comparison fix: when the search IS a county, get_parent_lad_info
    # returns the same county's LADs (county compares to itself → ratio ~1.0x).
    # Escalate to all-England comparison so the benchmark is meaningful.
    county_name_kwarg = expand_kwargs.get("county_name")
    if county_name_kwarg and parent_name and parent_name.lower() == county_name_kwarg.lower():
        from sqlalchemy import text as sa_text
        all_lads_result = await db.execute(
            sa_text("SELECT lad_code FROM core_lad_county_lookup")
        )
        parent_lad_codes = sorted({r["lad_code"] for r in all_lads_result.mappings().all()})
        parent_name = "England"

    # Deterministic session key
    key_parts = {"lad": lad_code, "ward": ward_code, "lsoa": lsoa_code}
    key_parts.update({k: v for k, v in expand_kwargs.items() if v is not None})
    if boundary_source:
        key_parts["boundary_source"] = boundary_source
    if boundary_id:
        key_parts["boundary_id"] = boundary_id
    if postcode_district:
        key_parts["postcode_district"] = postcode_district
    session_key = hashlib.sha256(
        _json.dumps(key_parts, sort_keys=True).encode()
    ).hexdigest()[:20]

    # Build breadcrumbs: [search_label, LAD_name, parent_name]
    breadcrumbs = [display_name] if display_name else []
    if display_lad_name and display_lad_name.lower() != (display_name or "").lower():
        breadcrumbs.append(display_lad_name)
    if parent_name and parent_name not in breadcrumbs:
        breadcrumbs.append(parent_name)

    from app.cache import cache_set
    await cache_set(f"lsoa_sess:{session_key}", {
        # Core LSOA expansion results
        "lsoa_codes": lsoa_codes,
        "lat": lat,
        "lon": lon,
        "search_mode": mode,
        "local_lads": local_lads,
        # Geo codes
        "lad_code": lad_code or "_",
        "ward_code": ward_code or "_",
        "lsoa_code": lsoa_code or "_",
        # Parent comparison (computed once, used by all 5 tab handlers)
        "parent_lad_codes": parent_lad_codes,
        "parent_name": parent_name,
        # Boundary info
        "boundary_source": boundary_source,
        "boundary_id": boundary_id,
        # Postcode-specific
        "postcode_district": postcode_district,
        # Place-specific (for boundary reconstruction)
        "place_name": place_name,
        "place_lad_code": place_lad_code,
        "place_type": place_type,
        # Display context
        "display_name": display_name,
        "display_breadcrumbs": breadcrumbs,
    }, ttl=86400)

    return lsoa_codes, lat, lon, mode, local_lads, session_key


async def get_lsoa_session(session_key: str) -> dict | None:
    """Retrieve the full session dict from Redis, or None if expired/missing."""
    from app.cache import cache_get
    data = await cache_get(f"lsoa_sess:{session_key}")
    if not data or "lsoa_codes" not in data:
        return None
    return data


async def get_parent_lad_info(db, lad_code: str):
    """Get all LAD codes sharing the same parent_comparison, plus the parent name.

    Returns (parent_lad_codes, parent_name).
    """
    from sqlalchemy import text
    if not lad_code or lad_code == "_":
        return [], "England"
    result = await db.execute(
        text("""
            SELECT l2.lad_code, l1.parent_comparison
            FROM core_lad_county_lookup l1
            JOIN core_lad_county_lookup l2 ON l2.parent_comparison = l1.parent_comparison
            WHERE l1.lad_code = :lad
        """),
        {"lad": lad_code},
    )
    rows = result.mappings().all()
    if not rows:
        return [], "England"
    parent_name = rows[0]["parent_comparison"]
    parent_lad_codes = [r["lad_code"] for r in rows]
    return parent_lad_codes, parent_name
