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

# England bounding box for Overpass API queries
ENGLAND_BBOX = "49.9,-6.5,55.9,2.0"

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
    "place_lsoa_mapping":       "core_place_lsoa_mapping",
    "place_lsoa_mapping_town":  "core_place_lsoa_mapping_town",
    "property_transactions":    "core_property_transactions",
    "hpi_lad":                  "core_hpi_lad",
    "voa_rents_lad":            "core_voa_rents_lad",
    "earnings_lad":             "core_earnings_lad",
    "epc_domestic":             "core_epc_domestic",
    "epc_lsoa":                 "core_epc_lsoa",
    "price_sqm_lad":            "core_price_sqm_lad",
    "price_sqm_lsoa":           "core_price_sqm_lsoa",
    "price_by_bedrooms_lad":    "core_price_by_bedrooms_lad",
    "crime_lsoa":               "core_crime_lsoa",
    "census_lsoa":              "core_census_lsoa",
    "census_ethnicity_ward":    "core_census_ethnicity_ward",
    "imd_lsoa":                 "core_imd_lsoa",
    "schools":                  "core_schools",
    "nhs_facilities":           "core_nhs_facilities",
    "nhs_lsoa":                 "core_nhs_lsoa",
    "osm_amenities":            "core_osm_amenities",
    "transport_stops":          "core_transport_stops",
    "ev_chargers":              "core_ev_chargers",
    "broadband_postcode":       "core_broadband_postcode",
    "broadband_lad":            "core_broadband_lad",
    "mobile_coverage_lad":      "core_mobile_coverage_lad",
    "ptal_lsoa":                "core_ptal_lsoa",
    "cycling_lsoa":             "core_cycling_lsoa",
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
