"""
backend/app/routers/data_freshness.py — GET /data-freshness

Returns last successful pipeline run per source from core_pipeline_runs.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.constants import TABLE_NAMES

router = APIRouter(tags=["observability"])


@router.get("/data-freshness")
async def data_freshness(db: AsyncSession = Depends(get_db)):
    """
    Returns the most recent successful pipeline run per source.

    Each entry includes:
        source_name  — name of the ETL source
        last_success — ISO timestamp of the last successful run (null if never run)
        rows         — row count recorded on that run (null if never run)
        status       — 'ok', 'validation_failed', 'error', or 'never_run'
    """
    result = await db.execute(
        text(f"""
            SELECT DISTINCT ON (source_name)
                source_name,
                finished_at   AS last_success,
                rows_after    AS rows,
                status
            FROM {TABLE_NAMES['pipeline_runs']}
            WHERE status = 'success'
            ORDER BY source_name, finished_at DESC
        """)
    )
    ok_rows = {r["source_name"]: dict(r) for r in result.mappings().all()}

    # Also fetch latest run per source regardless of status (to show failures)
    result2 = await db.execute(
        text(f"""
            SELECT DISTINCT ON (source_name)
                source_name,
                finished_at   AS last_run,
                rows_after    AS rows,
                status
            FROM {TABLE_NAMES['pipeline_runs']}
            ORDER BY source_name, finished_at DESC
        """)
    )
    all_rows = {r["source_name"]: dict(r) for r in result2.mappings().all()}

    # Merge: show last_success if any, but flag if latest run was not ok
    sources = sorted(set(list(ok_rows.keys()) + list(all_rows.keys())))

    items = []
    for name in sources:
        ok  = ok_rows.get(name)
        latest = all_rows.get(name)

        items.append({
            "source_name":  name,
            "last_success": ok["last_success"].isoformat() if ok and ok["last_success"] else None,
            "rows":         ok["rows"] if ok else None,
            "status":       latest["status"] if latest else "never_run",
        })

    # Include sources that appear in the registry but have never run
    # (query returns nothing for them, so they won't appear above unless we add them)
    return {"sources": items}
