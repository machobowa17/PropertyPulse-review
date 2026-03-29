"""Tab 1: Property & Market — Bible Part 4, Tab 1.
Queries: core_property_prices_lsoa, core_property_prices_lad, core_hpi_lad,
         core_voa_rents_lad."""
from sqlalchemy import text
from app.services.helpers import metric, get_parent_lad_codes


async def fetch_property_market(db, *, lad_code, ward_code, lsoa_codes, centroid_lat, centroid_lon):
    metrics = []
    parent_lads = await get_parent_lad_codes(db, lad_code)

    # --- Sales Market ---

    # Average Price (local = LSOA(s) latest 12 months, parent = LAD latest 12 months)
    local_prices = await db.execute(
        text("""
            SELECT property_type, AVG(avg_price) as avg_price, AVG(median_price) as median_price,
                   SUM(transaction_count) as transaction_count,
                   SUM(new_build_count) as new_build_count, SUM(freehold_count) as freehold_count,
                   SUM(leasehold_count) as leasehold_count,
                   AVG(avg_freehold_price) as avg_freehold_price,
                   AVG(avg_leasehold_price) as avg_leasehold_price
            FROM core_property_prices_lsoa
            WHERE lsoa_code = ANY(:codes)
              AND year_month >= (SELECT MAX(year_month) - INTERVAL '12 months' FROM core_property_prices_lsoa WHERE lsoa_code = ANY(:codes))
            GROUP BY property_type
        """),
        {"codes": lsoa_codes},
    )
    local_rows = local_prices.mappings().all()

    parent_prices = await db.execute(
        text("""
            SELECT property_type, AVG(avg_price) as avg_price, AVG(median_price) as median_price,
                   SUM(transaction_count) as transaction_count
            FROM core_property_prices_lad
            WHERE lad_code = ANY(:parent_lads)
              AND year_month >= (SELECT MAX(year_month) - INTERVAL '12 months' FROM core_property_prices_lad WHERE lad_code = :lad)
            GROUP BY property_type
        """),
        {"parent_lads": parent_lads, "lad": lad_code},
    )
    parent_rows = parent_prices.mappings().all()

    # Aggregate local prices — exclude type "O" (Other/commercial) which skews averages
    PRICE_TYPES = ("D", "S", "T", "F")
    local_by_type = {}
    for r in local_rows:
        pt = r["property_type"]
        if pt in PRICE_TYPES:
            local_by_type[pt] = float(r["avg_price"]) if r["avg_price"] else None

    # Transaction-weighted average across residential types only
    local_avg = _wavg(
        [float(r["avg_price"]) for r in local_rows if r["avg_price"] and r["property_type"] in PRICE_TYPES],
        [int(r["transaction_count"]) for r in local_rows if r["avg_price"] and r["property_type"] in PRICE_TYPES],
    )
    local_median = _wavg(
        [float(r["median_price"]) for r in local_rows if r["median_price"] and r["property_type"] in PRICE_TYPES],
        [int(r["transaction_count"]) for r in local_rows if r["median_price"] and r["property_type"] in PRICE_TYPES],
    )
    local_txn = sum(int(r["transaction_count"]) for r in local_rows if r["transaction_count"] and r["property_type"] in PRICE_TYPES)
    local_newbuild = sum(int(r["new_build_count"]) for r in local_rows if r["new_build_count"])
    local_freehold = sum(int(r["freehold_count"]) for r in local_rows if r["freehold_count"])
    local_leasehold = sum(int(r["leasehold_count"]) for r in local_rows if r["leasehold_count"])

    parent_avg = _wavg(
        [float(r["avg_price"]) for r in parent_rows if r["avg_price"] and r["property_type"] in PRICE_TYPES],
        [int(r["transaction_count"]) for r in parent_rows if r["avg_price"] and r["property_type"] in PRICE_TYPES],
    )
    parent_median = _wavg(
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

    # UK national median (all LADs, latest 12 months, excl. Other)
    uk_median_result = await db.execute(
        text("""
            SELECT ROUND(AVG(median_price)) as uk_median
            FROM core_property_prices_lad
            WHERE year_month >= (SELECT MAX(year_month) - INTERVAL '12 months' FROM core_property_prices_lad)
              AND property_type NOT IN ('O')
        """),
    )
    uk_median_row = uk_median_result.mappings().first()
    uk_median = int(uk_median_row["uk_median"]) if uk_median_row and uk_median_row["uk_median"] else None

    # Average Price
    metrics.append(metric(
        "avg_price", "Average House Price",
        _round(local_avg), _round(parent_avg), "GBP",
        details={**details_by_type, "uk_median": uk_median, "parent_median": _round(parent_median)} if details_by_type else None,
    ))

    # Median Price
    # Bible: "Expandable shows 5-year trend chart."
    trend_result = await db.execute(
        text("""
            SELECT EXTRACT(YEAR FROM year_month)::int as yr,
                   AVG(median_price) as median_price
            FROM core_property_prices_lsoa
            WHERE lsoa_code = ANY(:codes)
              AND property_type IN ('D','S','T','F')
              AND year_month >= (SELECT MAX(year_month) - INTERVAL '5 years' FROM core_property_prices_lsoa WHERE lsoa_code = ANY(:codes))
            GROUP BY yr ORDER BY yr
        """),
        {"codes": lsoa_codes},
    )
    trend_rows = trend_result.mappings().all()
    price_trend = {str(r["yr"]): _round(r["median_price"]) for r in trend_rows if r["median_price"]}

    metrics.append(metric(
        "median_price", "Median House Price",
        _round(local_median), _round(parent_median), "GBP",
        details=price_trend or None,
    ))

    # Price per Sqft (from UCL price-per-sqm dataset, converted sqm→sqft)
    ppsm_local = await db.execute(
        text("SELECT avg_price_per_sqm, avg_ppsm_detached, avg_ppsm_semi, avg_ppsm_terraced, avg_ppsm_flat FROM core_price_sqm_lad WHERE lad_code = :lad"),
        {"lad": lad_code},
    )
    ppsm_row = ppsm_local.mappings().first()
    ppsm_parent = await db.execute(
        text("SELECT AVG(avg_price_per_sqm) as avg_ppsm FROM core_price_sqm_lad WHERE lad_code = ANY(:lads)"),
        {"lads": parent_lads},
    )
    ppsm_parent_row = ppsm_parent.mappings().first()

    if ppsm_row and ppsm_row["avg_price_per_sqm"]:
        # Convert sqm to sqft: 1 sqm = 10.7639 sqft, so £/sqft = £/sqm / 10.7639
        local_ppsf = round(float(ppsm_row["avg_price_per_sqm"]) / 10.7639, 0)
        parent_ppsf = round(float(ppsm_parent_row["avg_ppsm"]) / 10.7639, 0) if ppsm_parent_row and ppsm_parent_row["avg_ppsm"] else None
        metrics.append(metric(
            "price_per_sqft", "Price per Sqft",
            local_ppsf, parent_ppsf, "GBP/sqft",
            details={
                "detached": round(float(ppsm_row["avg_ppsm_detached"]) / 10.7639, 0) if ppsm_row["avg_ppsm_detached"] else None,
                "semi": round(float(ppsm_row["avg_ppsm_semi"]) / 10.7639, 0) if ppsm_row["avg_ppsm_semi"] else None,
                "terraced": round(float(ppsm_row["avg_ppsm_terraced"]) / 10.7639, 0) if ppsm_row["avg_ppsm_terraced"] else None,
                "flat": round(float(ppsm_row["avg_ppsm_flat"]) / 10.7639, 0) if ppsm_row["avg_ppsm_flat"] else None,
            },
        ))

    # Transaction Volume (last 12 months) with YoY change
    # Bible: "Default shows last 12 months count. Expandable shows year-on-year change."
    txn_yoy = None
    prior_txn = None
    if local_txn:
        prior_txn_result = await db.execute(
            text("""
                SELECT SUM(transaction_count) as txn
                FROM core_property_prices_lsoa
                WHERE lsoa_code = ANY(:codes)
                  AND year_month >= (SELECT MAX(year_month) - INTERVAL '24 months' FROM core_property_prices_lsoa WHERE lsoa_code = ANY(:codes))
                  AND year_month < (SELECT MAX(year_month) - INTERVAL '12 months' FROM core_property_prices_lsoa WHERE lsoa_code = ANY(:codes))
            """),
            {"codes": lsoa_codes},
        )
        prior_txn_row = prior_txn_result.mappings().first()
        prior_txn = int(prior_txn_row["txn"]) if prior_txn_row and prior_txn_row["txn"] else None
        if prior_txn and prior_txn > 0:
            txn_yoy = round((local_txn - prior_txn) / prior_txn * 100, 1)

    metrics.append(metric(
        "transaction_volume", "Transaction Volume (12m)",
        local_txn or None, parent_txn or None, "count",
        details={"yoy_change_pct": txn_yoy, "prior_12m_count": prior_txn} if txn_yoy is not None else None,
    ))

    # Freehold vs Leasehold
    # Bible: "Default shows % split. Expandable shows price difference."
    total_tenure = (local_freehold or 0) + (local_leasehold or 0)
    freehold_pct = round(local_freehold / total_tenure * 100, 1) if total_tenure > 0 else None
    leasehold_pct = round(local_leasehold / total_tenure * 100, 1) if total_tenure > 0 else None
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
        freehold_pct, None, "% freehold",
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
    newbuild_pct = round(local_newbuild / local_txn * 100, 1) if local_txn else None
    nb_trend_result = await db.execute(
        text("""
            SELECT EXTRACT(YEAR FROM year_month)::int as yr,
                   SUM(new_build_count) as nb, SUM(transaction_count) as txn
            FROM core_property_prices_lsoa
            WHERE lsoa_code = ANY(:codes)
            GROUP BY yr ORDER BY yr
        """),
        {"codes": lsoa_codes},
    )
    nb_trend = {}
    for r in nb_trend_result.mappings().all():
        if r["txn"] and int(r["txn"]) > 0 and r["nb"] is not None:
            nb_trend[str(r["yr"])] = round(int(r["nb"]) / int(r["txn"]) * 100, 1)
    metrics.append(metric(
        "new_build_proportion", "New Build Proportion",
        newbuild_pct, None, "%",
        details=nb_trend or None,
    ))

    # --- HPI: Price Trend (yearly change) ---
    hpi_local = await db.execute(
        text("""
            SELECT average_price, yearly_change_pct, detached_price,
                   semi_detached_price, terraced_price, flat_price, sales_volume
            FROM core_hpi_lad
            WHERE lad_code = :lad
            ORDER BY date DESC LIMIT 1
        """),
        {"lad": lad_code},
    )
    hpi_row = hpi_local.mappings().first()

    # HPI parent = average across parent LADs
    hpi_parent = await db.execute(
        text("""
            SELECT AVG(yearly_change_pct) as avg_yoy
            FROM core_hpi_lad
            WHERE lad_code = ANY(:lads)
              AND date = (SELECT MAX(date) FROM core_hpi_lad WHERE lad_code = :lad)
        """),
        {"lads": parent_lads, "lad": lad_code},
    )
    hpi_parent_row = hpi_parent.mappings().first()

    if hpi_row:
        metrics.append(metric(
            "price_trend_yoy", "Price Trend (Year-on-Year)",
            _round(hpi_row["yearly_change_pct"]),
            _round(hpi_parent_row["avg_yoy"]) if hpi_parent_row else None,
            "%",
            details={
                "detached": _round(hpi_row["detached_price"]),
                "semi": _round(hpi_row["semi_detached_price"]),
                "terraced": _round(hpi_row["terraced_price"]),
                "flat": _round(hpi_row["flat_price"]),
            },
        ))

    # --- Rental Market ---
    rent_local = await db.execute(
        text("""
            SELECT median_rent_all, median_rent_1bed, median_rent_2bed,
                   median_rent_3bed, median_rent_4bed
            FROM core_voa_rents_lad WHERE lad_code = :lad
            ORDER BY period DESC LIMIT 1
        """),
        {"lad": lad_code},
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

    if rent_row:
        metrics.append(metric(
            "median_rent", "Median Monthly Rent",
            _round(rent_row["median_rent_all"]),
            _round(rent_parent_row["avg_rent"]) if rent_parent_row else None,
            "GBP/month",
            details={
                "1bed": _round(rent_row["median_rent_1bed"]),
                "2bed": _round(rent_row["median_rent_2bed"]),
                "3bed": _round(rent_row["median_rent_3bed"]),
                "4bed": _round(rent_row["median_rent_4bed"]),
                # yield per bedroom pre-computed here so the rent card can show both
                "yield_1bed": round(float(rent_row["median_rent_1bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_1bed"] and local_avg else None,
                "yield_2bed": round(float(rent_row["median_rent_2bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_2bed"] and local_avg else None,
                "yield_3bed": round(float(rent_row["median_rent_3bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_3bed"] and local_avg else None,
                "yield_4bed": round(float(rent_row["median_rent_4bed"]) * 12 / local_avg * 100, 2) if rent_row["median_rent_4bed"] and local_avg else None,
            },
        ))

        # Gross Yield = (annual rent / avg price) * 100
        # Bible: "Expandable shows yield by property type" — using bedroom count breakdown
        if local_avg and rent_row["median_rent_all"]:
            annual_rent = float(rent_row["median_rent_all"]) * 12
            gross_yield = round(annual_rent / local_avg * 100, 2)
            parent_yield = None
            if parent_avg and rent_parent_row and rent_parent_row["avg_rent"]:
                parent_annual = float(rent_parent_row["avg_rent"]) * 12
                parent_yield = round(parent_annual / parent_avg * 100, 2)
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

        # Affordability = annual rent / median annual earnings * 100
        earnings_result = await db.execute(
            text("SELECT median_annual_earnings FROM core_earnings_lad WHERE lad_code = :lad"),
            {"lad": lad_code},
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
            metrics.append(metric(
                "affordability", "Rent Affordability",
                local_afford, parent_afford, "% of income",
                details={
                    "annual_rent": round(local_annual_rent),
                    "median_earnings": round(float(earnings_row["median_annual_earnings"])),
                },
            ))

    # --- Median Earnings (for frontend mortgage calculator) ---
    earn_result = await db.execute(
        text("SELECT median_annual_earnings FROM core_earnings_lad WHERE lad_code = :lad"),
        {"lad": lad_code},
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
        ))

    # --- Investment Grade ---
    # Bible: A-F rating from yield + capital growth
    # Grade based on: gross_yield (weight 50%) + HPI yearly_change_pct (weight 50%)
    # A: combined >= 10, B: >= 7, C: >= 5, D: >= 3, E: >= 1, F: < 1
    if hpi_row and hpi_row["yearly_change_pct"] is not None:
        yoy = float(hpi_row["yearly_change_pct"]) if hpi_row["yearly_change_pct"] else 0
        gy = gross_yield if 'gross_yield' in locals() else 0
        combined = (gy or 0) + (yoy or 0)
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
