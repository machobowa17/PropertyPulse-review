"""
GET /api/v1/area/{lad_code}/{ward_code}/{lsoa_code}?tab={tab_name}
GET /api/v1/boundary/{ward_code}
Build Bible Part 6, Sections 6.1 & 6.2.4 — Data + Boundary Endpoints
"""
import json
import re
from fastapi import APIRouter, Depends, Query, HTTPException, Path
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ONS code pattern: E/W/S/N + 8 digits, or underscore (wildcard)
_CODE_RE = re.compile(r"^([EWSN]\d{8}|_)$")

from app.database import get_db
from app.cache import cache_get, cache_set
from app.services.helpers import expand_lsoa_codes
from app.services.tab_property import fetch_property_market
from app.services.tab_lifestyle import fetch_lifestyle_connectivity
from app.services.tab_environment import fetch_environment_safety
from app.services.tab_community import fetch_community_education
from app.services.tab_governance import fetch_local_governance
from app.services.comparable_areas import find_comparable_lads

router = APIRouter()

TAB_HANDLERS = {
    "Property & Market": fetch_property_market,
    "Lifestyle & Connectivity": fetch_lifestyle_connectivity,
    "Environment & Safety": fetch_environment_safety,
    "Community & Education": fetch_community_education,
    "Local Governance": fetch_local_governance,
}


@router.get("/area/{lad_code}/{ward_code}/{lsoa_code}")
async def get_area_data(
    lad_code: str,
    ward_code: str,
    lsoa_code: str,
    tab: str = Query("Property & Market", description="Tab name"),
    db: AsyncSession = Depends(get_db),
):
    # Validate ONS codes to prevent injection via path params
    for code, name in [(lad_code, "lad_code"), (ward_code, "ward_code"), (lsoa_code, "lsoa_code")]:
        if not _CODE_RE.match(code):
            raise HTTPException(status_code=400, detail=f"Invalid {name}: must be an ONS code (e.g. E09000033) or '_'")

    handler = TAB_HANDLERS.get(tab)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tab: {tab}. Valid tabs: {list(TAB_HANDLERS.keys())}",
        )

    cache_key = f"area:{lad_code}:{ward_code}:{lsoa_code}:{tab}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Bible Rule 4: Expand search key to all applicable LSOAs
    lsoa_codes, centroid_lat, centroid_lon = await expand_lsoa_codes(
        db, lad_code, ward_code, lsoa_code
    )

    metrics = await handler(
        db, lad_code=lad_code, ward_code=ward_code,
        lsoa_codes=lsoa_codes, centroid_lat=centroid_lat, centroid_lon=centroid_lon,
    )
    result = {"tab": tab, "metrics": metrics}
    await cache_set(cache_key, result, ttl=3600)
    return result


