"""Nursery API endpoints.

Serves nursery/childcare provider data — nearby nurseries, detail profiles.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from psycopg2.extras import RealDictCursor

from api.db import get_conn, put_conn

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/nearby")
def nearby_nurseries(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_m: int = Query(2000, ge=100, le=10000, description="Search radius in metres"),
    limit: int = Query(50, ge=1, le=200),
):
    """Return nurseries near a lat/lon point."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    n.urn, n.name, n.type, n.postcode,
                    n.latitude, n.longitude,
                    n.la_name, n.ofsted_rating, n.last_inspection,
                    n.max_places,
                    ROUND(ST_Distance(
                        n.geom::geography,
                        ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography
                    ))::int AS distance_m
                FROM schools.nurseries n
                WHERE n.geom IS NOT NULL
                  AND ST_DWithin(
                      n.geom::geography,
                      ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography,
                      %(radius)s
                  )
                ORDER BY distance_m
                LIMIT %(limit)s
                """,
                {"lat": lat, "lon": lon, "radius": radius_m, "limit": limit},
            )
            rows = [_serialize(r) for r in cur.fetchall()]
            return {"nurseries": rows, "count": len(rows)}
    except Exception as e:
        logger.exception("Nearby nurseries query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


@router.get("/by-la")
def nurseries_by_la(
    la_name: str = Query(..., description="Local authority name"),
    limit: int = Query(100, ge=1, le=500),
):
    """Return nurseries in a local authority area."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    n.urn, n.name, n.type, n.postcode,
                    n.latitude, n.longitude,
                    n.la_name, n.ofsted_rating, n.last_inspection,
                    n.max_places
                FROM schools.nurseries n
                WHERE n.la_name = %(la_name)s
                ORDER BY n.name
                LIMIT %(limit)s
                """,
                {"la_name": la_name, "limit": limit},
            )
            rows = [_serialize(r) for r in cur.fetchall()]
            return {"nurseries": rows, "count": len(rows)}
    except Exception as e:
        logger.exception("Nurseries by LA query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


@router.get("/summary")
def nurseries_summary(
    lat: float = Query(None),
    lon: float = Query(None),
    radius_m: int = Query(2000, ge=100, le=10000),
    la_name: Optional[str] = Query(None),
):
    """Return nursery Ofsted rating distribution near a point or in an LA."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            params = {}
            if la_name:
                area_filter = "n.la_name = %(la_name)s"
                params["la_name"] = la_name
            elif lat and lon:
                area_filter = """n.geom IS NOT NULL
                      AND ST_DWithin(
                          n.geom::geography,
                          ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography,
                          %(radius)s
                      )"""
                params["lat"] = lat
                params["lon"] = lon
                params["radius"] = radius_m
            else:
                raise HTTPException(400, "Provide lat+lon or la_name")

            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE ofsted_rating = 'Outstanding') AS outstanding,
                    COUNT(*) FILTER (WHERE ofsted_rating = 'Good') AS good,
                    COUNT(*) FILTER (WHERE ofsted_rating = 'Requires Improvement') AS requires_improvement,
                    COUNT(*) FILTER (WHERE ofsted_rating = 'Inadequate') AS inadequate,
                    COUNT(*) FILTER (WHERE ofsted_rating = 'Met') AS met,
                    COUNT(*) FILTER (WHERE ofsted_rating IS NULL) AS not_inspected
                FROM schools.nurseries n
                WHERE {area_filter}
                """,
                params,
            )
            row = cur.fetchone()
            return _serialize(row) if row else {}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Nurseries summary query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


@router.get("/{urn}")
def nursery_detail(urn: str):
    """Return detail for a single nursery."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM schools.nurseries WHERE urn = %(urn)s
                """,
                {"urn": urn},
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, f"Nursery URN {urn} not found")
            return _serialize(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Nursery detail query failed: %s", e)
        raise HTTPException(500, f"Query error: {e}")
    finally:
        put_conn(conn)


def _serialize(row):
    """Convert RealDictRow to JSON-safe dict."""
    if row is None:
        return None
    import datetime
    import decimal
    result = {}
    for k, v in row.items():
        if isinstance(v, decimal.Decimal):
            result[k] = float(v)
        elif isinstance(v, (datetime.date, datetime.datetime)):
            result[k] = v.isoformat()
        elif isinstance(v, memoryview):
            result[k] = None
        elif k == "geom":
            continue
        else:
            result[k] = v
    return result
