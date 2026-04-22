"""
PropertyPulse ETL — Shared Constants

Single source of truth for all values that appear in both the ETL pipeline
and the API layer. Import from here rather than defining literals inline.

Rules:
- Never hardcode property types, EPC bands, amenity names, LAD codes, etc.
  in any ETL script or API service. Always import from this module.
- When a value changes (e.g. a new property type is added), update it here
  and it will propagate everywhere automatically.
- This module has no external dependencies — it is pure Python constants.
"""

# ---------------------------------------------------------------------------
# Property types (Land Registry codes)
# ---------------------------------------------------------------------------

# All valid property type codes in LR Price Paid data
PROPERTY_TYPES = ("D", "S", "T", "F", "O")

# Codes used for price calculations (excludes O = Other/commercial which skews averages)
PRICE_TYPES = ("D", "S", "T", "F")

# Human-readable labels for each property type code
TYPE_NAMES = {
    "D": "Detached",
    "S": "Semi-Detached",
    "T": "Terraced",
    "F": "Flat",
    "O": "Other",
}

# Tenure codes (Land Registry duration field)
TENURE_NAMES = {
    "F": "Freehold",
    "L": "Leasehold",
    "U": "Unknown",
}

# Old/new build codes
OLD_NEW_NAMES = {
    "Y": "New Build",
    "N": "Existing",
}

# ---------------------------------------------------------------------------
# EPC rating bands
# ---------------------------------------------------------------------------

EPC_RATING_BANDS = ("A", "B", "C", "D", "E", "F", "G")

# Midpoint energy efficiency score for each EPC band (used in weighted averages)
EPC_BAND_SCORES = {
    "A": 92,
    "B": 81,
    "C": 69,
    "D": 55,
    "E": 39,
    "F": 21,
    "G": 1,
}

# ---------------------------------------------------------------------------
# Greater Manchester Police LAD codes
# (Used to identify areas not in national crime bulk download)
# ---------------------------------------------------------------------------

GMP_LAD_CODES = frozenset({
    "E08000001",  # Bolton
    "E08000002",  # Bury
    "E08000003",  # Manchester
    "E08000004",  # Oldham
    "E08000005",  # Rochdale
    "E08000006",  # Salford
    "E08000007",  # Stockport
    "E08000008",  # Tameside
    "E08000009",  # Trafford
    "E08000010",  # Wigan
})

# ---------------------------------------------------------------------------
# OSM amenity types (Bible Section 3.1)
# ---------------------------------------------------------------------------

# Ordered list used for display and query filtering
AMENITY_TYPES = [
    "supermarket",
    "cafe",
    "restaurant",
    "pub",
    "gym",
    "park",
    "pharmacy",
    "dentist",
    "hospital",
    "doctors",
]

# OSM tag mapping for each amenity type: (amenity_name, osm_key, osm_value)
AMENITY_OSM_TAGS = [
    ("supermarket", "shop",     "supermarket"),
    ("cafe",        "amenity",  "cafe"),
    ("restaurant",  "amenity",  "restaurant"),
    ("pub",         "amenity",  "pub"),
    ("gym",         "leisure",  "fitness_centre"),
    ("park",        "leisure",  "park"),
    ("pharmacy",    "amenity",  "pharmacy"),
    ("dentist",     "amenity",  "dentist"),
    ("hospital",    "amenity",  "hospital"),
    ("doctors",     "amenity",  "doctors"),
]

# Country rollout metadata for federated geography support
#
# Keep this block as the single source of truth for country coverage assumptions.
# Older tuple constants are preserved below for backwards compatibility while the
# rest of the ETL and API layers migrate to the richer metadata model.
COUNTRY_GEOGRAPHY = {
    "E": {
        "name": "England",
        "status": "live",
        "overpass_bbox": "49.9,-6.5,55.9,2.0",
        "has_regions": True,
        "has_counties": True,
        "default_parent_name": "England",
    },
    "S": {
        "name": "Scotland",
        "status": "planned",
        "overpass_bbox": "54.6,-8.0,60.9,-0.5",
        "has_regions": False,
        "has_counties": False,
        "default_parent_name": "Scotland",
    },
    "W": {
        "name": "Wales",
        "status": "partial",
        "overpass_bbox": "51.3,-5.7,53.6,-2.5",
        "has_regions": False,
        "has_counties": False,
        "default_parent_name": "Wales",
    },
    "N": {
        "name": "Northern Ireland",
        "status": "parked",
        "overpass_bbox": None,
        "has_regions": False,
        "has_counties": False,
        "default_parent_name": "Northern Ireland",
    },
}

