"""
GET /api/v1/area?session_key=&tab=
GET /api/v1/boundary?session_key=
Build Bible Part 6, Sections 6.1 & 6.2.4 — Data + Boundary Endpoints

All data endpoints accept a single session_key (created at /resolve time).
The session contains all derived values (LSOAs, centroid, parent comparison, etc.).
"""
import json
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import TABLE_NAMES, PRICE_TYPES, TYPE_NAMES, TENURE_NAMES
from app.database import get_db
from app.errors import http_error
from app.cache import cache_get, cache_set
from app.services.helpers import get_lsoa_session
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


async def _require_session(session_key: str | None) -> dict:
    """Validate and retrieve session, raising on missing/expired."""
    if not session_key:
        raise http_error(400, "SESSION_KEY_REQUIRED", "session_key is required")
    sess = await get_lsoa_session(session_key)
    if not sess:
        raise http_error(410, "SESSION_EXPIRED", "Session expired — please search again")
    return sess


# ---------------------------------------------------------------------------
# Tab data
# ---------------------------------------------------------------------------

@router.get("/area")
async def get_area_data(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    tab: str = Query("Property & Market", description="Tab name"),
    db: AsyncSession = Depends(get_db),
):
    handler = TAB_HANDLERS.get(tab)
    if not handler:
        raise http_error(400, "INVALID_TAB", f"Unknown tab: {tab}. Valid tabs: {list(TAB_HANDLERS.keys())}")

    cache_key = f"area:{session_key}:{tab}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    sess = await _require_session(session_key)

    metrics = await handler(
        db,
        lad_code=sess["lad_code"],
        ward_code=sess["ward_code"],
        lsoa_codes=sess["lsoa_codes"],
        centroid_lat=sess.get("lat"),
        centroid_lon=sess.get("lon"),
        search_mode=sess.get("search_mode", "postcode"),
        local_lads=sess.get("local_lads", []),
        parent_lads=sess.get("parent_lad_codes", []),
        parent_name=sess.get("parent_name", "England"),
        boundary_source=sess.get("boundary_source", "lad"),
    )
    result = {"tab": tab, "metrics": metrics}
    await cache_set(cache_key, result, ttl=3600)
    return result


# ---------------------------------------------------------------------------
# Price history
# ---------------------------------------------------------------------------

@router.get("/price-history")
async def get_price_history(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    db: AsyncSession = Depends(get_db),
):
    """Return yearly avg prices: local (matching search resolution) vs parent region."""
    cache_key = f"price_history:{session_key}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    sess = await _require_session(session_key)
    parent_lad_codes = sess.get("parent_lad_codes", [])
    parent_name = sess.get("parent_name", "England")
    boundary_source = sess.get("boundary_source", "lad")

    # Local — scope determined by what the search key resolved to
    if boundary_source in ("lad", "county"):
        local_lads = sess.get("local_lads", [])
        _lsoa_filter = "lsoa_code IN (SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = ANY(:lads))"
        _local_params = {"lads": local_lads, "price_types": list(PRICE_TYPES)}
    else:
        lsoa_codes = sess["lsoa_codes"]
        _lsoa_filter = "lsoa_code = ANY(:codes)"
        _local_params = {"codes": lsoa_codes, "price_types": list(PRICE_TYPES)}

    # True avg + true median from raw transaction prices (not pre-aggregated columns)
    local_res = await db.execute(
        text(f"""
            SELECT date_trunc('year', date_of_transfer)::date AS year,
                   ROUND(AVG(price))::int AS avg_price,
                   ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::int AS median_price,
                   COUNT(*) AS transactions,
                   ROUND(AVG(price::numeric / NULLIF(floor_area_sqm::numeric * 10.7639, 0)))::int AS avg_ppsf
            FROM core_property_transactions
            WHERE {_lsoa_filter}
              AND property_type = ANY(:price_types)
            GROUP BY 1 ORDER BY 1
        """),
        _local_params,
    )
    local_rows = [dict(r) for r in local_res.mappings().all()]

    # Regional — parent comparison line. True median from pre-computed materialized view
    # (mv_parent_yearly_price_stats), refreshed weekly. Avoids PERCENTILE_CONT on millions of rows.
    parent_res = await db.execute(
        text("""
            SELECT year::text AS year,
                   avg_price,
                   median_price,
                   transactions
            FROM mv_parent_yearly_price_stats
            WHERE parent_comparison = :parent_name
              AND property_type = 'ALL'
            ORDER BY year
        """),
        {"parent_name": parent_name},
    )
    parent_rows = [dict(r) for r in parent_res.mappings().all()]

    # Parent avg_ppsf by year (not in MV, computed from raw transactions)
    if parent_lad_codes:
        parent_ppsf_res = await db.execute(
            text("""
                SELECT EXTRACT(YEAR FROM date_of_transfer)::int AS yr,
                       ROUND(AVG(price::numeric / NULLIF(floor_area_sqm::numeric * 10.7639, 0)))::int AS avg_ppsf
                FROM core_property_transactions
                WHERE lsoa_code IN (SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = ANY(:lads))
                  AND property_type = ANY(:price_types)
                  AND floor_area_sqm > 0
                GROUP BY 1
            """),
            {"lads": parent_lad_codes, "price_types": list(PRICE_TYPES)},
        )
        parent_ppsf_by_year = {str(r["yr"]): int(r["avg_ppsf"]) for r in parent_ppsf_res.mappings().all() if r["avg_ppsf"]}
        for row in parent_rows:
            yr = str(row["year"]).strip()[:4]
            row["avg_ppsf"] = parent_ppsf_by_year.get(yr)

    # Serialize dates as year strings
    for row in local_rows:
        row["year"] = str(row["year"].year) if hasattr(row["year"], "year") else str(row["year"])[:4]
    for row in parent_rows:
        row["year"] = str(row["year"].year) if hasattr(row["year"], "year") else str(row["year"])[:4]

    # Bedroom breakdown — LAD-level only (core_price_by_bedrooms_lad is LAD-granularity)
    bedrooms_rows: list = []
    if boundary_source in ("lad", "county"):
        bedrooms_res = await db.execute(
            text("""
                SELECT year::text AS year,
                       bedrooms,
                       ROUND(AVG(avg_price))::int AS avg_price,
                       SUM(transaction_count) AS transaction_count
                FROM core_price_by_bedrooms_lad
                WHERE lad_code = ANY(:lads)
                  AND property_type = ANY(:price_types)
                  AND bedrooms BETWEEN 1 AND 5
                GROUP BY year, bedrooms
                ORDER BY year, bedrooms
            """),
            {"lads": local_lads, "price_types": list(PRICE_TYPES)},
        )
        bedrooms_rows = [dict(r) for r in bedrooms_res.mappings().all()]

    result = {
        "local": local_rows,
        "regional": parent_rows,
        "regional_name": parent_name,
        "by_bedrooms": bedrooms_rows,
    }
    await cache_set(cache_key, result, ttl=86400)
    return result


