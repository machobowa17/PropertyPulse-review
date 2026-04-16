"""Shared helpers for tab services. Bible Part 6 response shape."""
import hashlib
import json as _json
from copy import deepcopy

from app.constants import TABLE_NAMES
from app.metric_registry import METRIC_REGISTRY, SECTION_IDS


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
    # Guard against type mismatches (e.g. str vs float from categorical metrics)
    try:
        if local < parent:
            return "lower_than_parent"
        elif local > parent:
            return "higher_than_parent"
        return "equal_to_parent"
    except TypeError:
        return None


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


# ---------------------------------------------------------------------------
# Nested metric contract — enriches flat metric dicts for the frontend.
# Called as a post-processing step at the router level (area_tabs.py).
# Tab services remain unchanged — they still emit flat dicts via metric().
# ---------------------------------------------------------------------------

def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _safe_abs_diff(local_value, parent_value):
    if _is_number(local_value) and _is_number(parent_value):
        return round(local_value - parent_value, 2)
    return None


def _safe_pct_diff(local_value, parent_value):
    if _is_number(local_value) and _is_number(parent_value) and parent_value not in (0, 0.0):
        return round(((local_value - parent_value) / parent_value) * 100, 1)
    return None


def _build_trend_block(details: dict | None, trend_status: str) -> dict:
    """Build the nested trend sub-object from flat details."""
    if not details:
        return {
            "status": trend_status,
            "window_label": None,
            "direction": None,
            "value": None,
            "series": None,
            "parent_series": None,
            "trend_summary": None,
        }

    trend_value = None
    trend_window_label = None
    trend_direction = None
    trend_series = None
    trend_parent_series = None
    trend_summary = None

    raw_trend = details.get("trend")
    if isinstance(raw_trend, dict):
        trend_value = raw_trend.get("value", raw_trend.get("pct"))
        trend_window_label = raw_trend.get("window_label") or raw_trend.get("period") or raw_trend.get("label")
        trend_direction = raw_trend.get("direction")
        trend_series = raw_trend.get("series")
        trend_parent_series = raw_trend.get("parent_series")
        trend_summary = raw_trend.get("summary")
    elif raw_trend is not None:
        trend_value = raw_trend

    if trend_value is None and details.get("yoy_change_pct") is not None:
        trend_value = details["yoy_change_pct"]
        trend_window_label = trend_window_label or "Year-on-year"

    # Infer direction from value
    if trend_value is not None and not trend_direction and _is_number(trend_value):
        if trend_value > 0:
            trend_direction = "up"
        elif trend_value < 0:
            trend_direction = "down"
        else:
            trend_direction = "flat"

    # Reconcile trend_status with actual data
    effective_status = trend_status
    if trend_value is None and effective_status == "trended":
        effective_status = "not_modelled_yet"
    elif trend_value is not None and effective_status in ("not_modelled_yet", "no_history"):
        effective_status = "trended"

    return {
        "status": effective_status,
        "window_label": trend_window_label,
        "direction": trend_direction,
        "value": trend_value,
        "series": trend_series,
        "parent_series": trend_parent_series,
        "trend_summary": trend_summary,
    }


def _build_capsule(details: dict | None) -> dict | None:
    """Build capsule sub-object from details text fields."""
    if not details:
        return None

    text = None
    for key in ("capsule_text", "summary_note", "context_note", "method_note"):
        val = details.get(key)
        if isinstance(val, str) and val.strip():
            text = val.strip()
            break

    tone = None
    raw_tone = details.get("capsule_tone")
    if isinstance(raw_tone, str) and raw_tone.strip() and raw_tone.strip() != "neutral":
        tone = raw_tone.strip()

    if text is None and tone is None:
        return None

    capsule = {}
    if text is not None:
        capsule["text"] = text
    if tone is not None:
        capsule["tone"] = tone
    return capsule