LIVE_COUNTRY_PREFIXES = tuple(
    prefix for prefix, meta in COUNTRY_GEOGRAPHY.items() if meta["status"] == "live"
)
PARTIAL_COUNTRY_PREFIXES = tuple(
    prefix for prefix, meta in COUNTRY_GEOGRAPHY.items() if meta["status"] == "partial"
)
PLANNED_COUNTRY_PREFIXES = tuple(
    prefix for prefix, meta in COUNTRY_GEOGRAPHY.items() if meta["status"] == "planned"
)
PARKED_COUNTRY_PREFIXES = tuple(
    prefix for prefix, meta in COUNTRY_GEOGRAPHY.items() if meta["status"] == "parked"
)
SUPPORTED_COUNTRY_PREFIXES = tuple(
    prefix for prefix, meta in COUNTRY_GEOGRAPHY.items() if meta["status"] in {"live", "partial", "planned"}
)

# Supported LAD / council-area code families by country prefix.
# Keep this aligned with ONS UK local-authority district and council-area code families.
SUPPORTED_LAD_CODE_PREFIXES_BY_COUNTRY = {
    "E": ("E06", "E07", "E08", "E09"),
    "W": ("W06",),
    "S": ("S12",),
}
SUPPORTED_LAD_CODE_PREFIXES = tuple(
    prefix
    for country_prefix in SUPPORTED_COUNTRY_PREFIXES
    for prefix in SUPPORTED_LAD_CODE_PREFIXES_BY_COUNTRY.get(country_prefix, ())
)

LIVE_COUNTRIES = tuple(COUNTRY_GEOGRAPHY[prefix]["name"] for prefix in LIVE_COUNTRY_PREFIXES)
PARTIAL_COUNTRIES = tuple(COUNTRY_GEOGRAPHY[prefix]["name"] for prefix in PARTIAL_COUNTRY_PREFIXES)
PLANNED_COUNTRIES = tuple(COUNTRY_GEOGRAPHY[prefix]["name"] for prefix in PLANNED_COUNTRY_PREFIXES)
PARKED_COUNTRIES = tuple(COUNTRY_GEOGRAPHY[prefix]["name"] for prefix in PARKED_COUNTRY_PREFIXES)

COUNTRY_NAME_BY_PREFIX = {
    prefix: meta["name"]
    for prefix, meta in COUNTRY_GEOGRAPHY.items()
}

COUNTRY_PREFIX_BY_NAME = {
    meta["name"]: prefix
    for prefix, meta in COUNTRY_GEOGRAPHY.items()
}

COUNTRY_STATUS_BY_PREFIX = {
    prefix: meta["status"]
    for prefix, meta in COUNTRY_GEOGRAPHY.items()
}

COUNTRY_DEFAULT_PARENT_BY_PREFIX = {
    prefix: meta["default_parent_name"]
    for prefix, meta in COUNTRY_GEOGRAPHY.items()
}

# Backwards-compatible named bounding boxes used by existing ETL modules.
ENGLAND_BBOX = COUNTRY_GEOGRAPHY["E"]["overpass_bbox"]
SCOTLAND_BBOX = COUNTRY_GEOGRAPHY["S"]["overpass_bbox"]
GB_BBOX = "49.9,-8.0,60.9,2.0"


def country_prefix_from_code(code: str | None) -> str | None:
    if not code:
        return None
    prefix = str(code).strip()[:1].upper()
    return prefix or None


def country_name_from_code(code: str | None, default: str | None = None) -> str | None:
    prefix = country_prefix_from_code(code)
    if not prefix:
        return default
    return COUNTRY_NAME_BY_PREFIX.get(prefix, default)


def country_meta(prefix_or_code: str | None) -> dict | None:
    prefix = country_prefix_from_code(prefix_or_code)
    if not prefix:
        return None
    return COUNTRY_GEOGRAPHY.get(prefix)


def is_supported_country_prefix(prefix_or_code: str | None) -> bool:
    prefix = country_prefix_from_code(prefix_or_code)
    return bool(prefix and prefix in SUPPORTED_COUNTRY_PREFIXES)


def supported_overpass_bboxes() -> tuple[str, ...]:
    return tuple(
        meta["overpass_bbox"]
        for prefix, meta in COUNTRY_GEOGRAPHY.items()
        if prefix in SUPPORTED_COUNTRY_PREFIXES and meta.get("overpass_bbox")
    )


def supported_country_names() -> tuple[str, ...]:
    return tuple(COUNTRY_NAME_BY_PREFIX[prefix] for prefix in SUPPORTED_COUNTRY_PREFIXES)