# ---------------------------------------------------------------------------
# District price history
# ---------------------------------------------------------------------------

@router.get("/price-by-type")
async def get_price_by_type(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    db: AsyncSession = Depends(get_db),
):
    """Return yearly avg prices by property type — table determined by search resolution."""
    cache_key = f"price_by_type:{session_key}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    sess = await _require_session(session_key)
    boundary_source = sess.get("boundary_source", "lad")

    if boundary_source in ("lad", "county"):
        local_lads = sess.get("local_lads", [])
        _lsoa_filter = "lsoa_code IN (SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = ANY(:lads))"
        _local_params = {"lads": local_lads, "price_types": list(PRICE_TYPES)}
    else:
        lsoa_codes = sess["lsoa_codes"]
        _lsoa_filter = "lsoa_code = ANY(:codes)"
        _local_params = {"codes": lsoa_codes, "price_types": list(PRICE_TYPES)}

    res = await db.execute(
        text(f"""
            SELECT date_trunc('year', date_of_transfer)::date AS year,
                   property_type,
                   ROUND(AVG(price))::int AS avg_price,
                   ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::int AS median_price,
                   COUNT(*) AS transactions
            FROM core_property_transactions
            WHERE {_lsoa_filter}
              AND property_type = ANY(:price_types)
            GROUP BY 1, 2 ORDER BY 1, 2
        """),
        _local_params,
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

    # Parent by type — true median from pre-computed materialized view
    parent_lad_codes = sess.get("parent_lad_codes", [])
    parent_name = sess.get("parent_name", "England")
    parent_res = await db.execute(
        text("""
            SELECT year::text AS year,
                   property_type,
                   avg_price,
                   median_price,
                   transactions
            FROM mv_parent_yearly_price_stats
            WHERE parent_comparison = :parent_name
              AND property_type != 'ALL'
            ORDER BY year, property_type
        """),
        {"parent_name": parent_name},
    )
    parent_rows = [dict(r) for r in parent_res.mappings().all()]

    parent_by_type: dict = {}
    for row in parent_rows:
        pt = row["property_type"].strip()
        label = TYPE_NAMES.get(pt, pt)
        if label not in parent_by_type:
            parent_by_type[label] = []
        parent_by_type[label].append({
            "year": row["year"],
            "avg_price": row["avg_price"],
            "median_price": row["median_price"],
            "transactions": row["transactions"],
        })

    # Rolling 12-month point appended as "Last 12m" to align chart with Q1 details bar chart.
    # Q1 (avg_price) details use rolling 12m; without this the chart's partial current-year
    # bucket showed a different number for the same type on the same page.
    rolling_res = await db.execute(
        text(f"""
            SELECT property_type,
                   ROUND(AVG(price))::int AS avg_price,
                   ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::int AS median_price,
                   COUNT(*) AS transactions
            FROM core_property_transactions
            WHERE {_lsoa_filter}
              AND property_type = ANY(:price_types)
              AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
            GROUP BY property_type
        """),
        _local_params,
    )
    for r in rolling_res.mappings().all():
        pt = r["property_type"].strip()
        label = TYPE_NAMES.get(pt, pt)
        if label in by_type:
            by_type[label].append({
                "year": "Last 12m",
                "avg_price": r["avg_price"],
                "median_price": r["median_price"],
                "transactions": r["transactions"],
            })

    if parent_lad_codes:
        parent_rolling_res = await db.execute(
            text("""
                SELECT property_type, avg_price, median_price, transactions
                FROM mv_parent_rolling_price_stats
                WHERE parent_comparison = :parent_name
                  AND property_type != 'ALL'
            """),
            {"parent_name": parent_name},
        )
        for r in parent_rolling_res.mappings().all():
            pt = r["property_type"].strip()
            label = TYPE_NAMES.get(pt, pt)
            if label in parent_by_type:
                parent_by_type[label].append({
                    "year": "Last 12m",
                    "avg_price": r["avg_price"],
                    "median_price": r["median_price"],
                    "transactions": r["transactions"],
                })

    # ------------------------------------------------------------------
    # PPSF enrichment — yearly data from UCL core_price_sqm_lsoa_yearly,
    # rolling "Last 12m" from master table floor_area_sqm (2024+ coverage).
    # ------------------------------------------------------------------
    if boundary_source in ("lad", "county"):
        ppsf_res = await db.execute(
            text("""
                SELECT y.year, y.property_type,
                       ROUND((SUM(y.avg_ppsm * y.transaction_count) / NULLIF(SUM(y.transaction_count), 0) / 10.7639)::numeric, 2) AS avg_ppsf,
                       SUM(y.transaction_count) AS ppsf_txns
                FROM core_price_sqm_lsoa_yearly y
                WHERE y.lsoa_code IN (
                    SELECT DISTINCT lsoa_code FROM core_postcodes
                    WHERE lad_code = ANY(:lads) AND lsoa_code IS NOT NULL
                )
                  AND y.property_type = ANY(:price_types)
                GROUP BY y.year, y.property_type ORDER BY y.year, y.property_type
            """),
            {"lads": local_lads, "price_types": list(PRICE_TYPES)},
        )
        ppsf_rolling_res = await db.execute(
            text("""
                SELECT t.property_type,
                       ROUND(AVG(t.price::numeric / (t.floor_area_sqm::numeric * 10.7639)), 2) AS avg_ppsf
                FROM core_property_transactions t
                WHERE t.lsoa_code IN (
                    SELECT DISTINCT lsoa_code FROM core_postcodes
                    WHERE lad_code = ANY(:lads) AND lsoa_code IS NOT NULL
                )
                  AND t.floor_area_sqm > 0
                  AND t.property_type = ANY(:price_types)
                  AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                GROUP BY 1
            """),
            {"lads": local_lads, "price_types": list(PRICE_TYPES)},
        )
    else:
        ppsf_res = await db.execute(
            text("""
                SELECT y.year, y.property_type,
                       ROUND((SUM(y.avg_ppsm * y.transaction_count) / NULLIF(SUM(y.transaction_count), 0) / 10.7639)::numeric, 2) AS avg_ppsf,
                       SUM(y.transaction_count) AS ppsf_txns
                FROM core_price_sqm_lsoa_yearly y
                WHERE y.lsoa_code = ANY(:codes)
                  AND y.property_type = ANY(:price_types)
                GROUP BY y.year, y.property_type ORDER BY y.year, y.property_type
            """),
            {"codes": lsoa_codes, "price_types": list(PRICE_TYPES)},
        )
        ppsf_rolling_res = await db.execute(
            text("""
                SELECT t.property_type,
                       ROUND(AVG(t.price::numeric / (t.floor_area_sqm::numeric * 10.7639)), 2) AS avg_ppsf
                FROM core_property_transactions t
                WHERE t.lsoa_code = ANY(:codes)
                  AND t.floor_area_sqm > 0
                  AND t.property_type = ANY(:price_types)
                  AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                GROUP BY 1
            """),
            {"codes": lsoa_codes, "price_types": list(PRICE_TYPES)},
        )

    ppsf_lookup: dict = {}
    for r in ppsf_res.mappings().all():
        pt = r["property_type"].strip()
        label = TYPE_NAMES.get(pt, pt)
        year_str = str(r["year"].year) if hasattr(r["year"], "year") else str(r["year"])[:4]
        ppsf_lookup[(label, year_str)] = float(r["avg_ppsf"]) if r["avg_ppsf"] else None
    for r in ppsf_rolling_res.mappings().all():
        pt = r["property_type"].strip()
        label = TYPE_NAMES.get(pt, pt)
        ppsf_lookup[(label, "Last 12m")] = float(r["avg_ppsf"]) if r["avg_ppsf"] else None

    for label, points in by_type.items():
        for point in points:
            point["avg_ppsf"] = ppsf_lookup.get((label, point["year"]))

    # Parent ppsf — yearly from UCL, rolling from master
    if parent_lad_codes:
        parent_ppsf_res = await db.execute(
            text("""
                SELECT y.year, y.property_type,
                       ROUND((SUM(y.avg_ppsm * y.transaction_count) / NULLIF(SUM(y.transaction_count), 0) / 10.7639)::numeric, 2) AS avg_ppsf
                FROM core_price_sqm_lsoa_yearly y
                WHERE y.lsoa_code IN (
                    SELECT DISTINCT lsoa_code FROM core_postcodes
                    WHERE lad_code = ANY(:lads) AND lsoa_code IS NOT NULL
                )
                  AND y.property_type = ANY(:price_types)
                GROUP BY y.year, y.property_type ORDER BY y.year, y.property_type
            """),
            {"lads": parent_lad_codes, "price_types": list(PRICE_TYPES)},
        )
        parent_ppsf_rolling_res = await db.execute(
            text("""
                SELECT t.property_type,
                       ROUND(AVG(t.price::numeric / (t.floor_area_sqm::numeric * 10.7639)), 2) AS avg_ppsf
                FROM core_property_transactions t
                WHERE t.lsoa_code IN (
                    SELECT DISTINCT lsoa_code FROM core_postcodes
                    WHERE lad_code = ANY(:lads) AND lsoa_code IS NOT NULL
                )
                  AND t.floor_area_sqm > 0
                  AND t.property_type = ANY(:price_types)
                  AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                GROUP BY 1
            """),
            {"lads": parent_lad_codes, "price_types": list(PRICE_TYPES)},
        )
        parent_ppsf_lookup: dict = {}
        for r in parent_ppsf_res.mappings().all():
            pt = r["property_type"].strip()
            label = TYPE_NAMES.get(pt, pt)
            year_str = str(r["year"].year) if hasattr(r["year"], "year") else str(r["year"])[:4]
            parent_ppsf_lookup[(label, year_str)] = float(r["avg_ppsf"]) if r["avg_ppsf"] else None
        for r in parent_ppsf_rolling_res.mappings().all():
            pt = r["property_type"].strip()
            label = TYPE_NAMES.get(pt, pt)
            parent_ppsf_lookup[(label, "Last 12m")] = float(r["avg_ppsf"]) if r["avg_ppsf"] else None
        for label, points in parent_by_type.items():
            for point in points:
                point["avg_ppsf"] = parent_ppsf_lookup.get((label, point["year"]))

    result = {"by_type": by_type, "parent_by_type": parent_by_type}
    await cache_set(cache_key, result, ttl=86400)
    return result


# ---------------------------------------------------------------------------
# Individual transactions (paginated, sortable, filterable)
# ---------------------------------------------------------------------------

_TXN_SORT_COLUMNS = {
    "date": "date_of_transfer",
    "price": "price",
    "type": "property_type",
    "beds": "bedrooms_estimated",
    "size": "floor_area_sqm",
    "tenure": "duration",
    "epc": "epc_rating",
}


@router.get("/transactions")
async def get_transactions(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort_by: str = Query("date"),
    sort_dir: str = Query("desc"),
    property_type: str | None = Query(None, description="Comma-separated type codes, e.g. D,S"),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated individual transactions for the session's area."""
    sess = await _require_session(session_key)
    boundary_source = sess.get("boundary_source", "lad")

    # Validate sort params
    sort_col = _TXN_SORT_COLUMNS.get(sort_by)
    if not sort_col:
        raise http_error(400, "INVALID_SORT", f"sort_by must be one of: {', '.join(_TXN_SORT_COLUMNS)}")
    if sort_dir not in ("asc", "desc"):
        raise http_error(400, "INVALID_SORT_DIR", "sort_dir must be 'asc' or 'desc'")

    # Build WHERE clause
    if boundary_source in ("lad", "county"):
        local_lads = sess.get("local_lads", [])
        area_filter = "lad_code = ANY(:area_codes)"
        params: dict = {"area_codes": local_lads}
    else:
        lsoa_codes = sess.get("lsoa_codes", [])
        area_filter = "lsoa_code = ANY(:area_codes)"
        params = {"area_codes": lsoa_codes}

    # Property type filter — default excludes 'O' (Other/commercial)
    if property_type:
        type_codes = [t.strip().upper() for t in property_type.split(",") if t.strip()]
        valid = {t for t in type_codes if t in TYPE_NAMES}
        if not valid:
            raise http_error(400, "INVALID_TYPE", f"property_type must contain valid codes: {', '.join(TYPE_NAMES)}")
        params["type_filter"] = list(valid)
    else:
        params["type_filter"] = list(PRICE_TYPES)
    type_filter_clause = "AND property_type = ANY(:type_filter)"

    where = f"""
        WHERE {area_filter}
          AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
          {type_filter_clause}
    """

    # Count query
    count_result = await db.execute(
        text(f"SELECT COUNT(*) AS cnt FROM core_property_transactions {where}"),
        params,
    )
    total = int(count_result.mappings().first()["cnt"])
    total_pages = max(1, -(-total // page_size))  # ceil division

    # Clamp page
    if page > total_pages:
        page = total_pages

    # Data query
    nulls = "NULLS LAST" if sort_dir == "asc" else "NULLS FIRST"
    offset = (page - 1) * page_size

    rows_result = await db.execute(
        text(f"""
            SELECT date_of_transfer,
                   CONCAT_WS(', ',
                       NULLIF(NULLIF(NULLIF(TRIM(saon), ''), 'N'), 'Y'),
                       NULLIF(TRIM(paon), ''),
                       NULLIF(TRIM(street), ''),
                       NULLIF(TRIM(town), '')
                   ) AS address,
                   price,
                   property_type,
                   duration,
                   bedrooms_estimated,
                   floor_area_sqm,
                   epc_rating
            FROM core_property_transactions
            {where}
            ORDER BY {sort_col} {sort_dir} {nulls}
            LIMIT :lim OFFSET :off
        """),
        {**params, "lim": page_size, "off": offset},
    )
    rows = rows_result.mappings().all()

    transactions = []
    for r in rows:
        pt = (r["property_type"] or "").strip()
        dur = (r["duration"] or "").strip()
        beds = r["bedrooms_estimated"]
        transactions.append({
            "date": r["date_of_transfer"].isoformat() if r["date_of_transfer"] else None,
            "address": r["address"] or "",
            "price": r["price"],
            "property_type": pt,
            "property_type_label": TYPE_NAMES.get(pt, pt),
            "beds": beds,
            "beds_label": f"{beds} bed (est.)" if beds is not None else None,
            "size_sqm": round(r["floor_area_sqm"], 1) if r["floor_area_sqm"] else None,
            "tenure": dur,
            "tenure_label": TENURE_NAMES.get(dur, dur),
            "epc": (r["epc_rating"] or "").strip() or None,
        })

    return {
        "transactions": transactions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# ---------------------------------------------------------------------------
# AQ history
# ---------------------------------------------------------------------------

@router.get("/aq-history")
async def get_aq_history(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    db: AsyncSession = Depends(get_db),
):
    """Return yearly PM2.5/NO2 averages for the LAD (7-year trend)."""
    sess = await _require_session(session_key)
    lad_code = sess["lad_code"]

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


# ---------------------------------------------------------------------------
# Comparable areas
# ---------------------------------------------------------------------------

@router.get("/comparable")
async def get_comparable_areas(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    db: AsyncSession = Depends(get_db),
):
    """Find the 5 most similar LADs based on price, rent, earnings, AQ, HPI."""
    sess = await _require_session(session_key)
    lad_code = sess["lad_code"]

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


# ---------------------------------------------------------------------------
# Map POIs
# ---------------------------------------------------------------------------

@router.get("/map-pois")
async def get_map_pois(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    tab: str = Query("Property & Market"),
    db: AsyncSession = Depends(get_db),
):
    """Return nearby POIs relevant to the active tab for map display."""
    cache_key = f"pois:{session_key}:{tab}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    sess = await _require_session(session_key)
    lat = sess.get("lat")
    lon = sess.get("lon")
    is_area = sess.get("search_mode") == "area"
    ward_code = sess.get("ward_code", "_")
    lsoa_code = sess.get("lsoa_code", "_")
    area_lsoa_list = sess["lsoa_codes"] if is_area else []

    features = []

    if tab == "Property & Market":
        # Recent sold prices — use union of ward + LSOA boundaries
        if ward_code and ward_code != '_' and lsoa_code and lsoa_code != '_':
            # Two separate indexed queries merged in Python — each uses GiST index.
            ward_res = await db.execute(
                text("""
                    SELECT t.price, t.date_of_transfer, t.property_type, t.duration,
                           t.paon, t.saon, t.street, t.town, t.postcode, t.latitude, t.longitude, t.lsoa_code,
                           ST_Distance(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m,
                           t.bedrooms_estimated AS bedrooms,
                           t.floor_area_sqm,
                           t.epc_rating
                    FROM core_property_transactions t
                    JOIN core_ward_boundaries w ON w.ward_code = :ward_code
                    WHERE t.geom IS NOT NULL
                      AND ST_Within(t.geom, w.geom)
                      AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '24 months'
                    ORDER BY t.date_of_transfer DESC
                    LIMIT 500
                """),
                {"lat": lat, "lon": lon, "ward_code": ward_code},
            )
            ward_rows = {(r["latitude"], r["longitude"], str(r["date_of_transfer"])): dict(r) for r in ward_res.mappings().all()}

            lsoa_res = await db.execute(
                text("""
                    SELECT t.price, t.date_of_transfer, t.property_type, t.duration,
                           t.paon, t.saon, t.street, t.town, t.postcode, t.latitude, t.longitude, t.lsoa_code,
                           ST_Distance(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m,
                           t.bedrooms_estimated AS bedrooms,
                           t.floor_area_sqm,
                           t.epc_rating
                    FROM core_property_transactions t
                    JOIN core_lsoa_boundaries l ON l.lsoa_code = :lsoa_code
                    WHERE t.geom IS NOT NULL
                      AND ST_Within(t.geom, l.geom)
                      AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '24 months'
                    ORDER BY t.date_of_transfer DESC
                    LIMIT 500
                """),
                {"lat": lat, "lon": lon, "lsoa_code": lsoa_code},
            )
            merged = {}
            for key, r in ward_rows.items():
                r["in_ward"] = True
                merged[key] = r
            for r in lsoa_res.mappings().all():
                key = (r["latitude"], r["longitude"], str(r["date_of_transfer"]))
                if key not in merged:
                    row = dict(r)
                    row["in_ward"] = False
                    merged[key] = row
            all_rows = sorted(merged.values(), key=lambda x: x["date_of_transfer"], reverse=True)
            class _Rows:
                def __init__(self, rows): self._rows = rows
                def mappings(self):
                    return self
                def all(self):
                    return self._rows
            res = _Rows(all_rows)
        elif ward_code and ward_code != '_':
            res = await db.execute(
                text("""
                    SELECT t.price, t.date_of_transfer, t.property_type, t.duration,
                           t.paon, t.saon, t.street, t.town, t.postcode, t.latitude, t.longitude, t.lsoa_code,
                           ST_Distance(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m,
                           true AS in_ward,
                           t.bedrooms_estimated AS bedrooms,
                           t.floor_area_sqm,
                           t.epc_rating
                    FROM core_property_transactions t
                    JOIN core_ward_boundaries w ON w.ward_code = :ward_code
                    WHERE t.geom IS NOT NULL
                      AND ST_Within(t.geom, w.geom)
                      AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '24 months'
                    ORDER BY t.date_of_transfer DESC
                    LIMIT 500
                """),
                {"lat": lat, "lon": lon, "ward_code": ward_code},
            )
        elif is_area and area_lsoa_list:
            sample_codes = area_lsoa_list[:50]
            res = await db.execute(
                text("""
                    SELECT t.price, t.date_of_transfer, t.property_type, t.duration,
                           t.paon, t.saon, t.street, t.town, t.postcode, t.latitude, t.longitude, t.lsoa_code,
                           ST_Distance(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m,
                           true AS in_ward,
                           t.bedrooms_estimated AS bedrooms,
                           t.floor_area_sqm,
                           t.epc_rating
                    FROM core_property_transactions t
                    WHERE t.geom IS NOT NULL
                      AND t.lsoa_code = ANY(:codes)
                      AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '24 months'
                    ORDER BY t.date_of_transfer DESC
                    LIMIT 500
                """),
                {"lat": lat, "lon": lon, "codes": sample_codes},
            )
        else:
            res = await db.execute(
                text("""
                    SELECT t.price, t.date_of_transfer, t.property_type, t.duration,
                           t.paon, t.saon, t.street, t.town, t.postcode, t.latitude, t.longitude, t.lsoa_code,
                           ST_Distance(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS dist_m,
                           true AS in_ward,
                           t.bedrooms_estimated AS bedrooms,
                           t.floor_area_sqm,
                           t.epc_rating
                    FROM core_property_transactions t
                    WHERE t.geom IS NOT NULL
                      AND ST_DWithin(t.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1000)
                      AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                    ORDER BY t.date_of_transfer DESC
                    LIMIT 500
                """),
                {"lat": lat, "lon": lon},
            )
        TYPE_NAMES = {"D": "Detached", "S": "Semi-Detached", "T": "Terraced", "F": "Flat"}
        TENURE_NAMES = {"F": "Freehold", "L": "Leasehold"}

        sold_rows = res.mappings().all()

        for r in sold_rows:
            parts = [p for p in [r["saon"], r["paon"], r["street"]] if p]
            address = ", ".join(parts) if parts else r["town"] or "Unknown"
            pt = (r["property_type"] or "").strip()
            dur = (r["duration"] or "").strip()
            pc = (r.get("postcode") or "").strip()

            bedrooms = r.get("bedrooms")
            floor_area = float(r["floor_area_sqm"]) if r.get("floor_area_sqm") else None
            epc_rating = r.get("epc_rating")
            actual_psf = round(r["price"] / (floor_area * 10.7639)) if floor_area and floor_area > 0 else None

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": {
                    "name": address,
                    "category": "sold_price",
                    "price": r["price"],
                    "date": str(r["date_of_transfer"]),
                    "property_type": TYPE_NAMES.get(pt, pt),
                    "tenure": TENURE_NAMES.get(dur, ""),
                    "postcode": pc,
                    "bedrooms": bedrooms,
                    "floor_area_sqm": floor_area,
                    "actual_psf": actual_psf,
                    "epc_rating": epc_rating,
                    "dist_m": round(float(r["dist_m"])),
                    "lsoa_code": r["lsoa_code"],
                    "in_ward": bool(r["in_ward"]),
                },
            })

    elif tab == "Community & Education":
        if is_area and area_lsoa_list:
            res = await db.execute(
                text("""
                    SELECT DISTINCT ON (s.school_name) s.school_name, s.phase, s.ofsted_rating, s.latitude, s.longitude
                    FROM core_schools s
                    JOIN core_lsoa_boundaries lb ON ST_Within(s.geom, lb.geom)
                    WHERE s.is_open = true AND s.geom IS NOT NULL
                      AND lb.lsoa_code = ANY(:codes)
                    ORDER BY s.school_name
                    LIMIT 30
                """),
                {"codes": area_lsoa_list},
            )
        else:
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
            props = {
                "name": r["school_name"],
                "category": "school",
                "phase": r["phase"],
                "ofsted": r["ofsted_rating"],
            }
            if not is_area and "dist_m" in dict(r):
                props["dist_m"] = round(float(r["dist_m"]))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": props,
            })

    elif tab == "Environment & Safety":
        if is_area and area_lsoa_list:
            res = await db.execute(
                text("""
                    SELECT fz.flood_zone, ST_AsGeoJSON(ST_Intersection(fz.geom,
                        ST_Union(lb.geom)
                    ), 5) AS geojson
                    FROM core_flood_zones fz
                    JOIN core_lsoa_boundaries lb ON ST_Intersects(fz.geom, lb.geom)
                    WHERE lb.lsoa_code = ANY(:codes)
                    GROUP BY fz.flood_zone, fz.geom
                """),
                {"codes": area_lsoa_list},
            )
        else:
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
        if is_area and area_lsoa_list:
            res = await db.execute(
                text("""
                    SELECT DISTINCT ON (base_name)
                        REGEXP_REPLACE(ts.stop_name,
                            ' (Rail Station|Underground Station|DLR Station|Overground Station|Tram Stop|Station)$',
                            '', 'i') AS base_name,
                        ts.stop_name, ts.stop_type, ts.latitude, ts.longitude
                    FROM core_transport_stops ts
                    JOIN core_lsoa_boundaries lb ON ST_Within(ts.geom, lb.geom)
                    WHERE ts.stop_type IN ('RSE', 'RLY', 'MET')
                      AND ts.geom IS NOT NULL
                      AND lb.lsoa_code = ANY(:codes)
                    ORDER BY base_name
                    LIMIT 20
                """),
                {"codes": area_lsoa_list},
            )
        else:
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
            props = {
                "name": r["base_name"],
                "category": "station",
                "type": r["stop_type"],
            }
            if not is_area and "dist_m" in dict(r):
                props["dist_m"] = round(float(r["dist_m"]))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": props,
            })

        # EV chargers
        if is_area and area_lsoa_list:
            ev_res = await db.execute(
                text("""
                    SELECT ev.name, ev.operator, ev.connector_count, ev.max_power_kw, ev.latitude, ev.longitude
                    FROM core_ev_chargers ev
                    JOIN core_lsoa_boundaries lb ON ST_Within(ev.geom, lb.geom)
                    WHERE ev.geom IS NOT NULL
                      AND lb.lsoa_code = ANY(:codes)
                    ORDER BY ev.name
                    LIMIT 30
                """),
                {"codes": area_lsoa_list},
            )
        else:
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
            props = {
                "name": r["name"] or "EV Charger",
                "category": "ev_charger",
                "operator": r["operator"],
                "connectors": r["connector_count"],
                "max_kw": float(r["max_power_kw"]) if r["max_power_kw"] else None,
            }
            if not is_area and "dist_m" in dict(r):
                props["dist_m"] = round(float(r["dist_m"]))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]},
                "properties": props,
            })

    result: dict = {"type": "FeatureCollection", "features": features}

    # Include earliest sold-price date so the frontend legend can show "since MMM YYYY"
    if tab == "Property & Market" and features:
        min_date = min(
            (f["properties"]["date"] for f in features if f["properties"].get("date")),
            default=None,
        )
        if min_date:
            result["sold_prices_since"] = min_date

    await cache_set(cache_key, result, ttl=86400)
    return result


