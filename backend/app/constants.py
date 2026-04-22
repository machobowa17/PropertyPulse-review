"""
PropertyPulse API — Shared Constants

Single source of truth for values used across API route handlers and
tab service files. Mirrors etl/constants.py for the Python API layer.

Rules:
- Never write property type codes, EPC band letters, amenity names, or
  LAD code sets as inline string literals in any service or router.
  Always import from this module.
- Colour values here must stay in sync with frontend MapView.tsx.
  If a colour changes, update both files.
"""

# ---------------------------------------------------------------------------
# Property types (Land Registry codes)
# ---------------------------------------------------------------------------

PROPERTY_TYPES = ("D", "S", "T", "F", "O")

# Codes used for price calculations (excludes O = Other/commercial)
PRICE_TYPES = ("D", "S", "T", "F")

# Human-readable labels
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

# Midpoint energy efficiency score for each EPC band
EPC_BAND_SCORES = {
    "A": 92,
    "B": 81,
    "C": 69,
    "D": 55,
    "E": 39,
    "F": 21,
    "G": 1,
}

# Display colours for EPC bands — must stay in sync with frontend MapView.tsx EPC_COLOURS
EPC_COLOURS = {
    "A": "#008054",
    "B": "#19b459",
    "C": "#8dce46",
    "D": "#ffd500",
    "E": "#fcaa65",
    "F": "#ef8023",
    "G": "#e9153b",
}

# ---------------------------------------------------------------------------
# Property type display colours — must stay in sync with frontend MapView.tsx
# PROPERTY_TYPE_COLOURS uses full human-readable names as keys (not codes)
# ---------------------------------------------------------------------------

PROPERTY_TYPE_COLOURS = {
    "Detached":      "#2563eb",
    "Semi-Detached": "#16a34a",
    "Terraced":      "#d97706",
    "Flat":          "#9333ea",
}

# ---------------------------------------------------------------------------
# Greater Manchester Police LAD codes
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

# ---------------------------------------------------------------------------
# Core table names — import rather than writing string literals
# ---------------------------------------------------------------------------

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
    "pipeline_runs":            "core_pipeline_runs",
    "lsoa_green_space":         "core_lsoa_green_space",
    "lsoa_transport":           "core_lsoa_transport",
}

# ---------------------------------------------------------------------------
# VOA LAD code remapping — old district codes for restructured authorities
# ---------------------------------------------------------------------------
# VOA PRMS data (2022-23) predates the April 2023 (and some April 2021)
# LAD restructures. Our postcode table uses current ONS codes, but the VOA
# table still has the old district-level codes. When querying VOA rents
# for a new-code LAD, expand the lookup to include the old constituent codes.

VOA_LAD_REMAP: dict[str, list[str]] = {
    # Northamptonshire restructure (April 2021)
    "E06000061": ["E07000150", "E07000151", "E07000152", "E07000153"],  # North Northamptonshire = Corby + East Northants + Kettering + Wellingborough
    "E06000062": ["E07000154", "E07000155", "E07000156"],               # West Northamptonshire = Daventry + Northampton + South Northants
    # Cumbria restructure (April 2023)
    "E06000063": ["E07000026", "E07000028", "E07000029"],               # Cumberland = Allerdale + Carlisle + Copeland
    "E06000064": ["E07000027", "E07000030", "E07000031"],               # Westmorland and Furness = Barrow-in-Furness + Eden + South Lakeland
    # North Yorkshire restructure (April 2023)
    "E06000065": ["E07000163", "E07000164", "E07000165", "E07000166",   # North Yorkshire = Craven + Hambleton + Harrogate +
                  "E07000167", "E07000168", "E07000169"],               #   Richmondshire + Ryedale + Scarborough + Selby
    # Somerset restructure (April 2023)
    "E06000066": ["E07000187", "E07000188", "E07000189", "E07000246"],  # Somerset = Mendip + Sedgemoor + South Somerset + Somerset West and Taunton
}
