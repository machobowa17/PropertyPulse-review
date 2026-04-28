"""
backend/app/routers/health.py — GET /health, POST /admin/clear-cache

Checks DB connectivity (SELECT 1) and Redis ping.
Returns 200 on ok, 503 on degraded.
"""

import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import get_db
from app.cache import get_redis

log = logging.getLogger(__name__)
router = APIRouter(tags=["observability"])


@router.get("/health")
async def health():
    """
    Service health check.

    Returns:
        200  {status: "ok",       db: "ok",    redis: "ok"}
        503  {status: "degraded", db: <state>, redis: <state>}
    """
    db_status    = "error"
    redis_status = "error"

    # Database check
    try:
        async for db in get_db():
            await db.execute(text("SELECT 1"))
            db_status = "ok"
            break
    except Exception as e:
        log.warning("Health check: DB unreachable — %s", e)

    # Redis check
    try:
        r = await get_redis()
        if r:
            await r.ping()
            redis_status = "ok"
    except Exception as e:
        log.warning("Health check: Redis unreachable — %s", e)

    status = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    http_code = 200 if status == "ok" else 503

    return JSONResponse(
        status_code=http_code,
        content={"status": status, "db": db_status, "redis": redis_status},
    )


@router.post("/admin/clear-cache")
async def clear_cache():
    """
    Clear area/resolve caches after ETL data refresh.

    Deletes Redis keys matching: area:*, area_scope:*, resolve:*
    Call this after ETL completes to ensure fresh data is served.
    Only accessible from localhost (nginx blocks external access).
    """
    r = await get_redis()
    if not r:
        return JSONResponse(status_code=503, content={"error": "Redis unavailable"})
    deleted = 0
    for pattern in ("area:*", "area_scope:*", "resolve:*"):
        cursor = "0"
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=pattern, count=500)
            if keys:
                deleted += await r.delete(*keys)
            if cursor == 0 or cursor == "0":
                break
    log.info("clear-cache: deleted %d Redis keys", deleted)
    return {"deleted": deleted}
