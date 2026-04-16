"""
GET /api/v1/boundary
Boundary GeoJSON endpoint — returns ward/LSOA, LAD, county, place, or ward boundary.
"""
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import TABLE_NAMES
from app.database import get_db
from app.errors import http_error
from app.cache import cache_get, cache_set
from app.services.session_helpers import (
    session_boundary_source,
    session_boundary_id,
    require_session,
)

router = APIRouter()


@router.get("/boundary")
async def get_boundary(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    db: AsyncSession = Depends(get_db),
):
    """Return the appropriate boundary GeoJSON based on session boundary_source."""
    sess = await require_session(session_key)
    source = session_boundary_source(sess)
    bid = session_boundary_id(sess)

    if source == "ward_lsoa":
        # Postcode search: return FeatureCollection with ward + LSOA boundaries
        ward_code = sess.get("ward_code", "_")
        lsoa_code_val = sess.get("lsoa_code", "_")
        features = []

        # Ward boundary
        ward_cache = f"boundary:ward:{ward_code}"
        ward_feat = await cache_get(ward_cache)
        if not ward_feat:
            res = await db.execute(
                text("SELECT ward_name, ST_AsGeoJSON(geom, 6) as geojson FROM core_ward_boundaries WHERE ward_code = :code"),
                {"code": ward_code},
            )
            row = res.mappings().first()
            if row:
                ward_feat = {
                    "type": "Feature",
                    "properties": {"ward_code": ward_code, "ward_name": row["ward_name"], "layer": "ward"},
                    "geometry": json.loads(row["geojson"]),
                }
                await cache_set(ward_cache, ward_feat, ttl=86400)
        if ward_feat:
            features.append(ward_feat)

        # LSOA boundary
        lsoa_cache = f"boundary:lsoa:{lsoa_code_val}"
        lsoa_feat = await cache_get(lsoa_cache)
        if not lsoa_feat:
            res = await db.execute(
                text("SELECT lsoa_name, ST_AsGeoJSON(geom, 6) as geojson FROM core_lsoa_boundaries WHERE lsoa_code = :code"),
                {"code": lsoa_code_val},
            )
            row = res.mappings().first()
            if row:
                lsoa_feat = {
                    "type": "Feature",
                    "properties": {"lsoa_code": lsoa_code_val, "lsoa_name": row["lsoa_name"], "layer": "lsoa"},
                    "geometry": json.loads(row["geojson"]),
                }
                await cache_set(lsoa_cache, lsoa_feat, ttl=86400)
        if lsoa_feat:
            features.append(lsoa_feat)

        return JSONResponse(content={"type": "FeatureCollection", "features": features})

    elif source == "lad":
        cache_key = f"boundary:lad:{bid}"
        cached = await cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)
        res = await db.execute(
            text("SELECT lad_name, ST_AsGeoJSON(geom, 6) as geojson FROM core_lad_boundaries WHERE lad_code = :code"),
            {"code": bid},
        )
        row = res.mappings().first()
        if not row:
            raise http_error(404, "BOUNDARY_NOT_FOUND", "LAD boundary not found")
        feature = {
            "type": "Feature",
            "properties": {"lad_code": bid, "lad_name": row["lad_name"]},
            "geometry": json.loads(row["geojson"]),
        }
        collection = {"type": "FeatureCollection", "features": [feature]}
        await cache_set(cache_key, collection, ttl=86400)
        return JSONResponse(content=collection)

    elif source == "county":
        cache_key = f"boundary:county:{bid}"
        cached = await cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)
        res = await db.execute(
            text("SELECT county_name, ST_AsGeoJSON(geom, 6) as geojson FROM core_county_boundaries WHERE county_name = :name"),
            {"name": bid},
        )
        row = res.mappings().first()
        if not row:
            raise http_error(404, "BOUNDARY_NOT_FOUND", "County boundary not found")
        feature = {
            "type": "Feature",
            "properties": {"county_name": row["county_name"]},
            "geometry": json.loads(row["geojson"]),
        }
        collection = {"type": "FeatureCollection", "features": [feature]}
        await cache_set(cache_key, collection, ttl=86400)
        return JSONResponse(content=collection)

    elif source == "place":
        pn = sess.get("place_name") or bid
        plad = sess.get("place_lad_code", "")
        pt = sess.get("place_type", "Suburban Area")
        cache_key = f"boundary:place:{pn}:{plad}"
        cached = await cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        # Use pre-computed ST_Union from core_place_boundaries_union.
        # Avoids live spatial aggregation under concurrent load.
        # Falls back to on-the-fly ST_Union if row is missing (e.g. ETL not yet re-run).
        res = await db.execute(
            text(f"SELECT ST_AsGeoJSON(geom, 6) AS geojson FROM {TABLE_NAMES['place_boundaries_union']} WHERE place_name = :name AND lad_code = :lad"),
            {"name": pn, "lad": plad},
        )
        row = res.mappings().first()

        if not row or not row["geojson"]:
            use_town = pt in ('City', 'Town')
            primary = TABLE_NAMES["place_lsoa_mapping_town"] if use_town else TABLE_NAMES["place_lsoa_mapping"]
            fallback_tbl = TABLE_NAMES["place_lsoa_mapping"] if use_town else TABLE_NAMES["place_lsoa_mapping_town"]
            res2 = await db.execute(
                text(f"""
                    SELECT ST_AsGeoJSON(ST_Union(lb.geom), 6) as geojson
                    FROM core_lsoa_boundaries lb
                    JOIN {primary} m ON lb.lsoa_code = m.lsoa_code
                    WHERE m.place_name = :name AND m.lad_code = :lad
                """),
                {"name": pn, "lad": plad},
            )
            row = res2.mappings().first()
            if not row or not row["geojson"]:
                res3 = await db.execute(
                    text(f"""
                        SELECT ST_AsGeoJSON(ST_Union(lb.geom), 6) as geojson
                        FROM core_lsoa_boundaries lb
                        JOIN {fallback_tbl} m ON lb.lsoa_code = m.lsoa_code
                        WHERE m.place_name = :name AND m.lad_code = :lad
                    """),
                    {"name": pn, "lad": plad},
                )
                row = res3.mappings().first()

        if not row or not row["geojson"]:
            raise http_error(404, "BOUNDARY_NOT_FOUND", "Place boundary not found")

        feature = {
            "type": "Feature",
            "properties": {"place_name": pn, "lad_code": plad},
            "geometry": json.loads(row["geojson"]),
        }
        collection = {"type": "FeatureCollection", "features": [feature]}
        await cache_set(cache_key, collection, ttl=86400)
        return JSONResponse(content=collection)

    elif source == "ward":
        cache_key = f"boundary:ward:{bid}"
        cached = await cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)
        res = await db.execute(
            text("SELECT ward_name, ST_AsGeoJSON(geom, 6) as geojson FROM core_ward_boundaries WHERE ward_code = :code"),
            {"code": bid},
        )
        row = res.mappings().first()
        if not row:
            raise http_error(404, "BOUNDARY_NOT_FOUND", "Ward boundary not found")
        feature = {
            "type": "Feature",
            "properties": {"ward_code": bid, "ward_name": row["ward_name"]},
            "geometry": json.loads(row["geojson"]),
        }
        collection = {"type": "FeatureCollection", "features": [feature]}
        await cache_set(cache_key, collection, ttl=86400)
        return JSONResponse(content=collection)

    raise http_error(400, "INVALID_BOUNDARY_SOURCE", f"Unknown boundary_source: {source}")
