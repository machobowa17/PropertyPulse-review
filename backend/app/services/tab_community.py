"""Tab 4: Community & Education — Bible Part 4, Tab 4.
Queries: core_census_demographics_lsoa, core_census_housing_lsoa, core_schools,
         core_imd_lsoa, core_nhs_facilities."""
from sqlalchemy import text
from app.services.helpers import metric, get_lsoa_centroid


async def fetch_community_education(db, *, lad_code, ward_code, lsoa_code):
    metrics = []
    lat, lon = await get_lsoa_centroid(db, lsoa_code)

    # --- Demographics ---
    demo_local = await db.execute(
        text("""
            SELECT total_population, population_density, median_age,
                   pct_age_0_15, pct_age_16_64, pct_age_65_plus,
                   pct_families, pct_singles, pct_sharers
            FROM core_census_demographics_lsoa WHERE lsoa_code = :lsoa
        """),
        {"lsoa": lsoa_code},
    )
    demo_row = demo_local.mappings().first()

    # Parent averages (LAD-wide)
    demo_parent = await db.execute(
        text("""
            SELECT AVG(population_density) as avg_density, AVG(median_age) as avg_age,
                   AVG(pct_families) as avg_families, AVG(pct_singles) as avg_singles,
                   AVG(pct_sharers) as avg_sharers,
                   AVG(pct_age_0_15) as avg_0_15, AVG(pct_age_16_64) as avg_16_64,
                   AVG(pct_age_65_plus) as avg_65plus
            FROM core_census_demographics_lsoa d
            JOIN core_lsoa_boundaries l ON l.lsoa_code = d.lsoa_code
            WHERE l.lad_code = :lad
        """),
        {"lad": lad_code},
    )
    demo_parent_row = demo_parent.mappings().first()

    if demo_row:
        # Population Density
        metrics.append(metric(
            "population_density", "Population Density",
            _r(demo_row["population_density"]),
            _r(demo_parent_row["avg_density"]) if demo_parent_row else None,
            "people/hectare",
        ))

        # Median Age
        metrics.append(metric(
            "median_age", "Median Age",
            _r(demo_row["median_age"]),
            _r(demo_parent_row["avg_age"]) if demo_parent_row else None,
            "years",
            details={
                "pct_0_15": _r(demo_row["pct_age_0_15"]),
                "pct_16_64": _r(demo_row["pct_age_16_64"]),
                "pct_65_plus": _r(demo_row["pct_age_65_plus"]),
            },
        ))

        # Household Composition
        metrics.append(metric(
            "household_composition", "Household Composition",
            _r(demo_row["pct_families"]),
            _r(demo_parent_row["avg_families"]) if demo_parent_row else None,
            "% families",
            details={
                "pct_families": _r(demo_row["pct_families"]),
                "pct_singles": _r(demo_row["pct_singles"]),
                "pct_sharers": _r(demo_row["pct_sharers"]),
            },
        ))

    # --- Housing Tenure & Type ---
    housing_local = await db.execute(
        text("""
            SELECT total_households, pct_owned, pct_social_rent, pct_private_rent,
                   pct_detached, pct_semi, pct_terraced, pct_flat
            FROM core_census_housing_lsoa WHERE lsoa_code = :lsoa
        """),
        {"lsoa": lsoa_code},
    )
    housing_row = housing_local.mappings().first()

    housing_parent = await db.execute(
        text("""
            SELECT AVG(pct_owned) as avg_owned, AVG(pct_private_rent) as avg_priv_rent,
                   AVG(pct_detached) as avg_det, AVG(pct_semi) as avg_semi,
                   AVG(pct_terraced) as avg_terr, AVG(pct_flat) as avg_flat
            FROM core_census_housing_lsoa h
            JOIN core_lsoa_boundaries l ON l.lsoa_code = h.lsoa_code
            WHERE l.lad_code = :lad
        """),
        {"lad": lad_code},
    )
    housing_parent_row = housing_parent.mappings().first()

    if housing_row:
        metrics.append(metric(
            "housing_tenure", "Housing Tenure",
            _r(housing_row["pct_owned"]),
            _r(housing_parent_row["avg_owned"]) if housing_parent_row else None,
            "% owner-occupied",
            details={
                "pct_owned": _r(housing_row["pct_owned"]),
                "pct_social_rent": _r(housing_row["pct_social_rent"]),
                "pct_private_rent": _r(housing_row["pct_private_rent"]),
            },
        ))

        metrics.append(metric(
            "housing_type", "Housing Stock",
            _r(housing_row["pct_detached"]),
            _r(housing_parent_row["avg_det"]) if housing_parent_row else None,
            "% detached",
            details={
                "pct_detached": _r(housing_row["pct_detached"]),
                "pct_semi": _r(housing_row["pct_semi"]),
                "pct_terraced": _r(housing_row["pct_terraced"]),
                "pct_flat": _r(housing_row["pct_flat"]),
            },
        ))

    # --- Schools (Bible: count Outstanding/Good within radius) ---
    if lat is not None:
        # Primary: within 1 mile (1609m)
        primary = await db.execute(
            text("""
                SELECT COUNT(*) FILTER (WHERE ofsted_rating IN ('Outstanding', 'Good')) as good_count,
                       COUNT(*) as total
                FROM core_schools
                WHERE phase = 'Primary' AND is_open = TRUE
                  AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1609)
            """),
            {"lat": lat, "lon": lon},
        )
        prim_row = primary.mappings().first()

        # Nearest primary schools with details
        primary_list = await db.execute(
            text("""
                SELECT school_name, ofsted_rating, ks2_reading_pct, ks2_maths_pct,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) as distance_m
                FROM core_schools
                WHERE phase = 'Primary' AND is_open = TRUE
                  AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1609)
                ORDER BY distance_m LIMIT 10
            """),
            {"lat": lat, "lon": lon},
        )
        prim_list = [
            {
                "name": r["school_name"],
                "ofsted": r["ofsted_rating"],
                "ks2_reading": _r(r["ks2_reading_pct"]),
                "ks2_maths": _r(r["ks2_maths_pct"]),
                "distance_m": round(float(r["distance_m"])),
            }
            for r in primary_list.mappings().all()
        ]

        metrics.append(metric(
            "primary_schools", "Primary Schools (1 mile)",
            int(prim_row["good_count"]) if prim_row else 0,
            None, "Outstanding/Good count",
            details={"total_within_1mi": int(prim_row["total"]) if prim_row else 0, "schools": prim_list},
        ))

        # Secondary: within 3 miles (4828m)
        secondary = await db.execute(
            text("""
                SELECT COUNT(*) FILTER (WHERE ofsted_rating IN ('Outstanding', 'Good')) as good_count,
                       COUNT(*) as total
                FROM core_schools
                WHERE phase = 'Secondary' AND is_open = TRUE
                  AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 4828)
            """),
            {"lat": lat, "lon": lon},
        )
        sec_row = secondary.mappings().first()

        secondary_list = await db.execute(
            text("""
                SELECT school_name, ofsted_rating, gcse_progress_8, gcse_attainment_8,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) as distance_m
                FROM core_schools
                WHERE phase = 'Secondary' AND is_open = TRUE
                  AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 4828)
                ORDER BY distance_m LIMIT 10
            """),
            {"lat": lat, "lon": lon},
        )
        sec_list = [
            {
                "name": r["school_name"],
                "ofsted": r["ofsted_rating"],
                "progress_8": _r(r["gcse_progress_8"]),
                "attainment_8": _r(r["gcse_attainment_8"]),
                "distance_m": round(float(r["distance_m"])),
            }
            for r in secondary_list.mappings().all()
        ]

        metrics.append(metric(
            "secondary_schools", "Secondary Schools (3 miles)",
            int(sec_row["good_count"]) if sec_row else 0,
            None, "Outstanding/Good count",
            details={"total_within_3mi": int(sec_row["total"]) if sec_row else 0, "schools": sec_list},
        ))

    # --- IMD Deprivation ---
    imd_local = await db.execute(
        text("""
            SELECT imd_score, imd_rank, imd_decile, income_score, employment_score,
                   education_score, health_score, crime_score, barriers_score, living_env_score
            FROM core_imd_lsoa WHERE lsoa_code = :lsoa
        """),
        {"lsoa": lsoa_code},
    )
    imd_row = imd_local.mappings().first()

    imd_parent = await db.execute(
        text("""
            SELECT AVG(imd_score) as avg_score, AVG(imd_decile) as avg_decile,
                   AVG(crime_score) as avg_crime
            FROM core_imd_lsoa i
            JOIN core_lsoa_boundaries l ON l.lsoa_code = i.lsoa_code
            WHERE l.lad_code = :lad
        """),
        {"lad": lad_code},
    )
    imd_parent_row = imd_parent.mappings().first()

    if imd_row:
        metrics.append(metric(
            "deprivation", "IMD Deprivation",
            _r(imd_row["imd_score"]),
            _r(imd_parent_row["avg_score"]) if imd_parent_row else None,
            "score (lower=less deprived)",
            details={
                "rank": int(imd_row["imd_rank"]) if imd_row["imd_rank"] else None,
                "decile": int(imd_row["imd_decile"]) if imd_row["imd_decile"] else None,
                "income": _r(imd_row["income_score"]),
                "employment": _r(imd_row["employment_score"]),
                "education": _r(imd_row["education_score"]),
                "health": _r(imd_row["health_score"]),
                "crime": _r(imd_row["crime_score"]),
                "barriers": _r(imd_row["barriers_score"]),
                "living_environment": _r(imd_row["living_env_score"]),
            },
        ))

    # --- NHS Facilities nearby ---
    if lat is not None:
        nhs_result = await db.execute(
            text("""
                SELECT facility_type, COUNT(*) as cnt
                FROM core_nhs_facilities
                WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 2000)
                GROUP BY facility_type
            """),
            {"lat": lat, "lon": lon},
        )
        nhs_counts = {r["facility_type"]: int(r["cnt"]) for r in nhs_result.mappings().all()}
        total_nhs = sum(nhs_counts.values())

        metrics.append(metric(
            "nhs_facilities", "NHS Facilities (2km)",
            total_nhs, None, "count",
            details=nhs_counts or None,
        ))

    # --- Area Persona / Top Match ---
    # Bible: classify area based on demographics, housing, density
    demo = await db.execute(
        text("""
            SELECT d.population_density, d.median_age, d.pct_families, d.pct_singles,
                   d.pct_age_0_15, d.pct_age_16_64, d.pct_age_65_plus,
                   h.pct_owned, h.pct_private_rent, h.pct_detached, h.pct_flat
            FROM core_census_demographics_lsoa d
            JOIN core_census_housing_lsoa h ON h.lsoa_code = d.lsoa_code
            WHERE d.lsoa_code = :lsoa
        """),
        {"lsoa": lsoa_code},
    )
    demo_row = demo.mappings().first()
    if demo_row:
        density = float(demo_row["population_density"] or 0)
        med_age = float(demo_row["median_age"] or 35)
        pct_fam = float(demo_row["pct_families"] or 0)
        pct_singles = float(demo_row["pct_singles"] or 0)
        pct_owned = float(demo_row["pct_owned"] or 0)
        pct_rent = float(demo_row["pct_private_rent"] or 0)
        pct_flat = float(demo_row["pct_flat"] or 0)
        pct_65 = float(demo_row["pct_age_65_plus"] or 0)
        pct_0_15 = float(demo_row["pct_age_0_15"] or 0)

        # Scoring: compute scores for each persona type
        scores = {}
        scores["Urban Professional Hub"] = (
            min(density / 100, 10) + (10 if pct_singles > 40 else pct_singles / 5)
            + (10 if pct_rent > 40 else pct_rent / 5) + (10 if pct_flat > 50 else pct_flat / 6)
        )
        scores["Family Suburb"] = (
            (10 if pct_fam > 70 else pct_fam / 8) + (10 if pct_owned > 70 else pct_owned / 8)
            + (10 if pct_0_15 > 20 else pct_0_15 / 2.5) + (10 if density < 3000 else max(0, 10 - density / 1000))
        )
        scores["Retirement Haven"] = (
            (10 if pct_65 > 30 else pct_65 / 3.5) + (10 if med_age > 55 else med_age / 6)
            + (10 if pct_owned > 70 else pct_owned / 8) + (10 if density < 2000 else max(0, 10 - density / 800))
        )
        scores["Student Quarter"] = (
            (10 if pct_rent > 50 else pct_rent / 6) + (10 if pct_singles > 50 else pct_singles / 6)
            + (10 if med_age < 28 else max(0, 10 - (med_age - 20) / 3)) + min(density / 150, 10)
        )
        scores["Mixed Community"] = 20  # baseline for areas that don't strongly match

        top_persona = max(scores, key=scores.get)
        metrics.append(metric(
            "area_persona", "Area Persona",
            top_persona, None, "persona",
            details={k: round(v, 1) for k, v in sorted(scores.items(), key=lambda x: -x[1])},
        ))

    return metrics


def _r(val):
    if val is None:
        return None
    return round(float(val), 2)