def build_metric_contract(flat_metric: dict, parent_name: str | None = None) -> dict:
    """Enrich a flat metric dict into the nested Metric contract.

    Takes the output of metric() and adds nested sub-objects:
    - registry: static metadata from METRIC_REGISTRY
    - headline: value + unit + value_type
    - comparison: status + value + flag + diff + scope_label
    - trend: status + direction + value + series
    - capsule: optional text + tone
    - map_binding: type extracted from binding string
    - quality_flags: list of quality caveats

    The flat top-level fields are PRESERVED for backward compatibility.
    Frontend can migrate gradually from flat to nested access.
    """
    mid = flat_metric.get("id", "")
    reg = METRIC_REGISTRY.get(mid, {})
    details = flat_metric.get("details") or {}
    local_value = flat_metric.get("local_value")
    parent_value = flat_metric.get("parent_value")
    unit = flat_metric.get("unit", "")
    comp_flag = flat_metric.get("comparison_flag")
    comp_status = flat_metric.get("comparison_status", "not_modelled_yet")
    trend_status = flat_metric.get("trend_status", "not_modelled_yet")
    interp_dir = flat_metric.get("interpretation_direction", reg.get("interpretation_direction", "neutral"))

    # Build quality_flags list
    quality_flags = []
    qn = reg.get("quality_notes")
    if isinstance(qn, str) and qn:
        quality_flags.append(qn)
    elif isinstance(qn, list):
        quality_flags.extend(qn)
    for note_key in ("data_note", "data_unavailable_note"):
        note_val = details.get(note_key)
        if isinstance(note_val, str) and note_val and note_val not in quality_flags:
            quality_flags.append(note_val)

    # Extract map_binding type (e.g. "area_layer:choropleth_avg_price" → "area_layer")
    raw_binding = flat_metric.get("map_binding", reg.get("map_binding", "none"))
    binding_type = raw_binding.split(":")[0] if ":" in raw_binding else raw_binding

    # Determine scope_label for comparison
    scope_label = details.get("comparison_scope_label") or details.get("parent_name") or parent_name

    # Build the enriched contract — flat fields preserved, nested added
    contract = dict(flat_metric)  # shallow copy of all flat fields

    # Nested sub-objects
    contract["registry"] = {
        "metric_id": mid,
        "section_id": reg.get("section_id", "general"),
        "headline_label": reg.get("label", flat_metric.get("name", mid)),
        "short_label": reg.get("short_label", flat_metric.get("name", mid)),
        "description": reg.get("description", ""),
        "decision_question": reg.get("decision_question", ""),
        "display_priority": reg.get("sort_priority", 99),
        "map_binding_type": binding_type,
        "source_refresh_profile": "periodic",
        "quality_notes": quality_flags,
        "comparison_capability": "comparable" if reg.get("supports_parent", True) else "not_comparable",
        "trend_capability": "trended" if reg.get("supports_trend", False) else "not_modelled_yet",
        "interpretation_direction": interp_dir,
        "supports_persona_rendering": reg.get("status") == "core",
        "value_type": reg.get("value_type", "scalar"),
    }

    contract["headline"] = {
        "value": local_value,
        "unit": unit,
        "value_type": reg.get("value_type", "scalar"),
    }

    contract["comparison"] = {
        "status": comp_status,
        "value": parent_value,
        "scope_label": scope_label,
        "difference_abs": _safe_abs_diff(local_value, parent_value),
        "difference_pct": _safe_pct_diff(local_value, parent_value),
        "interpretation_direction": interp_dir,
        "comparison_flag": comp_flag,
    }

    contract["trend"] = _build_trend_block(details, trend_status)

    capsule = _build_capsule(details)
    contract["capsule"] = capsule

    contract["map_binding"] = {"type": binding_type} if binding_type != "none" else None

    contract["quality_flags"] = quality_flags

    return contract


def enrich_metrics(flat_metrics: list[dict], parent_name: str | None = None) -> list[dict]:
    """Post-process a list of flat metric dicts into nested contracts.

    Called at the router level (area_tabs.py, report.py) after tab services
    return their flat metric lists.
    """
    return [build_metric_contract(m, parent_name=parent_name) for m in flat_metrics]


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
    entity_type: str | None = None,
    entity_name: str | None = None,
    query_text: str | None = None,
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
    # Escalate to same-region LADs so the benchmark is meaningful without scanning all 300+.
    county_name_kwarg = expand_kwargs.get("county_name")
    if county_name_kwarg and parent_name and parent_name.lower() == county_name_kwarg.lower():
        from sqlalchemy import text as sa_text
        region_result = await db.execute(
            sa_text("""
                SELECT DISTINCT lb2.lad_code
                FROM core_lad_boundaries lb1
                JOIN core_lad_boundaries lb2 ON lb2.region_code = lb1.region_code
                WHERE lb1.lad_code = :lad AND lb2.lad_code IS NOT NULL
            """),
            {"lad": primary_lad},
        )
        region_lads = sorted({r["lad_code"] for r in region_result.mappings().all() if r["lad_code"]})
        if len(region_lads) > 1:
            parent_lad_codes = region_lads
            # Fetch region name for display
            rn_result = await db.execute(
                sa_text("SELECT region_name FROM core_lad_boundaries WHERE lad_code = :lad"),
                {"lad": primary_lad},
            )
            rn_row = rn_result.mappings().first()
            parent_name = rn_row["region_name"] if rn_row and rn_row["region_name"] else "England"
        else:
            # Fallback: if region data isn't populated, use all LADs in same country prefix
            country_prefix = primary_lad[0] if primary_lad else "E"
            all_lads_result = await db.execute(
                sa_text("SELECT lad_code FROM core_lad_boundaries WHERE lad_code LIKE :prefix"),
                {"prefix": f"{country_prefix}%"},
            )
            parent_lad_codes = sorted({r["lad_code"] for r in all_lads_result.mappings().all() if r["lad_code"]})
            parent_name = {"E": "England", "W": "Wales", "S": "Scotland"}.get(country_prefix, "England")

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
        # Geo entity metadata (from resolve)
        "entity_type": entity_type,
        "entity_name": entity_name,
        "query_text": query_text,
        "geo": {
            "entity": {"display_name": display_name or entity_name or None},
            "comparison_scope": {"name": parent_name},
        },
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
        fallback_country, _ = infer_country_from_geo_codes(lad_code, fallback="England")
        return [], fallback_country
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
        fallback_country, _ = infer_country_from_geo_codes(lad_code, fallback="England")
        return [], fallback_country
    parent_name = rows[0]["parent_comparison"]
    parent_lad_codes = [r["lad_code"] for r in rows]
    return parent_lad_codes, parent_name
