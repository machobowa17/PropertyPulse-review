"""Property & Market tab service.

Headline prices and price-per-sqft come from the Hetzner Property API which
queries the gold table (PPD + EPC matched data).
Parent comparison prices come from the pre-computed rolling parent view on EC2.
Rental and earnings context remain LAD-level only.
Housing-stock context is pulled from Census and EPC LSOA aggregates on EC2.
"""
import logging

from sqlalchemy import text

from app.constants import PRICE_TYPES, VOA_LAD_REMAP
from app.services.helpers import metric

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Property API client (Hetzner)
# ---------------------------------------------------------------------------
# Import lazily to avoid circular imports and allow graceful fallback
_property_api = None


def _get_property_api():
    global _property_api
    if _property_api is None:
        try:
            from etl_lib import property_api
            _property_api = property_api
        except ImportError:
            logger.warning("property_api module not available — will fall back to local DB")
    return _property_api


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

    # ------------------------------------------------------------------
    # Call Hetzner Property API for all transaction-based aggregations
    # LAD/county: use pre-aggregated LAD endpoint (instant, reads MVs)
    # Postcode/ward/place: use LSOA endpoint (live scan, fast for small sets)
    # ------------------------------------------------------------------
    prop_api = _get_property_api()
    api_data = None

    if prop_api and is_lad_or_coarser and local_lads:
        # Fast path: LAD-level pre-aggregated data (no LSOA expansion needed)
        api_data = prop_api.aggregate_transactions_by_lad(local_lads, price_types)
        if api_data is None:
            logger.warning("Property API LAD aggregate returned None — falling back to LSOA path")
            # Fall back to LSOA path if LAD endpoint unavailable
            lsoa_result = await db.execute(
                text("SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = ANY(:lads)"),
                {"lads": local_lads},
            )
            api_lsoa_codes = [row["lsoa_code"] for row in lsoa_result.mappings().all()]
            if api_lsoa_codes:
                api_data = prop_api.aggregate_transactions(api_lsoa_codes, price_types)
    elif prop_api:
        # Standard path: LSOA-level live aggregation (postcode, ward, place)
        api_lsoa_codes = list(lsoa_codes) if lsoa_codes else []
        if api_lsoa_codes:
            api_data = prop_api.aggregate_transactions(api_lsoa_codes, price_types)

    if api_data is None and prop_api:
        logger.warning("Property API returned None — no transaction data available")

    # ------------------------------------------------------------------
    # Extract local transaction aggregations from API response
    # ------------------------------------------------------------------
    if api_data:
        core = api_data.get("core_recent") or {}
        by_type_rows = api_data.get("by_type") or []
        ppsm_data = api_data.get("ppsm") or {}
        prior_data = api_data.get("prior_avg") or {}
        prior_txn_data = api_data.get("prior_txn") or {}
        nb_trend_data = api_data.get("nb_trend") or []
        price_trend_data = api_data.get("price_trend") or []
        spread_data = api_data.get("price_spread") or {}
    else:
        core = {}
        by_type_rows = []
        ppsm_data = {}
        prior_data = {}
        prior_txn_data = {}
        nb_trend_data = []
        price_trend_data = []
        spread_data = {}

    # ------------------------------------------------------------------
    # Core recent sales prices (from API)
    # ------------------------------------------------------------------
    raw_local_avg = float(core["avg_price"]) if core.get("avg_price") is not None else None
    raw_local_median = float(core["median_price"]) if core.get("median_price") is not None else None
    raw_local_ppsf = float(core["avg_ppsf"]) if core.get("avg_ppsf") is not None else None

    # Parent comparison from pre-computed materialized view (stays on EC2)
    if parent_lads:
        raw_parent = await db.execute(
            text(
                """
                SELECT ROUND(SUM(avg_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS avg_price,
                       ROUND(SUM(median_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS median_price,
                       SUM(avg_ppsf * transactions) / NULLIF(SUM(transactions), 0) AS avg_ppsf
                FROM mv_parent_rolling_price_stats
                WHERE lad_code = ANY(:parent_lads)
                  AND property_type = 'ALL'
                """
            ),
            {"parent_lads": parent_lads},
        )
        raw_parent_row = raw_parent.mappings().first()
    else:
        raw_parent_row = None

    raw_parent_avg = float(raw_parent_row["avg_price"]) if raw_parent_row and raw_parent_row["avg_price"] is not None else None
    raw_parent_median = float(raw_parent_row["median_price"]) if raw_parent_row and raw_parent_row["median_price"] is not None else None
    raw_parent_ppsf = float(raw_parent_row["avg_ppsf"]) if raw_parent_row and raw_parent_row["avg_ppsf"] is not None else None

    # Process by-type rows from API
    local_by_type = {}
    local_median_by_type = {}
    local_rows = by_type_rows  # alias for readability
    for row in local_rows:
        property_type = row.get("property_type", "")
        if property_type in PRICE_TYPES:
            local_by_type[property_type] = float(row["avg_price"]) if row.get("avg_price") else None
            local_median_by_type[property_type] = float(row["median_price"]) if row.get("median_price") else None

    local_avg = raw_local_avg or _wavg(
        [float(row["avg_price"]) for row in local_rows if row.get("avg_price") and row.get("property_type") in PRICE_TYPES],
        [int(row["transaction_count"]) for row in local_rows if row.get("avg_price") and row.get("property_type") in PRICE_TYPES],
    )
    local_median = raw_local_median or _wavg(
        [float(row["median_price"]) for row in local_rows if row.get("median_price") and row.get("property_type") in PRICE_TYPES],
        [int(row["transaction_count"]) for row in local_rows if row.get("median_price") and row.get("property_type") in PRICE_TYPES],
    )
    local_txn_raw = sum(
        int(row["transaction_count"])
        for row in local_rows
        if row.get("transaction_count") and row.get("property_type") in PRICE_TYPES
    )
    local_lsoa_count = len(lsoa_codes) if lsoa_codes else 1
    local_txn = round(local_txn_raw / local_lsoa_count, 1) if local_txn_raw else 0
    local_newbuild = sum(int(row["new_build_count"]) for row in local_rows if row.get("new_build_count") and row.get("property_type") in PRICE_TYPES)
    local_freehold = sum(int(row["freehold_count"]) for row in local_rows if row.get("freehold_count"))
    local_leasehold = sum(int(row["leasehold_count"]) for row in local_rows if row.get("leasehold_count"))

    # Parent by-type from materialized view (stays on EC2)
    parent_prices = await db.execute(
        text(
            """
            SELECT property_type,
                   ROUND(SUM(avg_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::numeric AS avg_price,
                   ROUND(SUM(median_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::numeric AS median_price,
                   SUM(transactions) AS transaction_count
            FROM mv_parent_rolling_price_stats
            WHERE lad_code = ANY(:parent_lads)
              AND property_type != 'ALL'
            GROUP BY property_type
            """
        ),
        {"parent_lads": parent_lads},
    )
    parent_rows = parent_prices.mappings().all()

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
    # Housing-stock context from Census 2021 (stays on EC2)
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

    # Prior period avg price (from API)
    prior_avg_price = float(prior_data["avg_price"]) if prior_data.get("avg_price") is not None else None

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
    # Price per sqft (from API)
    # ------------------------------------------------------------------
    ppsm_row = ppsm_data

    ppsm_parent = await db.execute(
        text(
            """
            SELECT SUM(avg_ppsf * transactions) / NULLIF(SUM(transactions), 0) * 10.7639 AS avg_ppsm
            FROM mv_parent_rolling_price_stats
            WHERE lad_code = ANY(:parent_lads)
              AND property_type = 'ALL'
              AND avg_ppsf IS NOT NULL
            """
        ),
        {"parent_lads": parent_lads},
    )
    ppsm_parent_row = ppsm_parent.mappings().first()

    local_ppsf_headline = round(raw_local_ppsf, 0) if raw_local_ppsf is not None else None
    parent_ppsf_headline = round(raw_parent_ppsf, 0) if raw_parent_ppsf is not None else None
    if local_ppsf_headline is None and ppsm_row.get("avg_price_per_sqm"):
        local_ppsf_headline = round(float(ppsm_row["avg_price_per_sqm"]) / 10.7639, 0)
    if parent_ppsf_headline is None and ppsm_parent_row and ppsm_parent_row["avg_ppsm"]:
        parent_ppsf_headline = round(float(ppsm_parent_row["avg_ppsm"]) / 10.7639, 0)

    if local_ppsf_headline is not None:
        # EPC coverage footnote
        _total_txn = ppsm_row.get("total_txn")
        _with_area = ppsm_row.get("txn_with_area")
        _coverage_note = None
        if _total_txn and _with_area:
            _pct = round(_with_area / _total_txn * 100, 1)
            _coverage_note = f"Based on {_pct}% of sales with EPC floor area ({_with_area:,} of {_total_txn:,})."
        metrics.append(
            metric(
                "price_per_sqft",
                "Price per Sqft",
                local_ppsf_headline,
                parent_ppsf_headline,
                "GBP/sqft",
                details={
                    "detached": round(float(ppsm_row["avg_ppsm_detached"]) / 10.7639, 0) if ppsm_row.get("avg_ppsm_detached") else None,
                    "semi": round(float(ppsm_row["avg_ppsm_semi"]) / 10.7639, 0) if ppsm_row.get("avg_ppsm_semi") else None,
                    "terraced": round(float(ppsm_row["avg_ppsm_terraced"]) / 10.7639, 0) if ppsm_row.get("avg_ppsm_terraced") else None,
                    "flat": round(float(ppsm_row["avg_ppsm_flat"]) / 10.7639, 0) if ppsm_row.get("avg_ppsm_flat") else None,
                    "data_note": _coverage_note,
                },
            )
        )

    # ------------------------------------------------------------------
    # Market activity (from API)
    # ------------------------------------------------------------------
    txn_yoy = None
    prior_txn_raw = int(prior_txn_data["txn"]) if prior_txn_data.get("txn") else None
    if local_txn and prior_txn_raw and prior_txn_raw > 0:
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

    # Parent tenure — use Hetzner API if available, otherwise fall back to EC2
    parent_freehold_pct = None
    parent_leasehold_pct = None
    parent_nb_data = None
    if parent_lads:
        # Resolve parent LADs to LSOA codes for the API call
        parent_lsoa_result = await db.execute(
            text("SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = ANY(:lads)"),
            {"lads": parent_lads},
        )
        parent_lsoa_codes = [row["lsoa_code"] for row in parent_lsoa_result.mappings().all()]

        parent_tenure_data = None
        if prop_api and parent_lsoa_codes:
            parent_agg = prop_api.parent_aggregate_transactions(parent_lsoa_codes, price_types)
            if parent_agg:
                parent_tenure_data = parent_agg.get("tenure")

        if parent_tenure_data:
            parent_fh = int(parent_tenure_data.get("fh") or 0)
            parent_lh = int(parent_tenure_data.get("lh") or 0)
            parent_tenure_total = parent_fh + parent_lh
            if parent_tenure_total > 0:
                parent_freehold_pct = round(parent_fh / parent_tenure_total * 100, 1)
                parent_leasehold_pct = round(parent_lh / parent_tenure_total * 100, 1)

            # Also get parent newbuild from same API call
            parent_nb_data = parent_agg.get("newbuild") if parent_agg else None
        else:
            # Fallback: query EC2 local DB
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
            parent_nb_data = None

    local_fh_price = _wavg(
        [float(row["avg_freehold_price"]) for row in local_rows if row.get("avg_freehold_price") and row.get("property_type") in PRICE_TYPES],
        [int(row["freehold_count"]) for row in local_rows if row.get("avg_freehold_price") and row.get("property_type") in PRICE_TYPES],
    )
    local_lh_price = _wavg(
        [float(row["avg_leasehold_price"]) for row in local_rows if row.get("avg_leasehold_price") and row.get("property_type") in PRICE_TYPES],
        [int(row["leasehold_count"]) for row in local_rows if row.get("avg_leasehold_price") and row.get("property_type") in PRICE_TYPES],
    )

    fl_breakdown = [
        {"label": "Freehold", "count": local_freehold, "pct": freehold_pct, "parent_pct": parent_freehold_pct, "avg_price": _round(local_fh_price)},
        {"label": "Leasehold", "count": local_leasehold, "pct": leasehold_pct, "parent_pct": parent_leasehold_pct, "avg_price": _round(local_lh_price)},
    ]

    if (freehold_pct or 0) >= (leasehold_pct or 0):
        fl_headline_value = freehold_pct
        fl_headline_parent = parent_freehold_pct
        fl_headline_unit = "% freehold"
    else:
        fl_headline_value = leasehold_pct
        fl_headline_parent = parent_leasehold_pct
        fl_headline_unit = "% leasehold"

    freehold_premium = None
    if local_fh_price and local_lh_price and local_lh_price > 0:
        freehold_premium = round(local_fh_price / local_lh_price, 2)

    freehold_details = {
        "breakdown": fl_breakdown,
        "breakdown_type": "tenure_table",
        "count_label": "Transactions",
        "freehold_premium": freehold_premium,
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

    # ------------------------------------------------------------------
    # New build proportion (from API)
    # ------------------------------------------------------------------
    nb_trend = []
    for row in nb_trend_data:
        txn_count = int(row.get("txn", 0))
        nb_count = int(row.get("nb", 0))
        if txn_count > 0:
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
        # Try to use data from parent_aggregate API call if available
        if parent_nb_data:
            p_nb = int(parent_nb_data.get("nb") or 0)
            p_txn = int(parent_nb_data.get("txn") or 0)
            if p_txn > 0:
                parent_newbuild_pct = round(p_nb / p_txn * 100, 1)
        else:
            # Fallback: query EC2 local DB
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
    # Price trend (year-on-year) — from API
    # ------------------------------------------------------------------
    local_price_yoy = None   # used later by investment_grade
    parent_price_yoy = None
    trend_rows = price_trend_data

    if len(trend_rows) >= 2:
        trend_series = []
        for i, r in enumerate(trend_rows):
            avg = int(r["avg_price"]) if r.get("avg_price") else None
            prev_avg = int(trend_rows[i - 1]["avg_price"]) if i > 0 and trend_rows[i - 1].get("avg_price") else None
            yoy = round((avg - prev_avg) / prev_avg * 100, 1) if avg and prev_avg and prev_avg > 0 else None
            trend_series.append({
                "year": int(r["year"]),
                "avg_price": avg,
                "yoy_pct": yoy,
                "detached": int(r["detached"]) if r.get("detached") else None,
                "semi": int(r["semi"]) if r.get("semi") else None,
                "terraced": int(r["terraced"]) if r.get("terraced") else None,
                "flat": int(r["flat"]) if r.get("flat") else None,
            })

        latest_yoy = trend_series[-1]["yoy_pct"]
        local_price_yoy = latest_yoy

        # Parent YoY from pre-computed materialized view (stays on EC2)
        parent_yoy = None
        if parent_lads:
            parent_trend_result = await db.execute(
                text(
                    """
                    SELECT year,
                           ROUND(SUM(avg_price::bigint * transactions) / NULLIF(SUM(transactions), 0))::int AS avg_price
                    FROM mv_parent_yearly_price_stats
                    WHERE lad_code = ANY(:parent_lads)
                      AND property_type = 'ALL'
                    GROUP BY year
                    ORDER BY year DESC
                    LIMIT 2
                    """
                ),
                {"parent_lads": parent_lads},
            )
            parent_rows_yoy = parent_trend_result.mappings().all()
            if len(parent_rows_yoy) >= 2:
                cur_p = float(parent_rows_yoy[0]["avg_price"]) if parent_rows_yoy[0]["avg_price"] else None
                prev_p = float(parent_rows_yoy[1]["avg_price"]) if parent_rows_yoy[1]["avg_price"] else None
                if cur_p and prev_p and prev_p > 0:
                    parent_yoy = round((cur_p - prev_p) / prev_p * 100, 1)
        parent_price_yoy = parent_yoy

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
    # Rental market and affordability (stays on EC2 — LAD-level data)
    # ------------------------------------------------------------------
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
                SELECT SUM(r.median_rent_all * p.total_hh) / NULLIF(SUM(p.total_hh), 0) AS median_rent_all,
                       SUM(r.median_rent_1bed * p.total_hh) / NULLIF(SUM(p.total_hh), 0) AS median_rent_1bed,
                       SUM(r.median_rent_2bed * p.total_hh) / NULLIF(SUM(p.total_hh), 0) AS median_rent_2bed,
                       SUM(r.median_rent_3bed * p.total_hh) / NULLIF(SUM(p.total_hh), 0) AS median_rent_3bed,
                       SUM(r.median_rent_4bed * p.total_hh) / NULLIF(SUM(p.total_hh), 0) AS median_rent_4bed
                FROM core_voa_rents_lad r
                LEFT JOIN mv_lad_population p ON p.lad_code = r.lad_code
                WHERE r.lad_code = ANY(:lads)
                  AND r.period = :period
                """
            ),
            {"lads": voa_local, "period": rent_period},
        )
        rent_row = rent_local.mappings().first()

        rent_parent = await db.execute(
            text(
                """
                SELECT SUM(r.median_rent_all * p.total_hh) / NULLIF(SUM(p.total_hh), 0) AS avg_rent
                FROM core_voa_rents_lad r
                LEFT JOIN mv_lad_population p ON p.lad_code = r.lad_code
                WHERE r.lad_code = ANY(:lads)
                  AND r.period = :period
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
            text("SELECT SUM(e.median_annual_earnings * p.total_pop) / NULLIF(SUM(p.total_pop), 0) AS median_annual_earnings FROM core_earnings_lad e LEFT JOIN mv_lad_population p ON p.lad_code = e.lad_code WHERE e.lad_code = ANY(:lads)"),
            {"lads": local_lads},
        )
        earnings_row = earnings_result.mappings().first()
        earnings_parent = await db.execute(
            text("SELECT SUM(e.median_annual_earnings * p.total_pop) / NULLIF(SUM(p.total_pop), 0) AS avg_earn FROM core_earnings_lad e LEFT JOIN mv_lad_population p ON p.lad_code = e.lad_code WHERE e.lad_code = ANY(:lads)"),
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

        parent_grade = None
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
    # Official ONS House Price Index (stays on EC2)
    # ------------------------------------------------------------------
    hpi_result = await db.execute(
        text(
            """
            SELECT date, average_price, yearly_change_pct,
                   detached_price, semi_detached_price, terraced_price, flat_price
            FROM core_hpi_lad
            WHERE lad_code = ANY(:lads)
            ORDER BY date
            """
        ),
        {"lads": local_lads},
    )
    hpi_rows = hpi_result.mappings().all()

    if hpi_rows:
        latest_hpi = hpi_rows[-1]
        latest_yoy_official = float(latest_hpi["yearly_change_pct"]) if latest_hpi["yearly_change_pct"] is not None else None

        parent_hpi_yoy = None
        if parent_lads:
            parent_hpi_result = await db.execute(
                text(
                    """
                    SELECT SUM(yearly_change_pct * sales_volume) / NULLIF(SUM(sales_volume), 0) AS avg_yoy
                    FROM core_hpi_lad
                    WHERE lad_code = ANY(:lads)
                      AND date = (SELECT MAX(date) FROM core_hpi_lad WHERE lad_code = ANY(:lads))
                      AND sales_volume IS NOT NULL
                    """
                ),
                {"lads": parent_lads},
            )
            parent_hpi_row = parent_hpi_result.mappings().first()
            if parent_hpi_row and parent_hpi_row["avg_yoy"] is not None:
                parent_hpi_yoy = round(float(parent_hpi_row["avg_yoy"]), 1)

        hpi_series = []
        for row in hpi_rows:
            d = row["date"]
            if d.month == 1 and d.day == 1 and d.year >= 2010:
                hpi_series.append({
                    "year": d.year,
                    "avg_price": int(float(row["average_price"])) if row["average_price"] else None,
                    "yoy_pct": float(row["yearly_change_pct"]) if row["yearly_change_pct"] is not None else None,
                    "detached": int(float(row["detached_price"])) if row["detached_price"] else None,
                    "semi": int(float(row["semi_detached_price"])) if row["semi_detached_price"] else None,
                    "terraced": int(float(row["terraced_price"])) if row["terraced_price"] else None,
                    "flat": int(float(row["flat_price"])) if row["flat_price"] else None,
                })

        hpi_details = {
            "hpi_series": hpi_series,
            "latest_avg_price": int(float(latest_hpi["average_price"])) if latest_hpi["average_price"] else None,
            "latest_date": latest_hpi["date"].strftime("%Y-%m") if latest_hpi["date"] else None,
            "data_note": "Source: ONS UK House Price Index. Official government statistic based on mortgage completions and cash sales. Published at local-authority level.",
        }
        if latest_yoy_official is not None:
            hpi_details["trend"] = {
                "pct": latest_yoy_official,
                "direction": "up" if latest_yoy_official > 0 else ("down" if latest_yoy_official < 0 else "flat"),
            }

        metrics.append(
            metric(
                "official_hpi",
                "ONS House Price Index",
                latest_yoy_official,
                parent_hpi_yoy,
                "% YoY",
                details=hpi_details,
            )
        )

    # ------------------------------------------------------------------
    # Price Spread (from API)
    # ------------------------------------------------------------------
    if spread_data.get("min_price") is not None and spread_data.get("max_price") is not None:
        min_p = int(spread_data["min_price"])
        max_p = int(spread_data["max_price"])
        p10 = int(float(spread_data["p10"])) if spread_data.get("p10") else None
        p90 = int(float(spread_data["p90"])) if spread_data.get("p90") else None
        spread_ratio = round(max_p / min_p, 1) if min_p > 0 else None

        metrics.append(
            metric(
                "price_spread",
                "Price Spread (last 12m)",
                max_p - min_p,
                None,
                "GBP",
                details={
                    "min_price": min_p,
                    "max_price": max_p,
                    "p10": p10,
                    "p90": p90,
                    "spread_ratio": spread_ratio,
                    "transaction_count": int(spread_data.get("txn_count", 0)),
                },
            )
        )

    # ------------------------------------------------------------------
    # EPC housing-stock efficiency (stays on EC2)
    # ------------------------------------------------------------------
    epc_local = await db.execute(
        text(
            """
            SELECT SUM(total_certs * avg_energy_score) / NULLIF(SUM(total_certs), 0) AS avg_energy_score,
                   SUM(total_certs * pct_rating_a_b) / NULLIF(SUM(total_certs), 0) AS pct_ab,
                   SUM(total_certs * pct_rating_c) / NULLIF(SUM(total_certs), 0) AS pct_c,
                   SUM(total_certs * pct_rating_d) / NULLIF(SUM(total_certs), 0) AS pct_d,
                   SUM(total_certs * pct_rating_e_g) / NULLIF(SUM(total_certs), 0) AS pct_eg,
                   SUM(total_certs * heat_gas_pct) / NULLIF(SUM(total_certs), 0) AS heat_gas_pct,
                   SUM(total_certs * heat_electric_pct) / NULLIF(SUM(total_certs), 0) AS heat_electric_pct,
                   SUM(total_certs * heat_oil_pct) / NULLIF(SUM(total_certs), 0) AS heat_oil_pct,
                   SUM(total_certs * heat_district_pct) / NULLIF(SUM(total_certs), 0) AS heat_district_pct,
                   SUM(total_certs * heat_other_pct) / NULLIF(SUM(total_certs), 0) AS heat_other_pct,
                   SUM(total_certs * heat_none_pct) / NULLIF(SUM(total_certs), 0) AS heat_none_pct,
                   SUM(total_certs * avg_co2_emissions) / NULLIF(SUM(total_certs), 0) AS avg_co2,
                   SUM(total_certs * avg_energy_consumption) / NULLIF(SUM(total_certs), 0) AS avg_energy_kwh,
                   SUM(total_certs * avg_heating_cost) / NULLIF(SUM(total_certs), 0) AS avg_heating_cost,
                   SUM(total_certs * avg_hotwater_cost) / NULLIF(SUM(total_certs), 0) AS avg_hotwater_cost,
                   SUM(total_certs * avg_lighting_cost) / NULLIF(SUM(total_certs), 0) AS avg_lighting_cost,
                   SUM(total_certs * pct_mains_gas) / NULLIF(SUM(total_certs), 0) AS pct_mains_gas,
                   SUM(total_certs * pct_solar) / NULLIF(SUM(total_certs), 0) AS pct_solar,
                   SUM(total_certs * age_pre1900_pct) / NULLIF(SUM(total_certs), 0) AS age_pre1900_pct,
                   SUM(total_certs * age_1900_1929_pct) / NULLIF(SUM(total_certs), 0) AS age_1900_1929_pct,
                   SUM(total_certs * age_1930_1949_pct) / NULLIF(SUM(total_certs), 0) AS age_1930_1949_pct,
                   SUM(total_certs * age_1950_1966_pct) / NULLIF(SUM(total_certs), 0) AS age_1950_1966_pct,
                   SUM(total_certs * age_1967_1982_pct) / NULLIF(SUM(total_certs), 0) AS age_1967_1982_pct,
                   SUM(total_certs * age_1983_2002_pct) / NULLIF(SUM(total_certs), 0) AS age_1983_2002_pct,
                   SUM(total_certs * age_post2002_pct) / NULLIF(SUM(total_certs), 0) AS age_post2002_pct,
                   SUM(total_certs * windows_good_pct) / NULLIF(SUM(total_certs), 0) AS windows_good_pct,
                   SUM(total_certs * windows_vpoor_pct) / NULLIF(SUM(total_certs), 0) AS windows_vpoor_pct,
                   SUM(total_certs * windows_poor_pct) / NULLIF(SUM(total_certs), 0) AS windows_poor_pct,
                   SUM(total_certs * windows_avg_pct) / NULLIF(SUM(total_certs), 0) AS windows_avg_pct,
                   SUM(total_certs * walls_good_pct) / NULLIF(SUM(total_certs), 0) AS walls_good_pct,
                   SUM(total_certs * walls_vpoor_pct) / NULLIF(SUM(total_certs), 0) AS walls_vpoor_pct,
                   SUM(total_certs * roof_good_pct) / NULLIF(SUM(total_certs), 0) AS roof_good_pct,
                   SUM(total_certs * roof_vpoor_pct) / NULLIF(SUM(total_certs), 0) AS roof_vpoor_pct,
                   SUM(total_certs * glaze_single_pct) / NULLIF(SUM(total_certs), 0) AS glaze_single_pct,
                   SUM(total_certs * glaze_double_pct) / NULLIF(SUM(total_certs), 0) AS glaze_double_pct,
                   SUM(total_certs * glaze_triple_pct) / NULLIF(SUM(total_certs), 0) AS glaze_triple_pct,
                   SUM(total_certs * avg_multi_glaze_pct) / NULLIF(SUM(total_certs), 0) AS avg_multi_glaze_pct,
                   SUM(total_certs * form_detached_pct) / NULLIF(SUM(total_certs), 0) AS form_detached_pct,
                   SUM(total_certs * form_semi_pct) / NULLIF(SUM(total_certs), 0) AS form_semi_pct,
                   SUM(total_certs * form_terrace_pct) / NULLIF(SUM(total_certs), 0) AS form_terrace_pct,
                   SUM(total_certs * form_end_terrace_pct) / NULLIF(SUM(total_certs), 0) AS form_end_terrace_pct
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
                   SUM(e.total_certs * e.pct_rating_a_b) / NULLIF(SUM(e.total_certs), 0) AS pct_ab,
                   SUM(e.total_certs * e.pct_rating_c) / NULLIF(SUM(e.total_certs), 0) AS pct_c,
                   SUM(e.total_certs * e.pct_rating_d) / NULLIF(SUM(e.total_certs), 0) AS pct_d,
                   SUM(e.total_certs * e.pct_rating_e_g) / NULLIF(SUM(e.total_certs), 0) AS pct_eg
            FROM core_epc_lsoa e
            JOIN core_lsoa_boundaries l ON l.lsoa_code = e.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
            """
        ),
        {"parent_lads": parent_lads},
    )
    epc_parent_row = epc_parent.mappings().first()

    if epc_row and epc_row["avg_energy_score"] is not None:
        local_c_plus = float(epc_row["pct_ab"] or 0) + float(epc_row["pct_c"] or 0)
        parent_c_plus = None
        parent_avg_score = None
        parent_ratings = None
        if epc_parent_row and epc_parent_row["avg_score"] is not None:
            parent_avg_score = _round(epc_parent_row["avg_score"])
            parent_c_plus = round(
                float(epc_parent_row["pct_ab"] or 0)
                + float(epc_parent_row["pct_c"] or 0),
                2,
            )
            parent_ratings = {
                "ab": _round(epc_parent_row["pct_ab"]),
                "c": _round(epc_parent_row["pct_c"]),
                "d": _round(epc_parent_row["pct_d"]),
                "eg": _round(epc_parent_row["pct_eg"]),
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
                    "pct_ab": _round(epc_row["pct_ab"]),
                    "pct_c": _round(epc_row["pct_c"]),
                    "pct_d": _round(epc_row["pct_d"]),
                    "pct_eg": _round(epc_row["pct_eg"]),
                    "parent_ratings": parent_ratings,
                    "c_plus_pct": round(local_c_plus, 2),
                    "parent_c_plus_pct": parent_c_plus,
                },
            )
        )

        # Building Profile — heating, CO2, costs, age bands, renewables
        bp_co2 = _round(epc_row["avg_co2"])
        if bp_co2 is not None:
            metrics.append(
                metric(
                    "building_profile",
                    "Building Profile",
                    bp_co2,
                    None,
                    "tCO2/yr",
                    details={
                        "avg_co2": bp_co2,
                        "avg_energy_kwh": _round(epc_row["avg_energy_kwh"]),
                        "avg_heating_cost": _round(epc_row["avg_heating_cost"]),
                        "avg_hotwater_cost": _round(epc_row["avg_hotwater_cost"]),
                        "avg_lighting_cost": _round(epc_row["avg_lighting_cost"]),
                        "heat_gas_pct": _round(epc_row["heat_gas_pct"]),
                        "heat_electric_pct": _round(epc_row["heat_electric_pct"]),
                        "heat_oil_pct": _round(epc_row["heat_oil_pct"]),
                        "heat_district_pct": _round(epc_row["heat_district_pct"]),
                        "heat_other_pct": _round(epc_row["heat_other_pct"]),
                        "heat_none_pct": _round(epc_row["heat_none_pct"]),
                        "pct_mains_gas": _round(epc_row["pct_mains_gas"]),
                        "pct_solar": _round(epc_row["pct_solar"]),
                        "age_pre1900_pct": _round(epc_row["age_pre1900_pct"]),
                        "age_1900_1929_pct": _round(epc_row["age_1900_1929_pct"]),
                        "age_1930_1949_pct": _round(epc_row["age_1930_1949_pct"]),
                        "age_1950_1966_pct": _round(epc_row["age_1950_1966_pct"]),
                        "age_1967_1982_pct": _round(epc_row["age_1967_1982_pct"]),
                        "age_1983_2002_pct": _round(epc_row["age_1983_2002_pct"]),
                        "age_post2002_pct": _round(epc_row["age_post2002_pct"]),
                        "windows_good_pct": _round(epc_row["windows_good_pct"]),
                        "windows_vpoor_pct": _round(epc_row["windows_vpoor_pct"]),
                        "windows_poor_pct": _round(epc_row["windows_poor_pct"]),
                        "windows_avg_pct": _round(epc_row["windows_avg_pct"]),
                        "walls_good_pct": _round(epc_row["walls_good_pct"]),
                        "walls_vpoor_pct": _round(epc_row["walls_vpoor_pct"]),
                        "roof_good_pct": _round(epc_row["roof_good_pct"]),
                        "roof_vpoor_pct": _round(epc_row["roof_vpoor_pct"]),
                        "glaze_single_pct": _round(epc_row["glaze_single_pct"]),
                        "glaze_double_pct": _round(epc_row["glaze_double_pct"]),
                        "glaze_triple_pct": _round(epc_row["glaze_triple_pct"]),
                        "avg_multi_glaze_pct": _round(epc_row["avg_multi_glaze_pct"]),
                        "form_detached_pct": _round(epc_row["form_detached_pct"]),
                        "form_semi_pct": _round(epc_row["form_semi_pct"]),
                        "form_terrace_pct": _round(epc_row["form_terrace_pct"]),
                        "form_end_terrace_pct": _round(epc_row["form_end_terrace_pct"]),
                    },
                )
            )

    # ------------------------------------------------------------------
    # Housing Tenure & Housing Stock (Census 2021, stays on EC2)
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
