"""
GET /api/v1/price-history
GET /api/v1/price-by-type
GET /api/v1/transactions
Price-related endpoints for the Results page charts and transaction table.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import PRICE_TYPES, TYPE_NAMES, TENURE_NAMES
from app.database import get_db
from app.errors import http_error
from app.cache import cache_get, cache_set
from app.services.session_helpers import require_session

router = APIRouter()

# Must match area_tabs.py — bump both when session schema changes
PRICE_CACHE_VERSION = "v36"


# ---------------------------------------------------------------------------
# Price history
# ---------------------------------------------------------------------------

@router.get("/price-history")
async def get_price_history(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    db: AsyncSession = Depends(get_db),
):
    """Return yearly avg prices: local (matching search resolution) vs parent region."""
    cache_key = f"price_history:{PRICE_CACHE_VERSION}:{session_key}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    sess = await require_session(session_key)
    parent_lad_codes = sess.get("parent_lad_codes", [])
    parent_name = sess.get("parent_name", "England")
    boundary_source = sess.get("boundary_source", "lad")

    # Local — scope determined by what the search key resolved to.
    # For LAD/county searches, use pre-computed MVs (fast — <1s even for large LADs).
    # For sub-LAD (postcode/ward/place), query raw transactions (small row counts, fast).
    if boundary_source in ("lad", "county"):
        local_lads = sess.get("local_lads", [])

        # Per-LAD MV rows aggregated across local LADs
        local_res = await db.execute(
            text("""
                SELECT year::text AS year,
                       ROUND(SUM(avg_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS avg_price,
                       ROUND(SUM(median_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS median_price,
                       SUM(transactions) AS transactions
                FROM mv_parent_yearly_price_stats
                WHERE lad_code = ANY(:lads)
                  AND property_type = 'ALL'
                GROUP BY year
                ORDER BY year
            """),
            {"lads": local_lads},
        )
        local_rows = [dict(r) for r in local_res.mappings().all()]

        # Local PPSF from the dedicated MV
        local_ppsf_res = await db.execute(
            text("""
                SELECT year::text AS yr, ROUND(AVG(avg_ppsf))::int AS avg_ppsf
                FROM mv_parent_yearly_ppsf
                WHERE lad_code = ANY(:lads)
                GROUP BY year ORDER BY year
            """),
            {"lads": local_lads},
        )
        local_ppsf_by_year = {str(r["yr"]): int(r["avg_ppsf"]) for r in local_ppsf_res.mappings().all() if r["avg_ppsf"]}
        for row in local_rows:
            yr = str(row["year"]).strip()[:4]
            row["avg_ppsf"] = local_ppsf_by_year.get(yr)
    else:
        lsoa_codes = sess["lsoa_codes"]
        _area_filter = "lsoa_code = ANY(:codes)"
        _local_params = {"codes": lsoa_codes, "price_types": list(PRICE_TYPES)}

        # True avg + true median from raw transaction prices (small area, fast)
        local_res = await db.execute(
            text(f"""
                SELECT date_trunc('year', date_of_transfer)::date AS year,
                       ROUND(AVG(price))::int AS avg_price,
                       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::int AS median_price,
                       COUNT(*) AS transactions,
                       ROUND(AVG(price::numeric / NULLIF(floor_area_sqm::numeric * 10.7639, 0)))::int AS avg_ppsf
                FROM core_property_transactions
                WHERE {_area_filter}
                  AND property_type = ANY(:price_types)
                GROUP BY 1 ORDER BY 1
            """),
            _local_params,
        )
        local_rows = [dict(r) for r in local_res.mappings().all()]

    # Regional — parent comparison line from pre-computed MVs (per-LAD rows).
    if parent_lad_codes:
        parent_res = await db.execute(
            text("""
                SELECT year::text AS year,
                       ROUND(SUM(avg_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS avg_price,
                       ROUND(SUM(median_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS median_price,
                       SUM(transactions) AS transactions
                FROM mv_parent_yearly_price_stats
                WHERE lad_code = ANY(:lads)
                  AND property_type = 'ALL'
                GROUP BY year
                ORDER BY year
            """),
            {"lads": parent_lad_codes},
        )
        parent_rows = [dict(r) for r in parent_res.mappings().all()]

        # Parent avg_ppsf by year
        parent_ppsf_res = await db.execute(
            text("""
                SELECT year::text AS yr,
                       ROUND(SUM(avg_ppsf * transactions) / NULLIF(SUM(transactions), 0))::int AS avg_ppsf
                FROM mv_parent_yearly_ppsf
                WHERE lad_code = ANY(:lads)
                GROUP BY year ORDER BY year
            """),
            {"lads": parent_lad_codes},
        )
        parent_ppsf_by_year = {str(r["yr"]): int(r["avg_ppsf"]) for r in parent_ppsf_res.mappings().all() if r["avg_ppsf"]}
        for row in parent_rows:
            yr = str(row["year"]).strip()[:4]
            row["avg_ppsf"] = parent_ppsf_by_year.get(yr)
    else:
        parent_rows = []

    # Serialize dates as year strings
    for row in local_rows:
        row["year"] = str(row["year"].year) if hasattr(row["year"], "year") else str(row["year"])[:4]
    for row in parent_rows:
        row["year"] = str(row["year"].year) if hasattr(row["year"], "year") else str(row["year"])[:4]

    # Bedroom breakdown — avg_price from fast pre-aggregated table.
    # median_price and avg_ppsf not available per bedroom (PERCENTILE_CONT and
    # floor_area AVG are too slow for large LADs — 73s+ for Bristol alone).
    # Frontend falls back: median→avg_price, ppsf→null (hides bedroom lines).
    bedrooms_rows: list = []
    bed_lads = sess.get("local_lads", [])
    if bed_lads:
        bedrooms_res = await db.execute(
            text("""
                SELECT year::text AS year,
                       bedrooms,
                       ROUND(SUM(avg_price * transaction_count) / NULLIF(SUM(transaction_count), 0))::int AS avg_price,
                       SUM(transaction_count) AS transaction_count
                FROM core_price_by_bedrooms_lad
                WHERE lad_code = ANY(:lads)
                  AND property_type = ANY(:price_types)
                  AND bedrooms BETWEEN 1 AND 5
                GROUP BY year, bedrooms
                ORDER BY year, bedrooms
            """),
            {"lads": bed_lads, "price_types": list(PRICE_TYPES)},
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
    cache_key = f"price_by_type:{PRICE_CACHE_VERSION}:{session_key}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    sess = await require_session(session_key)
    boundary_source = sess.get("boundary_source", "lad")

    _TYPE_NAMES = {"D": "Detached", "S": "Semi-Detached", "T": "Terraced", "F": "Flat"}
    parent_lad_codes = sess.get("parent_lad_codes", [])
    parent_name = sess.get("parent_name", "England")

    if boundary_source in ("lad", "county"):
        local_lads = sess.get("local_lads", [])

        # Yearly by type from per-LAD MV
        res = await db.execute(
            text("""
                SELECT year::text AS year,
                       property_type,
                       ROUND(SUM(avg_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS avg_price,
                       ROUND(SUM(median_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS median_price,
                       SUM(transactions) AS transactions
                FROM mv_parent_yearly_price_stats
                WHERE lad_code = ANY(:lads)
                  AND property_type != 'ALL'
                GROUP BY year, property_type
                ORDER BY year, property_type
            """),
            {"lads": local_lads},
        )
        rows = [dict(r) for r in res.mappings().all()]
        for row in rows:
            row["year"] = str(row["year"]).strip()[:4]

        # Rolling 12m from per-LAD MV
        rolling_res = await db.execute(
            text("""
                SELECT property_type,
                       ROUND(SUM(avg_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS avg_price,
                       ROUND(SUM(median_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS median_price,
                       SUM(transactions) AS transactions
                FROM mv_parent_rolling_price_stats
                WHERE lad_code = ANY(:lads)
                  AND property_type != 'ALL'
                GROUP BY property_type
            """),
            {"lads": local_lads},
        )
        rolling_by_type: dict = {}
        for r in rolling_res.mappings().all():
            pt = r["property_type"].strip()
            label = _TYPE_NAMES.get(pt, pt)
            rolling_by_type[label] = {
                "year": "Last 12m",
                "avg_price": r["avg_price"],
                "median_price": r["median_price"],
                "transactions": r["transactions"],
            }
    else:
        lsoa_codes = sess["lsoa_codes"]
        _area_filter = "lsoa_code = ANY(:codes)"
        _local_params = {"codes": lsoa_codes, "price_types": list(PRICE_TYPES)}

        res = await db.execute(
            text(f"""
                SELECT date_trunc('year', date_of_transfer)::date AS year,
                       property_type,
                       ROUND(AVG(price))::int AS avg_price,
                       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::int AS median_price,
                       COUNT(*) AS transactions
                FROM core_property_transactions
                WHERE {_area_filter}
                  AND property_type = ANY(:price_types)
                GROUP BY 1, 2 ORDER BY 1, 2
            """),
            _local_params,
        )
        rows = [dict(r) for r in res.mappings().all()]
        for row in rows:
            row["year"] = str(row["year"].year) if hasattr(row["year"], "year") else str(row["year"])[:4]

        # Rolling 12m from raw transactions (small area, fast)
        rolling_raw_res = await db.execute(
            text(f"""
                SELECT property_type,
                       ROUND(AVG(price))::int AS avg_price,
                       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::int AS median_price,
                       COUNT(*) AS transactions
                FROM core_property_transactions
                WHERE {_area_filter}
                  AND property_type = ANY(:price_types)
                  AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                GROUP BY property_type
            """),
            _local_params,
        )
        rolling_by_type = {}
        for r in rolling_raw_res.mappings().all():
            pt = r["property_type"].strip()
            label = _TYPE_NAMES.get(pt, pt)
            rolling_by_type[label] = {
                "year": "Last 12m",
                "avg_price": r["avg_price"],
                "median_price": r["median_price"],
                "transactions": r["transactions"],
            }

    by_type: dict = {}
    for row in rows:
        pt = row["property_type"].strip()
        label = _TYPE_NAMES.get(pt, pt)
        if label not in by_type:
            by_type[label] = []
        by_type[label].append({
            "year": row["year"],
            "avg_price": row["avg_price"],
            "median_price": row["median_price"],
            "transactions": row["transactions"],
        })
    # Append rolling 12m
    for label, rolling_point in rolling_by_type.items():
        if label not in by_type:
            by_type[label] = []
        by_type[label].append(rolling_point)

    # Parent by type — per-LAD MV aggregated across parent LAD codes
    parent_by_type: dict = {}
    if parent_lad_codes:
        parent_res = await db.execute(
            text("""
                SELECT year::text AS year,
                       property_type,
                       ROUND(SUM(avg_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS avg_price,
                       ROUND(SUM(median_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS median_price,
                       SUM(transactions) AS transactions
                FROM mv_parent_yearly_price_stats
                WHERE lad_code = ANY(:lads)
                  AND property_type != 'ALL'
                GROUP BY year, property_type
                ORDER BY year, property_type
            """),
            {"lads": parent_lad_codes},
        )
        parent_rows = [dict(r) for r in parent_res.mappings().all()]

        for row in parent_rows:
            pt = row["property_type"].strip()
            label = _TYPE_NAMES.get(pt, pt)
            if label not in parent_by_type:
                parent_by_type[label] = []
            parent_by_type[label].append({
                "year": row["year"],
                "avg_price": row["avg_price"],
                "median_price": row["median_price"],
                "transactions": row["transactions"],
            })

        parent_rolling_res = await db.execute(
            text("""
                SELECT property_type,
                       ROUND(SUM(avg_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS avg_price,
                       ROUND(SUM(median_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS median_price,
                       SUM(transactions) AS transactions
                FROM mv_parent_rolling_price_stats
                WHERE lad_code = ANY(:lads)
                  AND property_type != 'ALL'
                GROUP BY property_type
            """),
            {"lads": parent_lad_codes},
        )
        for r in parent_rolling_res.mappings().all():
            pt = r["property_type"].strip()
            label = _TYPE_NAMES.get(pt, pt)
            if label not in parent_by_type:
                parent_by_type[label] = []
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
        # Rolling PPSF from MV (fast, avoids scanning raw transactions)
        ppsf_rolling_res = await db.execute(
            text("""
                SELECT property_type,
                       ROUND((SUM(avg_ppsf * transactions) / NULLIF(SUM(transactions), 0))::numeric, 2) AS avg_ppsf
                FROM mv_parent_rolling_price_stats
                WHERE lad_code = ANY(:lads)
                  AND property_type <> 'ALL'
                  AND avg_ppsf IS NOT NULL
                GROUP BY property_type
            """),
            {"lads": local_lads},
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
        label = _TYPE_NAMES.get(pt, pt)
        year_str = str(r["year"].year) if hasattr(r["year"], "year") else str(r["year"])[:4]
        ppsf_lookup[(label, year_str)] = float(r["avg_ppsf"]) if r["avg_ppsf"] else None
    for r in ppsf_rolling_res.mappings().all():
        pt = r["property_type"].strip()
        label = _TYPE_NAMES.get(pt, pt)
        ppsf_lookup[(label, "Last 12m")] = float(r["avg_ppsf"]) if r["avg_ppsf"] else None

    for label, points in by_type.items():
        for point in points:
            point["avg_ppsf"] = ppsf_lookup.get((label, point["year"]))

    # Parent ppsf — yearly from UCL, rolling from MV
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
                SELECT property_type,
                       ROUND((SUM(avg_ppsf * transactions) / NULLIF(SUM(transactions), 0))::numeric, 2) AS avg_ppsf
                FROM mv_parent_rolling_price_stats
                WHERE lad_code = ANY(:lads)
                  AND property_type <> 'ALL'
                  AND avg_ppsf IS NOT NULL
                GROUP BY property_type
            """),
            {"lads": parent_lad_codes},
        )
        parent_ppsf_lookup: dict = {}
        for r in parent_ppsf_res.mappings().all():
            pt = r["property_type"].strip()
            label = _TYPE_NAMES.get(pt, pt)
            year_str = str(r["year"].year) if hasattr(r["year"], "year") else str(r["year"])[:4]
            parent_ppsf_lookup[(label, year_str)] = float(r["avg_ppsf"]) if r["avg_ppsf"] else None
        for r in parent_ppsf_rolling_res.mappings().all():
            pt = r["property_type"].strip()
            label = _TYPE_NAMES.get(pt, pt)
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
    year: int | None = Query(None, description="Calendar year to filter by, e.g. 2023. Default: last 12 months"),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated individual transactions for the session's area."""
    sess = await require_session(session_key)
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

    # Date filter: calendar year or last 13 months (default)
    if year is not None:
        date_filter = "AND EXTRACT(YEAR FROM date_of_transfer) = :year"
        params["year"] = year
    else:
        date_filter = "AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'"

    where = f"""
        WHERE {area_filter}
          {date_filter}
          {type_filter_clause}
    """

    # Available years for the dropdown
    years_result = await db.execute(
        text(f"""
            SELECT DISTINCT EXTRACT(YEAR FROM date_of_transfer)::int AS yr
            FROM core_property_transactions
            WHERE {area_filter}
              AND property_type = ANY(:type_filter)
            ORDER BY yr DESC
        """),
        params,
    )
    available_years = [r["yr"] for r in years_result.mappings().all()]

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
                   transaction_id,
                   postcode,
                   paon,
                   saon,
                   street,
                   price,
                   property_type,
                   duration,
                   bedrooms_estimated,
                   floor_area_sqm,
                   epc_rating,
                   latitude,
                   longitude,
                   old_new,
                   price_per_sqft,
                   ppd_category,
                   locality,
                   habitable_rooms,
                   epc_match_score,
                   lsoa_month_avg_price,
                   lsoa_month_median_price,
                   lsoa_month_transaction_count
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
        raw_saon = (r["saon"] or "").strip()
        transactions.append({
            "date": r["date_of_transfer"].isoformat() if r["date_of_transfer"] else None,
            "address": r["address"] or "",
            "transaction_id": r["transaction_id"] or "",
            "postcode": (r["postcode"] or "").strip(),
            "paon": (r["paon"] or "").strip(),
            "saon": "" if raw_saon in ("", "N", "Y") else raw_saon,
            "street": (r["street"] or "").strip(),
            "price": r["price"],
            "property_type": pt,
            "property_type_label": TYPE_NAMES.get(pt, pt),
            "beds": beds,
            "beds_label": f"{beds} bed (est.)" if beds is not None else None,
            "size_sqm": round(r["floor_area_sqm"], 1) if r["floor_area_sqm"] else None,
            "tenure": dur,
            "tenure_label": TENURE_NAMES.get(dur, dur),
            "epc": (r["epc_rating"] or "").strip() or None,
            "lat": float(r["latitude"]) if r["latitude"] else None,
            "lon": float(r["longitude"]) if r["longitude"] else None,
            "new_build": (r["old_new"] or "").strip() == "Y",
            "price_per_sqft": round(float(r["price_per_sqft"]), 0) if r["price_per_sqft"] else None,
            "ppd_category": (r["ppd_category"] or "").strip() or None,
            "locality": loc if len(loc := (r["locality"] or "").strip()) > 1 else None,
            "habitable_rooms": r["habitable_rooms"],
            "epc_match_score": round(float(r["epc_match_score"]), 2) if r["epc_match_score"] else None,
            "area_avg_price": round(float(r["lsoa_month_avg_price"]), 0) if r["lsoa_month_avg_price"] else None,
            "area_median_price": round(float(r["lsoa_month_median_price"]), 0) if r["lsoa_month_median_price"] else None,
            "area_sales_count": r["lsoa_month_transaction_count"],
        })

    return {
        "transactions": transactions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "available_years": available_years,
    }


# ---------------------------------------------------------------------------
# Property sale history (previous sales of same property)
# ---------------------------------------------------------------------------

@router.get("/transactions/history")
async def get_property_history(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    postcode: str = Query(..., description="Property postcode"),
    paon: str = Query(..., description="Primary address number"),
    street: str = Query(..., description="Street name"),
    saon: str = Query("", description="Secondary address number (flat, unit)"),
    exclude_id: str = Query("", description="Transaction ID to exclude from results"),
    db: AsyncSession = Depends(get_db),
):
    """Return previous sales of the same property, matched by address fields."""
    await require_session(session_key)

    # Uppercase to match stored data format; postcode uses idx_transactions_postcode
    params: dict = {
        "postcode": postcode.strip().upper(),
        "paon": paon.strip().upper(),
        "street": street.strip().upper(),
        "saon": saon.strip().upper(),
        "exclude_id": exclude_id.strip(),
    }

    # SAON matching: if empty (original had no flat/unit), skip saon filter
    # to catch historical records with varying saon descriptions.
    # If non-empty (e.g. "FLAT 4"), filter to that specific unit.
    if not params["saon"]:
        saon_clause = "TRUE"
    else:
        saon_clause = "saon = :saon"

    exclude_clause = "AND transaction_id != :exclude_id" if params["exclude_id"] else ""

    result = await db.execute(
        text(f"""
            SELECT date_of_transfer, price, property_type, duration,
                   bedrooms_estimated, floor_area_sqm, epc_rating
            FROM core_property_transactions
            WHERE postcode = :postcode
              AND paon = :paon
              AND street = :street
              AND {saon_clause}
              {exclude_clause}
            ORDER BY date_of_transfer DESC
            LIMIT 20
        """),
        params,
    )
    rows = result.mappings().all()

    history = []
    for r in rows:
        pt = (r["property_type"] or "").strip()
        dur = (r["duration"] or "").strip()
        beds = r["bedrooms_estimated"]
        history.append({
            "date": r["date_of_transfer"].isoformat() if r["date_of_transfer"] else None,
            "price": r["price"],
            "property_type": pt,
            "property_type_label": TYPE_NAMES.get(pt, pt),
            "beds": beds,
            "size_sqm": round(r["floor_area_sqm"], 1) if r["floor_area_sqm"] else None,
            "tenure": dur,
            "tenure_label": TENURE_NAMES.get(dur, dur),
            "epc": (r["epc_rating"] or "").strip() or None,
        })

    return {"history": history, "count": len(history)}


# ---------------------------------------------------------------------------
# Transaction EPC detail (proxy to Hetzner)
# ---------------------------------------------------------------------------

@router.get("/transactions/{transaction_id}/epc")
async def transaction_epc_detail(
    transaction_id: str,
    session_key: str = Query(...),
):
    """Fetch full EPC certificate matched to a transaction from Hetzner."""
    await require_session(session_key)
    try:
        from etl_lib import property_api
        result = property_api.epc_by_transaction(transaction_id)
    except Exception:
        result = None
    return {"epc": result}