def partial_country_names() -> tuple[str, ...]:
    return tuple(COUNTRY_NAME_BY_PREFIX[prefix] for prefix in PARTIAL_COUNTRY_PREFIXES)


def planned_country_names() -> tuple[str, ...]:
    return tuple(COUNTRY_NAME_BY_PREFIX[prefix] for prefix in PLANNED_COUNTRY_PREFIXES)


def parked_country_names() -> tuple[str, ...]:
    return tuple(COUNTRY_NAME_BY_PREFIX[prefix] for prefix in PARKED_COUNTRY_PREFIXES)


def live_country_names() -> tuple[str, ...]:
    return tuple(COUNTRY_NAME_BY_PREFIX[prefix] for prefix in LIVE_COUNTRY_PREFIXES)


def countries_with_regions() -> tuple[str, ...]:
    return tuple(
        prefix
        for prefix, meta in COUNTRY_GEOGRAPHY.items()
        if prefix in SUPPORTED_COUNTRY_PREFIXES and meta.get("has_regions")
    )


def countries_with_counties() -> tuple[str, ...]:
    return tuple(
        prefix
        for prefix, meta in COUNTRY_GEOGRAPHY.items()
        if prefix in SUPPORTED_COUNTRY_PREFIXES and meta.get("has_counties")
    )


def default_parent_name_for_country(prefix_or_code: str | None, fallback: str | None = None) -> str | None:
    prefix = country_prefix_from_code(prefix_or_code)
    if not prefix:
        return fallback
    return COUNTRY_DEFAULT_PARENT_BY_PREFIX.get(prefix, fallback)


def country_status(prefix_or_code: str | None, default: str | None = None) -> str | None:
    prefix = country_prefix_from_code(prefix_or_code)
    if not prefix:
        return default
    return COUNTRY_STATUS_BY_PREFIX.get(prefix, default)


def supported_country_prefixes() -> tuple[str, ...]:
    return SUPPORTED_COUNTRY_PREFIXES


def supported_lad_code_prefixes() -> tuple[str, ...]:
    return SUPPORTED_LAD_CODE_PREFIXES


def is_supported_lad_code(code: str | None) -> bool:
    if not code:
        return False
    normalized = str(code).strip().upper()
    return any(normalized.startswith(prefix) for prefix in SUPPORTED_LAD_CODE_PREFIXES)


def partial_country_prefixes() -> tuple[str, ...]:
    return PARTIAL_COUNTRY_PREFIXES


def planned_country_prefixes() -> tuple[str, ...]:
    return PLANNED_COUNTRY_PREFIXES


def live_country_prefixes() -> tuple[str, ...]:
    return LIVE_COUNTRY_PREFIXES


def parked_country_prefixes() -> tuple[str, ...]:
    return PARKED_COUNTRY_PREFIXES


def country_prefixes_for_status(*statuses: str) -> tuple[str, ...]:
    allowed = {status for status in statuses if status}
    return tuple(
        prefix
        for prefix, meta in COUNTRY_GEOGRAPHY.items()
        if meta["status"] in allowed
    )


def country_names_for_status(*statuses: str) -> tuple[str, ...]:
    return tuple(
        COUNTRY_NAME_BY_PREFIX[prefix]
        for prefix in country_prefixes_for_status(*statuses)
    )


def country_names_with_overpass_bbox() -> tuple[str, ...]:
    return tuple(
        meta["name"]
        for prefix, meta in COUNTRY_GEOGRAPHY.items()
        if prefix in SUPPORTED_COUNTRY_PREFIXES and meta.get("overpass_bbox")
    )


def is_live_country_prefix(prefix_or_code: str | None) -> bool:
    prefix = country_prefix_from_code(prefix_or_code)
    return bool(prefix and prefix in LIVE_COUNTRY_PREFIXES)


def is_partial_country_prefix(prefix_or_code: str | None) -> bool:
    prefix = country_prefix_from_code(prefix_or_code)
    return bool(prefix and prefix in PARTIAL_COUNTRY_PREFIXES)


def is_planned_country_prefix(prefix_or_code: str | None) -> bool:
    prefix = country_prefix_from_code(prefix_or_code)
    return bool(prefix and prefix in PLANNED_COUNTRY_PREFIXES)


def is_parked_country_prefix(prefix_or_code: str | None) -> bool:
    prefix = country_prefix_from_code(prefix_or_code)
    return bool(prefix and prefix in PARKED_COUNTRY_PREFIXES)


def all_country_prefixes() -> tuple[str, ...]:
    return tuple(COUNTRY_GEOGRAPHY.keys())


def overpass_bbox_for_country(prefix_or_code: str | None, default: str | None = None) -> str | None:
    meta = country_meta(prefix_or_code)
    if not meta:
        return default
    return meta.get("overpass_bbox") or default


