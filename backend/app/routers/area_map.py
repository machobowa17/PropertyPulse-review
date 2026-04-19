"""
GET /api/v1/map-pois
GET /api/v1/map-choropleth
Map layer endpoints — POIs and LSOA choropleth heatmaps.
"""
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import PRICE_TYPES
from app.database import get_db
from app.errors import http_error
from app.cache import cache_get, cache_set
from app.services.session_helpers import (
    session_centroid,
    session_boundary_source,
    session_local_scope_type,
    require_session,
)

router = APIRouter()

MAP_CACHE_VERSION = "v2"


# ---------------------------------------------------------------------------
# Map POIs
# ---------------------------------------------------------------------------

@router.get("/map-pois")
async def get_map_pois(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    tab: str = Query("Property & Market"),
    db: AsyncSession = Depends(get_db),
):
    """Return nearby POIs relevant to the active tab for map display."""
    cache_key = f"pois:{MAP_CACHE_VERSION}:{session_key}:{tab}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    sess = await require_session(session_key)
    lat, lon = session_centroid(sess)
    local_scope_type = session_local_scope_type(sess)
    is_area = local_scope_type != "lsoa"
    ward_code = sess.get("ward_code", "_")
    lsoa_code = sess.get("lsoa_code", "_")
    area_lsoa_list = sess["lsoa_codes"] if is_area else []

    features = []

    if tab == "Property & Market":
        # Recent sold prices — use union of ward + LSOA boundaries
        res = None
        all_rows = None
        if ward_code and ward_code != '_' and lsoa_code and lsoa_code != '_':
            # Two separate indexed queries merged in Python — each uses GiST index.
            # PARTITION BY lsoa_code limits to 10 per LSOA for geographic spread.
            ward_res = await db.execute(
                text("""
                    SELECT price, date_of_transfer, property_type, duration,
                           paon, saon, street, town, postcode, latitude, longitude, lsoa_code,
                           dist_m, bedrooms, floor_area_sqm, epc_rating
                    FROM (
                        SELECT t.price, t.date_of_transfer, t.property_type, t.duration,
                               t.paon, t.saon, t.street, t.town, t.postcode, t.latitude, t.longitude, t.lsoa_code,
                               ST_Distance(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m,
                               t.bedrooms_estimated AS bedrooms,
                               t.floor_area_sqm,
                               t.epc_rating,
                               ROW_NUMBER() OVER (PARTITION BY t.lsoa_code ORDER BY t.date_of_transfer DESC) AS rn
                        FROM core_property_transactions t
                        JOIN core_ward_boundaries w ON w.ward_code = :ward_code
                        WHERE t.geom IS NOT NULL
                          AND ST_Within(t.geom, w.geom)
                          AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '24 months'
                    ) sub
                    WHERE rn <= 10
                    ORDER BY date_of_transfer DESC
                    LIMIT 500
                """),
                {"lat": lat, "lon": lon, "ward_code": ward_code},
            )
            ward_rows = {(r["latitude"], r["longitude"], str(r["date_of_transfer"])): dict(r) for r in ward_res.mappings().all()}

            lsoa_res = await db.execute(
                text("""
                    SELECT price, date_of_transfer, property_type, duration,
                           paon, saon, street, town, postcode, latitude, longitude, lsoa_code,
                           dist_m, bedrooms, floor_area_sqm, epc_rating
                    FROM (
                        SELECT t.price, t.date_of_transfer, t.property_type, t.duration,
                               t.paon, t.saon, t.street, t.town, t.postcode, t.latitude, t.longitude, t.lsoa_code,
                               ST_Distance(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m,
                               t.bedrooms_estimated AS bedrooms,
                               t.floor_area_sqm,
                               t.epc_rating,
                               ROW_NUMBER() OVER (PARTITION BY t.lsoa_code ORDER BY t.date_of_transfer DESC) AS rn
                        FROM core_property_transactions t
                        JOIN core_lsoa_boundaries l ON l.lsoa_code = :lsoa_code
                        WHERE t.geom IS NOT NULL
                          AND ST_Within(t.geom, l.geom)
                          AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '24 months'
                    ) sub
                    WHERE rn <= 10
                    ORDER BY date_of_transfer DESC
                    LIMIT 500
                """),
                {"lat": lat, "lon": lon, "lsoa_code": lsoa_code},
            )
            merged = {}
            for key, r in ward_rows.items():
                r["in_ward"] = True
                merged[key] = r
            for r in lsoa_res.mappings().all():
                key = (r["latitude"], r["longitude"], str(r["date_of_transfer"]))
                if key not in merged:
                    row = dict(r)
                    row["in_ward"] = False
                    merged[key] = row
            all_rows = sorted(merged.values(), key=lambda x: x["date_of_transfer"], reverse=True)
            res = None  # merged results already in all_rows
        elif ward_code and ward_code != '_':
            res = await db.execute(
                text("""
                    SELECT price, date_of_transfer, property_type, duration,
                           paon, saon, street, town, postcode, latitude, longitude, lsoa_code,
                           dist_m, in_ward, bedrooms, floor_area_sqm, epc_rating
                    FROM (
                        SELECT t.price, t.date_of_transfer, t.property_type, t.duration,
                               t.paon, t.saon, t.street, t.town, t.postcode, t.latitude, t.longitude, t.lsoa_code,
                               ST_Distance(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m,
                               true AS in_ward,
                               t.bedrooms_estimated AS bedrooms,
                               t.floor_area_sqm,
                               t.epc_rating,
                               ROW_NUMBER() OVER (PARTITION BY t.lsoa_code ORDER BY t.date_of_transfer DESC) AS rn
                        FROM core_property_transactions t
                        JOIN core_ward_boundaries w ON w.ward_code = :ward_code
                        WHERE t.geom IS NOT NULL
                          AND ST_Within(t.geom, w.geom)
                          AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '24 months'
                    ) sub
                    WHERE rn <= 10
                    ORDER BY date_of_transfer DESC
                    LIMIT 500
                """),
                {"lat": lat, "lon": lon, "ward_code": ward_code},
            )
        elif is_area and area_lsoa_list:
            sample_codes = area_lsoa_list[:50]
            res = await db.execute(
                text("""
                    SELECT price, date_of_transfer, property_type, duration,
                           paon, saon, street, town, postcode, latitude, longitude, lsoa_code,
                           dist_m, in_ward, bedrooms, floor_area_sqm, epc_rating
                    FROM (
                        SELECT t.price, t.date_of_transfer, t.property_type, t.duration,
                               t.paon, t.saon, t.street, t.town, t.postcode, t.latitude, t.longitude, t.lsoa_code,
                               ST_Distance(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m,
                               true AS in_ward,
                               t.bedrooms_estimated AS bedrooms,
                               t.floor_area_sqm,
                               t.epc_rating,
                               ROW_NUMBER() OVER (PARTITION BY t.lsoa_code ORDER BY t.date_of_transfer DESC) AS rn
                        FROM core_property_transactions t
                        WHERE t.geom IS NOT NULL
                          AND t.lsoa_code = ANY(:codes)
                          AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '24 months'
                    ) sub
                    WHERE rn <= 10
                    ORDER BY date_of_transfer DESC
                    LIMIT 500
                """),
                {"lat": lat, "lon": lon, "codes": sample_codes},
            )
        else:
            res = await db.execute(
                text("""
                    SELECT price, date_of_transfer, property_type, duration,
                           paon, saon, street, town, postcode, latitude, longitude, lsoa_code,
                           dist_m, in_ward, bedrooms, floor_area_sqm, epc_rating
                    FROM (
                        SELECT t.price, t.date_of_transfer, t.property_type, t.duration,
                               t.paon, t.saon, t.street, t.town, t.postcode, t.latitude, t.longitude, t.lsoa_code,
                               ST_Distance(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m,
                               true AS in_ward,
                               t.bedrooms_estimated AS bedrooms,
                               t.floor_area_sqm,
                               t.epc_rating,
                               ROW_NUMBER() OVER (PARTITION BY t.lsoa_code ORDER BY t.date_of_transfer DESC) AS rn
                        FROM core_property_transactions t
                        WHERE t.geom IS NOT NULL
                          AND ST_DWithin(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1000)
                          AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                    ) sub
                    WHERE rn <= 10
                    ORDER BY date_of_transfer DESC
                    LIMIT 500
                """),
                {"lat": lat, "lon": lon},
            )
        _TYPE_NAMES = {"D": "Detached", "S": "Semi-Detached", "T": "Terraced", "F": "Flat"}
        _TENURE_NAMES = {"F": "Freehold", "L": "Leasehold"}

        sold_rows = all_rows if res is None else res.mappings().all()

        for r in sold_rows:
            saon = r["saon"] if r["saon"] and r["saon"] != "N" else None
            parts = [p for p in [saon, r["paon"], r["street"]] if p]
            address = ", ".join(parts) if parts else r["town"] or "Unknown"
            pt = (r["property_type"] or "").strip()
            dur = (r["duration"] or "").strip()
            pc = (r.get("postcode") or "").strip()

            bedrooms = r.get("bedrooms")
            floor_area = float(r["floor_area_sqm"]) if r.get("floor_area_sqm") else None
            epc_rating = r.get("epc_rating")
            actual_psf = round(r["price"] / (floor_area * 10.7639)) if floor_area and floor_area > 0 else None

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": {
                    "name": address,
                    "category": "sold_price",
                    "price": r["price"],
                    "date": str(r["date_of_transfer"]),
                    "property_type": _TYPE_NAMES.get(pt, pt),
                    "tenure": _TENURE_NAMES.get(dur, ""),
                    "postcode": pc,
                    "bedrooms": bedrooms,
                    "floor_area_sqm": floor_area,
                    "actual_psf": actual_psf,
                    "epc_rating": epc_rating,
                    "dist_m": round(float(r["dist_m"])),
                    "lsoa_code": r["lsoa_code"],
                    "in_ward": bool(r["in_ward"]),
                },
            })

    elif tab == "Community & Education":
        if is_area and area_lsoa_list:
            res = await db.execute(
                text("""
                    SELECT DISTINCT ON (s.school_name) s.school_name, s.phase, s.ofsted_rating, s.latitude, s.longitude
                    FROM core_schools s
                    JOIN core_lsoa_boundaries lb ON ST_Within(s.geom, lb.geom)
                    WHERE s.is_open = true AND s.geom IS NOT NULL
                      AND lb.lsoa_code = ANY(:codes)
                    ORDER BY s.school_name
                    LIMIT 30
                """),
                {"codes": area_lsoa_list},
            )
        else:
            res = await db.execute(
                text("""
                    SELECT school_name, phase, ofsted_rating, latitude, longitude,
                           ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m
                    FROM core_schools
                    WHERE is_open = true
                      AND geom IS NOT NULL
                      AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 2000)
                    ORDER BY dist_m
                    LIMIT 20
                """),
                {"lat": lat, "lon": lon},
            )
        for r in res.mappings().all():
            props = {
                "name": r["school_name"],
                "category": "school",
                "phase": r["phase"],
                "ofsted": r["ofsted_rating"],
            }
            if not is_area and "dist_m" in dict(r):
                props["dist_m"] = round(float(r["dist_m"]))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": props,
            })

        if is_area and area_lsoa_list:
            nhs_res = await db.execute(
                text("""
                    SELECT nf.name, nf.facility_type, nf.latitude, nf.longitude
                    FROM core_nhs_facilities nf
                    JOIN core_lsoa_boundaries lb ON ST_Within(nf.geom, lb.geom)
                    WHERE nf.geom IS NOT NULL
                      AND lb.lsoa_code = ANY(:codes)
                    ORDER BY nf.facility_type, nf.name
                    LIMIT 30
                """),
                {"codes": area_lsoa_list},
            )
        else:
            nhs_res = await db.execute(
                text("""
                    SELECT name, facility_type, latitude, longitude,
                           ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m
                    FROM core_nhs_facilities
                    WHERE geom IS NOT NULL
                      AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 2000)
                    ORDER BY dist_m
                    LIMIT 20
                """),
                {"lat": lat, "lon": lon},
            )
        for r in nhs_res.mappings().all():
            props = {
                "name": r["name"] or "NHS facility",
                "category": "nhs_facility",
                "facility_type": r["facility_type"],
            }
            if not is_area and "dist_m" in dict(r):
                props["dist_m"] = round(float(r["dist_m"]))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": props,
            })

    elif tab == "Environment & Safety":
        if is_area and area_lsoa_list:
            res = await db.execute(
                text("""
                    SELECT fz.flood_zone, ST_AsGeoJSON(ST_Intersection(fz.geom,
                        ST_Union(lb.geom)
                    ), 5) AS geojson
                    FROM core_flood_zones fz
                    JOIN core_lsoa_boundaries lb ON ST_Intersects(fz.geom, lb.geom)
                    WHERE lb.lsoa_code = ANY(:codes)
                    GROUP BY fz.flood_zone, fz.geom
                """),
                {"codes": area_lsoa_list},
            )
        else:
            res = await db.execute(
                text("""
                    SELECT flood_zone, ST_AsGeoJSON(ST_Intersection(geom,
                        ST_Buffer(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 2000)::geometry
                    ), 5) AS geojson
                    FROM core_flood_zones
                    WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 2000)
                """),
                {"lat": lat, "lon": lon},
            )
        for r in res.mappings().all():
            geojson = json.loads(r["geojson"])
            features.append({
                "type": "Feature",
                "geometry": geojson,
                "properties": {
                    "category": "flood_zone",
                    "flood_zone": r["flood_zone"],
                },
            })

        park_types = ["Public Park Or Garden"]
        sport_types = [
            "Playing Field",
            "Sports Facility",
            "Golf Course",
            "Tennis Court",
            "Bowling Green",
            "Other Sports Facility",
        ]
        if is_area and area_lsoa_list:
            green_res = await db.execute(
                text("""
                    SELECT gs.site_name, gs.site_type,
                           COALESCE(gs.area_hectares, ST_Area(gs.geom::geography) / 10000) AS area_ha,
                           ST_Y(ST_PointOnSurface(gs.geom)) AS latitude,
                           ST_X(ST_PointOnSurface(gs.geom)) AS longitude,
                           CASE
                               WHEN gs.site_type = ANY(:park_types) THEN 'park'
                               ELSE 'sports_recreation'
                           END AS category
                    FROM core_green_space gs
                    JOIN core_lsoa_boundaries lb ON ST_Intersects(gs.geom, lb.geom)
                    WHERE gs.geom IS NOT NULL
                      AND lb.lsoa_code = ANY(:codes)
                      AND gs.site_type = ANY(:all_types)
                    ORDER BY area_ha DESC NULLS LAST, gs.site_name
                    LIMIT 40
                """),
                {"codes": area_lsoa_list, "park_types": park_types, "all_types": park_types + sport_types},
            )
        else:
            green_res = await db.execute(
                text("""
                    SELECT gs.site_name, gs.site_type,
                           COALESCE(gs.area_hectares, ST_Area(gs.geom::geography) / 10000) AS area_ha,
                           ST_Y(ST_PointOnSurface(gs.geom)) AS latitude,
                           ST_X(ST_PointOnSurface(gs.geom)) AS longitude,
                           ST_Distance(gs.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m,
                           CASE
                               WHEN gs.site_type = ANY(:park_types) THEN 'park'
                               ELSE 'sports_recreation'
                           END AS category
                    FROM core_green_space gs
                    WHERE gs.geom IS NOT NULL
                      AND ST_DWithin(gs.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1500)
                      AND gs.site_type = ANY(:all_types)
                    ORDER BY dist_m
                    LIMIT 30
                """),
                {"lat": lat, "lon": lon, "park_types": park_types, "all_types": park_types + sport_types},
            )
        for r in green_res.mappings().all():
            props = {
                "name": r["site_name"] or "Green space",
                "category": r["category"],
                "site_type": r["site_type"],
                "area_ha": round(float(r["area_ha"]), 2) if r["area_ha"] is not None else None,
            }
            if not is_area and "dist_m" in dict(r):
                props["dist_m"] = round(float(r["dist_m"]))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": props,
            })

    elif tab == "Lifestyle & Connectivity":
        if is_area and area_lsoa_list:
            res = await db.execute(
                text("""
                    SELECT DISTINCT ON (base_name)
                        REGEXP_REPLACE(ts.stop_name,
                            ' (Rail Station|Underground Station|DLR Station|Overground Station|Tram Stop|Station)$',
                            '', 'i') AS base_name,
                        ts.stop_name, ts.stop_type, ts.latitude, ts.longitude
                    FROM core_transport_stops ts
                    JOIN core_lsoa_boundaries lb ON ST_Within(ts.geom, lb.geom)
                    WHERE ts.stop_type IN ('RSE', 'RLY', 'MET')
                      AND ts.geom IS NOT NULL
                      AND lb.lsoa_code = ANY(:codes)
                    ORDER BY base_name
                    LIMIT 20
                """),
                {"codes": area_lsoa_list},
            )
        else:
            res = await db.execute(
                text("""
                    SELECT DISTINCT ON (base_name)
                        REGEXP_REPLACE(stop_name,
                            ' (Rail Station|Underground Station|DLR Station|Overground Station|Tram Stop|Station)$',
                            '', 'i') AS base_name,
                        stop_name, stop_type, latitude, longitude,
                        ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m
                    FROM core_transport_stops
                    WHERE stop_type IN ('RSE', 'RLY', 'MET')
                      AND geom IS NOT NULL
                      AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 3000)
                    ORDER BY base_name, dist_m
                    LIMIT 15
                """),
                {"lat": lat, "lon": lon},
            )
        for r in res.mappings().all():
            props = {
                "name": r["base_name"],
                "category": "station",
                "type": r["stop_type"],
            }
            if not is_area and "dist_m" in dict(r):
                props["dist_m"] = round(float(r["dist_m"]))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": props,
            })

        # EV chargers
        if is_area and area_lsoa_list:
            ev_res = await db.execute(
                text("""
                    SELECT ev.name, ev.operator, ev.connector_count, ev.max_power_kw, ev.latitude, ev.longitude
                    FROM core_ev_chargers ev
                    JOIN core_lsoa_boundaries lb ON ST_Within(ev.geom, lb.geom)
                    WHERE ev.geom IS NOT NULL
                      AND lb.lsoa_code = ANY(:codes)
                    ORDER BY ev.name
                    LIMIT 30
                """),
                {"codes": area_lsoa_list},
            )
        else:
            ev_res = await db.execute(
                text("""
                    SELECT name, operator, connector_count, max_power_kw, latitude, longitude,
                           ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m
                    FROM core_ev_chargers
                    WHERE geom IS NOT NULL
                      AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1000)
                    ORDER BY dist_m
                    LIMIT 20
                """),
                {"lat": lat, "lon": lon},
            )
        for r in ev_res.mappings().all():
            props = {
                "name": r["name"] or "EV Charger",
                "category": "ev_charger",
                "operator": r["operator"],
                "connectors": r["connector_count"],
                "max_kw": float(r["max_power_kw"]) if r["max_power_kw"] else None,
            }
            if not is_area and "dist_m" in dict(r):
                props["dist_m"] = round(float(r["dist_m"]))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": props,
            })

        amenity_types = ['supermarket', 'cafe', 'restaurant', 'pub', 'gym', 'park', 'pharmacy', 'dentist', 'hospital', 'doctors']
        if is_area and area_lsoa_list:
            amenity_res = await db.execute(
                text("""
                    SELECT DISTINCT ON (a.amenity_type, COALESCE(a.name, 'Unnamed'))
                        COALESCE(a.name, INITCAP(REPLACE(a.amenity_type, '_', ' '))) AS name,
                        a.amenity_type,
                        a.latitude,
                        a.longitude
                    FROM core_osm_amenities a
                    JOIN core_lsoa_boundaries lb ON ST_Within(a.geom, lb.geom)
                    WHERE a.geom IS NOT NULL
                      AND lb.lsoa_code = ANY(:codes)
                      AND a.amenity_type = ANY(:types)
                    ORDER BY a.amenity_type, COALESCE(a.name, 'Unnamed')
                    LIMIT 40
                """),
                {"codes": area_lsoa_list, "types": amenity_types},
            )
        else:
            amenity_res = await db.execute(
                text("""
                    SELECT COALESCE(name, INITCAP(REPLACE(amenity_type, '_', ' '))) AS name,
                           amenity_type,
                           latitude,
                           longitude,
                           ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m
                    FROM core_osm_amenities
                    WHERE geom IS NOT NULL
                      AND amenity_type = ANY(:types)
                      AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1500)
                    ORDER BY dist_m
                    LIMIT 30
                """),
                {"lat": lat, "lon": lon, "types": amenity_types},
            )
        for r in amenity_res.mappings().all():
            props = {
                "name": r["name"],
                "category": "amenity",
                "amenity_type": r["amenity_type"],
            }
            if not is_area and "dist_m" in dict(r):
                props["dist_m"] = round(float(r["dist_m"]))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": props,
            })

    result: dict = {"type": "FeatureCollection", "features": features}

    # Include earliest sold-price date so the frontend legend can show "since MMM YYYY"
    if tab == "Property & Market" and features:
        min_date = min(
            (f["properties"]["date"] for f in features if f["properties"].get("date")),
            default=None,
        )
        if min_date:
            result["sold_prices_since"] = min_date

    await cache_set(cache_key, result, ttl=86400)
    return result


