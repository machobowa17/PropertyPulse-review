"""Tab 0: Overview — Cross-tab headline metrics.
Aggregates 10 key metrics (2 per existing tab) from lightweight queries.
All queries use pre-computed tables or simple aggregations — no spatial joins,
no external API calls. Run sequentially on the shared async session.
"""
from sqlalchemy import text

from app.services.helpers import metric


async def fetch_overview(
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
    if local_lads is None:
        local_lads = [lad_code] if lad_code and lad_code != "_" else []
    if parent_lads is None:
        parent_lads = []

    # Run sequentially — SQLAlchemy async session is not safe for concurrent use
    all_metrics = []
    all_metrics.extend(await _overview_property(db, lsoa_codes, local_lads, parent_lads))
    all_metrics.extend(await _overview_lifestyle(db, lsoa_codes, local_lads, parent_lads))
    all_metrics.extend(await _overview_safety(db, lsoa_codes, local_lads, parent_lads))
    all_metrics.extend(await _overview_community(db, lsoa_codes, parent_lads))
    all_metrics.extend(await _overview_people(db, lsoa_codes, parent_lads))
    return all_metrics


# ---------------------------------------------------------------------------
# Property snapshot: avg_price + council_tax
# ---------------------------------------------------------------------------
async def _overview_property(db, lsoa_codes, local_lads, parent_lads):
    metrics = []

    # Average price (13-month rolling)
    local_result = await db.execute(
        text("""
            SELECT ROUND(AVG(price))::int AS avg_price, COUNT(*) AS txn_count
            FROM core_property_transactions
            WHERE lsoa_code = ANY(:codes)
              AND date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
              AND property_type IN ('D','S','T','F')
        """),
        {"codes": lsoa_codes},
    )
    local_row = local_result.mappings().first()
    local_price = int(local_row["avg_price"]) if local_row and local_row["avg_price"] else None

    parent_price = None
    if parent_lads:
        parent_result = await db.execute(
            text("""
                SELECT ROUND(AVG(price))::int AS avg_price
                FROM core_property_transactions t
                JOIN core_lsoa_boundaries b ON b.lsoa_code = t.lsoa_code
                WHERE b.lad_code = ANY(:parent_lads)
                  AND t.date_of_transfer >= CURRENT_DATE - INTERVAL '13 months'
                  AND t.property_type IN ('D','S','T','F')
            """),
            {"parent_lads": parent_lads},
        )
        p_row = parent_result.mappings().first()
        parent_price = int(p_row["avg_price"]) if p_row and p_row["avg_price"] else None

    metrics.append(metric(
        "overview_avg_price", "Average Price",
        local_price, parent_price, "GBP",
        details={"txn_count": int(local_row["txn_count"]) if local_row and local_row["txn_count"] else 0},
    ))

    # Council tax Band D
    ct_result = await db.execute(
        text("SELECT AVG(band_d) AS band_d FROM core_council_tax_lad WHERE lad_code = ANY(:lads)"),
        {"lads": local_lads},
    )
    ct_row = ct_result.mappings().first()
    local_ct = round(float(ct_row["band_d"])) if ct_row and ct_row["band_d"] else None

    parent_ct = None
    if parent_lads:
        pct_result = await db.execute(
            text("SELECT AVG(band_d) AS band_d FROM core_council_tax_lad WHERE lad_code = ANY(:lads)"),
            {"lads": parent_lads},
        )
        pct_row = pct_result.mappings().first()
        parent_ct = round(float(pct_row["band_d"])) if pct_row and pct_row["band_d"] else None

    metrics.append(metric(
        "overview_council_tax", "Council Tax (Band D)",
        local_ct, parent_ct, "GBP/year",
    ))

    return metrics


# ---------------------------------------------------------------------------
# Lifestyle snapshot: nearest_station + broadband
# ---------------------------------------------------------------------------
async def _overview_lifestyle(db, lsoa_codes, local_lads, parent_lads):
    metrics = []

    # Nearest station (metres)
    st_result = await db.execute(
        text("SELECT AVG(nearest_station_m) AS avg_m FROM core_lsoa_transport WHERE lsoa_code = ANY(:codes)"),
        {"codes": lsoa_codes},
    )
    st_row = st_result.mappings().first()
    local_station = round(float(st_row["avg_m"])) if st_row and st_row["avg_m"] else None

    parent_station = None
    if parent_lads:
        pst_result = await db.execute(
            text("""
                SELECT AVG(t.nearest_station_m) AS avg_m
                FROM core_lsoa_transport t
                JOIN core_lsoa_boundaries b ON b.lsoa_code = t.lsoa_code
                WHERE b.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        pst_row = pst_result.mappings().first()
        parent_station = round(float(pst_row["avg_m"])) if pst_row and pst_row["avg_m"] else None

    metrics.append(metric(
        "overview_nearest_station", "Nearest Station",
        local_station, parent_station, "metres",
    ))

    # Broadband avg download (LAD-level)
    bb_result = await db.execute(
        text("SELECT AVG(avg_download_mbps) AS dl FROM core_broadband_lad WHERE lad_code = ANY(:lads)"),
        {"lads": local_lads},
    )
    bb_row = bb_result.mappings().first()
    local_dl = round(float(bb_row["dl"]), 1) if bb_row and bb_row["dl"] else None

    parent_dl = None
    if parent_lads:
        pbb_result = await db.execute(
            text("SELECT AVG(avg_download_mbps) AS dl FROM core_broadband_lad WHERE lad_code = ANY(:lads)"),
            {"lads": parent_lads},
        )
        pbb_row = pbb_result.mappings().first()
        parent_dl = round(float(pbb_row["dl"]), 1) if pbb_row and pbb_row["dl"] else None

    metrics.append(metric(
        "overview_broadband", "Avg Broadband Speed",
        local_dl, parent_dl, "Mbit/s",
    ))

    return metrics


# ---------------------------------------------------------------------------
# Safety snapshot: crime_rate + air_quality
# ---------------------------------------------------------------------------
async def _overview_safety(db, lsoa_codes, local_lads, parent_lads):
    metrics = []
    from dateutil.relativedelta import relativedelta

    # Crime rate per 1,000 population (12-month rolling)
    latest_result = await db.execute(text("SELECT MAX(month) AS latest FROM core_crime_lsoa"))
    latest_month = latest_result.scalar()

    local_crime = None
    parent_crime = None
    if latest_month:
        window_start = latest_month - relativedelta(years=1)

        cr_result = await db.execute(
            text("""
                SELECT SUM(c.crime_count)::float /
                       NULLIF((SELECT SUM(cs.total_population) FROM core_census_lsoa cs WHERE cs.lsoa_code = ANY(:codes)), 0)
                       * 1000 AS rate
                FROM core_crime_lsoa c
                WHERE c.lsoa_code = ANY(:codes) AND c.month > :window_start
            """),
            {"codes": lsoa_codes, "window_start": window_start},
        )
        cr_row = cr_result.scalar()
        local_crime = round(float(cr_row), 1) if cr_row else None

        if parent_lads:
            pcr_result = await db.execute(
                text("""
                    SELECT SUM(c.crime_count)::float /
                           NULLIF((SELECT SUM(cs.total_population) FROM core_census_lsoa cs
                                   JOIN core_lsoa_boundaries b ON b.lsoa_code = cs.lsoa_code
                                   WHERE b.lad_code = ANY(:parent_lads)), 0)
                           * 1000 AS rate
                    FROM core_crime_lsoa c
                    JOIN core_lsoa_boundaries b ON b.lsoa_code = c.lsoa_code
                    WHERE b.lad_code = ANY(:parent_lads) AND c.month > :window_start
                """),
                {"parent_lads": parent_lads, "window_start": window_start},
            )
            pcr_row = pcr_result.scalar()
            parent_crime = round(float(pcr_row), 1) if pcr_row else None

    metrics.append(metric(
        "overview_crime_rate", "Crime Rate",
        local_crime, parent_crime, "per 1,000",
    ))

    # Air quality PM2.5 (latest year, LAD-level)
    aq_result = await db.execute(
        text("""
            SELECT AVG(pm25_ugm3) AS pm25
            FROM core_air_quality_lad
            WHERE lad_code = ANY(:lads)
              AND year = (SELECT MAX(year) FROM core_air_quality_lad WHERE lad_code = ANY(:lads))
        """),
        {"lads": local_lads},
    )
    aq_row = aq_result.mappings().first()
    local_pm25 = round(float(aq_row["pm25"]), 1) if aq_row and aq_row["pm25"] else None

    parent_pm25 = None
    if parent_lads:
        paq_result = await db.execute(
            text("""
                SELECT AVG(pm25_ugm3) AS pm25
                FROM core_air_quality_lad
                WHERE lad_code = ANY(:parent_lads)
                  AND year = (SELECT MAX(year) FROM core_air_quality_lad)
            """),
            {"parent_lads": parent_lads},
        )
        paq_row = paq_result.mappings().first()
        parent_pm25 = round(float(paq_row["pm25"]), 1) if paq_row and paq_row["pm25"] else None

    metrics.append(metric(
        "overview_air_quality", "Air Quality (PM2.5)",
        local_pm25, parent_pm25, "µg/m³",
    ))

    return metrics


# ---------------------------------------------------------------------------
# Community snapshot: median_age + deprivation
# ---------------------------------------------------------------------------
async def _overview_community(db, lsoa_codes, parent_lads):
    metrics = []

    # Median age (population-weighted)
    age_result = await db.execute(
        text("""
            SELECT SUM(total_population * median_age) / NULLIF(SUM(total_population), 0) AS median_age,
                   SUM(total_population) AS total_pop,
                   SUM(total_population * population_density) / NULLIF(SUM(total_population), 0) AS pop_density
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    age_row = age_result.mappings().first()
    local_age = round(float(age_row["median_age"]), 1) if age_row and age_row["median_age"] else None

    parent_age = None
    if parent_lads:
        page_result = await db.execute(
            text("""
                SELECT SUM(d.total_population * d.median_age) / NULLIF(SUM(d.total_population), 0) AS median_age
                FROM core_census_lsoa d
                JOIN core_lsoa_boundaries b ON b.lsoa_code = d.lsoa_code
                WHERE b.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        page_row = page_result.mappings().first()
        parent_age = round(float(page_row["median_age"]), 1) if page_row and page_row["median_age"] else None

    metrics.append(metric(
        "overview_median_age", "Median Age",
        local_age, parent_age, "years",
    ))

    # Deprivation — population-weighted IMD decile
    imd_result = await db.execute(
        text("""
            SELECT SUM(c.total_population * i.imd_decile) / NULLIF(SUM(c.total_population), 0) AS avg_decile,
                   SUM(c.total_population * i.imd_score) / NULLIF(SUM(c.total_population), 0) AS avg_score
            FROM core_imd_lsoa i
            JOIN core_census_lsoa c ON c.lsoa_code = i.lsoa_code
            WHERE i.lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    imd_row = imd_result.mappings().first()
    local_decile = round(float(imd_row["avg_decile"]), 1) if imd_row and imd_row["avg_decile"] else None

    parent_decile = None
    if parent_lads:
        pimd_result = await db.execute(
            text("""
                SELECT SUM(c.total_population * i.imd_decile) / NULLIF(SUM(c.total_population), 0) AS avg_decile
                FROM core_imd_lsoa i
                JOIN core_census_lsoa c ON c.lsoa_code = i.lsoa_code
                JOIN core_lsoa_boundaries b ON b.lsoa_code = i.lsoa_code
                WHERE b.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        pimd_row = pimd_result.mappings().first()
        parent_decile = round(float(pimd_row["avg_decile"]), 1) if pimd_row and pimd_row["avg_decile"] else None

    metrics.append(metric(
        "overview_deprivation", "Deprivation (IMD)",
        local_decile, parent_decile, "score",
        details={
            "imd_score": round(float(imd_row["avg_score"]), 1) if imd_row and imd_row["avg_score"] else None,
            "context_note": "IMD decile 1 = most deprived, 10 = least deprived.",
        },
    ))

    return metrics


# ---------------------------------------------------------------------------
# People snapshot: population_density + degree_educated
# ---------------------------------------------------------------------------
async def _overview_people(db, lsoa_codes, parent_lads):
    metrics = []

    # Population density (people per hectare, population-weighted)
    pop_result = await db.execute(
        text("""
            SELECT SUM(total_population)::float / NULLIF(SUM(total_population::float / NULLIF(population_density, 0)), 0)
                   AS pop_density
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes) AND population_density > 0
        """),
        {"codes": lsoa_codes},
    )
    pop_row = pop_result.scalar()
    local_density = round(float(pop_row)) if pop_row else None

    parent_density = None
    if parent_lads:
        ppop_result = await db.execute(
            text("""
                SELECT SUM(d.total_population)::float / NULLIF(SUM(d.total_population::float / NULLIF(d.population_density, 0)), 0)
                       AS pop_density
                FROM core_census_lsoa d
                JOIN core_lsoa_boundaries b ON b.lsoa_code = d.lsoa_code
                WHERE b.lad_code = ANY(:parent_lads) AND d.population_density > 0
            """),
            {"parent_lads": parent_lads},
        )
        ppop_row = ppop_result.scalar()
        parent_density = round(float(ppop_row)) if ppop_row else None

    metrics.append(metric(
        "overview_pop_density", "Population Density",
        local_density, parent_density, "people/hectare",
    ))

    # Degree-educated % (population-weighted)
    deg_result = await db.execute(
        text("""
            SELECT SUM(total_population * pct_degree) / NULLIF(SUM(total_population), 0) AS pct_degree
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    deg_row = deg_result.scalar()
    local_degree = round(float(deg_row), 1) if deg_row else None

    parent_degree = None
    if parent_lads:
        pdeg_result = await db.execute(
            text("""
                SELECT SUM(d.total_population * d.pct_degree) / NULLIF(SUM(d.total_population), 0) AS pct_degree
                FROM core_census_lsoa d
                JOIN core_lsoa_boundaries b ON b.lsoa_code = d.lsoa_code
                WHERE b.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        pdeg_row = pdeg_result.scalar()
        parent_degree = round(float(pdeg_row), 1) if pdeg_row else None

    metrics.append(metric(
        "overview_degree_educated", "Degree Educated",
        local_degree, parent_degree, "%",
    ))

    return metrics