def bbox_contains_point(bbox: str | None, lat: float | None, lon: float | None) -> bool:
    if not bbox or lat is None or lon is None:
        return False
    try:
        south, west, north, east = [float(part) for part in bbox.split(",")]
    except (TypeError, ValueError):
        return False
    return south <= lat <= north and west <= lon <= east


def point_in_supported_country_bbox(lat: float | None, lon: float | None) -> bool:
    return any(
        bbox_contains_point(meta.get("overpass_bbox"), lat, lon)
        for prefix, meta in COUNTRY_GEOGRAPHY.items()
        if prefix in SUPPORTED_COUNTRY_PREFIXES
    )

# ---------------------------------------------------------------------------
# Core table names
# ---------------------------------------------------------------------------

# All core_ table names used across ETL and API.
# Import TABLE_NAMES["epc_domestic"] rather than writing "core_epc_domestic" inline.
TABLE_NAMES = {
    "postcodes":                "core_postcodes",
    "lsoa_boundaries":          "core_lsoa_boundaries",
    "ward_boundaries":          "core_ward_boundaries",
    "lad_boundaries":           "core_lad_boundaries",
    "county_boundaries":        "core_county_boundaries",
    "lad_county_lookup":        "core_lad_county_lookup",
    "place_names":              "core_place_names",
    "place_boundaries":         "core_place_boundaries",
    "place_lsoa_mapping":         "core_place_lsoa_mapping",
    "place_lsoa_mapping_town":    "core_place_lsoa_mapping_town",
    "place_boundaries_union":     "core_place_boundaries_union",
    "property_transactions":    "core_property_transactions",
    "hpi_lad":                  "core_hpi_lad",
    "voa_rents_lad":            "core_voa_rents_lad",
    "earnings_lad":             "core_earnings_lad",
    "epc_domestic":             "core_epc_domestic",
    "epc_lsoa":                 "core_epc_lsoa",
    "price_sqm_lad":            "core_price_sqm_lad",
    "price_sqm_lsoa":           "core_price_sqm_lsoa",
    "price_sqm_lsoa_yearly":    "core_price_sqm_lsoa_yearly",
    "price_by_bedrooms_lad":    "core_price_by_bedrooms_lad",
    "crime_lsoa":               "core_crime_lsoa",
    "census_lsoa":              "core_census_lsoa",
    "census_ethnicity_ward":    "core_census_ethnicity_ward",
    "census_religion_ward":     "core_census_religion_ward",
    "imd_lsoa":                 "core_imd_lsoa",
    "schools":                  "core_schools",
    "nhs_facilities":           "core_nhs_facilities",
    "nhs_lsoa":                 "core_nhs_lsoa",
    "osm_amenities":            "core_osm_amenities",
    "transport_stops":          "core_transport_stops",
    "station_destinations":     "core_station_destinations",
    "ev_chargers":              "core_ev_chargers",
    "broadband_postcode":       "core_broadband_postcode",
    "broadband_lad":            "core_broadband_lad",
    "mobile_coverage_lad":      "core_mobile_coverage_lad",
    "ptal_lsoa":                "core_ptal_lsoa",
    "cycling_lsoa":             "core_cycling_lsoa",
    "connectivity_lsoa":        "core_connectivity_lsoa",
    "flood_zones":              "core_flood_zones",
    "flood_lsoa":               "core_flood_lsoa",
    "air_quality":              "core_air_quality",
    "air_quality_lad":          "core_air_quality_lad",
    "noise":                    "core_noise",
    "green_space":              "core_green_space",
    "council_tax_lad":          "core_council_tax_lad",
    "council_control_lad":      "core_council_control_lad",
    "s114_notices":             "core_s114_notices",
    "water_company_lad":        "core_water_company_lad",
    "inspire_parcels":          "core_inspire_parcels",
    "llc_charges":              "core_llc_charges",
    "pipeline_runs":            "core_pipeline_runs",
}

# ---------------------------------------------------------------------------
# Schedules (used in source module METADATA)
# ---------------------------------------------------------------------------

SCHEDULE_FOUNDATION = "foundation"   # One-time initial load; run before anything else
SCHEDULE_MONTHLY    = "monthly"      # Monthly refresh (LR, HPI, crime, EPC)
SCHEDULE_QUARTERLY  = "quarterly"    # Quarterly refresh (OSM, EV, mobile, EPC LSOA)
SCHEDULE_ANNUAL     = "annual"       # Annual refresh (boundaries, broadband, etc.)
SCHEDULE_ONE_TIME   = "one_time"     # Only once (census, IMD — until next release)