# ---------------------------------------------------------------------------
# Boundary (consolidated — replaces 5 separate endpoints)
# ---------------------------------------------------------------------------

@router.get("/boundary")
async def get_boundary(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    db: AsyncSession = Depends(get_db),
):
    """Return the appropriate boundary GeoJSON based on session boundary_source."""
    sess = await _require_session(session_key)
    source = sess.get("boundary_source", "lad")
    bid = sess.get("boundary_id", "")

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
        await cache_set(cache_key, feature, ttl=86400)
        return JSONResponse(content=feature)

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
        await cache_set(cache_key, feature, ttl=86400)
        return JSONResponse(content=feature)

    elif source == "place":
        pn = sess.get("place_name") or bid
        plad = sess.get("place_lad_code", "")
        pt = sess.get("place_type", "Suburban Area")
        cache_key = f"boundary:place:{pn}:{plad}"
        cached = await cache_get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        use_town = pt in ('City', 'Town')
        primary = TABLE_NAMES["place_lsoa_mapping_town"] if use_town else TABLE_NAMES["place_lsoa_mapping"]
        fallback_tbl = TABLE_NAMES["place_lsoa_mapping"] if use_town else TABLE_NAMES["place_lsoa_mapping_town"]

        res = await db.execute(
            text(f"""
                SELECT ST_AsGeoJSON(ST_Union(lb.geom), 6) as geojson
                FROM core_lsoa_boundaries lb
                JOIN {primary} m ON lb.lsoa_code = m.lsoa_code
                WHERE m.place_name = :name AND m.lad_code = :lad
            """),
            {"name": pn, "lad": plad},
        )
        row = res.mappings().first()

        if not row or not row["geojson"]:
            res2 = await db.execute(
                text(f"""
                    SELECT ST_AsGeoJSON(ST_Union(lb.geom), 6) as geojson
                    FROM core_lsoa_boundaries lb
                    JOIN {fallback_tbl} m ON lb.lsoa_code = m.lsoa_code
                    WHERE m.place_name = :name AND m.lad_code = :lad
                """),
                {"name": pn, "lad": plad},
            )
            row = res2.mappings().first()

        if not row or not row["geojson"]:
            raise http_error(404, "BOUNDARY_NOT_FOUND", "Place boundary not found")

        feature = {
            "type": "Feature",
            "properties": {"place_name": pn, "lad_code": plad},
            "geometry": json.loads(row["geojson"]),
        }
        await cache_set(cache_key, feature, ttl=86400)
        return JSONResponse(content=feature)

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
        await cache_set(cache_key, feature, ttl=86400)
        return JSONResponse(content=feature)

    raise http_error(400, "INVALID_BOUNDARY_SOURCE", f"Unknown boundary_source: {source}")