@router.get("/price-history/{lad_code}/{ward_code}/{lsoa_code}")
async def get_price_history(
    lad_code: str,
    ward_code: str,
    lsoa_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Return yearly avg prices for LSOA(s) (local) and LAD (regional comparison)."""
    cache_key = f"price_history:{lad_code}:{ward_code}:{lsoa_code}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Bible Rule 4: Expand to all applicable LSOAs
    lsoa_codes, _, _ = await expand_lsoa_codes(db, lad_code, ward_code, lsoa_code)

    # Local (LSOA) — yearly average across all property types and all applicable LSOAs
    local_res = await db.execute(
        text("""
            SELECT date_trunc('year', year_month)::date AS year,
                   AVG(avg_price)::int AS avg_price,
                   AVG(median_price)::int AS median_price,
                   SUM(transaction_count) AS transactions
            FROM core_property_prices_lsoa
            WHERE lsoa_code = ANY(:codes)
              AND property_type IN ('D','S','T','F')
            GROUP BY 1 ORDER BY 1
        """),
        {"codes": lsoa_codes},
    )
    local_rows = [dict(r) for r in local_res.mappings().all()]

    # Regional (LAD) — yearly average across all property types
    lad_res = await db.execute(
        text("""
            SELECT date_trunc('year', year_month)::date AS year,
                   AVG(avg_price)::int AS avg_price,
                   AVG(median_price)::int AS median_price,
                   SUM(transaction_count) AS transactions
            FROM core_property_prices_lad
            WHERE lad_code = :lad
              AND property_type IN ('D','S','T','F')
            GROUP BY 1 ORDER BY 1
        """),
        {"lad": lad_code},
    )
    lad_rows = [dict(r) for r in lad_res.mappings().all()]

    # Get LAD name for the chart legend
    lad_name_res = await db.execute(
        text("SELECT lad_name FROM core_lad_boundaries WHERE lad_code = :lad"),
        {"lad": lad_code},
    )
    lad_name_row = lad_name_res.mappings().first()
    lad_name = lad_name_row["lad_name"] if lad_name_row else lad_code

    # Serialize dates as year strings
    for row in local_rows:
        row["year"] = str(row["year"].year) if hasattr(row["year"], "year") else str(row["year"])[:4]
    for row in lad_rows:
        row["year"] = str(row["year"].year) if hasattr(row["year"], "year") else str(row["year"])[:4]

    result = {
        "local": local_rows,
        "regional": lad_rows,
        "regional_name": lad_name,
    }
    await cache_set(cache_key, result, ttl=86400)
    return result


@router.get("/district-price-history/{postcode_district}")
async def get_district_price_history(
    postcode_district: str,
    db: AsyncSession = Depends(get_db),
):
    """Return yearly avg prices by property type for a postcode district."""
    # Validate: only alphanumeric up to 4 chars
    import re as _re
    if not _re.match(r'^[A-Z]{1,2}\d{1,2}[A-Z]?$', postcode_district.upper()):
        raise HTTPException(status_code=400, detail="Invalid postcode district")
    district = postcode_district.upper()

    cache_key = f"district_price_history:{district}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    res = await db.execute(
        text("""
            SELECT date_trunc('year', year_month)::date AS year,
                   property_type,
                   AVG(avg_price)::int AS avg_price,
                   AVG(median_price)::int AS median_price,
                   SUM(transaction_count) AS transactions
            FROM core_property_prices_district
            WHERE postcode_district = :district
              AND property_type IN ('D','S','T','F')
            GROUP BY 1, 2 ORDER BY 1, 2
        """),
        {"district": district},
    )
    rows = [dict(r) for r in res.mappings().all()]
    for row in rows:
        row["year"] = str(row["year"].year) if hasattr(row["year"], "year") else str(row["year"])[:4]

    TYPE_NAMES = {"D": "Detached", "S": "Semi-Detached", "T": "Terraced", "F": "Flat"}
    by_type: dict = {}
    for row in rows:
        pt = row["property_type"].strip()
        label = TYPE_NAMES.get(pt, pt)
        if label not in by_type:
            by_type[label] = []
        by_type[label].append({
            "year": row["year"],
            "avg_price": row["avg_price"],
            "median_price": row["median_price"],
            "transactions": row["transactions"],
        })

    result = {"district": district, "by_type": by_type}
    await cache_set(cache_key, result, ttl=86400)
    return result


@router.get("/aq-history/{lad_code}")
async def get_aq_history(
    lad_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Return yearly PM2.5/NO2 averages for a LAD (7-year trend)."""
    cache_key = f"aq_history:{lad_code}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Local LAD
    local_res = await db.execute(
        text("""
            SELECT year, pm25_ugm3, no2_ugm3, pm10_ugm3
            FROM core_air_quality_lad
            WHERE lad_code = :lad
            ORDER BY year
        """),
        {"lad": lad_code},
    )
    local_rows = [dict(r) for r in local_res.mappings().all()]

    # National average per year
    national_res = await db.execute(
        text("""
            SELECT year,
                   ROUND(AVG(pm25_ugm3)::numeric, 2) AS pm25_ugm3,
                   ROUND(AVG(no2_ugm3)::numeric, 2) AS no2_ugm3,
                   ROUND(AVG(pm10_ugm3)::numeric, 2) AS pm10_ugm3
            FROM core_air_quality_lad
            GROUP BY year ORDER BY year
        """),
    )
    national_rows = [dict(r) for r in national_res.mappings().all()]

    # LAD name
    lad_name_res = await db.execute(
        text("SELECT lad_name FROM core_lad_boundaries WHERE lad_code = :lad"),
        {"lad": lad_code},
    )
    lad_name_row = lad_name_res.mappings().first()
    lad_name = lad_name_row["lad_name"] if lad_name_row else lad_code

    # Serialize numeric types
    for row in local_rows + national_rows:
        for k in ("pm25_ugm3", "no2_ugm3", "pm10_ugm3"):
            if row.get(k) is not None:
                row[k] = float(row[k])

    result = {
        "local": local_rows,
        "national": national_rows,
        "lad_name": lad_name,
    }
    await cache_set(cache_key, result, ttl=86400)
    return result


@router.get("/comparable/{lad_code}")
async def get_comparable_areas(
    lad_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Find the 5 most similar LADs based on price, rent, earnings, AQ, HPI."""
    cache_key = f"comparable:{lad_code}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    result = await find_comparable_lads(db, lad_code=lad_code, limit=5)

    # Serialize Decimal types
    for area in result.get("comparable", []):
        for k in ("avg_price", "median_rent", "earnings", "pm25", "hpi_yoy", "distance"):
            if area.get(k) is not None:
                area[k] = float(area[k])
    for k in ("avg_price", "median_rent", "earnings"):
        if result.get("target", {}).get(k) is not None:
            result["target"][k] = float(result["target"][k])

    await cache_set(cache_key, result, ttl=86400)
    return result


@router.get("/map-pois")
async def get_map_pois(
    lat: float = Query(...),
    lon: float = Query(...),
    tab: str = Query("Property & Market"),
    db: AsyncSession = Depends(get_db),
):
    """Return nearby POIs relevant to the active tab for map display."""
    cache_key = f"pois:{round(lat,4)}:{round(lon,4)}:{tab}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    features = []

    if tab == "Community & Education":
        # Schools within 2km
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
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": {
                    "name": r["school_name"],
                    "category": "school",
                    "phase": r["phase"],
                    "ofsted": r["ofsted_rating"],
                    "dist_m": round(float(r["dist_m"])),
                },
            })

    elif tab == "Environment & Safety":
        # Flood Zones 2 & 3 within 2km — Bible: "Expandable shows map of Flood Zones 2 & 3"
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

    elif tab == "Lifestyle & Connectivity":
        # Rail stations within 3km — deduplicated by base name (strip standard suffixes)
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
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": {
                    "name": r["base_name"],
                    "category": "station",
                    "type": r["stop_type"],
                    "dist_m": round(float(r["dist_m"])),
                },
            })

        # EV chargers within 1km
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
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": {
                    "name": r["name"] or "EV Charger",
                    "category": "ev_charger",
                    "operator": r["operator"],
                    "connectors": r["connector_count"],
                    "max_kw": float(r["max_power_kw"]) if r["max_power_kw"] else None,
                    "dist_m": round(float(r["dist_m"])),
                },
            })

    result = {"type": "FeatureCollection", "features": features}
    await cache_set(cache_key, result, ttl=86400)
    return result


@router.get("/boundary/{ward_code}")
async def get_ward_boundary(
    ward_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Bible 6.2.4: Return ward boundary as GeoJSON for map display."""
    cache_key = f"boundary:{ward_code}"
    cached = await cache_get(cache_key)
    if cached:
        return JSONResponse(content=cached)

    result = await db.execute(
        text("""
            SELECT ward_name, ST_AsGeoJSON(geom, 6) as geojson
            FROM core_ward_boundaries WHERE ward_code = :code
        """),
        {"code": ward_code},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Ward boundary not found")

    feature = {
        "type": "Feature",
        "properties": {"ward_code": ward_code, "ward_name": row["ward_name"]},
        "geometry": json.loads(row["geojson"]),
    }
    await cache_set(cache_key, feature, ttl=86400)
    return JSONResponse(content=feature)


@router.get("/boundary/lsoa/{lsoa_code}")
async def get_lsoa_boundary(
    lsoa_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Return LSOA boundary as GeoJSON from core_lsoa_boundaries."""
    cache_key = f"lsoa_boundary:{lsoa_code}"
    cached = await cache_get(cache_key)
    if cached:
        return JSONResponse(content=cached)

    result = await db.execute(
        text("""
            SELECT lsoa_name, ST_AsGeoJSON(geom, 6) as geojson
            FROM core_lsoa_boundaries WHERE lsoa_code = :code
        """),
        {"code": lsoa_code},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="LSOA boundary not found")

    feature = {
        "type": "Feature",
        "properties": {"lsoa_code": lsoa_code, "lsoa_name": row["lsoa_name"]},
        "geometry": json.loads(row["geojson"]),
    }
    await cache_set(cache_key, feature, ttl=86400)
    return JSONResponse(content=feature)
