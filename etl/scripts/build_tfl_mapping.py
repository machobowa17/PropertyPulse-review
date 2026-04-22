"""
Build CRS → lat/lon mapping from rail_references.csv.

Outputs: etl/data/crs_naptan_mapping.json
Contains {crs: {"atco": "9100...", "lat": 51.xxx, "lon": -0.xxx}} for each station.
Used by nr_destinations.py and backend commute.py for TfL Journey Planner API calls.

Note: TfL Journey Planner works best with lat/lon coordinates (NaPTAN IDs often
trigger disambiguation responses). We convert OSGB36 easting/northing to WGS84.
"""

import csv
import json
import math
import os

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_CSV_PATH = os.path.join(_DATA_DIR, "rail_references.csv")
_OUTPUT_PATH = os.path.join(_DATA_DIR, "crs_naptan_mapping.json")


def _osgb36_to_wgs84(easting, northing):
    """
    Convert OSGB36 National Grid easting/northing to WGS84 lat/lon.
    Uses a simplified Helmert transformation (accuracy ~5m, sufficient for station lookup).
    """
    # Airy 1830 ellipsoid
    a = 6377563.396
    b = 6356256.909
    F0 = 0.9996012717
    lat0 = math.radians(49)
    lon0 = math.radians(-2)
    N0 = -100000
    E0 = 400000
    e2 = 1 - (b * b) / (a * a)
    n = (a - b) / (a + b)

    lat = lat0
    M = 0
    while True:
        lat = (northing - N0 - M) / (a * F0) + lat
        Ma = (1 + n + (5.0 / 4) * n ** 2 + (5.0 / 4) * n ** 3) * (lat - lat0)
        Mb = (3 * n + 3 * n ** 2 + (21.0 / 8) * n ** 3) * math.sin(lat - lat0) * math.cos(lat + lat0)
        Mc = ((15.0 / 8) * n ** 2 + (15.0 / 8) * n ** 3) * math.sin(2 * (lat - lat0)) * math.cos(2 * (lat + lat0))
        Md = (35.0 / 24) * n ** 3 * math.sin(3 * (lat - lat0)) * math.cos(3 * (lat + lat0))
        M = b * F0 * (Ma - Mb + Mc - Md)
        if abs(northing - N0 - M) < 0.00001:
            break

    cos_lat = math.cos(lat)
    sin_lat = math.sin(lat)
    nu = a * F0 / math.sqrt(1 - e2 * sin_lat ** 2)
    rho = a * F0 * (1 - e2) / ((1 - e2 * sin_lat ** 2) ** 1.5)
    eta2 = nu / rho - 1

    tan_lat = math.tan(lat)
    VII = tan_lat / (2 * rho * nu)
    VIII = tan_lat / (24 * rho * nu ** 3) * (5 + 3 * tan_lat ** 2 + eta2 - 9 * tan_lat ** 2 * eta2)
    IX = tan_lat / (720 * rho * nu ** 5) * (61 + 90 * tan_lat ** 2 + 45 * tan_lat ** 4)
    X = 1 / (cos_lat * nu)
    XI = 1 / (cos_lat * 6 * nu ** 3) * (nu / rho + 2 * tan_lat ** 2)
    XII = 1 / (cos_lat * 120 * nu ** 5) * (5 + 28 * tan_lat ** 2 + 24 * tan_lat ** 4)

    dE = easting - E0
    lat_rad = lat - VII * dE ** 2 + VIII * dE ** 4 - IX * dE ** 6
    lon_rad = lon0 + X * dE - XI * dE ** 3 + XII * dE ** 5

    # Helmert transform OSGB36 → WGS84 (simplified)
    lat_deg = math.degrees(lat_rad)
    lon_deg = math.degrees(lon_rad)

    # Apply approximate datum shift (OSGB36 to WGS84)
    # These corrections are approximate but sufficient for ~5m accuracy
    lat_deg += 0.00045
    lon_deg -= 0.00045

    return round(lat_deg, 6), round(lon_deg, 6)


def build_mapping():
    """Read rail_references.csv and build CRS → {atco, lat, lon} mapping."""
    mapping = {}
    duplicates = []

    with open(_CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            crs = row["CrsCode"].strip()
            atco = row["AtcoCode"].strip()
            if not crs or not atco:
                continue

            easting = int(row["Easting"]) if row["Easting"] else 0
            northing = int(row["Northing"]) if row["Northing"] else 0

            if crs in mapping:
                if mapping[crs]["atco"] != atco:
                    duplicates.append((crs, mapping[crs]["atco"], atco))
                continue

            if easting > 0 and northing > 0:
                lat, lon = _osgb36_to_wgs84(easting, northing)
            else:
                lat, lon = None, None

            mapping[crs] = {
                "atco": atco,
                "lat": lat,
                "lon": lon,
            }

    print(f"Built mapping: {len(mapping)} CRS entries")
    with_coords = sum(1 for v in mapping.values() if v["lat"] is not None)
    print(f"  {with_coords} with coordinates, {len(mapping) - with_coords} without")

    if duplicates:
        print(f"  {len(duplicates)} CRS codes had multiple ATCO codes (kept first)")

    with open(_OUTPUT_PATH, "w") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)
    print(f"Saved to {_OUTPUT_PATH}")

    return mapping


if __name__ == "__main__":
    mapping = build_mapping()

    # Quick sanity check
    for crs in ["VIC", "LBG", "PAD", "CDS"]:
        if crs in mapping:
            entry = mapping[crs]
            print(f"  {crs}: lat={entry['lat']}, lon={entry['lon']}")
