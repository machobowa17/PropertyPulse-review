"""
GET /api/v1/resolve?q={search_key}
Build Bible Part 6, Section 6.1 — Geo-Resolution Endpoint
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.geo_resolver import resolve_search

router = APIRouter()


@router.get("/resolve")
async def resolve(
    q: str = Query(..., description="Search key: postcode or place name"),
    db: AsyncSession = Depends(get_db),
):
    return await resolve_search(db, q)