# ---------------------------------------------------------------------------
# Choropleth (LSOA-level heatmap polygons)
# ---------------------------------------------------------------------------

VALID_CHOROPLETH_LAYERS = {
    "avg_price",
    "median_price",
    "price_per_sqft",
    "epc_score",
    "population_density",
    "median_age",
    "household_composition",
    "good_health",
    "economically_active",
    "degree_educated",
    "no_car",
    "born_abroad",
    "housing_tenure",
    "housing_type",
    "household_size",
    "deprivation",
    "deprivation_income",
    "deprivation_employment",
    "deprivation_education",
    "deprivation_health",
    "deprivation_crime",
    "deprivation_barriers",
    "deprivation_living_environment",
    "broadband",
    "mobile_coverage",
    "air_quality_no2",
    "air_quality_pm25",
    "council_tax",
    "median_earnings",
    "median_rent",
}


@router.get("/map-choropleth")
async def get_map_choropleth(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    layer: str = Query(..., description="avg_price | price_per_sqft | epc_score"),
    db: AsyncSession = Depends(get_db),
):
    """Return LSOA polygons with metric values for choropleth rendering."""
    if layer not in VALID_CHOROPLETH_LAYERS:
        raise http_error(400, "INVALID_LAYER", f"Invalid layer: {layer}. Valid: {VALID_CHOROPLETH_LAYERS}")

    cache_key = f"choropleth:{MAP_CACHE_VERSION}:{session_key}:{layer}"
    cached = await cache_get(cache_key)
    if cached:
        return JSONResponse(content=cached)

    sess = await require_session(session_key)
    boundary_source = session_boundary_source(sess)
    local_lads = sess.get("local_lads", [])
    lsoa_codes = sess.get("lsoa_codes", [])
    ward_code = sess.get("ward_code", "_")

    # --- Determine LSOA scope ---
    if boundary_source == "ward_lsoa":
        # Postcode: expand to all LSOAs in the ward
        scope_res = await db.execute(
            text("SELECT DISTINCT lsoa_code FROM core_postcodes WHERE ward_code = :ward AND lsoa_code IS NOT NULL"),
            {"ward": ward_code},
        )
        scope_codes = [r["lsoa_code"] for r in scope_res.mappings().all()]
    elif boundary_source in ("place", "ward"):
        scope_codes = lsoa_codes
    else:
        # LAD / county: all LSOAs in the local LADs
        scope_res = await db.execute(
            text("SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = ANY(:lads)"),
            {"lads": local_lads},
        )
        scope_codes = [r["lsoa_code"] for r in scope_res.mappings().all()]

    if not scope_codes:
        return JSONResponse(content={"type": "FeatureCollection", "metadata": {"layer": layer, "lsoa_count": 0}, "features": []})

    # --- Adaptive simplification ---
    n = len(scope_codes)
    if n > 1000:
        geom_expr = "ST_SimplifyPreserveTopology(lb.geom, 0.001)"
        prec = 4
    elif n > 200:
        geom_expr = "ST_SimplifyPreserveTopology(lb.geom, 0.0003)"
        prec = 5
    else:
        geom_expr = "lb.geom"
        prec = 5

    # --- Query: geometry + metric value ---
    metadata_note = None
    metadata_grain = "lsoa"
    if layer == "avg_price":
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   sub.wavg_price AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN (
                SELECT lsoa_code,
                       ROUND(AVG(price)) AS wavg_price
                FROM core_property_transactions
                WHERE date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                  AND property_type = ANY(:price_types)
                  AND lsoa_code = ANY(:codes)
                GROUP BY lsoa_code
            ) sub ON sub.lsoa_code = lb.lsoa_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "GBP"
    elif layer == "median_price":
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   sub.median_price AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN (
                SELECT lsoa_code,
                       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price)::numeric) AS median_price
                FROM core_property_transactions
                WHERE date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                  AND property_type = ANY(:price_types)
                  AND lsoa_code = ANY(:codes)
                GROUP BY lsoa_code
            ) sub ON sub.lsoa_code = lb.lsoa_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "GBP"
    elif layer == "price_per_sqft":
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   ROUND(sub.avg_ppsft) AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN (
                SELECT lsoa_code,
                       ROUND(AVG(price::numeric / NULLIF(floor_area_sqm::numeric * 10.7639, 0)), 2) AS avg_ppsft
                FROM core_property_transactions
                WHERE floor_area_sqm > 0
                  AND lsoa_code = ANY(:codes)
                GROUP BY lsoa_code
            ) sub ON sub.lsoa_code = lb.lsoa_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "GBP/sqft"
    elif layer == "epc_score":
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   e.avg_energy_score AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN core_epc_lsoa e ON e.lsoa_code = lb.lsoa_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "score"
    elif layer in {
        "population_density",
        "median_age",
        "household_composition",
        "good_health",
        "economically_active",
        "degree_educated",
        "no_car",
        "born_abroad",
        "housing_tenure",
        "housing_type",
        "household_size",
    }:
        census_columns = {
            "population_density": "population_density",
            "median_age": "median_age",
            "household_composition": "pct_families",
            "good_health": "pct_good_health",
            "economically_active": "pct_economically_active",
            "degree_educated": "pct_degree",
            "no_car": "pct_no_car",
            "born_abroad": "pct_born_abroad",
            "housing_tenure": "pct_owned",
            "housing_type": "pct_detached",
            "household_size": "pct_1person",
        }
        census_units = {
            "population_density": "people/hectare",
            "median_age": "years",
            "household_composition": "% families",
            "good_health": "%",
            "economically_active": "%",
            "degree_educated": "%",
            "no_car": "%",
            "born_abroad": "%",
            "housing_tenure": "% owner-occupied",
            "housing_type": "% detached",
            "household_size": "% one-person",
        }
        census_notes = {
            "household_composition": "Household composition heatmap currently maps the family-household share, matching the headline metric while the card details still carry the broader household mix.",
            "housing_tenure": "Housing tenure heatmap currently maps owner-occupation share, matching the headline metric while the card details still carry the wider tenure mix.",
            "housing_type": "Housing stock heatmap currently maps detached-home share, matching the headline metric while the card details still carry the broader stock mix.",
            "household_size": "Household size heatmap currently maps one-person-household share, matching the headline metric while the card details still carry the broader size mix.",
        }
        value_column = census_columns[layer]
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   c.{value_column} AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN core_census_lsoa c ON c.lsoa_code = lb.lsoa_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = census_units[layer]
        metadata_note = census_notes.get(layer)
    elif layer in {
        "deprivation",
        "deprivation_income",
        "deprivation_employment",
        "deprivation_education",
        "deprivation_health",
        "deprivation_crime",
        "deprivation_barriers",
        "deprivation_living_environment",
    }:
        deprivation_columns = {
            "deprivation": "imd_score",
            "deprivation_income": "income_score",
            "deprivation_employment": "employment_score",
            "deprivation_education": "education_score",
            "deprivation_health": "health_score",
            "deprivation_crime": "crime_score",
            "deprivation_barriers": "barriers_score",
            "deprivation_living_environment": "living_env_score",
        }
        value_column = deprivation_columns[layer]
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   imd.{value_column} AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN core_imd_lsoa imd ON imd.lsoa_code = lb.lsoa_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "score"
    elif layer == "broadband":
        value_column = "gigabit_pct"
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   sub.value AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN (
                SELECT p.lsoa_code,
                       ROUND(AVG(b.{value_column}), 1) AS value
                FROM core_broadband_postcode b
                JOIN core_postcodes p ON p.postcode = b.postcode
                WHERE p.lsoa_code = ANY(:codes)
                GROUP BY p.lsoa_code
            ) sub ON sub.lsoa_code = lb.lsoa_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "%"
    elif layer == "mobile_coverage":
        value_column = "pct_4g_outdoor"
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   m.{value_column} AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN core_mobile_coverage_lad m ON m.lad_code = lb.lad_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "%"
        metadata_grain = "lad_proxy"
        metadata_note = "Mobile coverage is sourced at local-authority grain and repeated across LSOAs as the best currently integrated official geographic proxy."
    elif layer in {"air_quality_no2", "air_quality_pm25"}:
        air_quality_columns = {
            "air_quality_no2": "no2_ugm3",
            "air_quality_pm25": "pm25_ugm3",
        }
        air_quality_notes = {
            "air_quality_no2": "NO2 heatmap aggregates intersecting DEFRA air-quality grid cells to each LSOA, preserving published grid-cell evidence without implying address-level precision.",
            "air_quality_pm25": "PM2.5 heatmap aggregates intersecting DEFRA air-quality grid cells to each LSOA, preserving published grid-cell evidence without implying address-level precision.",
        }
        value_column = air_quality_columns[layer]
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   aq.value AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN (
                SELECT lb2.lsoa_code,
                       ROUND(AVG(a.{value_column})::numeric, 2) AS value
                FROM core_lsoa_boundaries lb2
                JOIN core_air_quality a ON ST_Intersects(a.geom, lb2.geom)
                WHERE lb2.lsoa_code = ANY(:codes)
                GROUP BY lb2.lsoa_code
            ) aq ON aq.lsoa_code = lb.lsoa_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "µg/m³"
        metadata_grain = "grid_to_lsoa"
        metadata_note = air_quality_notes[layer]
    elif layer == "council_tax":
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   ct.band_d AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN core_council_tax_lad ct ON ct.lad_code = lb.lad_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "GBP/year"
        metadata_grain = "lad_proxy"
        metadata_note = "Council tax is published at local-authority level, so the heatmap repeats each authority's Band D charge across its constituent LSOAs as the best currently integrated official geographic proxy."
    elif layer == "median_earnings":
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   e.median_annual_earnings AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN core_earnings_lad e ON e.lad_code = lb.lad_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "GBP/year"
        metadata_grain = "lad_proxy"
        metadata_note = "Median annual earnings are published at local-authority level, so the heatmap repeats each authority's ASHE earnings value across its constituent LSOAs as the best currently integrated official geographic proxy."
    elif layer == "median_rent":
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   r.median_rent_all AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN (
                SELECT DISTINCT ON (lad_code)
                       lad_code,
                       median_rent_all,
                       period
                FROM core_voa_rents_lad
                ORDER BY lad_code, period DESC
            ) r ON r.lad_code = lb.lad_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "GBP/month"
        metadata_grain = "lad_proxy"
        metadata_note = "Median rent is published at local-authority level, so the heatmap repeats each authority's latest official private-rent value across its constituent LSOAs as the best currently integrated geographic proxy."
    else:
        raise http_error(400, "INVALID_LAYER", f"Invalid layer: {layer}. Valid: {VALID_CHOROPLETH_LAYERS}")

    res = await db.execute(text(sql), {"codes": scope_codes, "price_types": list(PRICE_TYPES)})
    rows = res.mappings().all()

    # --- Build features + compute quintiles ---
    features = []
    values = []
    for r in rows:
        if not r["geojson"]:
            continue
        val = round(float(r["value"]), 1) if r["value"] is not None else None
        if val is not None:
            values.append(val)
        features.append({
            "type": "Feature",
            "geometry": json.loads(r["geojson"]),
            "properties": {
                "lsoa_code": r["lsoa_code"],
                "lsoa_name": r["lsoa_name"],
                "value": val,
                "quantile": None,  # placeholder, filled below
            },
        })

    # Compute quintile breaks (4 cut-points → 5 buckets).
    # Deduplicate breaks so discrete / zero-heavy metrics get a binary map
    # instead of all non-zero values collapsing into bucket 4.
    quantiles = []
    if len(values) >= 5:
        values_sorted = sorted(values)
        raw = [values_sorted[len(values_sorted) * i // 5] for i in range(1, 5)]
        quantiles = sorted(set(raw))
    elif len(values) >= 2:
        min_v, max_v = min(values), max(values)
        if max_v > min_v:
            step = (max_v - min_v) / 5
            raw = [min_v + step * i for i in range(1, 5)]
            quantiles = sorted(set(raw))

    # Assign quantile index to each feature
    for f in features:
        v = f["properties"]["value"]
        if v is None:
            f["properties"]["quantile"] = None
        elif not quantiles:
            f["properties"]["quantile"] = 2  # single value: middle bucket
        else:
            f["properties"]["quantile"] = sum(1 for q in quantiles if v > q)

    min_val = min(values) if values else None
    max_val = max(values) if values else None

    result = {
        "type": "FeatureCollection",
        "metadata": {
            "layer": layer,
            "unit": unit,
            "grain": metadata_grain,
            "note": metadata_note,
            "min_value": min_val,
            "max_value": max_val,
            "quantiles": quantiles,
            "lsoa_count": len(features),
        },
        "features": features,
    }

    await cache_set(cache_key, result, ttl=86400)
    return JSONResponse(content=result)
