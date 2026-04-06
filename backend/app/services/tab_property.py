"""Tab 1: Property & Market — Bible Part 4, Tab 1.
Headline metrics (avg, median, ppsf): PERCENTILE_CONT / AVG on core_property_transactions.
Parent (regional) medians: pre-computed mv_parent_rolling_price_stats materialized view.
EPC data (floor_area_sqm) absorbed directly onto master table — no JOIN needed.
Other tables: core_hpi_lad, core_voa_rents_lad, core_earnings_lad, core_epc_lsoa."""
from sqlalchemy import text
from app.constants import PRICE_TYPES
from app.services.helpers import metric


async def fetch_property_market(db, *, lad_code, ward_code, lsoa_codes, centroid_lat, centroid_lon, search_mode="postcode", local_lads=None, parent_lads=None, parent_name="England", boundary_source="lad"):
    metrics = []
    if parent_lads is None:
        parent_lads = []

    # local_lads is passed from session via area endpoint
    if local_lads is None:
        local_lads = [lad_code] if lad_code and lad_code != "_" else []

    # Whether the search resolution is LAD or coarser (LAD/county).
    # Used to suppress metrics whose components are LAD-level only,
    # making them misleading for finer-grained searches.
    is_lad_or_coarser = boundary_source in ("lad", "county")

    # --- Headline price stats from raw transactions (true avg, true median, true ppsf) ---
    # core_property_transactions covers 2024-2025; rolling 12m window falls within that range.
    # PERCENTILE_CONT gives the real median across all transactions, not an average of monthly medians.

    _PRICE_TYPES_ARRAY = list(PRICE_TYPES)

    if is_lad_or_coarser:
        _local_txn_filter = """
            t.lsoa_code IN (
                SELECT DISTINCT lsoa_code FROM core_postcodes
                WHERE lad_code = ANY(:local_lads) AND lsoa_code IS NOT NULL
            )"""
        _local_txn_params: dict = {"local_lads": local_lads, "price_types": _PRICE_TYPES_ARRAY}
    else:
        _local_txn_filter = "t.lsoa_code = ANY(:lsoa_codes)"
        _local_txn_params = {"lsoa_codes": lsoa_codes, "price_types": _PRICE_TYPES_ARRAY}

    raw_local = await db.execute(
        text(f"""
            SELECT
                AVG(t.price)                                                                  AS avg_price,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.price)                          AS median_price,
                AVG(t.price::numeric / NULLIF(t.floor_area_sqm::numeric * 10.7639, 0))     AS avg_ppsf
            FROM core_property_transactions t
            WHERE {_local_txn_filter}
              AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
              AND t.property_type = ANY(:price_types)
        """),
        _local_txn_params,
    )
    raw_local_row = raw_local.mappings().first()

    if parent_lads:
        raw_parent = await db.execute(
            text("""
                SELECT avg_price, median_price, avg_ppsf
                FROM mv_parent_rolling_price_stats
                WHERE parent_comparison = :parent_name
                  AND property_type = 'ALL'
            """),
            {"parent_name": parent_name},
        )
        raw_parent_row = raw_parent.mappings().first()
    else:
        raw_parent_row = None

    # Extract headline values from raw transactions
    raw_local_avg    = float(raw_local_row["avg_price"])    if raw_local_row and raw_local_row["avg_price"]    is not None else None
    raw_local_median = float(raw_local_row["median_price"]) if raw_local_row and raw_local_row["median_price"] is not None else None
    raw_local_ppsf   = float(raw_local_row["avg_ppsf"])     if raw_local_row and raw_local_row["avg_ppsf"]     is not None else None
    raw_parent_avg    = float(raw_parent_row["avg_price"])    if raw_parent_row and raw_parent_row["avg_price"]    is not None else None
    raw_parent_median = float(raw_parent_row["median_price"]) if raw_parent_row and raw_parent_row["median_price"] is not None else None
    raw_parent_ppsf   = float(raw_parent_row["avg_ppsf"])     if raw_parent_row and raw_parent_row["avg_ppsf"]     is not None else None

    # --- Sales Market ---

    # Average Price (local = LSOA(s) latest 12 months, parent = LAD latest 12 months)
    # NOTE: local_avg, local_median, parent_avg, parent_median are OVERRIDDEN below
    # by raw_local_avg / raw_local_median which come from PERCENTILE_CONT on raw transactions.
    local_prices = await db.execute(
        text("""
            SELECT property_type,
                   ROUND(AVG(price)::numeric, 2) AS avg_price,
                   ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price))::numeric, 2) AS median_price,
                   COUNT(*) AS transaction_count,
                   COUNT(*) FILTER (WHERE old_new = 'Y') AS new_build_count,
                   COUNT(*) FILTER (WHERE duration = 'F') AS freehold_count,
                   COUNT(*) FILTER (WHERE duration = 'L') AS leasehold_count,
                   ROUND((AVG(price) FILTER (WHERE duration = 'F'))::numeric, 2) AS avg_freehold_price,
                   ROUND((AVG(price) FILTER (WHERE duration = 'L'))::numeric, 2) AS avg_leasehold_price
            FROM core_property_transactions
            WHERE lsoa_code = ANY(:codes)
              AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
            GROUP BY property_type
        """),
        {"codes": lsoa_codes},
    )
    local_rows = local_prices.mappings().all()

    parent_prices = await db.execute(
        text("""
            SELECT property_type,
                   avg_price::numeric AS avg_price,
                   median_price::numeric AS median_price,
                   transactions AS transaction_count
            FROM mv_parent_rolling_price_stats
            WHERE parent_comparison = :parent_name
              AND property_type != 'ALL'
        """),
        {"parent_name": parent_name},
    )
    parent_rows = parent_prices.mappings().all()

    # Aggregate local prices — exclude type "O" (Other/commercial) which skews averages
    local_by_type = {}
    local_median_by_type = {}
    for r in local_rows:
        pt = r["property_type"]
        if pt in PRICE_TYPES:
            local_by_type[pt] = float(r["avg_price"]) if r["avg_price"] else None
            local_median_by_type[pt] = float(r["median_price"]) if r["median_price"] else None

    # Headline avg and median come from raw transactions (true values, not averages of monthly medians)
    local_avg    = raw_local_avg    or _wavg(
        [float(r["avg_price"]) for r in local_rows if r["avg_price"] and r["property_type"] in PRICE_TYPES],
        [int(r["transaction_count"]) for r in local_rows if r["avg_price"] and r["property_type"] in PRICE_TYPES],
    )
    local_median = raw_local_median or _wavg(
        [float(r["median_price"]) for r in local_rows if r["median_price"] and r["property_type"] in PRICE_TYPES],
        [int(r["transaction_count"]) for r in local_rows if r["median_price"] and r["property_type"] in PRICE_TYPES],
    )
    local_txn_raw = sum(int(r["transaction_count"]) for r in local_rows if r["transaction_count"] and r["property_type"] in PRICE_TYPES)
    # Normalize to per-LSOA average so local is comparable to parent (also per-LSOA).
    # For a single-LSOA postcode search this divides by 1 (no-op).
    local_lsoa_count = len(lsoa_codes) if lsoa_codes else 1
    local_txn = round(local_txn_raw / local_lsoa_count, 1) if local_txn_raw else 0
    local_newbuild = sum(int(r["new_build_count"]) for r in local_rows if r["new_build_count"] and r["property_type"] in PRICE_TYPES)
    local_freehold = sum(int(r["freehold_count"]) for r in local_rows if r["freehold_count"])
    local_leasehold = sum(int(r["leasehold_count"]) for r in local_rows if r["leasehold_count"])

    parent_avg    = raw_parent_avg    or _wavg(
        [float(r["avg_price"]) for r in parent_rows if r["avg_price"] and r["property_type"] in PRICE_TYPES],
        [int(r["transaction_count"]) for r in parent_rows if r["avg_price"] and r["property_type"] in PRICE_TYPES],
    )
    parent_median = raw_parent_median or _wavg(
        [float(r["median_price"]) for r in parent_rows if r["median_price"] and r["property_type"] in PRICE_TYPES],
        [int(r["transaction_count"]) for r in parent_rows if r["median_price"] and r["property_type"] in PRICE_TYPES],
    )
    parent_txn_total = sum(int(r["transaction_count"]) for r in parent_rows if r["transaction_count"])
    # Divide by number of LSOAs in parent comparison group so comparison is per-LSOA average,
    # not the raw LAD total (which would be ~6,000× larger than an LSOA figure).
    parent_lsoa_count_result = await db.execute(
        text("SELECT COUNT(*) as cnt FROM core_lsoa_boundaries WHERE lad_code = ANY(:lads)"),
        {"lads": parent_lads},
    )
    parent_lsoa_count_row = parent_lsoa_count_result.mappings().first()
    parent_lsoa_count = int(parent_lsoa_count_row["cnt"]) if parent_lsoa_count_row and parent_lsoa_count_row["cnt"] else 1
    parent_txn = round(parent_txn_total / parent_lsoa_count, 1) if parent_lsoa_count > 0 else None

    # Type breakdown for details
    type_names = {"D": "detached", "S": "semi", "T": "terraced", "F": "flat"}
    details_by_type = {type_names.get(k, k): v for k, v in local_by_type.items() if k in type_names}
    median_details_by_type = {type_names.get(k, k): _round(v) for k, v in local_median_by_type.items() if k in type_names}

    # UK national median (context metric — uses AVG(price) across all recent UK transactions.
    # CURRENT_DATE constant lets the planner use the date index; subquery MAX() would force seq scan.)
    uk_median_result = await db.execute(
        text("""
            SELECT ROUND(AVG(price))::int AS uk_median
            FROM core_property_transactions
            WHERE date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
              AND property_type NOT IN ('O')
        """),
    )
    uk_median_row = uk_median_result.mappings().first()
    uk_median = int(uk_median_row["uk_median"]) if uk_median_row and uk_median_row["uk_median"] else None

    # Year-on-year trend: prior 12m window (12–24 months before latest data).
    # Groups by property_type first — identical aggregation method to the current-period
    # query above (AVG per type → wavg across types by transaction count).
    prior_result = await db.execute(
        text("""
            SELECT ROUND(AVG(price), 2) AS wavg_price
            FROM core_property_transactions
            WHERE lsoa_code = ANY(:codes)
              AND property_type = ANY(:price_types)
              AND date_of_transfer >= CURRENT_DATE - INTERVAL '25 months'
              AND date_of_transfer < CURRENT_DATE - INTERVAL '13 months'
        """),
        {"codes": lsoa_codes, "price_types": list(PRICE_TYPES)},
    )
    prior_row = prior_result.mappings().first()
    prior_avg_price = float(prior_row["wavg_price"]) if prior_row and prior_row["wavg_price"] else None

    price_trend = None
    if local_avg and prior_avg_price and prior_avg_price > 0:
        pct = round((local_avg - prior_avg_price) / prior_avg_price * 100, 1)
        price_trend = {"direction": "up" if pct > 0.05 else ("down" if pct < -0.05 else "flat"), "pct": pct}

    # Average Price
    avg_price_details = {**details_by_type, "uk_median": uk_median, "parent_median": _round(parent_median)} if details_by_type else {}
    if price_trend:
        avg_price_details["trend"] = price_trend
    metrics.append(metric(
        "avg_price", "Average Sale Price (last 12m)",
        _round(local_avg), _round(parent_avg), "GBP",
        details=avg_price_details or None,
    ))

    # Median Price — by-type breakdown (same shape as avg_price details)
    median_details = {**median_details_by_type, "uk_median": uk_median, "parent_median": _round(parent_median)} if median_details_by_type else {}

    metrics.append(metric(
        "median_price", "Median House Price",
        _round(local_median), _round(parent_median), "GBP",
        details=median_details or None,
    ))

    # Price per Sqft (from UCL price-per-sqm dataset, converted sqm→sqft)
    # Dynamic: LSOA table for postcode/place/ward, LAD table for LAD/county
    _ppsm_expr = "price::numeric / NULLIF(floor_area_sqm::numeric, 0)"
    if is_lad_or_coarser:
        ppsm_local = await db.execute(
            text(f"""
                SELECT AVG({_ppsm_expr}) AS avg_price_per_sqm,
                       AVG(CASE WHEN property_type = 'D' THEN {_ppsm_expr} END) AS avg_ppsm_detached,
                       AVG(CASE WHEN property_type = 'S' THEN {_ppsm_expr} END) AS avg_ppsm_semi,
                       AVG(CASE WHEN property_type = 'T' THEN {_ppsm_expr} END) AS avg_ppsm_terraced,
                       AVG(CASE WHEN property_type = 'F' THEN {_ppsm_expr} END) AS avg_ppsm_flat
                FROM core_property_transactions
                WHERE lsoa_code IN (SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = ANY(:lads))
                  AND floor_area_sqm > 0
                  AND date_of_transfer >= CURRENT_DATE - INTERVAL '25 months'
            """),
            {"lads": local_lads},
        )
    else:
        ppsm_local = await db.execute(
            text(f"""
                SELECT AVG({_ppsm_expr}) AS avg_price_per_sqm,
                       AVG(CASE WHEN property_type = 'D' THEN {_ppsm_expr} END) AS avg_ppsm_detached,
                       AVG(CASE WHEN property_type = 'S' THEN {_ppsm_expr} END) AS avg_ppsm_semi,
                       AVG(CASE WHEN property_type = 'T' THEN {_ppsm_expr} END) AS avg_ppsm_terraced,
                       AVG(CASE WHEN property_type = 'F' THEN {_ppsm_expr} END) AS avg_ppsm_flat
                FROM core_property_transactions
                WHERE lsoa_code = ANY(:codes)
                  AND floor_area_sqm > 0
                  AND date_of_transfer >= CURRENT_DATE - INTERVAL '25 months'
            """),
            {"codes": lsoa_codes},
        )
    ppsm_row = ppsm_local.mappings().first()

    # Parent ppsm
    ppsm_parent = await db.execute(
        text(f"""
            SELECT AVG({_ppsm_expr}) AS avg_ppsm
            FROM core_property_transactions
            WHERE lsoa_code IN (SELECT lsoa_code FROM core_lsoa_boundaries WHERE lad_code = ANY(:lads))
              AND floor_area_sqm > 0
              AND date_of_transfer >= CURRENT_DATE - INTERVAL '25 months'
        """),
        {"lads": parent_lads},
    )
    ppsm_parent_row = ppsm_parent.mappings().first()

    # Headline ppsf: use raw transactions (true rolling 12m avg) when available,
    # fall back to sqm snapshot table. Per-type details stay on sqm snapshot table.
    _local_ppsf_headline  = round(raw_local_ppsf, 0)  if raw_local_ppsf  is not None else None
    _parent_ppsf_headline = round(raw_parent_ppsf, 0) if raw_parent_ppsf is not None else None

    if _local_ppsf_headline is None and ppsm_row and ppsm_row["avg_price_per_sqm"]:
        _local_ppsf_headline = round(float(ppsm_row["avg_price_per_sqm"]) / 10.7639, 0)
    if _parent_ppsf_headline is None and ppsm_parent_row and ppsm_parent_row["avg_ppsm"]:
        _parent_ppsf_headline = round(float(ppsm_parent_row["avg_ppsm"]) / 10.7639, 0)

    if _local_ppsf_headline is not None:
        metrics.append(metric(
            "price_per_sqft", "Price per Sqft",
            _local_ppsf_headline, _parent_ppsf_headline, "GBP/sqft",
            details={
                "detached": round(float(ppsm_row["avg_ppsm_detached"]) / 10.7639, 0) if ppsm_row and ppsm_row["avg_ppsm_detached"] else None,
                "semi": round(float(ppsm_row["avg_ppsm_semi"]) / 10.7639, 0) if ppsm_row and ppsm_row["avg_ppsm_semi"] else None,
                "terraced": round(float(ppsm_row["avg_ppsm_terraced"]) / 10.7639, 0) if ppsm_row and ppsm_row["avg_ppsm_terraced"] else None,
                "flat": round(float(ppsm_row["avg_ppsm_flat"]) / 10.7639, 0) if ppsm_row and ppsm_row["avg_ppsm_flat"] else None,
            },
        ))

    # Transaction Volume (last 12 months) with YoY change
    # Both local and parent are per-LSOA averages so comparison is fair at any search granularity.
    txn_yoy = None
    prior_txn = None
    if local_txn:
        prior_txn_result = await db.execute(
            text("""
                SELECT COUNT(*) AS txn
                FROM core_property_transactions
                WHERE lsoa_code = ANY(:codes)
                  AND property_type = ANY(:price_types)
                  AND date_of_transfer >= CURRENT_DATE - INTERVAL '25 months'
                  AND date_of_transfer < CURRENT_DATE - INTERVAL '13 months'
            """),
            {"codes": lsoa_codes, "price_types": list(PRICE_TYPES)},
        )
        prior_txn_row = prior_txn_result.mappings().first()
        prior_txn_raw = int(prior_txn_row["txn"]) if prior_txn_row and prior_txn_row["txn"] else None
        prior_txn = round(prior_txn_raw / local_lsoa_count, 1) if prior_txn_raw else None
        if prior_txn_raw and prior_txn_raw > 0:
            # YoY uses raw totals — ratio is identical to per-LSOA ratio
            txn_yoy = round((local_txn_raw - prior_txn_raw) / prior_txn_raw * 100, 1)

    metrics.append(metric(
        "transaction_volume", "Transaction Volume (12m)",
        local_txn or None, parent_txn or None, "count/LSOA",
        details={"yoy_change_pct": txn_yoy, "prior_12m_count": prior_txn} if txn_yoy is not None else None,
    ))

    # Freehold vs Leasehold
    # Bible: "Default shows % split. Expandable shows price difference."
    total_tenure = (local_freehold or 0) + (local_leasehold or 0)
    freehold_pct = round(local_freehold / total_tenure * 100, 1) if total_tenure > 0 else None
    leasehold_pct = round(local_leasehold / total_tenure * 100, 1) if total_tenure > 0 else None
    # Parent freehold % (same 13-month window, across parent LADs)
    parent_freehold_pct = None
    if parent_lads:
        parent_tenure_result = await db.execute(
            text("""
                SELECT COUNT(*) FILTER (WHERE duration = 'F') AS fh,
                       COUNT(*) FILTER (WHERE duration = 'L') AS lh
                FROM core_property_transactions
                WHERE lsoa_code IN (
                    SELECT DISTINCT lsoa_code FROM core_postcodes
                    WHERE lad_code = ANY(:lads) AND lsoa_code IS NOT NULL
                )
                  AND property_type = ANY(:price_types)
                  AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
            """),
            {"lads": parent_lads, "price_types": list(PRICE_TYPES)},
        )
        pt_row = parent_tenure_result.mappings().first()
        if pt_row:
            pt_total = (int(pt_row["fh"] or 0)) + (int(pt_row["lh"] or 0))
            if pt_total > 0:
                parent_freehold_pct = round(int(pt_row["fh"]) / pt_total * 100, 1)
    local_fh_price = _wavg(
        [float(r["avg_freehold_price"]) for r in local_rows if r["avg_freehold_price"] and r["property_type"] in PRICE_TYPES],
        [int(r["freehold_count"]) for r in local_rows if r["avg_freehold_price"] and r["property_type"] in PRICE_TYPES],
    )
    local_lh_price = _wavg(
        [float(r["avg_leasehold_price"]) for r in local_rows if r["avg_leasehold_price"] and r["property_type"] in PRICE_TYPES],
        [int(r["leasehold_count"]) for r in local_rows if r["avg_leasehold_price"] and r["property_type"] in PRICE_TYPES],
    )
    price_diff = round(local_fh_price - local_lh_price) if local_fh_price and local_lh_price else None
    metrics.append(metric(
        "freehold_leasehold", "Freehold vs Leasehold",
        freehold_pct, parent_freehold_pct, "% freehold",
        details={
            "freehold_pct": freehold_pct,
            "leasehold_pct": leasehold_pct,
            "avg_freehold_price": _round(local_fh_price),
            "avg_leasehold_price": _round(local_lh_price),
            "price_difference": price_diff,
        },
    ))

    # New Build Proportion
    # Bible: "Expandable shows 10-year trend."
    newbuild_pct = round(local_newbuild / local_txn_raw * 100, 1) if local_txn_raw else None
    nb_trend_result = await db.execute(
        text("""
            SELECT EXTRACT(YEAR FROM date_of_transfer)::int AS yr,
                   COUNT(*) FILTER (WHERE old_new = 'Y') AS nb,
                   COUNT(*) AS txn
            FROM core_property_transactions
            WHERE lsoa_code = ANY(:codes)
              AND property_type = ANY(:price_types)
            GROUP BY yr ORDER BY yr
        """),
        {"codes": lsoa_codes, "price_types": list(PRICE_TYPES)},
    )
    nb_trend = []
    for r in nb_trend_result.mappings().all():
        if r["txn"] and int(r["txn"]) > 0 and r["nb"] is not None:
            nb_count = int(r["nb"])
            txn_count = int(r["txn"])
            nb_trend.append({
                "year": int(r["yr"]),
                "new_builds": nb_count,
                "total": txn_count,
                "pct": round(nb_count / txn_count * 100, 1),
            })
    # Parent new-build proportion (same 13-month window, across parent LADs)
    parent_newbuild_pct = None
    if parent_lads:
        parent_nb_result = await db.execute(
            text("""
                SELECT COUNT(*) FILTER (WHERE old_new = 'Y') AS nb,
                       COUNT(*) AS txn
                FROM core_property_transactions
                WHERE lsoa_code IN (
                    SELECT DISTINCT lsoa_code FROM core_postcodes
                    WHERE lad_code = ANY(:lads) AND lsoa_code IS NOT NULL
                )
                  AND property_type = ANY(:price_types)
                  AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
            """),
            {"lads": parent_lads, "price_types": list(PRICE_TYPES)},
        )
        parent_nb_row = parent_nb_result.mappings().first()
        if parent_nb_row and parent_nb_row["txn"] and int(parent_nb_row["txn"]) > 0:
            parent_newbuild_pct = round(int(parent_nb_row["nb"]) / int(parent_nb_row["txn"]) * 100, 1)

    nb_details = {
        "nb_trend": nb_trend,
        "caveat_note": (
            "Based on Land Registry's new-build flag, which is set by the submitting solicitor. "
            "This flag is unreliable for house-to-flat conversions and other redevelopments — "
            "newly created dwellings within existing buildings are often recorded as 'not new build'. "
            "Actual new-build activity in the area may be higher than shown."
        ),
    }
    metrics.append(metric(
        "new_build_proportion", "New Build Proportion",
        newbuild_pct, parent_newbuild_pct, "%",
        details=nb_details,
    ))

    # --- HPI: Price Trend (yearly change) ---
    hpi_local = await db.execute(
        text("""
            SELECT AVG(average_price) AS average_price, AVG(yearly_change_pct) AS yearly_change_pct,
                   AVG(detached_price) AS detached_price, AVG(semi_detached_price) AS semi_detached_price,
                   AVG(terraced_price) AS terraced_price, AVG(flat_price) AS flat_price,
                   SUM(sales_volume) AS sales_volume
            FROM core_hpi_lad
            WHERE lad_code = ANY(:lads)
              AND date = (SELECT MAX(date) FROM core_hpi_lad WHERE lad_code = ANY(:lads))
        """),
        {"lads": local_lads},
    )
    hpi_row = hpi_local.mappings().first()

    # HPI parent = average across parent LADs
    hpi_parent = await db.execute(
        text("""
            SELECT AVG(yearly_change_pct) as avg_yoy
            FROM core_hpi_lad
            WHERE lad_code = ANY(:lads)
              AND date = (SELECT MAX(date) FROM core_hpi_lad WHERE lad_code = ANY(:ref_lads))
        """),
        {"lads": parent_lads, "ref_lads": local_lads or ["_"]},
    )
    hpi_parent_row = hpi_parent.mappings().first()

    if hpi_row and hpi_row["yearly_change_pct"] is not None:
        hpi_details: dict = {
            "data_note": "Source: ONS/Land Registry House Price Index. Published at local authority level only — "
            "the index methodology requires sufficient transaction volume, making sub-LAD figures statistically unreliable. "
            "The value shown represents the entire local authority.",
        }
        # Only include by-type price breakdown for LAD/county searches;
        # for postcode/place/ward it would show property types that may not
        # exist in the searched area (e.g. detached prices in central London).
        if is_lad_or_coarser:
            hpi_details["detached"] = _round(hpi_row["detached_price"])
            hpi_details["semi"] = _round(hpi_row["semi_detached_price"])
            hpi_details["terraced"] = _round(hpi_row["terraced_price"])
            hpi_details["flat"] = _round(hpi_row["flat_price"])
        metrics.append(metric(
            "price_trend_yoy", "Price Trend (Year-on-Year)",
            _round(hpi_row["yearly_change_pct"]),
            _round(hpi_parent_row["avg_yoy"]) if hpi_parent_row else None,
            "%",
            details=hpi_details,
        ))

    # --- Rental Market ---
    rent_local = await db.execute(
        text("""
            SELECT AVG(median_rent_all) AS median_rent_all,
                   AVG(median_rent_1bed) AS median_rent_1bed,
                   AVG(median_rent_2bed) AS median_rent_2bed,
                   AVG(median_rent_3bed) AS median_rent_3bed,
                   AVG(median_rent_4bed) AS median_rent_4bed
            FROM core_voa_rents_lad
            WHERE lad_code = ANY(:lads)
              AND period = (SELECT MAX(period) FROM core_voa_rents_lad WHERE lad_code = ANY(:lads))
        """),
        {"lads": local_lads},
    )
    rent_row = rent_local.mappings().first()

    rent_parent = await db.execute(
        text("""
            SELECT AVG(median_rent_all) as avg_rent
            FROM core_voa_rents_lad
            WHERE lad_code = ANY(:lads)
        """),
        {"lads": parent_lads},
    )
    rent_parent_row = rent_parent.mappings().first()

    if rent_row and rent_row["median_rent_all"] is not None:
        rent_details = {
                "1bed": _round(rent_row["median_rent_1bed"]),
                "2bed": _round(rent_row["median_rent_2bed"]),
                "3bed": _round(rent_row["median_rent_3bed"]),
                "4bed": _round(rent_row["median_rent_4bed"]),
                # yield per bedroom pre-computed here so the rent card can show both
                "yield_1bed": round(float(rent_row["median_rent_1bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_1bed"] and local_avg else None,
                "yield_2bed": round(float(rent_row["median_rent_2bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_2bed"] and local_avg else None,
                "yield_3bed": round(float(rent_row["median_rent_3bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_3bed"] and local_avg else None,
                "yield_4bed": round(float(rent_row["median_rent_4bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_4bed"] and local_avg else None,
                "data_note": "Source: ONS Private Rental Market Statistics. Published at local authority level only — no postcode or LSOA-level breakdown exists. The value shown represents the entire local authority, not the specific area searched.",
        }
        metrics.append(metric(
            "median_rent", "Median Monthly Rent",
            _round(rent_row["median_rent_all"]),
            _round(rent_parent_row["avg_rent"]) if rent_parent_row else None,
            "GBP/month",
            details=rent_details,
        ))

        # Gross Yield = (annual rent / avg price) * 100
        # Bible: "Expandable shows yield by property type" — using bedroom count breakdown
        # Rent is LAD-level only (ONS PRMS), so yield is only meaningful when search >= LAD.
        # For postcode/place/ward: rent is borough-wide while price is hyperlocal → misleading.
        if local_avg and rent_row["median_rent_all"]:
            annual_rent = float(rent_row["median_rent_all"]) * 12
            gross_yield = round(annual_rent / local_avg * 100, 2)
            parent_yield = None
            if parent_avg and rent_parent_row and rent_parent_row["avg_rent"]:
                parent_annual = float(rent_parent_row["avg_rent"]) * 12
                parent_yield = round(parent_annual / parent_avg * 100, 2)
            if is_lad_or_coarser:
                yield_details = {}
                for beds, col in [("1bed", "median_rent_1bed"), ("2bed", "median_rent_2bed"),
                                  ("3bed", "median_rent_3bed"), ("4bed", "median_rent_4bed")]:
                    if rent_row[col] and local_avg:
                        yield_details[beds] = round(float(rent_row[col]) * 12 / local_avg * 100, 2)
                        yield_details[f"rent_{beds}"] = _round(rent_row[col])
                metrics.append(metric(
                    "gross_yield", "Gross Rental Yield",
                    gross_yield, parent_yield, "%",
                    details=yield_details or None,
                ))
            else:
                metrics.append(metric(
                    "gross_yield", "Gross Rental Yield",
                    None, None, "%",
                    details={
                        "data_note": "Gross rental yield is not shown for postcode, place, or ward searches. "
                        "Rent data (ONS Private Rental Market Statistics) is only available at local authority level, "
                        "while property prices are at a finer resolution — combining them would produce a misleading yield figure. "
                        "Search for a local authority (e.g. Croydon) or county (e.g. Greater London) to see this metric.",
                    },
                ))

        # Affordability = annual rent / median annual earnings * 100
        earnings_result = await db.execute(
            text("SELECT AVG(median_annual_earnings) AS median_annual_earnings FROM core_earnings_lad WHERE lad_code = ANY(:lads)"),
            {"lads": local_lads},
        )
        earnings_row = earnings_result.mappings().first()
        earnings_parent = await db.execute(
            text("SELECT AVG(median_annual_earnings) as avg_earn FROM core_earnings_lad WHERE lad_code = ANY(:lads)"),
            {"lads": parent_lads},
        )
        ep_row = earnings_parent.mappings().first()

        if earnings_row and earnings_row["median_annual_earnings"] and rent_row["median_rent_all"]:
            local_annual_rent = float(rent_row["median_rent_all"]) * 12
            local_afford = round(local_annual_rent / float(earnings_row["median_annual_earnings"]) * 100, 1)
            parent_afford = None
            if ep_row and ep_row["avg_earn"] and rent_parent_row and rent_parent_row["avg_rent"]:
                parent_annual_rent = float(rent_parent_row["avg_rent"]) * 12
                parent_afford = round(parent_annual_rent / float(ep_row["avg_earn"]) * 100, 1)
            if is_lad_or_coarser:
                metrics.append(metric(
                    "affordability", "Rent Affordability",
                    local_afford, parent_afford, "% of income",
                    details={
                        "annual_rent": round(local_annual_rent),
                        "median_earnings": round(float(earnings_row["median_annual_earnings"])),
                    },
                ))
            else:
                metrics.append(metric(
                    "affordability", "Rent Affordability",
                    None, None, "% of income",
                    details={
                        "data_note": "Rent affordability is not shown for postcode, place, or ward searches. "
                        "Both rent (ONS PRMS) and earnings (ONS ASHE) data are only available at local authority level — "
                        "the figure would be identical regardless of which postcode or neighbourhood you searched within the same borough. "
                        "Search for a local authority (e.g. Croydon) or county (e.g. Greater London) to see this metric.",
                    },
                ))

    # --- Median Earnings (for frontend mortgage calculator) ---
    earn_result = await db.execute(
        text("SELECT AVG(median_annual_earnings) AS median_annual_earnings FROM core_earnings_lad WHERE lad_code = ANY(:lads)"),
        {"lads": local_lads},
    )
    earn_row = earn_result.mappings().first()
    earn_parent_result = await db.execute(
        text("SELECT AVG(median_annual_earnings) as avg_earn FROM core_earnings_lad WHERE lad_code = ANY(:lads)"),
        {"lads": parent_lads},
    )
    earn_parent_row = earn_parent_result.mappings().first()
    if earn_row and earn_row["median_annual_earnings"]:
        parent_earn_val = round(float(earn_parent_row["avg_earn"])) if earn_parent_row and earn_parent_row["avg_earn"] else None
        metrics.append(metric(
            "median_earnings", "Median Annual Earnings",
            round(float(earn_row["median_annual_earnings"])),
            parent_earn_val, "GBP/year",
            details={
                "data_note": "Source: ONS Annual Survey of Hours and Earnings (ASHE). Published at local authority level only "
                "(residence-based, i.e. where employees live, not where they work). "
                "No postcode or LSOA-level breakdown exists. The value shown represents the entire local authority.",
            },
        ))

    # --- Investment Grade ---
    # Bible: A-F rating from yield + capital growth
    # Grade based on: gross_yield (weight 50%) + HPI yearly_change_pct (weight 50%)
    # Both components are LAD-level only, so grade is only meaningful for LAD/county searches.
    if hpi_row and hpi_row["yearly_change_pct"] is not None:
        yoy = float(hpi_row["yearly_change_pct"]) if hpi_row["yearly_change_pct"] else 0
        gy = gross_yield if 'gross_yield' in locals() else 0
        combined = (gy or 0) + (yoy or 0)
        if is_lad_or_coarser:
            if combined >= 10:
                grade = "A"
            elif combined >= 7:
                grade = "B"
            elif combined >= 5:
                grade = "C"
            elif combined >= 3:
                grade = "D"
            elif combined >= 1:
                grade = "E"
            else:
                grade = "F"
            metrics.append(metric(
                "investment_grade", "Investment Grade",
                grade, None, "grade",
                details={
                    "gross_yield": _round(gy) if gy else None,
                    "capital_growth_yoy": _round(yoy),
                    "combined_score": round(combined, 2),
                },
            ))
        else:
            metrics.append(metric(
                "investment_grade", "Investment Grade",
                None, None, "grade",
                details={
                    "data_note": "Investment grade is not shown for postcode, place, or ward searches. "
                    "It is derived from gross rental yield (requires LAD-level rent data) and HPI year-on-year change "
                    "(published at LAD level only). Both components would be identical for any search within the same borough. "
                    "Search for a local authority (e.g. Croydon) or county (e.g. Greater London) to see this metric.",
                },
            ))

    # --- EPC Energy Ratings ---
    epc_local = await db.execute(
        text("""
            SELECT AVG(avg_energy_score) as avg_energy_score,
                   AVG(pct_a) as pct_a, AVG(pct_b) as pct_b, AVG(pct_c) as pct_c,
                   AVG(pct_d) as pct_d, AVG(pct_e) as pct_e, AVG(pct_f) as pct_f,
                   AVG(pct_g) as pct_g,
                   AVG(heat_gas_pct) as heat_gas_pct,
                   AVG(heat_electric_pct) as heat_electric_pct,
                   AVG(heat_oil_pct) as heat_oil_pct,
                   AVG(heat_district_pct) as heat_district_pct,
                   AVG(heat_other_pct) as heat_other_pct,
                   AVG(heat_none_pct) as heat_none_pct
            FROM core_epc_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    epc_row = epc_local.mappings().first()

    epc_parent = await db.execute(
        text("""
            SELECT AVG(e.avg_energy_score) as avg_score,
                   AVG(e.pct_a) as pct_a, AVG(e.pct_b) as pct_b, AVG(e.pct_c) as pct_c,
                   AVG(e.pct_d) as pct_d, AVG(e.pct_e) as pct_e, AVG(e.pct_f) as pct_f,
                   AVG(e.pct_g) as pct_g
            FROM core_epc_lsoa e
            JOIN core_lsoa_boundaries l ON l.lsoa_code = e.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    epc_parent_row = epc_parent.mappings().first()

    if epc_row and epc_row["avg_energy_score"] is not None:
        local_c_plus = (float(epc_row["pct_a"] or 0) + float(epc_row["pct_b"] or 0)
                        + float(epc_row["pct_c"] or 0))
        parent_c_plus = None
        parent_avg_score = None
        parent_ratings = None
        if epc_parent_row and epc_parent_row["avg_score"] is not None:
            parent_avg_score = _round(epc_parent_row["avg_score"])
            parent_c_plus = round(
                float(epc_parent_row["pct_a"] or 0) + float(epc_parent_row["pct_b"] or 0)
                + float(epc_parent_row["pct_c"] or 0), 2
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

        metrics.append(metric(
            "epc_energy_score", "EPC Energy Score",
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
        ))

        metrics.append(metric(
            "epc_rating_c_plus", "EPC Rated C or Above",
            round(local_c_plus, 2),
            parent_c_plus,
            "%",
        ))

    return metrics


def _avg(values):
    return sum(values) / len(values) if values else None


def _wavg(values, weights):
    """Transaction-weighted average — ignores rows where either value or weight is 0."""
    pairs = [(v, w) for v, w in zip(values, weights) if w and w > 0]
    if not pairs:
        return None
    total_w = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / total_w if total_w else None


def _round(val):
    if val is None:
        return None
    return round(float(val), 2)
