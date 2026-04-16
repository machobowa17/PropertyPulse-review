"""
Area endpoints — orchestrator module.

Includes sub-routers for:
  - area_tabs:         GET /area (tab data)
  - area_price:        GET /price-history, /price-by-type, /transactions
  - area_supplemental: GET /aq-history, /comparable
  - area_map:          GET /map-pois, /map-choropleth
  - area_boundary:     GET /boundary
"""
from fastapi import APIRouter

from app.routers.area_tabs import router as tabs_router
from app.routers.area_price import router as price_router
from app.routers.area_supplemental import router as supplemental_router
from app.routers.area_map import router as map_router
from app.routers.area_boundary import router as boundary_router

router = APIRouter()

router.include_router(tabs_router)
router.include_router(price_router)
router.include_router(supplemental_router)
router.include_router(map_router)
router.include_router(boundary_router)
