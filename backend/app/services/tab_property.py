"""Property & Market tab service.

Headline prices and price-per-sqft come from raw Land Registry transactions.
Parent comparison prices come from the pre-computed rolling parent view.
Rental and earnings context remain LAD-level only.
Housing-stock context is pulled from Census and EPC LSOA aggregates rather than
from the currently empty bedroom-price table.
"""
from sqlalchemy import text

from app.constants import PRICE_TYPES, VOA_LAD_REMAP
from app.services.helpers import metric


async def fetch_property_market(
    db,
    *,
    lad_code,
    ward_code,
    lsoa_codes,
    centroid_lat,
    centroid_lon,
    search_mode="postcode",
    local_lads=None,
    parent_lads=None,
    parent_name="England",
    boundary_source="lad",
):
    metrics = []
    if parent_lads is None:
        parent_lads = []

    if local_lads is None:
        local_lads = [lad_code] if lad_code and lad_code != "_" else []

    is_lad_or_coarser = boundary_source in ("lad", "county")
    price_types = list(PRICE_TYPES)

    if is_lad_or_coarser:
        local_txn_filter = "t.lad_code = ANY(:local_lads)"
        local_txn_filter_plain = "lad_code = ANY(:local_lads)"
        local_txn_params = {"local_lads": local_lads, "price_types": price_types}
    else:
        local_txn_filter = "t.lsoa_code = ANY(:lsoa_codes)"
        local_txn_filter_plain = "lsoa_code = ANY(:lsoa_codes)"
        local_txn_params = {"lsoa_codes": lsoa_codes, "price_types": price_types}

    # ------------------------------------------------------------------
    # Core recent sales prices
    # ------------------------------------------------------------------
    raw_local = await db.execute(
        text(
            f"""
            SELECT
                AVG(t.price) AS avg_price,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.price) AS median_price,
                AVG(t.price::numeric / NULLIF(t.floor_area_sqm::numeric * 10.7639, 0)) AS avg_ppsf
            FROM core_property_transactions t
            WHERE {local_txn_filter}
              AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
              AND t.property_type = ANY(:price_types)
            """
        ),
        local_txn_params,
    )
    raw_local_row = raw_local.mappings().first()

    if parent_lads:
        raw_parent = await db.execute(
            text(
                """
                SELECT avg_price, median_price, avg_ppsf
                FROM mv_parent_rolling_price_stats
                WHERE parent_comparison = :parent_name
                  AND property_type = 'ALL'
                """
            ),
            {"parent_name": parent_name},
        )
        raw_parent_row = raw_parent.mappings().first()
    else:
        raw_parent_row = None

    raw_local_avg = float(raw_local_row["avg_price"]) if raw_local_row and raw_local_row["avg_price"] is not None else None
    raw_local_median = float(raw_local_row["median_price"]) if raw_local_row and raw_local_row["median_price"] is not None else None
    raw_local_ppsf = float(raw_local_row["avg_ppsf"]) if raw_local_row and raw_local_row["avg_ppsf"] is not None else None
    raw_parent_avg = float(raw_parent_row["avg_price"]) if raw_parent_row and raw_parent_row["avg_price"] is not None else None
    raw_parent_median = float(raw_parent_row["median_price"]) if raw_parent_row and raw_parent_row["median_price"] is not None else None
    raw_parent_ppsf = float(raw_parent_row["avg_ppsf"]) if raw_parent_row and raw_parent_row["avg_ppsf"] is not None else None

    local_prices = await db.execute(
        text(
            f"""
            SELECT
                property_type,
                ROUND(AVG(price)::numeric, 2) AS avg_price,
                ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::numeric, 2) AS median_price,
                COUNT(*) AS transaction_count,
                COUNT(*) FILTER (WHERE old_new = 'Y') AS new_build_count,
                COUNT(*) FILTER (WHERE duration = 'F') AS freehold_count,
                COUNT(*) FILTER (WHERE duration = 'L') AS leasehold_count,
                ROUND((AVG(price) FILTER (WHERE duration = 'F'))::numeric, 2) AS avg_freehold_price,
                ROUND((AVG(price) FILTER (WHERE duration = 'L'))::numeric, 2) AS avg_leasehold_price
            FROM core_property_transactions
            WHERE {local_txn_filter_plain}
              AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
              AND property_type = ANY(:price_types)
            GROUP BY property_type
            """
        ),
        local_txn_params,
    )
    local_rows = local_prices.mappings().all()

    parent_prices = await db.execute(
        text(
            """
            SELECT property_type,
                   avg_price::numeric AS avg_price,
                   median_price::numeric AS median_price,
                   transactions AS transaction_count
            FROM mv_parent_rolling_price_stats
            WHERE parent_comparison = :parent_name
              AND property_type != 'ALL'
            """
        ),
        {"parent_name": parent_name},
    )
    parent_rows = parent_prices.mappings().all()

    local_by_type = {}
    local_median_by_type = {}
    for row in local_rows:
        property_type = row["property_type"]
        if property_type in PRICE_TYPES:
            local_by_type[property_type] = float(row["avg_price"]) if row["avg_price"] else None
            local_median_by_type[property_type] = float(row["median_price"]) if row["median_price"] else None

    local_avg = raw_local_avg or _wavg(
        [float(row["avg_price"]) for row in local_rows if row["avg_price"] and row["property_type"] in PRICE_TYPES],
        [int(row["transaction_count"]) for row in local_rows if row["avg_price"] and row["property_type"] in PRICE_TYPES],
    )
    local_median = raw_local_median or _wavg(
        [float(row["median_price"]) for row in local_rows if row["median_price"] and row["property_type"] in PRICE_TYPES],
        [int(row["transaction_count"]) for row in local_rows if row["median_price"] and row["property_type"] in PRICE_TYPES],
    )
    local_txn_raw = sum(
        int(row["transaction_count"])
        for row in local_rows
        if row["transaction_count"] and row["property_type"] in PRICE_TYPES
    )
    local_lsoa_count = len(lsoa_codes) if lsoa_codes else 1
    local_txn = round(local_txn_raw / local_lsoa_count, 1) if local_txn_raw else 0
    local_newbuild = sum(int(row["new_build_count"]) for row in local_rows if row["new_build_count"] and row["property_type"] in PRICE_TYPES)
    local_freehold = sum(int(row["freehold_count"]) for row in local_rows if row["freehold_count"])
    local_leasehold = sum(int(row["leasehold_count"]) for row in local_rows if row["leasehold_count"])

    parent_avg = raw_parent_avg or _wavg(
        [float(row["avg_price"]) for row in parent_rows if row["avg_price"] and row["property_type"] in PRICE_TYPES],
        [int(row["transaction_count"]) for row in parent_rows if row["avg_price"] and row["property_type"] in PRICE_TYPES],
    )
    parent_median = raw_parent_median or _wavg(
        [float(row["median_price"]) for row in parent_rows if row["median_price"] and row["property_type"] in PRICE_TYPES],
        [int(row["transaction_count"]) for row in parent_rows if row["median_price"] and row["property_type"] in PRICE_TYPES],
    )
    parent_txn_total = sum(int(row["transaction_count"]) for row in parent_rows if row["transaction_count"])

    parent_lsoa_count_result = await db.execute(
        text("SELECT COUNT(*) AS cnt FROM core_lsoa_boundaries WHERE lad_code = ANY(:lads)"),
        {"lads": parent_lads},
    )
    parent_lsoa_count_row = parent_lsoa_count_result.mappings().first()
    parent_lsoa_count = int(parent_lsoa_count_row["cnt"]) if parent_lsoa_count_row and parent_lsoa_count_row["cnt"] else 1
    parent_txn = round(parent_txn_total / parent_lsoa_count, 1) if parent_lsoa_count > 0 else None

    # ------------------------------------------------------------------
    # Housing-stock context from Census 2021
    # ------------------------------------------------------------------
    stock_local = await db.execute(
        text(
            """
            SELECT
                SUM(total_households) AS total_households,
                SUM(total_households * pct_owned) / NULLIF(SUM(total_households), 0) AS pct_owned,
                SUM(total_households * pct_private_rent) / NULLIF(SUM(total_households), 0) AS pct_private_rent,
                SUM(total_households * pct_social_rent) / NULLIF(SUM(total_households), 0) AS pct_social_rent,
                SUM(total_households * pct_detached) / NULLIF(SUM(total_households), 0) AS pct_detached,
                SUM(total_households * pct_semi) / NULLIF(SUM(total_households), 0) AS pct_semi,
                SUM(total_households * pct_terraced) / NULLIF(SUM(total_households), 0) AS pct_terraced,
                SUM(total_households * pct_flat) / NULLIF(SUM(total_households), 0) AS pct_flat
            FROM core_census_lsoa
            WHERE lsoa_code = ANY(:codes)
            """
        ),
        {"codes": lsoa_codes},
    )
    stock_row = stock_local.mappings().first()

    stock_parent = await db.execute(
        text(
            """
            SELECT
                SUM(c.total_households * c.pct_owned) / NULLIF(SUM(c.total_households), 0) AS pct_owned,
                SUM(c.total_households * c.pct_private_rent) / NULLIF(SUM(c.total_households), 0) AS pct_private_rent,
                SUM(c.total_households * c.pct_social_rent) / NULLIF(SUM(c.total_households), 0) AS pct_social_rent,
                SUM(c.total_households * c.pct_detached) / NULLIF(SUM(c.total_households), 0) AS pct_detached,
                SUM(c.total_households * c.pct_semi) / NULLIF(SUM(c.total_households), 0) AS pct_semi,
                SUM(c.total_households * c.pct_terraced) / NULLIF(SUM(c.total_households), 0) AS pct_terraced,
                SUM(c.total_households * c.pct_flat) / NULLIF(SUM(c.total_households), 0) AS pct_flat
            FROM core_census_lsoa c
            JOIN core_lsoa_boundaries l ON l.lsoa_code = c.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
            """
        ),
        {"parent_lads": parent_lads},
    )
    stock_parent_row = stock_parent.mappings().first()

    type_names = {"D": "detached", "S": "semi", "T": "terraced", "F": "flat"}
    details_by_type = {type_names.get(key, key): _round(value) for key, value in local_by_type.items() if key in type_names}
    median_details_by_type = {type_names.get(key, key): _round(value) for key, value in local_median_by_type.items() if key in type_names}

    # Keep the legacy `uk_median` detail key for frontend compatibility, but source
    # the benchmark from the precomputed rolling parent view instead of scanning the
    # full transactions table during every request.
    uk_median_result = await db.execute(
        text(
            """
            SELECT ROUND(SUM(avg_price * transactions) / NULLIF(SUM(transactions), 0))::int AS uk_median
            FROM mv_parent_rolling_price_stats
            WHERE property_type = 'ALL'
              AND transactions > 0
            """
        )
    )
    uk_median_row = uk_median_result.mappings().first()
    uk_median = int(uk_median_row["uk_median"]) if uk_median_row and uk_median_row["uk_median"] else None

    if uk_median is None and raw_parent_avg is not None:
        uk_median = _round(raw_parent_avg)

    prior_result = await db.execute(
        text(
            f"""
            SELECT ROUND(AVG(price), 2) AS avg_price
            FROM core_property_transactions
            WHERE {local_txn_filter_plain}
              AND property_type = ANY(:price_types)
              AND date_of_transfer >= CURRENT_DATE - INTERVAL '25 months'
              AND date_of_transfer < CURRENT_DATE - INTERVAL '13 months'
            """
        ),
        local_txn_params,
    )
    prior_row = prior_result.mappings().first()
    prior_avg_price = float(prior_row["avg_price"]) if prior_row and prior_row["avg_price"] else None

    price_trend = None
    if local_avg and prior_avg_price and prior_avg_price > 0:
        pct = round((local_avg - prior_avg_price) / prior_avg_price * 100, 1)
        price_trend = {
            "direction": "up" if pct > 0.05 else ("down" if pct < -0.05 else "flat"),
            "pct": pct,
        }

    avg_price_details = {
        **details_by_type,
        "uk_median": uk_median,
        "parent_median": _round(parent_median),
    }
    if price_trend:
        avg_price_details["trend"] = price_trend
    metrics.append(
        metric(
            "avg_price",
            "Average Sale Price (last 12m)",
            _round(local_avg),
            _round(parent_avg),
            "GBP",
            details=avg_price_details or None,
        )
    )

    median_details = {
        **median_details_by_type,
        "uk_median": uk_median,
        "parent_median": _round(parent_median),
    }
    metrics.append(
        metric(
            "median_price",
            "Median House Price",
            _round(local_median),
            _round(parent_median),
            "GBP",
            details=median_details or None,
        )
    )

    # ------------------------------------------------------------------
    # Price per sqft
    # ------------------------------------------------------------------
    ppsm_local = await db.execute(
        text(
            f"""
            SELECT
                AVG(price::numeric / NULLIF(floor_area_sqm::numeric, 0)) AS avg_price_per_sqm,
                AVG(CASE WHEN property_type = 'D' THEN price::numeric / NULLIF(floor_area_sqm::numeric, 0) END) AS avg_ppsm_detached,
                AVG(CASE WHEN property_type = 'S' THEN price::numeric / NULLIF(floor_area_sqm::numeric, 0) END) AS avg_ppsm_semi,
                AVG(CASE WHEN property_type = 'T' THEN price::numeric / NULLIF(floor_area_sqm::numeric, 0) END) AS avg_ppsm_terraced,
                AVG(CASE WHEN property_type = 'F' THEN price::numeric / NULLIF(floor_area_sqm::numeric, 0) END) AS avg_ppsm_flat
            FROM core_property_transactions
            WHERE {local_txn_filter_plain}
              AND floor_area_sqm > 0
              AND date_of_transfer >= CURRENT_DATE - INTERVAL '25 months'
              AND property_type = ANY(:price_types)
            """
        ),
        local_txn_params,
    )
    ppsm_row = ppsm_local.mappings().first()

    ppsm_parent = await db.execute(
        text(
            """
            SELECT avg_ppsf * 10.7639 AS avg_ppsm
            FROM mv_parent_rolling_price_stats
            WHERE parent_comparison = :parent_name
              AND property_type = 'ALL'
              AND avg_ppsf IS NOT NULL
            """
        ),
        {"parent_name": parent_name},
    )
    ppsm_parent_row = ppsm_parent.mappings().first()

    local_ppsf_headline = round(raw_local_ppsf, 0) if raw_local_ppsf is not None else None
    parent_ppsf_headline = round(raw_parent_ppsf, 0) if raw_parent_ppsf is not None else None
    if local_ppsf_headline is None and ppsm_row and ppsm_row["avg_price_per_sqm"]:
        local_ppsf_headline = round(float(ppsm_row["avg_price_per_sqm"]) / 10.7639, 0)
    if parent_ppsf_headline is None and ppsm_parent_row and ppsm_parent_row["avg_ppsm"]:
        parent_ppsf_headline = round(float(ppsm_parent_row["avg_ppsm"]) / 10.7639, 0)

    if local_ppsf_headline is not None:
        metrics.append(
            metric(
                "price_per_sqft",
                "Price per Sqft",
                local_ppsf_headline,
                parent_ppsf_headline,
                "GBP/sqft",
                details={
                    "detached": round(float(ppsm_row["avg_ppsm_detached"]) / 10.7639, 0) if ppsm_row and ppsm_row["avg_ppsm_detached"] else None,
                    "semi": round(float(ppsm_row["avg_ppsm_semi"]) / 10.7639, 0) if ppsm_row and ppsm_row["avg_ppsm_semi"] else None,
                    "terraced": round(float(ppsm_row["avg_ppsm_terraced"]) / 10.7639, 0) if ppsm_row and ppsm_row["avg_ppsm_terraced"] else None,
                    "flat": round(float(ppsm_row["avg_ppsm_flat"]) / 10.7639, 0) if ppsm_row and ppsm_row["avg_ppsm_flat"] else None,
                },
            )
        )

    # ------------------------------------------------------------------
    # Market activity
    # ------------------------------------------------------------------
    txn_yoy = None
    prior_txn = None
    if local_txn:
        prior_txn_result = await db.execute(
            text(
                f"""
                SELECT COUNT(*) AS txn
                FROM core_property_transactions
                WHERE {local_txn_filter_plain}
                  AND property_type = ANY(:price_types)
                  AND date_of_transfer >= CURRENT_DATE - INTERVAL '25 months'
                  AND date_of_transfer < CURRENT_DATE - INTERVAL '13 months'
                """
            ),
            local_txn_params,
        )
        prior_txn_row = prior_txn_result.mappings().first()
        prior_txn_raw = int(prior_txn_row["txn"]) if prior_txn_row and prior_txn_row["txn"] else None
        if prior_txn_raw and prior_txn_raw > 0:
            txn_yoy = round((local_txn_raw - prior_txn_raw) / prior_txn_raw * 100, 1)

    txn_details = {
        "local_absolute": local_txn_raw or None,
        "parent_absolute": parent_txn_total or None,
    }
    if txn_yoy is not None and prior_txn_raw:
        direction = "up" if txn_yoy > 0 else "down"
        yoy_str = f"{abs(txn_yoy):g}"
        txn_details["yoy_summary"] = f"{yoy_str}% {direction} from {prior_txn_raw:,} sales in the prior 12 months"

    metrics.append(
        metric(
            "transaction_volume",
            "Transaction Volume (last 12m)",
            local_txn or None,
            parent_txn or None,
            "sales/LSOA",
            details=txn_details,
        )
    )

    total_tenure = (local_freehold or 0) + (local_leasehold or 0)
    freehold_pct = round(local_freehold / total_tenure * 100, 1) if total_tenure > 0 else None
    leasehold_pct = round(local_leasehold / total_tenure * 100, 1) if total_tenure > 0 else None

    parent_freehold_pct = None
    parent_leasehold_pct = None
    if parent_lads:
        parent_tenure_result = await db.execute(
            text(
                """
                SELECT COUNT(*) FILTER (WHERE duration = 'F') AS fh,
                       COUNT(*) FILTER (WHERE duration = 'L') AS lh
                FROM core_property_transactions
                WHERE lad_code = ANY(:lads)
                  AND property_type = ANY(:price_types)
                  AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                """
            ),
            {"lads": parent_lads, "price_types": price_types},
        )
        parent_tenure_row = parent_tenure_result.mappings().first()
        if parent_tenure_row:
            parent_tenure_total = int(parent_tenure_row["fh"] or 0) + int(parent_tenure_row["lh"] or 0)
            if parent_tenure_total > 0:
                parent_freehold_pct = round(int(parent_tenure_row["fh"]) / parent_tenure_total * 100, 1)
                parent_leasehold_pct = round(int(parent_tenure_row["lh"]) / parent_tenure_total * 100, 1)

    local_fh_price = _wavg(
        [float(row["avg_freehold_price"]) for row in local_rows if row["avg_freehold_price"] and row["property_type"] in PRICE_TYPES],
        [int(row["freehold_count"]) for row in local_rows if row["avg_freehold_price"] and row["property_type"] in PRICE_TYPES],
    )
    local_lh_price = _wavg(
        [float(row["avg_leasehold_price"]) for row in local_rows if row["avg_leasehold_price"] and row["property_type"] in PRICE_TYPES],
        [int(row["leasehold_count"]) for row in local_rows if row["avg_leasehold_price"] and row["property_type"] in PRICE_TYPES],
    )

    # Build breakdown for table rendering
    fl_breakdown = [
        {"label": "Freehold", "count": local_freehold, "pct": freehold_pct, "parent_pct": parent_freehold_pct, "avg_price": _round(local_fh_price)},
        {"label": "Leasehold", "count": local_leasehold, "pct": leasehold_pct, "parent_pct": parent_leasehold_pct, "avg_price": _round(local_lh_price)},
    ]

    # Dynamic headline: pick dominant type, parent comparison is SAME type
    if (freehold_pct or 0) >= (leasehold_pct or 0):
        fl_headline_value = freehold_pct
        fl_headline_parent = parent_freehold_pct
        fl_headline_unit = "% freehold"
    else:
        fl_headline_value = leasehold_pct
        fl_headline_parent = parent_leasehold_pct
        fl_headline_unit = "% leasehold"

    freehold_details = {
        "breakdown": fl_breakdown,
        "breakdown_type": "tenure_table",
        "count_label": "Transactions",
    }

    metrics.append(
        metric(
            "freehold_leasehold",
            "Freehold vs Leasehold",
            fl_headline_value,
            fl_headline_parent,
            fl_headline_unit,
            details=freehold_details,
        )
    )

    nb_trend_result = await db.execute(
        text(
            f"""
            SELECT EXTRACT(YEAR FROM date_of_transfer)::int AS yr,
                   COUNT(*) FILTER (WHERE old_new = 'Y') AS nb,
                   COUNT(*) AS txn
            FROM core_property_transactions
            WHERE {local_txn_filter_plain}
              AND property_type = ANY(:price_types)
            GROUP BY yr
            ORDER BY yr
            """
        ),
        local_txn_params,
    )
    nb_trend = []
    for row in nb_trend_result.mappings().all():
        if row["txn"] and int(row["txn"]) > 0 and row["nb"] is not None:
            nb_count = int(row["nb"])
            txn_count = int(row["txn"])
            nb_trend.append(
                {
                    "year": int(row["yr"]),
                    "new_builds": nb_count,
                    "total": txn_count,
                    "pct": round(nb_count / txn_count * 100, 1),
                }
            )

    parent_newbuild_pct = None
    if parent_lads:
        parent_nb_result = await db.execute(
            text(
                """
                SELECT COUNT(*) FILTER (WHERE old_new = 'Y') AS nb,
                       COUNT(*) AS txn
                FROM core_property_transactions
                WHERE lad_code = ANY(:lads)
                  AND property_type = ANY(:price_types)
                  AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                """
            ),
            {"lads": parent_lads, "price_types": price_types},
        )
        parent_nb_row = parent_nb_result.mappings().first()
        if parent_nb_row and parent_nb_row["txn"] and int(parent_nb_row["txn"]) > 0:
            parent_newbuild_pct = round(int(parent_nb_row["nb"]) / int(parent_nb_row["txn"]) * 100, 1)

    newbuild_pct = round(local_newbuild / local_txn_raw * 100, 1) if local_txn_raw else None
    metrics.append(
        metric(
            "new_build_proportion",
            "New Build Proportion (last 12m)",
            newbuild_pct,
            parent_newbuild_pct,
            "%",
            details={
                "nb_trend": nb_trend,
                "caveat_note": "Based on Land Registry's new-build flag, which can undercount conversions and some redevelopments.",
            },
        )
    )

    # ------------------------------------------------------------------
    # Price trend (year-on-year) — from raw transactions at search-key level
    # ------------------------------------------------------------------
    local_price_yoy = None   # used later by investment_grade
    parent_price_yoy = None
    trend_series_result = await db.execute(
        text(
            f"""
            SELECT EXTRACT(YEAR FROM date_of_transfer)::int AS year,
                   ROUND(AVG(price))::int AS avg_price,
                   COUNT(*) AS txn_count,
                   ROUND(AVG(CASE WHEN property_type = 'D' THEN price END))::int AS detached,
                   ROUND(AVG(CASE WHEN property_type = 'S' THEN price END))::int AS semi,
                   ROUND(AVG(CASE WHEN property_type = 'T' THEN price END))::int AS terraced,
                   ROUND(AVG(CASE WHEN property_type = 'F' THEN price END))::int AS flat
            FROM core_property_transactions
            WHERE {local_txn_filter_plain}
              AND property_type = ANY(:price_types)
              AND date_of_transfer >= '2010-01-01'
            GROUP BY 1
            ORDER BY 1
            """
        ),
        local_txn_params,
    )
    trend_rows = trend_series_result.mappings().all()

    if len(trend_rows) >= 2:
        # Build series with YoY % computed from avg prices
        trend_series = []
        for i, r in enumerate(trend_rows):
            avg = int(r["avg_price"]) if r["avg_price"] else None
            prev_avg = int(trend_rows[i - 1]["avg_price"]) if i > 0 and trend_rows[i - 1]["avg_price"] else None
            yoy = round((avg - prev_avg) / prev_avg * 100, 1) if avg and prev_avg and prev_avg > 0 else None
            trend_series.append({
                "year": int(r["year"]),
                "avg_price": avg,
                "yoy_pct": yoy,
                "detached": int(r["detached"]) if r["detached"] else None,
                "semi": int(r["semi"]) if r["semi"] else None,
                "terraced": int(r["terraced"]) if r["terraced"] else None,
                "flat": int(r["flat"]) if r["flat"] else None,
            })

        # Headline: latest year's YoY %
        latest_yoy = trend_series[-1]["yoy_pct"]
        local_price_yoy = latest_yoy  # for investment_grade later

        # Parent YoY from pre-computed materialized view
        parent_yoy = None
        if parent_lads:
            parent_trend_result = await db.execute(
                text(
                    """
                    SELECT avg_price
                    FROM mv_parent_yearly_price_stats
                    WHERE parent_comparison = :parent_name
                      AND property_type = 'ALL'
                    ORDER BY year DESC
                    LIMIT 2
                    """
                ),
                {"parent_name": parent_name},
            )
            parent_rows_yoy = parent_trend_result.mappings().all()
            if len(parent_rows_yoy) >= 2:
                cur_p = float(parent_rows_yoy[0]["avg_price"]) if parent_rows_yoy[0]["avg_price"] else None
                prev_p = float(parent_rows_yoy[1]["avg_price"]) if parent_rows_yoy[1]["avg_price"] else None
                if cur_p and prev_p and prev_p > 0:
                    parent_yoy = round((cur_p - prev_p) / prev_p * 100, 1)
        parent_price_yoy = parent_yoy  # for investment_grade later

        trend_details = {
            "hpi_series": trend_series,
            "data_note": "Year-on-year price change computed from Land Registry transactions for this search area.",
        }
        metrics.append(
            metric(
                "price_trend_yoy",
                "Price Trend (Year-on-Year)",
                latest_yoy,
                parent_yoy,
                "%",
                details=trend_details,
            )
        )

    # ------------------------------------------------------------------
    # Rental market and affordability
    # ------------------------------------------------------------------
    # VOA PRMS data predates 2021/2023 LAD restructures — expand new codes
    # to their old constituent district codes so the lookup succeeds.
    voa_local = list(local_lads)
    for code in local_lads:
        voa_local.extend(VOA_LAD_REMAP.get(code, []))
    voa_parent = list(parent_lads)
    for code in parent_lads:
        voa_parent.extend(VOA_LAD_REMAP.get(code, []))

    rent_period_result = await db.execute(
        text("SELECT MAX(period) AS latest_period FROM core_voa_rents_lad WHERE lad_code = ANY(:lads)"),
        {"lads": voa_local},
    )
    rent_period_row = rent_period_result.mappings().first()
    rent_period = rent_period_row["latest_period"] if rent_period_row else None

    rent_row = None
    rent_parent_row = None
    if rent_period:
        rent_local = await db.execute(
            text(
                """
                SELECT AVG(median_rent_all) AS median_rent_all,
                       AVG(median_rent_1bed) AS median_rent_1bed,
                       AVG(median_rent_2bed) AS median_rent_2bed,
                       AVG(median_rent_3bed) AS median_rent_3bed,
                       AVG(median_rent_4bed) AS median_rent_4bed
                FROM core_voa_rents_lad
                WHERE lad_code = ANY(:lads)
                  AND period = :period
                """
            ),
            {"lads": voa_local, "period": rent_period},
        )
        rent_row = rent_local.mappings().first()

        rent_parent = await db.execute(
            text(
                """
                SELECT AVG(median_rent_all) AS avg_rent
                FROM core_voa_rents_lad
                WHERE lad_code = ANY(:lads)
                  AND period = :period
                """
            ),
            {"lads": voa_parent, "period": rent_period},
        )
        rent_parent_row = rent_parent.mappings().first()

    gross_yield = None
    if rent_row and rent_row["median_rent_all"] is not None:
        rent_details = {
            "1bed": _round(rent_row["median_rent_1bed"]),
            "2bed": _round(rent_row["median_rent_2bed"]),
            "3bed": _round(rent_row["median_rent_3bed"]),
            "4bed": _round(rent_row["median_rent_4bed"]),
            "source_period": rent_period,
            "data_note": "Source: ONS Private Rental Market Statistics. Published at local-authority level only; sub-LAD searches inherit the relevant LAD value.",
        }
        if local_avg:
            rent_details.update(
                {
                    "yield_1bed": round(float(rent_row["median_rent_1bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_1bed"] else None,
                    "yield_2bed": round(float(rent_row["median_rent_2bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_2bed"] else None,
                    "yield_3bed": round(float(rent_row["median_rent_3bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_3bed"] else None,
                    "yield_4bed": round(float(rent_row["median_rent_4bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_4bed"] else None,
                }
            )

        metrics.append(
            metric(
                "median_rent",
                "Median Monthly Rent",
                _round(rent_row["median_rent_all"]),
                _round(rent_parent_row["avg_rent"]) if rent_parent_row else None,
                "GBP/month",
                details=rent_details,
            )
        )

        if local_avg and rent_row["median_rent_all"]:
            annual_rent = float(rent_row["median_rent_all"]) * 12
            gross_yield = round(annual_rent / local_avg * 100, 2)
            parent_yield = None
            if parent_avg and rent_parent_row and rent_parent_row["avg_rent"]:
                parent_annual = float(rent_parent_row["avg_rent"]) * 12
                parent_yield = round(parent_annual / parent_avg * 100, 2)

            if is_lad_or_coarser:
                yield_details = {
                    "source_period": rent_period,
                    "data_note": "Combines LAD-level VOA rent evidence with recent purchase prices. Interpret as borough/county investment context rather than a hyperlocal street-level yield.",
                }
                for beds, column in [("1bed", "median_rent_1bed"), ("2bed", "median_rent_2bed"), ("3bed", "median_rent_3bed"), ("4bed", "median_rent_4bed")]:
                    if rent_row[column] and local_avg:
                        yield_details[beds] = round(float(rent_row[column]) * 12 / local_avg * 100, 2)
                        yield_details[f"rent_{beds}"] = _round(rent_row[column])
                metrics.append(
                    metric(
                        "gross_yield",
                        "Gross Rental Yield",
                        gross_yield,
                        parent_yield,
                        "%",
                        details=yield_details,
                    )
                )
            else:
                metrics.append(
                    metric(
                        "gross_yield",
                        "Gross Rental Yield",
                        None,
                        None,
                        "%",
                        details={
                            "source_period": rent_period,
                            "data_note": "Rent data is only available at local authority level, so yield cannot be calculated for this search type.",
                        },
                    )
                )

        earnings_result = await db.execute(
            text("SELECT AVG(median_annual_earnings) AS median_annual_earnings FROM core_earnings_lad WHERE lad_code = ANY(:lads)"),
            {"lads": local_lads},
        )
        earnings_row = earnings_result.mappings().first()
        earnings_parent = await db.execute(
            text("SELECT AVG(median_annual_earnings) AS avg_earn FROM core_earnings_lad WHERE lad_code = ANY(:lads)"),
            {"lads": parent_lads},
        )
        earnings_parent_row = earnings_parent.mappings().first()

        if earnings_row and earnings_row["median_annual_earnings"] and rent_row["median_rent_all"]:
            local_annual_rent = float(rent_row["median_rent_all"]) * 12
            local_afford = round(local_annual_rent / float(earnings_row["median_annual_earnings"]) * 100, 1)
            parent_afford = None
            if earnings_parent_row and earnings_parent_row["avg_earn"] and rent_parent_row and rent_parent_row["avg_rent"]:
                parent_annual_rent = float(rent_parent_row["avg_rent"]) * 12
                parent_afford = round(parent_annual_rent / float(earnings_parent_row["avg_earn"]) * 100, 1)

            if is_lad_or_coarser:
                metrics.append(
                    metric(
                        "affordability",
                        "Rent Affordability",
                        local_afford,
                        parent_afford,
                        "% of income",
                        details={
                            "annual_rent": round(local_annual_rent),
                            "median_earnings": round(float(earnings_row["median_annual_earnings"])),
                            "source_period": rent_period,
                            "data_note": "Calculated from LAD-level VOA rent and LAD-level residence-based ASHE earnings.",
                        },
                    )
                )
            else:
                metrics.append(
                    metric(
                        "affordability",
                        "Rent Affordability",
                        None,
                        None,
                        "% of income",
                        details={
                            "source_period": rent_period,
                            "data_note": "Rent and earnings data are only available at local authority level.",
                        },
                    )
                )

    # (Earnings query retained here for affordability calculation above;
    #  standalone median_earnings metric now emitted from tab_community.py)

    # ------------------------------------------------------------------
    # Investment grade heuristic
    # ------------------------------------------------------------------
    def _grade_from_combined(score):
        if score >= 10:
            return "A"
        elif score >= 7:
            return "B"
        elif score >= 5:
            return "C"
        elif score >= 3:
            return "D"
        elif score >= 1:
            return "E"
        return "F"

    if local_price_yoy is not None:
        yoy = float(local_price_yoy)
        combined = (gross_yield or 0) + yoy

        # Derive parent investment grade from parent yield + parent price YoY
        parent_grade = None
        # parent_yield may not be in scope (defined inside rent block); recompute from available data
        p_yield = None
        if parent_avg and rent_parent_row and rent_parent_row["avg_rent"]:
            p_yield = round(float(rent_parent_row["avg_rent"]) * 12 / parent_avg * 100, 2)
        if parent_price_yoy is not None and p_yield is not None:
            parent_grade = _grade_from_combined(p_yield + parent_price_yoy)

        if is_lad_or_coarser and gross_yield is not None:
            grade = _grade_from_combined(combined)
            metrics.append(
                metric(
                    "investment_grade",
                    "Investment Grade",
                    grade,
                    parent_grade,
                    "grade",
                    details={
                        "gross_yield": _round(gross_yield),
                        "capital_growth_yoy": _round(yoy),
                        "combined_score": round(combined, 2),
                        "source_period": rent_period,
                        "data_note": "This is a heuristic interpretation layer built from gross rental yield and year-on-year price growth. It should be read as a quick synthesis, not as an official statistic.",
                    },
                )
            )
        else:
            metrics.append(
                metric(
                    "investment_grade",
                    "Investment Grade",
                    None,
                    None,
                    "grade",
                    details={
                        "source_period": rent_period,
                        "data_note": "Source data is only available at local authority level.",
                    },
                )
            )

    # ------------------------------------------------------------------
    # EPC housing-stock efficiency
    # ------------------------------------------------------------------
    epc_local = await db.execute(
        text(
            """
            SELECT SUM(total_certs * avg_energy_score) / NULLIF(SUM(total_certs), 0) AS avg_energy_score,
                   SUM(total_certs * pct_a) / NULLIF(SUM(total_certs), 0) AS pct_a,
                   SUM(total_certs * pct_b) / NULLIF(SUM(total_certs), 0) AS pct_b,
                   SUM(total_certs * pct_c) / NULLIF(SUM(total_certs), 0) AS pct_c,
                   SUM(total_certs * pct_d) / NULLIF(SUM(total_certs), 0) AS pct_d,
                   SUM(total_certs * pct_e) / NULLIF(SUM(total_certs), 0) AS pct_e,
                   SUM(total_certs * pct_f) / NULLIF(SUM(total_certs), 0) AS pct_f,
                   SUM(total_certs * pct_g) / NULLIF(SUM(total_certs), 0) AS pct_g,
                   SUM(total_certs * heat_gas_pct) / NULLIF(SUM(total_certs), 0) AS heat_gas_pct,
                   SUM(total_certs * heat_electric_pct) / NULLIF(SUM(total_certs), 0) AS heat_electric_pct,
                   SUM(total_certs * heat_oil_pct) / NULLIF(SUM(total_certs), 0) AS heat_oil_pct,
                   SUM(total_certs * heat_district_pct) / NULLIF(SUM(total_certs), 0) AS heat_district_pct,
                   SUM(total_certs * heat_other_pct) / NULLIF(SUM(total_certs), 0) AS heat_other_pct,
                   SUM(total_certs * heat_none_pct) / NULLIF(SUM(total_certs), 0) AS heat_none_pct
            FROM core_epc_lsoa
            WHERE lsoa_code = ANY(:codes)
            """
        ),
        {"codes": lsoa_codes},
    )
    epc_row = epc_local.mappings().first()

    epc_parent = await db.execute(
        text(
            """
            SELECT SUM(e.total_certs * e.avg_energy_score) / NULLIF(SUM(e.total_certs), 0) AS avg_score,
                   SUM(e.total_certs * e.pct_a) / NULLIF(SUM(e.total_certs), 0) AS pct_a,
                   SUM(e.total_certs * e.pct_b) / NULLIF(SUM(e.total_certs), 0) AS pct_b,
                   SUM(e.total_certs * e.pct_c) / NULLIF(SUM(e.total_certs), 0) AS pct_c,
                   SUM(e.total_certs * e.pct_d) / NULLIF(SUM(e.total_certs), 0) AS pct_d,
                   SUM(e.total_certs * e.pct_e) / NULLIF(SUM(e.total_certs), 0) AS pct_e,
                   SUM(e.total_certs * e.pct_f) / NULLIF(SUM(e.total_certs), 0) AS pct_f,
                   SUM(e.total_certs * e.pct_g) / NULLIF(SUM(e.total_certs), 0) AS pct_g
            FROM core_epc_lsoa e
            JOIN core_lsoa_boundaries l ON l.lsoa_code = e.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
            """
        ),
        {"parent_lads": parent_lads},
    )
    epc_parent_row = epc_parent.mappings().first()

    if epc_row and epc_row["avg_energy_score"] is not None:
        local_c_plus = float(epc_row["pct_a"] or 0) + float(epc_row["pct_b"] or 0) + float(epc_row["pct_c"] or 0)
        parent_c_plus = None
        parent_avg_score = None
        parent_ratings = None
        if epc_parent_row and epc_parent_row["avg_score"] is not None:
            parent_avg_score = _round(epc_parent_row["avg_score"])
            parent_c_plus = round(
                float(epc_parent_row["pct_a"] or 0)
                + float(epc_parent_row["pct_b"] or 0)
                + float(epc_parent_row["pct_c"] or 0),
                2,
            )
            parent_ratings = {
                "a": _round(epc_parent_row["pct_a"]),
                "b": _round(epc_parent_row["pct_b"]),
                "c": _round(epc_parent_row["pct_c"]),
                "d": _round(epc_parent_row["pct_d"]),
                "e": _round(epc_parent_row["pct_e"]),
                "f": _round(epc_parent_row["pct_f"]),
                "g": _round(epc_parent_row["pct_g"]),
            }

        metrics.append(
            metric(
                "epc_energy_score",
                "EPC Energy Score",
                _round(epc_row["avg_energy_score"]),
                parent_avg_score,
                "score",
                details={
                    "avg_energy_score": _round(epc_row["avg_energy_score"]),
                    "parent_avg_score": parent_avg_score,
                    "pct_a": _round(epc_row["pct_a"]),
                    "pct_b": _round(epc_row["pct_b"]),
                    "pct_c": _round(epc_row["pct_c"]),
                    "pct_d": _round(epc_row["pct_d"]),
                    "pct_e": _round(epc_row["pct_e"]),
                    "pct_f": _round(epc_row["pct_f"]),
                    "pct_g": _round(epc_row["pct_g"]),
                    "heat_gas_pct": _round(epc_row["heat_gas_pct"]),
                    "heat_electric_pct": _round(epc_row["heat_electric_pct"]),
                    "heat_oil_pct": _round(epc_row["heat_oil_pct"]),
                    "heat_district_pct": _round(epc_row["heat_district_pct"]),
                    "heat_other_pct": _round(epc_row["heat_other_pct"]),
                    "heat_none_pct": _round(epc_row["heat_none_pct"]),
                    "parent_ratings": parent_ratings,
                    "c_plus_pct": round(local_c_plus, 2),
                    "parent_c_plus_pct": parent_c_plus,
                },
            )
        )

    # ------------------------------------------------------------------
    # Housing Tenure & Housing Stock (Census 2021, moved from Community tab)
    # ------------------------------------------------------------------
    housing_local = await db.execute(
        text(
            """
            SELECT SUM(total_households) as total_households,
                   SUM(total_households * pct_owned) / NULLIF(SUM(total_households), 0) as pct_owned,
                   SUM(total_households * pct_social_rent) / NULLIF(SUM(total_households), 0) as pct_social_rent,
                   SUM(total_households * pct_private_rent) / NULLIF(SUM(total_households), 0) as pct_private_rent,
                   SUM(total_households * pct_detached) / NULLIF(SUM(total_households), 0) as pct_detached,
                   SUM(total_households * pct_semi) / NULLIF(SUM(total_households), 0) as pct_semi,
                   SUM(total_households * pct_terraced) / NULLIF(SUM(total_households), 0) as pct_terraced,
                   SUM(total_households * pct_flat) / NULLIF(SUM(total_households), 0) as pct_flat
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
            """
        ),
        {"codes": lsoa_codes},
    )
    housing_row = housing_local.mappings().first()

    housing_parent = await db.execute(
        text(
            """
            SELECT SUM(h.total_households * h.pct_owned) / NULLIF(SUM(h.total_households), 0) as avg_owned,
                   SUM(h.total_households * h.pct_social_rent) / NULLIF(SUM(h.total_households), 0) as avg_social_rent,
                   SUM(h.total_households * h.pct_private_rent) / NULLIF(SUM(h.total_households), 0) as avg_priv_rent,
                   SUM(h.total_households * h.pct_detached) / NULLIF(SUM(h.total_households), 0) as avg_det,
                   SUM(h.total_households * h.pct_semi) / NULLIF(SUM(h.total_households), 0) as avg_semi,
                   SUM(h.total_households * h.pct_terraced) / NULLIF(SUM(h.total_households), 0) as avg_terr,
                   SUM(h.total_households * h.pct_flat) / NULLIF(SUM(h.total_households), 0) as avg_flat
            FROM core_census_lsoa h
            JOIN core_lsoa_boundaries l ON l.lsoa_code = h.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
            """
        ),
        {"parent_lads": parent_lads},
    )
    housing_parent_row = housing_parent.mappings().first()

    if housing_row:
        total_hh = int(housing_row["total_households"]) if housing_row["total_households"] else 0

        # Housing Tenure — breakdown with counts derived from total_households * pct
        # (label, local_col, parent_col, unit_qualifier)
        tenure_categories = [
            ("Owner-occupied", "pct_owned", "avg_owned", "owner-occupied"),
            ("Social rent", "pct_social_rent", "avg_social_rent", "socially rented"),
            ("Private rent", "pct_private_rent", "avg_priv_rent", "privately rented"),
        ]
        tenure_breakdown = []
        for label, local_key, parent_key, _uq in tenure_categories:
            pct = _round(housing_row[local_key])
            count = round(total_hh * float(pct) / 100) if pct and total_hh else None
            parent_pct = _round(housing_parent_row[parent_key]) if housing_parent_row else None
            tenure_breakdown.append({"label": label, "count": count, "pct": pct, "parent_pct": parent_pct})

        # Dynamic headline: pick dominant tenure type
        dominant_idx = max(range(len(tenure_breakdown)), key=lambda i: tenure_breakdown[i]["pct"] or 0)
        dominant_tenure = tenure_breakdown[dominant_idx]
        dominant_tenure_unit = tenure_categories[dominant_idx][3]
        metrics.append(
            metric(
                "housing_tenure",
                "Housing Tenure",
                dominant_tenure["pct"],
                dominant_tenure["parent_pct"],
                f"% {dominant_tenure_unit}",
                details={
                    "breakdown": tenure_breakdown,
                    "total_households": total_hh or None,
                    "breakdown_type": "tenure_table",
                    "count_label": "Households",
                },
            )
        )

        # Housing Stock — breakdown with counts derived from total_households * pct
        # (label, local_col, parent_col, unit_qualifier)
        stock_categories = [
            ("Detached", "pct_detached", "avg_det", "detached"),
            ("Semi-detached", "pct_semi", "avg_semi", "semi-detached"),
            ("Terraced", "pct_terraced", "avg_terr", "terraced"),
            ("Flat", "pct_flat", "avg_flat", "flats"),
        ]
        stock_breakdown = []
        for label, local_key, parent_key, _uq in stock_categories:
            pct = _round(housing_row[local_key])
            count = round(total_hh * float(pct) / 100) if pct and total_hh else None
            parent_pct = _round(housing_parent_row[parent_key]) if housing_parent_row else None
            stock_breakdown.append({"label": label, "count": count, "pct": pct, "parent_pct": parent_pct})

        # Dynamic headline: pick dominant stock type
        dominant_idx = max(range(len(stock_breakdown)), key=lambda i: stock_breakdown[i]["pct"] or 0)
        dominant_stock = stock_breakdown[dominant_idx]
        dominant_stock_unit = stock_categories[dominant_idx][3]
        metrics.append(
            metric(
                "housing_type",
                "Housing Stock",
                dominant_stock["pct"],
                dominant_stock["parent_pct"],
                f"% {dominant_stock_unit}",
                details={
                    "breakdown": stock_breakdown,
                    "total_households": total_hh or None,
                    "breakdown_type": "tenure_table",
                    "count_label": "Households",
                },
            )
        )

    return metrics


def _wavg(values, weights):
    pairs = [(value, weight) for value, weight in zip(values, weights) if weight and weight > 0]
    if not pairs:
        return None
    total_weight = sum(weight for _, weight in pairs)
    return sum(value * weight for value, weight in pairs) / total_weight if total_weight else None


def _round(val):
    if val is None:
        return None
    return round(float(val), 2)
