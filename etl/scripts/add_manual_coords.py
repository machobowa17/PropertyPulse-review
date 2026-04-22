"""Add manually-researched coordinates for 19 CRS codes that Nominatim missed."""
import json
import os

MAPPING_PATH = os.environ.get(
    "CRS_MAPPING_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "crs_naptan_mapping.json"),
)

MANUAL = {
    "ARA": {"lat": 55.922, "lon": -4.267},
    "BCZ": {"lat": 53.404, "lon": -3.079},
    "BDS": {"lat": 55.918, "lon": -4.367},
    "CAP": {"lat": 53.094, "lon": -3.835},
    "ELT": {"lat": 56.739, "lon": -2.735},
    "ERB": {"lat": 51.433, "lon": -0.957},
    "FEG": {"lat": 54.954, "lon": -1.467},
    "HBL": {"lat": 53.483, "lon": -2.883},
    "HXX": {"lat": 51.470, "lon": -0.455},
    "NCZ": {"lat": 54.968, "lon": -1.617},
    "NWH": {"lat": 55.046, "lon": -1.497},
    "PRI": {"lat": 55.810, "lon": -4.353},
    "SCN": {"lat": 57.311, "lon": -6.118},
    "STI": {"lat": 54.918, "lon": -1.388},
    "UIG": {"lat": 57.585, "lon": -6.355},
    "WEO": {"lat": 52.942, "lon": -2.157},
    "WER": {"lat": 52.941, "lon": -2.157},
    "WWC": {"lat": 51.381, "lon": -0.015},
    "XAA": {"lat": 55.617, "lon": -2.809},
}

with open(MAPPING_PATH) as f:
    mapping = json.load(f)

print(f"Before: {len(mapping)} entries")

added = 0
for crs, coords in MANUAL.items():
    if crs not in mapping:
        mapping[crs] = coords
        added += 1
        print(f"  Added {crs}: {coords['lat']}, {coords['lon']}")

with open(MAPPING_PATH, "w") as f:
    json.dump(mapping, f, indent=2)

print(f"After: {len(mapping)} entries (+{added})")
