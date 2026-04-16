"""
GET /api/v1/commute?session_key=&destination=

This endpoint is intentionally withdrawn for now.
The previous implementation returned heuristic travel-time estimates derived
from straight-line distance and fixed mode assumptions, which is not acceptable
for a source-backed production portal.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.errors import http_error
from app.services.session_helpers import require_session

router = APIRouter()


@router.get("/commute")
async def commute(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    destination: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
):
    del destination
    del db

    sess = await require_session(session_key)

    raise http_error(
        501,
        "COMMUTE_ESTIMATOR_WITHDRAWN",
        "The commute estimator is not yet implemented. A source-backed replacement is planned.",
    )
