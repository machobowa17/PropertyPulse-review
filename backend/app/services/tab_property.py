"""Tab 1: Property & Market — Bible Part 4, Tab 1.
Queries: core_property_prices_lsoa, core_property_prices_lad, core_hpi_lad,
         core_voa_rents_lad."""
from sqlalchemy import text
from app.services.helpers import metric, get_parent_lad_codes


async def fetch_property_market(db, *, lad_code, ward_code, lsoa_code):
    metrics = []
    parent_lads = await get_parent_lad_codes(db, lad_code)

    # --- Sales Market ---

    # Average Price (local = LSOA latest 12 months, parent = LAD latest 12 months)
    local_prices = await db.execute(
        text("""
            SELECT property_type, avg_price, median_price, transaction_count,
                   new_build_count, freehold_count, leasehold_count
            FROM core_property_prices_lsoa
            WHERE lsoa_code = :lsoa
              AND year_month >= (SELECT MAX(year_month) - INTERVAL '12 months' FROM core_property_prices_lsoa WHERE lsoa_code = :lsoa)
        """),
        {"lsoa": lsoa_code},
    )
    local_rows = local_prices.mappings().all()

    parent_prices = await db.execute(
        text("""
            SELECT property_type, avg_price, median_price, transaction_count
            FROM core_property_prices_lad
            WHERE lad_code = :lad
              AND year_month >= (SELECT MAX(year_month) - INTERVAL '12 months' FROM core_property_prices_lad WHERE lad_code = :lad)
        """),
        {"lad": lad_code},
    )
    parent_rows = parent_prices.mappings().all()

    # Aggregate local prices across all property types (no "A" type in data)
    local_by_type = {}
    for r in local_rows:
        pt = r["property_type"]
        if pt in ("D", "S", "T", "F"):
            local_by_type[pt] = float(r["avg_price"]) if r["avg_price"] else None

    local_avg = _avg([float(r["avg_price"]) for r in local_rows if r["avg_price"]])
    local_median = _avg([float(r["median_price"]) for r in local_rows if r["median_price"]])
    local_txn = sum(int(r["transaction_count"]) for r in local_rows if r["transaction_count"])
    local_newbuild = sum(int(r["new_build_count"]) for r in local_rows if r["new_build_count"])
    local_freehold = sum(int(r["freehold_count"]) for r in local_rows if r["freehold_count"])
    local_leasehold = sum(int(r["leasehold_count"]) for r in local_rows if r["leasehold_count"])

    parent_avg = _avg([float(r["avg_price"]) for r in parent_rows if r["avg_price"]])
    parent_median = _avg([float(r["median_price"]) for r in parent_rows if r["median_price"]])
    parent_txn = sum(int(r["transaction_count"]) for r in parent_rows if r["transaction_count"])

    # Type breakdown for details
    type_names = {"D": "detached", "S": "semi", "T": "terraced", "F": "flat"}
    details_by_type = {type_names.get(k, k): v for k, v in local_by_type.items() if k in type_names}

    # Average Price
    metrics.append(metric(
        "avg_price", "Average House Price",
        _round(local_avg), _round(parent_avg), "GBP",
        details=details_by_type or None,
    ))

    # Median Price
    metrics.append(metric(
        "median_price", "Median House Price",
        _round(local_median), _round(parent_median), "GBP",
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

    # Transaction Volume (last 12 months)
    metrics.append(metric(
        "transaction_volume", "Transaction Volume (12m)",
        local_txn or None, parent_txn or None, "count",
    ))

    # Freehold vs Leasehold
    total_tenure = (local_freehold or 0) + (local_leasehold or 0)
    freehold_pct = round(local_freehold / total_tenure * 100, 1) if total_tenure > 0 else None
    leasehold_pct = round(local_leasehold / total_tenure * 100, 1) if total_tenure > 0 else None
    metrics.append(metric(
        "freehold_leasehold", "Freehold vs Leasehold",
        freehold_pct, None, "% freehold",
        details={"freehold_pct": freehold_pct, "leasehold_pct": leasehold_pct},
    ))

    # New Build Proportion
    newbuild_pct = round(local_newbuild / local_txn * 100, 1) if local_txn and local_newbuild else None
    metrics.append(metric(
        "new_build_proportion", "New Build Proportion",
        newbuild_pct, None, "%",
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
            },
        ))

        # Gross Yield = (annual rent / avg price) * 100
        if local_avg and rent_row["median_rent_all"]:
            annual_rent = float(rent_row["median_rent_all"]) * 12
            gross_yield = round(annual_rent / local_avg * 100, 2)
            parent_yield = None
            if parent_avg and rent_parent_row and rent_parent_row["avg_rent"]:
                parent_annual = float(rent_parent_row["avg_rent"]) * 12
                parent_yield = round(parent_annual / parent_avg * 100, 2)
            metrics.append(metric(
                "gross_yield", "Gross Rental Yield",
                gross_yield, parent_yield, "%",
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

    return metrics


def _avg(values):
    return sum(values) / len(values) if values else None


def _round(val):
    if val is None:
        return None
    return round(float(val), 2)
