"""
GET /api/v1/area/{lad_code}/{ward_code}/{lsoa_code}?tab={tab_name}
GET /api/v1/boundary/{ward_code}
Build Bible Part 6, Sections 6.1 & 6.2.4 — Data + Boundary Endpoints
"""
import json
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.tab_property import fetch_property_market
from app.services.tab_lifestyle import fetch_lifestyle_connectivity
from app.services.tab_environment import fetch_environment_safety
from app.services.tab_community import fetch_community_education
from app.services.tab_governance import fetch_local_governance

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
    handler = TAB_HANDLERS.get(tab)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tab: {tab}. Valid tabs: {list(TAB_HANDLERS.keys())}",
        )

    metrics = await handler(db, lad_code=lad_code, ward_code=ward_code, lsoa_code=lsoa_code)
    return {"tab": tab, "metrics": metrics}


@router.get("/boundary/{ward_code}")
async def get_ward_boundary(
    ward_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Bible 6.2.4: Return ward boundary as GeoJSON for map display."""
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
    return JSONResponse(content=feature)
