"""Tab 3: Environment & Safety — Bible Part 4, Tab 3.
Queries: core_crime_lsoa, core_flood_zones, core_air_quality, core_noise, core_green_space, core_epc_lsoa.
Bible Rule 4: multi-LSOA aggregation for non-postcode searches."""
from dateutil.relativedelta import relativedelta
from sqlalchemy import text
from app.constants import GMP_LAD_CODES
from app.services.helpers import metric


async def fetch_environment_safety(db, *, lad_code, ward_code, lsoa_codes, centroid_lat, centroid_lon, search_mode="postcode", local_lads=None, parent_lads=None, parent_name="England", boundary_source="lad"):
    metrics = []
    lat, lon = centroid_lat, centroid_lon
    if parent_lads is None:
        parent_lads = []
    is_area = search_mode == "area"

    # --- Crime & Safety ---
    # Bible: Overall crime rate per 1,000 population vs national average, breakdown by type
    # Both local and parent use the same 12-month rolling window for apples-to-apples comparison
    latest_month_result = await db.execute(
        text("SELECT MAX(month) as latest FROM core_crime_lsoa"),
    )
    latest_month = latest_month_result.scalar()

    window_start = latest_month - relativedelta(years=1) if latest_month else None

    crime_local = await db.execute(
        text("""
            SELECT crime_type, SUM(crime_count) as cnt,
                   COUNT(DISTINCT month) as months_count
            FROM core_crime_lsoa
            WHERE lsoa_code = ANY(:codes)
              AND month > :window_start AND month <= :window_end
            GROUP BY crime_type ORDER BY cnt DESC
        """),
        {"codes": lsoa_codes, "window_start": window_start, "window_end": latest_month},
    )
    crime_rows = crime_local.mappings().all()
    local_total = sum(int(r["cnt"]) for r in crime_rows)
    local_months = max((int(r["months_count"]) for r in crime_rows), default=0)
    crime_breakdown = {r["crime_type"]: int(r["cnt"]) for r in crime_rows}

    crime_data_unavailable = False

    # MSOA-level fallback: LSOAs absent or sparse in crime dataset (incl. GMP partial coverage)
    if local_total == 0:
        crime_msoa = await db.execute(
            text("""
                SELECT c.crime_type, SUM(c.crime_count) as cnt,
                       COUNT(DISTINCT c.month) as months_count
                FROM core_crime_lsoa c
                JOIN core_postcodes p ON p.lsoa_code = c.lsoa_code
                WHERE p.msoa_code IN (
                    SELECT DISTINCT msoa_code FROM core_postcodes
                    WHERE lsoa_code = ANY(:codes) AND msoa_code IS NOT NULL
                ) AND c.month > :window_start AND c.month <= :window_end
                GROUP BY c.crime_type ORDER BY cnt DESC
            """),
            {"codes": lsoa_codes, "window_start": window_start, "window_end": latest_month},
        )
        crime_rows_msoa = crime_msoa.mappings().all()
        if crime_rows_msoa:
            local_total = sum(int(r["cnt"]) for r in crime_rows_msoa)
            local_months = max((int(r["months_count"]) for r in crime_rows_msoa), default=0)
            crime_breakdown = {r["crime_type"]: int(r["cnt"]) for r in crime_rows_msoa}
        elif lad_code in GMP_LAD_CODES:
            crime_data_unavailable = True

    # Get local population — try direct LSOA first, then MSOA fallback (deduped)
    pop_result = await db.execute(
        text("SELECT SUM(total_population) as total_population FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)"),
        {"codes": lsoa_codes},
    )
    pop_row = pop_result.mappings().first()
    local_pop = int(pop_row["total_population"]) if pop_row and pop_row["total_population"] else None

    if not local_pop:
        pop_result = await db.execute(
            text("""
                SELECT SUM(d.total_population) as total_population
                FROM core_census_lsoa d
                WHERE d.lsoa_code IN (
                    SELECT DISTINCT p2.lsoa_code FROM core_postcodes p2
                    WHERE p2.msoa_code IN (
                        SELECT DISTINCT msoa_code FROM core_postcodes
                        WHERE lsoa_code = ANY(:codes) AND msoa_code IS NOT NULL
                    )
                )
            """),
            {"codes": lsoa_codes},
        )
        pop_row = pop_result.mappings().first()
        local_pop = int(pop_row["total_population"]) if pop_row and pop_row["total_population"] else None

    # Parent average crime rate (parent comparison group, per 1000 pop)
    # Use 12-month rolling window to smooth out single-month coverage gaps (e.g. GMP API ingest)
    parent_result = await db.execute(
        text("""
            WITH parent_lsoas AS (
                SELECT DISTINCT c.lsoa_code
                FROM core_crime_lsoa c
                JOIN core_lsoa_boundaries l ON l.lsoa_code = c.lsoa_code
                WHERE l.lad_code = ANY(:parent_lads)
                  AND c.month > :window_start AND c.month <= :window_end
            )
            SELECT SUM(c.crime_count) as total_crimes,
                   COUNT(DISTINCT c.month) as months_count,
                   (SELECT SUM(d.total_population) FROM core_census_lsoa d
                    WHERE d.lsoa_code IN (SELECT lsoa_code FROM parent_lsoas)) as total_pop
            FROM core_crime_lsoa c
            WHERE c.lsoa_code IN (SELECT lsoa_code FROM parent_lsoas)
              AND c.month > :window_start AND c.month <= :window_end
        """),
        {"parent_lads": parent_lads,
         "window_start": latest_month - relativedelta(years=1),
         "window_end": latest_month},
    )
    pr_row = parent_result.mappings().first()
    parent_crimes = int(pr_row["total_crimes"]) if pr_row and pr_row["total_crimes"] else 0
    parent_pop = int(pr_row["total_pop"]) if pr_row and pr_row["total_pop"] else 0
    parent_months = int(pr_row["months_count"]) if pr_row and pr_row["months_count"] else 0

    # Annualise both local and parent identically: total / months_in_window * 12, per 1,000 pop
    local_rate = None
    if local_pop and local_pop > 0 and local_months > 0:
        local_rate = round(local_total / local_months / local_pop * 1000 * 12, 1)
    parent_rate = None
    # GMP parent areas: crime data is too incomplete for a meaningful parent comparison
    gmp_parent = lad_code in GMP_LAD_CODES
    if parent_pop > 0 and parent_months > 0 and not gmp_parent:
        parent_rate = round(parent_crimes / parent_months / parent_pop * 1000 * 12, 1)

    if crime_data_unavailable:
        metrics.append(metric(
            "crime_rate", "Crime Rate (per 1,000 pop/yr)",
            None, None, "per 1,000/yr",
            details={"data_unavailable_note": "Greater Manchester Police do not publish crime data to the national open data platform. Data not available for this area."},
        ))
    elif local_rate is not None:
        crime_details = dict(crime_breakdown) if crime_breakdown else {}
        crime_details["rolling_12m_crimes"] = local_total
        crime_details["months_with_data"] = local_months
        crime_details["resident_population"] = local_pop
        # Flag high-footfall areas where resident pop << daytime footfall inflates rate
        if local_rate > 500:
            crime_details["high_footfall_note"] = "High rate reflects low resident population vs crime volume (city centre / commercial LSOA)"
        metrics.append(metric(
            "crime_rate", "Crime Rate (per 1,000 pop/yr)",
            local_rate, parent_rate, "per 1,000/yr",
            details=crime_details,
        ))

    # Bible: Crime Trend — year-on-year change using rolling 12-month windows
    # Single-month comparisons are too noisy for small LSOAs (e.g. 8 vs 4 = +100%).
    if latest_month:
        rolling_current = await db.execute(
            text("""
                SELECT SUM(crime_count) as cnt
                FROM core_crime_lsoa
                WHERE lsoa_code = ANY(:codes)
                  AND month > :month_start AND month <= :month_end
            """),
            {"codes": lsoa_codes,
             "month_start": latest_month - relativedelta(years=1),
             "month_end": latest_month},
        )
        rolling_prior = await db.execute(
            text("""
                SELECT SUM(crime_count) as cnt
                FROM core_crime_lsoa
                WHERE lsoa_code = ANY(:codes)
                  AND month > :month_start AND month <= :month_end
            """),
            {"codes": lsoa_codes,
             "month_start": latest_month - relativedelta(years=2),
             "month_end": latest_month - relativedelta(years=1)},
        )
        current_row = rolling_current.mappings().first()
        prior_row = rolling_prior.mappings().first()
        rolling_current_total = int(current_row["cnt"]) if current_row and current_row["cnt"] is not None else None
        rolling_prior_total = int(prior_row["cnt"]) if prior_row and prior_row["cnt"] is not None else None

        if rolling_prior_total is not None and rolling_prior_total > 0 and rolling_current_total is not None:
            yoy_change = round((rolling_current_total - rolling_prior_total) / rolling_prior_total * 100, 1)
            # Parent crime trend (same YoY window)
            parent_crime_yoy = None
            if parent_lads and not gmp_parent:
                parent_current_res = await db.execute(
                    text("""
                        SELECT SUM(c.crime_count) as cnt
                        FROM core_crime_lsoa c
                        JOIN core_lsoa_boundaries l ON l.lsoa_code = c.lsoa_code
                        WHERE l.lad_code = ANY(:parent_lads)
                          AND c.month > :month_start AND c.month <= :month_end
                    """),
                    {"parent_lads": parent_lads,
                     "month_start": latest_month - relativedelta(years=1),
                     "month_end": latest_month},
                )
                parent_prior_res = await db.execute(
                    text("""
                        SELECT SUM(c.crime_count) as cnt
                        FROM core_crime_lsoa c
                        JOIN core_lsoa_boundaries l ON l.lsoa_code = c.lsoa_code
                        WHERE l.lad_code = ANY(:parent_lads)
                          AND c.month > :month_start AND c.month <= :month_end
                    """),
                    {"parent_lads": parent_lads,
                     "month_start": latest_month - relativedelta(years=2),
                     "month_end": latest_month - relativedelta(years=1)},
                )
                pc = parent_current_res.mappings().first()
                pp = parent_prior_res.mappings().first()
                pc_total = int(pc["cnt"]) if pc and pc["cnt"] else 0
                pp_total = int(pp["cnt"]) if pp and pp["cnt"] else 0
                if pp_total > 0 and pc_total > 0:
                    parent_crime_yoy = round((pc_total - pp_total) / pp_total * 100, 1)

            metrics.append(metric(
                "crime_trend", "Crime Trend (YoY)",
                yoy_change, parent_crime_yoy, "%",
                details={"current_12m_crimes": rolling_current_total, "prior_12m_crimes": rolling_prior_total},
            ))

    # --- Flood Risk ---
    # Zone 3 = High risk (>1% annual), Zone 2 = Medium (0.1–1%), neither = Low/Very Low
    flood_local = await db.execute(
        text("""
            SELECT
                COUNT(*) as total_lsoas,
                SUM(in_zone_3::int) as zone3_count,
                SUM(in_zone_2::int) as zone2_count
            FROM core_flood_lsoa
            WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    flood_row = flood_local.mappings().first()

    flood_parent = await db.execute(
        text("""
            SELECT
                COUNT(*) as total_lsoas,
                SUM(f.in_zone_3::int) as zone3_count,
                SUM(f.in_zone_2::int) as zone2_count
            FROM core_flood_lsoa f
            JOIN core_lsoa_boundaries l ON l.lsoa_code = f.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    flood_parent_row = flood_parent.mappings().first()

    if flood_row and flood_row["total_lsoas"]:
        total = int(flood_row["total_lsoas"])
        z3 = int(flood_row["zone3_count"] or 0)
        z2 = int(flood_row["zone2_count"] or 0)
        pct_high = round(z3 / total * 100, 1)
        pct_medium = round(z2 / total * 100, 1)

        # Overall risk level: based on highest zone present
        if z3 > 0:
            flood_level = "High" if pct_high >= 10 else "Low-Medium"
        elif z2 > 0:
            flood_level = "Medium" if pct_medium >= 10 else "Low"
        else:
            flood_level = "Very Low"

        # Parent percentages and level
        parent_flood_level = None
        parent_pct_high = None
        parent_pct_medium = None
        if flood_parent_row and flood_parent_row["total_lsoas"]:
            pt = int(flood_parent_row["total_lsoas"])
            pz3 = int(flood_parent_row["zone3_count"] or 0)
            pz2 = int(flood_parent_row["zone2_count"] or 0)
            parent_pct_high = round(pz3 / pt * 100, 1)
            parent_pct_medium = round(pz2 / pt * 100, 1)
            if pz3 > 0:
                parent_flood_level = "High" if parent_pct_high >= 10 else "Low-Medium"
            elif pz2 > 0:
                parent_flood_level = "Medium" if parent_pct_medium >= 10 else "Low"
            else:
                parent_flood_level = "Very Low"

        # risk_score: 0=Very Low … 100=High (drives gauge needle)
        risk_score = {"Very Low": 5, "Low": 20, "Low-Medium": 40, "Medium": 60, "High": 90}.get(flood_level, 5)

        metrics.append(metric(
            "flood_risk", "Flood Risk",
            flood_level, parent_flood_level, "level",
            details={
                "risk_score": risk_score,
                "flood_level": flood_level,
                "zone_3_pct": pct_high,
                "zone_2_pct": pct_medium,
                "high_risk_lsoa_count": z3,
                "medium_risk_lsoa_count": z2,
                "total_lsoas": total,
                "parent_zone_3_pct": parent_pct_high,
                "parent_zone_2_pct": parent_pct_medium,
            },
        ))

    # --- Air Quality ---
    # WHO limits: NO2 = 10 µg/m³ (annual), PM2.5 = 5 µg/m³ (annual)
    if is_area:
        # Area mode: average AQ across grid cells intersecting LSOA boundaries
        aq_result = await db.execute(
            text("""
                SELECT AVG(a.no2_ugm3) as no2_ugm3, AVG(a.pm25_ugm3) as pm25_ugm3,
                       AVG(a.pm10_ugm3) as pm10_ugm3
                FROM core_air_quality a
                JOIN core_lsoa_boundaries lb ON ST_Intersects(a.geom, lb.geom)
                WHERE lb.lsoa_code = ANY(:codes)
            """),
            {"codes": lsoa_codes},
        )
        aq_row = aq_result.mappings().first()
    elif lat is not None:
        aq_result = await db.execute(
            text("""
                SELECT no2_ugm3, pm25_ugm3, pm10_ugm3
                FROM core_air_quality
                WHERE geom IS NOT NULL
                ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                LIMIT 1
            """),
            {"lat": lat, "lon": lon},
        )
        aq_row = aq_result.mappings().first()
    else:
        aq_row = None

    # Parent average via pre-computed LAD-level table (avoids expensive spatial join)
    if aq_row:
        aq_parent = await db.execute(
            text("""
                SELECT AVG(no2_ugm3) as avg_no2, AVG(pm25_ugm3) as avg_pm25
                FROM core_air_quality_lad
                WHERE lad_code = ANY(:parent_lads)
                  AND year >= 2020
            """),
            {"parent_lads": parent_lads},
        )
        aq_parent_row = aq_parent.mappings().first()
    else:
        aq_parent_row = None

    if aq_row and aq_row["no2_ugm3"]:
        local_no2 = round(float(aq_row["no2_ugm3"]), 1)
        parent_no2 = round(float(aq_parent_row["avg_no2"]), 1) if aq_parent_row and aq_parent_row["avg_no2"] else None

        metrics.append(metric(
            "air_quality_no2", "Air Quality (NO2)",
            local_no2, parent_no2, "µg/m³",
            details={
                "who_limit": 10.0,
                "exceeds_who": local_no2 > 10.0,
            },
        ))

    if aq_row and aq_row["pm25_ugm3"]:
        local_pm25 = round(float(aq_row["pm25_ugm3"]), 1)
        parent_pm25 = round(float(aq_parent_row["avg_pm25"]), 1) if aq_parent_row and aq_parent_row["avg_pm25"] else None

        metrics.append(metric(
            "air_quality_pm25", "Air Quality (PM2.5)",
            local_pm25, parent_pm25, "µg/m³",
            details={
                "who_limit": 5.0,
                "exceeds_who": local_pm25 > 5.0,
            },
        ))

    # --- Noise ---
    # Bible: average decibel level (road/rail/air)
    # Query postcodes in LSOA(s) for noise data, average across all
    noise_result = await db.execute(
        text("""
            SELECT AVG(n.road_noise_db) as road_noise_db,
                   AVG(n.rail_noise_db) as rail_noise_db,
                   AVG(n.air_noise_db) as air_noise_db,
                   MODE() WITHIN GROUP (ORDER BY n.noise_band) as noise_band
            FROM core_noise n
            JOIN core_postcodes p ON p.postcode = n.postcode
            WHERE p.lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    noise_row = noise_result.mappings().first()
    # Parent noise average
    parent_noise = None
    if noise_row and noise_row["road_noise_db"] and parent_lads:
        noise_parent_res = await db.execute(
            text("""
                SELECT AVG(n.road_noise_db) as avg_road
                FROM core_noise n
                JOIN core_postcodes p ON p.postcode = n.postcode
                JOIN core_lsoa_boundaries l ON l.lsoa_code = p.lsoa_code
                WHERE l.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        noise_parent_row = noise_parent_res.mappings().first()
        parent_noise = round(float(noise_parent_row["avg_road"]), 1) if noise_parent_row and noise_parent_row["avg_road"] else None

    if noise_row and any(noise_row[k] is not None for k in ("road_noise_db", "rail_noise_db", "air_noise_db")):
        metrics.append(metric(
            "noise", "Noise Level",
            float(noise_row["road_noise_db"]) if noise_row["road_noise_db"] else None,
            parent_noise, "dB",
            details={
                "road_db": float(noise_row["road_noise_db"]) if noise_row["road_noise_db"] else None,
                "rail_db": float(noise_row["rail_noise_db"]) if noise_row["rail_noise_db"] else None,
                "air_db": float(noise_row["air_noise_db"]) if noise_row["air_noise_db"] else None,
                "noise_band": noise_row["noise_band"],
            },
        ))

    # --- Green Space & Sports/Recreation ---
    # Parks = "Public Park Or Garden" only
    # Sports = Golf Course, Tennis Court, Bowling Green, Other Sports Facility, Play Space, Playing Field
    # Excluded entirely: Allotments, Cemetery, Religious Grounds
    PARK_TYPES = ('Public Park Or Garden',)
    SPORT_TYPES = ('Golf Course', 'Tennis Court', 'Bowling Green', 'Other Sports Facility', 'Play Space', 'Playing Field')

    # Parent averages for spatial metrics (pre-computed in core_lsoa_green_space)
    parent_green = None
    if parent_lads:
        parent_green_res = await db.execute(
            text("""
                SELECT AVG(g.nearest_park_m) AS avg_park_m,
                       AVG(g.parks_1km) AS avg_parks,
                       AVG(g.green_cover_pct) AS avg_cover,
                       AVG(g.sports_rec_1km) AS avg_sports
                FROM core_lsoa_green_space g
                JOIN core_lsoa_boundaries l ON l.lsoa_code = g.lsoa_code
                WHERE l.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        parent_green = parent_green_res.mappings().first()

    parent_park_m = round(float(parent_green["avg_park_m"])) if parent_green and parent_green["avg_park_m"] else None
    parent_parks_1km = round(float(parent_green["avg_parks"]), 1) if parent_green and parent_green["avg_parks"] else None
    parent_cover_pct = round(float(parent_green["avg_cover"]), 1) if parent_green and parent_green["avg_cover"] else None
    parent_sports = round(float(parent_green["avg_sports"]), 1) if parent_green and parent_green["avg_sports"] else None

    if is_area:
        # Area mode: parks + sports within LSOA boundaries
        gs_within = await db.execute(
            text("""
                SELECT gs.site_name, gs.site_type,
                       ST_Area(gs.geom::geography) / 10000 as area_ha
                FROM core_green_space gs
                JOIN core_lsoa_boundaries lb ON ST_Intersects(gs.geom, lb.geom)
                WHERE lb.lsoa_code = ANY(:codes)
                  AND gs.geom IS NOT NULL
                  AND gs.site_type = ANY(:types)
                ORDER BY ST_Area(gs.geom::geography) DESC
            """),
            {"codes": lsoa_codes, "types": list(PARK_TYPES + SPORT_TYPES)},
        )
        gs_rows = gs_within.mappings().all()

        park_rows = [r for r in gs_rows if r["site_type"] in PARK_TYPES]
        sport_rows = [r for r in gs_rows if r["site_type"] in SPORT_TYPES]

        # Parks metric
        park_ha = sum(float(r["area_ha"]) for r in park_rows if r["area_ha"])
        parks_list = [
            {"name": r["site_name"] or "Unnamed", "area_ha": round(float(r["area_ha"]), 2) if r["area_ha"] else None}
            for r in park_rows[:8]
        ]
        metrics.append(metric(
            "green_spaces", "Parks & Gardens in Area",
            len(park_rows), parent_parks_1km, "count",
            details={
                "total_hectares": round(park_ha, 1),
                "parks": parks_list,
            } if park_rows else None,
        ))

        # Sports & Recreation metric
        sport_ha = sum(float(r["area_ha"]) for r in sport_rows if r["area_ha"])
        sport_type_counts: dict[str, int] = {}
        for r in sport_rows:
            st = r["site_type"] or "Other"
            sport_type_counts[st] = sport_type_counts.get(st, 0) + 1
        metrics.append(metric(
            "sports_recreation", "Sports & Recreation in Area",
            len(sport_rows), parent_sports, "count",
            details={
                "total_hectares": round(sport_ha, 1),
                **{k.lower().replace(" ", "_") + "_count": v for k, v in sport_type_counts.items()},
            } if sport_rows else None,
        ))

    elif lat is not None:
        # Postcode mode: distance-based queries
        # Nearest park (Public Park Or Garden only)
        park_result = await db.execute(
            text("""
                SELECT site_name, site_type,
                       ST_Area(geom::geography) / 10000 as area_ha,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)::int as distance_m
                FROM core_green_space
                WHERE geom IS NOT NULL
                  AND site_type = ANY(:park_types)
                ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                LIMIT 1
            """),
            {"lat": lat, "lon": lon, "park_types": list(PARK_TYPES)},
        )
        park_row = park_result.mappings().first()

        # Parks within 1km
        gs_parks = await db.execute(
            text("""
                SELECT site_name, site_type,
                       ST_Area(geom::geography) / 10000 as area_ha,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)::int as distance_m
                FROM core_green_space
                WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1000)
                  AND geom IS NOT NULL
                  AND site_type = ANY(:park_types)
                ORDER BY distance_m
            """),
            {"lat": lat, "lon": lon, "park_types": list(PARK_TYPES)},
        )
        park_rows = gs_parks.mappings().all()

        park_ha = sum(float(r["area_ha"]) for r in park_rows if r["area_ha"])
        park_count = len(park_rows)
        green_cover_pct = round(park_ha / 314.16 * 100, 1) if park_ha else 0.0

        parks_list = [
            {"name": r["site_name"] or "Unnamed", "distance_m": int(r["distance_m"]), "area_ha": round(float(r["area_ha"]), 2) if r["area_ha"] else None}
            for r in park_rows[:8]
        ]

        nearest_dist = int(park_row["distance_m"]) if park_row else None

        metrics.append(metric(
            "green_cover", "Park Cover (1km)",
            green_cover_pct, parent_cover_pct, "%",
            details={
                "total_hectares": round(park_ha, 1),
                "parks_within_1km": park_count,
            },
        ))

        metrics.append(metric(
            "nearest_park", "Nearest Park",
            nearest_dist, parent_park_m, "metres",
            details={
                "park_name": park_row["site_name"] if park_row else None,
                "park_area_ha": round(float(park_row["area_ha"]), 1) if park_row and park_row["area_ha"] else None,
            },
        ))

        metrics.append(metric(
            "parks_1km", "Parks Within 1km",
            park_count, parent_parks_1km, "count",
            details={"parks": parks_list} if parks_list else None,
        ))

        # Sports & Recreation within 1km
        gs_sports = await db.execute(
            text("""
                SELECT site_name, site_type,
                       ST_Area(geom::geography) / 10000 as area_ha,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)::int as distance_m
                FROM core_green_space
                WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1000)
                  AND geom IS NOT NULL
                  AND site_type = ANY(:sport_types)
                ORDER BY distance_m
            """),
            {"lat": lat, "lon": lon, "sport_types": list(SPORT_TYPES)},
        )
        sport_rows = gs_sports.mappings().all()

        sport_type_counts: dict[str, int] = {}
        for r in sport_rows:
            st = r["site_type"] or "Other"
            sport_type_counts[st] = sport_type_counts.get(st, 0) + 1
        sport_list = [
            {"name": r["site_name"] or "Unnamed", "type": r["site_type"], "distance_m": int(r["distance_m"])}
            for r in sport_rows[:8]
        ]
        metrics.append(metric(
            "sports_recreation", "Sports & Recreation (1km)",
            len(sport_rows), parent_sports, "count",
            details={
                **{k.lower().replace(" ", "_") + "_count": v for k, v in sport_type_counts.items()},
                "facilities": sport_list,
            } if sport_rows else None,
        ))

    # --- EPC Energy Performance ---
    # Bible: Average EPC rating, % below Band C
    epc_result = await db.execute(
        text("""
            SELECT AVG(avg_energy_score) as avg_energy_score,
                   AVG(pct_rating_a_b) as pct_rating_a_b,
                   AVG(pct_rating_c) as pct_rating_c,
                   AVG(pct_rating_d) as pct_rating_d,
                   AVG(pct_rating_e_g) as pct_rating_e_g,
                   AVG(avg_co2_emissions) as avg_co2_emissions,
                   SUM(total_certs) as total_certs,
                   AVG(heat_gas_pct) as heat_gas_pct,
                   AVG(heat_electric_pct) as heat_electric_pct,
                   AVG(heat_oil_pct) as heat_oil_pct,
                   AVG(heat_district_pct) as heat_district_pct
            FROM core_epc_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    epc_row = epc_result.mappings().first()

    # Parent EPC average (parent comparison group)
    epc_parent = await db.execute(
        text("""
            SELECT AVG(avg_energy_score) as avg_score,
                   AVG(pct_rating_a_b) as avg_ab,
                   AVG(pct_rating_c) as avg_c
            FROM core_epc_lsoa e
            JOIN core_lsoa_boundaries l ON l.lsoa_code = e.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    epc_parent_row = epc_parent.mappings().first()

    if epc_row and epc_row["avg_energy_score"]:
        local_score = round(float(epc_row["avg_energy_score"]), 1)
        parent_score = round(float(epc_parent_row["avg_score"]), 1) if epc_parent_row and epc_parent_row["avg_score"] else None

        epc_details = {
            "pct_a_b": round(float(epc_row["pct_rating_a_b"]), 1) if epc_row["pct_rating_a_b"] else None,
            "pct_c": round(float(epc_row["pct_rating_c"]), 1) if epc_row["pct_rating_c"] else None,
            "pct_d": round(float(epc_row["pct_rating_d"]), 1) if epc_row["pct_rating_d"] else None,
            "pct_e_g": round(float(epc_row["pct_rating_e_g"]), 1) if epc_row["pct_rating_e_g"] else None,
        }
        # Heating type breakdown (from extended EPC data)
        if epc_row["heat_gas_pct"] is not None:
            epc_details["heating_gas_pct"] = round(float(epc_row["heat_gas_pct"]), 1)
        if epc_row["heat_electric_pct"] is not None:
            epc_details["heating_electric_pct"] = round(float(epc_row["heat_electric_pct"]), 1)
        if epc_row["heat_oil_pct"] is not None:
            epc_details["heating_oil_pct"] = round(float(epc_row["heat_oil_pct"]), 1)
        if epc_row["heat_district_pct"] is not None:
            epc_details["heating_district_pct"] = round(float(epc_row["heat_district_pct"]), 1)

        metrics.append(metric(
            "epc_rating", "Average EPC Score",
            local_score, parent_score, "score",
            details=epc_details,
        ))

        epc_c_plus_local = None
        if epc_row["pct_rating_a_b"] is not None or epc_row["pct_rating_c"] is not None:
            epc_c_plus_local = round(
                float(epc_row["pct_rating_a_b"] or 0) + float(epc_row["pct_rating_c"] or 0),
                1,
            )
        epc_c_plus_parent = None
        if epc_parent_row and (epc_parent_row["avg_ab"] is not None or epc_parent_row["avg_c"] is not None):
            epc_c_plus_parent = round(
                float(epc_parent_row["avg_ab"] or 0) + float(epc_parent_row["avg_c"] or 0),
                1,
            )
        if epc_c_plus_local is not None:
            metrics.append(metric(
                "epc_rating_c_plus", "EPC Rated C or Above",
                epc_c_plus_local, epc_c_plus_parent, "%",
                details={
                    "pct_a_b": epc_details.get("pct_a_b"),
                    "pct_c": epc_details.get("pct_c"),
                },
            ))

    return metrics