# ---------------------------------------------------------------------------
# Choropleth (LSOA-level heatmap polygons)
# ---------------------------------------------------------------------------

VALID_CHOROPLETH_LAYERS = {"avg_price", "price_per_sqft", "epc_score"}


@router.get("/map-choropleth")
async def get_map_choropleth(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    layer: str = Query(..., description="avg_price | price_per_sqft | epc_score"),
    db: AsyncSession = Depends(get_db),
):
    """Return LSOA polygons with metric values for choropleth rendering."""
    if layer not in VALID_CHOROPLETH_LAYERS:
        raise http_error(400, "INVALID_LAYER", f"Invalid layer: {layer}. Valid: {VALID_CHOROPLETH_LAYERS}")

    cache_key = f"choropleth:{session_key}:{layer}"
    cached = await cache_get(cache_key)
    if cached:
        return JSONResponse(content=cached)

    sess = await _require_session(session_key)
    boundary_source = sess.get("boundary_source", "lad")
    local_lads = sess.get("local_lads", [])
    lsoa_codes = sess.get("lsoa_codes", [])
    ward_code = sess.get("ward_code", "_")

    # --- Determine LSOA scope ---
    if boundary_source == "ward_lsoa":
        # Postcode: expand to all LSOAs in the ward
        scope_res = await db.execute(
            text("SELECT DISTINCT lsoa_code FROM core_postcodes WHERE ward_code = :ward AND lsoa_code IS NOT NULL"),
            {"ward": ward_code},
        )
        scope_codes = [r["lsoa_code"] for r in scope_res.mappings().all()]
    elif boundary_source in ("place", "ward"):
        scope_codes = lsoa_codes
    else:
        # LAD / county: all LSOAs in the local LADs
        scope_res = await db.execute(
            text("SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = ANY(:lads)"),
            {"lads": local_lads},
        )
        scope_codes = [r["lsoa_code"] for r in scope_res.mappings().all()]

    if not scope_codes:
        return JSONResponse(content={"type": "FeatureCollection", "metadata": {"layer": layer, "lsoa_count": 0}, "features": []})

    # --- Adaptive simplification ---
    n = len(scope_codes)
    if n > 1000:
        geom_expr = "ST_Simplify(lb.geom, 0.001)"
        prec = 4
    elif n > 200:
        geom_expr = "ST_Simplify(lb.geom, 0.0003)"
        prec = 5
    else:
        geom_expr = "lb.geom"
        prec = 5

    # --- Query: geometry + metric value ---
    if layer == "avg_price":
        # Match tab_property aggregation: wavg across types weighted by transaction count
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   sub.wavg_price AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN (
                SELECT lsoa_code,
                       ROUND(AVG(price)) AS wavg_price
                FROM core_property_transactions
                WHERE date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                  AND property_type = ANY(:price_types)
                  AND lsoa_code = ANY(:codes)
                GROUP BY lsoa_code
            ) sub ON sub.lsoa_code = lb.lsoa_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "GBP"
    elif layer == "price_per_sqft":
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   ROUND(sub.avg_ppsft) AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN (
                SELECT lsoa_code,
                       ROUND(AVG(price::numeric / NULLIF(floor_area_sqm::numeric * 10.7639, 0)), 2) AS avg_ppsft
                FROM core_property_transactions
                WHERE floor_area_sqm > 0
                  AND lsoa_code = ANY(:codes)
                GROUP BY lsoa_code
            ) sub ON sub.lsoa_code = lb.lsoa_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "GBP/sqft"
    else:  # epc_score
        sql = f"""
            SELECT lb.lsoa_code, lb.lsoa_name,
                   ST_AsGeoJSON({geom_expr}, {prec}) AS geojson,
                   e.avg_energy_score AS value
            FROM core_lsoa_boundaries lb
            LEFT JOIN core_epc_lsoa e ON e.lsoa_code = lb.lsoa_code
            WHERE lb.lsoa_code = ANY(:codes)
        """
        unit = "score"

    res = await db.execute(text(sql), {"codes": scope_codes, "price_types": list(PRICE_TYPES)})
    rows = res.mappings().all()

    # --- Build features + compute quintiles ---
    features = []
    values = []
    for r in rows:
        if not r["geojson"]:
            continue
        val = round(float(r["value"]), 1) if r["value"] is not None else None
        if val is not None:
            values.append(val)
        features.append({
            "type": "Feature",
            "geometry": json.loads(r["geojson"]),
            "properties": {
                "lsoa_code": r["lsoa_code"],
                "lsoa_name": r["lsoa_name"],
                "value": val,
                "quantile": -1,  # placeholder
            },
        })

    # Compute quintile breaks (4 cut-points → 5 buckets)
    quantiles = []
    if len(values) >= 5:
        values_sorted = sorted(values)
        quantiles = [values_sorted[len(values_sorted) * i // 5] for i in range(1, 5)]
    elif len(values) >= 2:
        # Fewer than 5 values: use linear interpolation for 5 buckets
        min_v, max_v = min(values), max(values)
        if max_v > min_v:
            step = (max_v - min_v) / 5
            quantiles = [min_v + step * i for i in range(1, 5)]

    # Assign quantile index to each feature
    for f in features:
        v = f["properties"]["value"]
        if v is None:
            f["properties"]["quantile"] = -1
        elif not quantiles:
            f["properties"]["quantile"] = 2  # single value: middle bucket
        else:
            f["properties"]["quantile"] = sum(1 for q in quantiles if v > q)

    min_val = min(values) if values else None
    max_val = max(values) if values else None

    result = {
        "type": "FeatureCollection",
        "metadata": {
            "layer": layer,
            "unit": unit,
            "min_value": min_val,
            "max_value": max_val,
            "quantiles": quantiles,
            "lsoa_count": len(features),
        },
        "features": features,
    }

    await cache_set(cache_key, result, ttl=86400)
    return JSONResponse(content=result)
