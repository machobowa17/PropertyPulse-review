"""
backend/app/routers/health.py — GET /health

Checks DB connectivity (SELECT 1) and Redis ping.
Returns 200 on ok, 503 on degraded.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import get_db
from app.cache import get_redis

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
    except Exception:
        pass

    # Redis check
    try:
        r = await get_redis()
        if r:
            await r.ping()
            redis_status = "ok"
    except Exception:
        pass

    status = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    http_code = 200 if status == "ok" else 503

    return JSONResponse(
        status_code=http_code,
        content={"status": status, "db": db_status, "redis": redis_status},
    )
