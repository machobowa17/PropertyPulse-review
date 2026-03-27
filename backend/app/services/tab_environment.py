"""Tab 3: Environment & Safety — Bible Part 4, Tab 3.
Queries: core_crime_lsoa, core_flood_zones, core_air_quality, core_noise, core_green_space, core_epc_lsoa."""
from sqlalchemy import text
from app.services.helpers import metric, get_lsoa_centroid


async def fetch_environment_safety(db, *, lad_code, ward_code, lsoa_code):
    metrics = []
    lat, lon = await get_lsoa_centroid(db, lsoa_code)

    # --- Crime & Safety ---
    # Bible: Overall crime rate per 1,000 population vs national average, breakdown by type
    # Use latest month only for rate
    latest_month_result = await db.execute(
        text("SELECT MAX(month) as latest FROM core_crime_lsoa"),
    )
    latest_month = latest_month_result.scalar()

    crime_local = await db.execute(
        text("""
            SELECT crime_type, SUM(crime_count) as cnt
            FROM core_crime_lsoa WHERE lsoa_code = :lsoa AND month = :month
            GROUP BY crime_type ORDER BY cnt DESC
        """),
        {"lsoa": lsoa_code, "month": latest_month},
    )
    crime_rows = crime_local.mappings().all()
    local_total = sum(int(r["cnt"]) for r in crime_rows)
    crime_breakdown = {r["crime_type"]: int(r["cnt"]) for r in crime_rows}

    # Get local population for rate calculation
    pop_result = await db.execute(
        text("SELECT total_population FROM core_census_demographics_lsoa WHERE lsoa_code = :lsoa"),
        {"lsoa": lsoa_code},
    )
    pop_row = pop_result.mappings().first()
    local_pop = int(pop_row["total_population"]) if pop_row and pop_row["total_population"] else None

    # Parent average crime rate (LAD level, per 1000 pop)
    crime_parent = await db.execute(
        text("""
            SELECT SUM(c.crime_count) as total_crimes,
                   SUM(d.total_population) as total_pop
            FROM core_crime_lsoa c
            JOIN core_lsoa_boundaries l ON l.lsoa_code = c.lsoa_code
            JOIN core_census_demographics_lsoa d ON d.lsoa_code = c.lsoa_code
            WHERE l.lad_code = :lad AND c.month = :month
        """),
        {"lad": lad_code, "month": latest_month},
    )
    cp_row = crime_parent.mappings().first()

    local_rate = round(local_total / local_pop * 1000, 1) if local_pop and local_pop > 0 else None
    parent_rate = None
    if cp_row and cp_row["total_pop"] and int(cp_row["total_pop"]) > 0:
        parent_rate = round(int(cp_row["total_crimes"]) / int(cp_row["total_pop"]) * 1000, 1)

    if local_rate is not None:
        metrics.append(metric(
            "crime_rate", "Crime Rate (per 1,000 pop)",
            local_rate, parent_rate, "per 1,000",
            details=crime_breakdown or None,
        ))

    # Bible: Crime Trend — year-on-year change
    if latest_month:
        from datetime import timedelta
        prior_month = latest_month.replace(year=latest_month.year - 1)
        prior_local = await db.execute(
            text("SELECT SUM(crime_count) as cnt FROM core_crime_lsoa WHERE lsoa_code = :lsoa AND month = :month"),
            {"lsoa": lsoa_code, "month": prior_month},
        )
        prior_row = prior_local.mappings().first()
        prior_total = int(prior_row["cnt"]) if prior_row and prior_row["cnt"] else None

        if prior_total and prior_total > 0 and local_total > 0:
            yoy_change = round((local_total - prior_total) / prior_total * 100, 1)
            metrics.append(metric(
                "crime_trend", "Crime Trend (YoY)",
                yoy_change, None, "%",
                details={"latest_month_crimes": local_total, "prior_year_crimes": prior_total},
            ))

    # --- Flood Risk ---
    # Bible: Flood Risk level (High/Medium/Low/Very Low)
    # Zone 3 = High, Zone 2 = Medium, neither = Low/Very Low
    if lat is not None:
        flood_result = await db.execute(
            text("""
                SELECT flood_zone
                FROM core_flood_zones
                WHERE ST_Intersects(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                ORDER BY flood_zone DESC LIMIT 1
            """),
            {"lat": lat, "lon": lon},
        )
        flood_row = flood_result.mappings().first()
        if flood_row:
            zone = flood_row["flood_zone"]
            flood_level = "High" if zone == "3" else "Medium"
        else:
            flood_level = "Very Low"

        metrics.append(metric(
            "flood_risk", "Flood Risk",
            flood_level, None, "level",
        ))

    # --- Air Quality ---
    # Bible: NO2 and PM2.5 levels vs WHO limits
    # WHO limits: NO2 = 10 µg/m³ (annual), PM2.5 = 5 µg/m³ (annual)
    if lat is not None:
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

        # Parent average across LAD
        aq_parent = await db.execute(
            text("""
                SELECT AVG(a.no2_ugm3) as avg_no2, AVG(a.pm25_ugm3) as avg_pm25
                FROM core_air_quality a
                JOIN core_lsoa_boundaries l ON ST_Intersects(l.geom, a.geom)
                WHERE l.lad_code = :lad
            """),
            {"lad": lad_code},
        )
        aq_parent_row = aq_parent.mappings().first()

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
    # Query nearest postcode in LSOA for noise data
    noise_result = await db.execute(
        text("""
            SELECT n.road_noise_db, n.rail_noise_db, n.air_noise_db, n.noise_band
            FROM core_noise n
            JOIN core_postcodes p ON p.postcode = n.postcode
            WHERE p.lsoa_code = :lsoa
            LIMIT 1
        """),
        {"lsoa": lsoa_code},
    )
    noise_row = noise_result.mappings().first()
    if noise_row:
        metrics.append(metric(
            "noise", "Noise Level",
            float(noise_row["road_noise_db"]) if noise_row["road_noise_db"] else None,
            None, "dB",
            details={
                "road_db": float(noise_row["road_noise_db"]) if noise_row["road_noise_db"] else None,
                "rail_db": float(noise_row["rail_noise_db"]) if noise_row["rail_noise_db"] else None,
                "air_db": float(noise_row["air_noise_db"]) if noise_row["air_noise_db"] else None,
                "noise_band": noise_row["noise_band"],
            },
        ))

    # --- Green Space ---
    # Bible: distance to nearest park, total green space area within 1km
    if lat is not None:
        park_result = await db.execute(
            text("""
                SELECT site_name, area_hectares,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) as distance_m
                FROM core_green_space
                WHERE geom IS NOT NULL
                ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                LIMIT 1
            """),
            {"lat": lat, "lon": lon},
        )
        park_row = park_result.mappings().first()

        # Total green space within 1km
        gs_total = await db.execute(
            text("""
                SELECT SUM(area_hectares) as total_ha, COUNT(*) as cnt
                FROM core_green_space
                WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1000)
            """),
            {"lat": lat, "lon": lon},
        )
        gs_row = gs_total.mappings().first()

        nearest_dist = round(float(park_row["distance_m"])) if park_row else None
        metrics.append(metric(
            "nearest_park", "Nearest Park",
            nearest_dist, None, "metres",
            details={
                "park_name": park_row["site_name"] if park_row else None,
                "park_area_ha": round(float(park_row["area_hectares"]), 1) if park_row and park_row["area_hectares"] else None,
                "green_space_1km_ha": round(float(gs_row["total_ha"]), 1) if gs_row and gs_row["total_ha"] else None,
                "green_space_1km_count": int(gs_row["cnt"]) if gs_row else 0,
            },
        ))

    # --- EPC Energy Performance ---
    # Bible: Average EPC rating, % below Band C
    epc_result = await db.execute(
        text("""
            SELECT avg_energy_score, pct_rating_a_b, pct_rating_c, pct_rating_d,
                   pct_rating_e_g, avg_co2_emissions, total_certs
            FROM core_epc_lsoa WHERE lsoa_code = :lsoa
        """),
        {"lsoa": lsoa_code},
    )
    epc_row = epc_result.mappings().first()

    # Parent EPC average
    epc_parent = await db.execute(
        text("""
            SELECT AVG(avg_energy_score) as avg_score, AVG(pct_rating_a_b) as avg_ab
            FROM core_epc_lsoa e
            JOIN core_lsoa_boundaries l ON l.lsoa_code = e.lsoa_code
            WHERE l.lad_code = :lad
        """),
        {"lad": lad_code},
    )
    epc_parent_row = epc_parent.mappings().first()

    if epc_row and epc_row["avg_energy_score"]:
        local_score = round(float(epc_row["avg_energy_score"]), 1)
        parent_score = round(float(epc_parent_row["avg_score"]), 1) if epc_parent_row and epc_parent_row["avg_score"] else None

        metrics.append(metric(
            "epc_rating", "Average EPC Score",
            local_score, parent_score, "score",
            details={
                "pct_a_b": round(float(epc_row["pct_rating_a_b"]), 1) if epc_row["pct_rating_a_b"] else None,
                "pct_c": round(float(epc_row["pct_rating_c"]), 1) if epc_row["pct_rating_c"] else None,
                "pct_d": round(float(epc_row["pct_rating_d"]), 1) if epc_row["pct_rating_d"] else None,
                "pct_e_g": round(float(epc_row["pct_rating_e_g"]), 1) if epc_row["pct_rating_e_g"] else None,
            },
        ))

    # --- ESG Score (Composite 0-100) ---
    # Computed from: EPC score (0-100, weight 25%), Air Quality (WHO compliance, 25%),
    # Flood Risk (25%), Green Space accessibility (25%)
    esg_components = []

    # EPC component: score already 0-100 (higher = better)
    if epc_row and epc_row["avg_energy_score"]:
        esg_components.append(("epc", min(float(epc_row["avg_energy_score"]), 100)))

    # Air quality: NO2 score (10 µg/m³ WHO limit → 100 at 0, 0 at 20+)
    if 'local_no2' in locals():
        aq_score = max(0, min(100, (20 - local_no2) / 20 * 100)) if local_no2 else 50
        esg_components.append(("air_quality", round(aq_score, 1)))

    # Flood risk: Very Low=100, Low=75, Medium=50, High=25
    flood_scores = {"Very Low": 100, "Low": 75, "Medium": 50, "High": 25}
    if 'flood_level' in locals():
        esg_components.append(("flood_risk", flood_scores.get(flood_level, 50)))

    # Green space: park within 500m=100, 1km=75, 2km=50, else 25
    if 'nearest_dist' in locals() and nearest_dist is not None:
        if nearest_dist <= 500:
            gs_score = 100
        elif nearest_dist <= 1000:
            gs_score = 75
        elif nearest_dist <= 2000:
            gs_score = 50
        else:
            gs_score = 25
        esg_components.append(("green_space", gs_score))

    if esg_components:
        esg_score = round(sum(s for _, s in esg_components) / len(esg_components), 1)
        metrics.append(metric(
            "esg_score", "ESG Score",
            esg_score, None, "score /100",
            details={k: v for k, v in esg_components},
        ))

    return metrics
