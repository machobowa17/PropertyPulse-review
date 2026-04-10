"""Tab 4: Community & Education — Bible Part 4, Tab 4.
Queries: core_census_lsoa (consolidated), core_census_ethnicity_ward, core_schools,
         core_imd_lsoa, core_nhs_facilities.
Bible Rule 4: multi-LSOA aggregation for non-postcode searches."""
from sqlalchemy import text
from app.services.helpers import metric


async def fetch_community_education(db, *, lad_code, ward_code, lsoa_codes, centroid_lat, centroid_lon, search_mode="postcode", local_lads=None, parent_lads=None, parent_name="England", boundary_source="lad"):
    metrics = []
    lat, lon = centroid_lat, centroid_lon
    if parent_lads is None:
        parent_lads = []
    is_area = search_mode == "area"

    # --- Demographics ---
    demo_local = await db.execute(
        text("""
            SELECT SUM(total_population) as total_population,
                   AVG(population_density) as population_density,
                   AVG(median_age) as median_age,
                   AVG(pct_age_0_15) as pct_age_0_15,
                   AVG(pct_age_16_64) as pct_age_16_64,
                   AVG(pct_age_65_plus) as pct_age_65_plus,
                   AVG(pct_families) as pct_families,
                   AVG(pct_singles) as pct_singles,
                   AVG(pct_sharers) as pct_sharers
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    demo_row = demo_local.mappings().first()

    # Parent averages (parent comparison group — e.g. all London boroughs)
    demo_parent = await db.execute(
        text("""
            SELECT AVG(population_density) as avg_density, AVG(median_age) as avg_age,
                   AVG(pct_families) as avg_families, AVG(pct_singles) as avg_singles,
                   AVG(pct_sharers) as avg_sharers,
                   AVG(pct_age_0_15) as avg_0_15, AVG(pct_age_16_64) as avg_16_64,
                   AVG(pct_age_65_plus) as avg_65plus
            FROM core_census_lsoa d
            JOIN core_lsoa_boundaries l ON l.lsoa_code = d.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
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

    # --- Census Extra (LSOA-level): degree, health, economic activity, car ownership, born abroad ---
    extra_result = await db.execute(
        text("""
            SELECT AVG(pct_good_health) as pct_good_health,
                   AVG(pct_economically_active) as pct_economically_active,
                   AVG(pct_degree) as pct_degree,
                   AVG(pct_no_car) as pct_no_car,
                   AVG(pct_born_abroad) as pct_born_abroad
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    extra_row = extra_result.mappings().first()

    extra_parent = await db.execute(
        text("""
            SELECT AVG(e.pct_good_health) as pct_good_health,
                   AVG(e.pct_economically_active) as pct_economically_active,
                   AVG(e.pct_degree) as pct_degree,
                   AVG(e.pct_no_car) as pct_no_car,
                   AVG(e.pct_born_abroad) as pct_born_abroad
            FROM core_census_lsoa e
            JOIN core_lsoa_boundaries l ON l.lsoa_code = e.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    extra_parent_row = extra_parent.mappings().first()

    if extra_row and extra_row["pct_good_health"] is not None:
        metrics.append(metric(
            "good_health", "Good Health",
            _r(extra_row["pct_good_health"]),
            _r(extra_parent_row["pct_good_health"]) if extra_parent_row else None,
            "%",
        ))
    if extra_row and extra_row["pct_economically_active"] is not None:
        metrics.append(metric(
            "economically_active", "Economically Active",
            _r(extra_row["pct_economically_active"]),
            _r(extra_parent_row["pct_economically_active"]) if extra_parent_row else None,
            "%",
        ))
    if extra_row and extra_row["pct_degree"] is not None:
        metrics.append(metric(
            "degree_educated", "Degree Educated",
            _r(extra_row["pct_degree"]),
            _r(extra_parent_row["pct_degree"]) if extra_parent_row else None,
            "%",
        ))
    if extra_row and extra_row["pct_no_car"] is not None:
        metrics.append(metric(
            "no_car", "No Car Household",
            _r(extra_row["pct_no_car"]),
            _r(extra_parent_row["pct_no_car"]) if extra_parent_row else None,
            "%",
        ))
    if extra_row and extra_row["pct_born_abroad"] is not None:
        metrics.append(metric(
            "born_abroad", "Born Abroad",
            _r(extra_row["pct_born_abroad"]),
            _r(extra_parent_row["pct_born_abroad"]) if extra_parent_row else None,
            "%",
        ))

    # --- WFH (from census commute data, consolidated into core_census_lsoa) ---
    wfh_result = await db.execute(
        text("""
            SELECT AVG(pct_wfh) as pct_wfh
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    wfh_row = wfh_result.mappings().first()

    wfh_parent = await db.execute(
        text("""
            SELECT AVG(c.pct_wfh) as avg_wfh
            FROM core_census_lsoa c
            JOIN core_lsoa_boundaries l ON l.lsoa_code = c.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    wfh_parent_row = wfh_parent.mappings().first()

    if wfh_row and wfh_row["pct_wfh"] is not None:
        metrics.append(metric(
            "wfh", "Works From Home",
            _r(wfh_row["pct_wfh"]),
            _r(wfh_parent_row["avg_wfh"]) if wfh_parent_row else None,
            "%",
        ))

    # --- Demographics Overview (grouped 8-card panel) ---
    demo_cards: dict = {}
    if demo_row:
        demo_cards["population_density"] = {
            "label": "Population Density", "value": _r(demo_row["population_density"]),
            "unit": "ppl/ha", "parent": _r(demo_parent_row["avg_density"]) if demo_parent_row else None,
        }
        demo_cards["median_age"] = {
            "label": "Median Age", "value": _r(demo_row["median_age"]),
            "unit": "yrs", "parent": _r(demo_parent_row["avg_age"]) if demo_parent_row else None,
        }
        demo_cards["pct_families"] = {
            "label": "Families", "value": _r(demo_row["pct_families"]),
            "unit": "%", "parent": _r(demo_parent_row["avg_families"]) if demo_parent_row else None,
        }
    if extra_row and extra_row["pct_good_health"] is not None:
        demo_cards["good_health"] = {
            "label": "Good Health", "value": _r(extra_row["pct_good_health"]),
            "unit": "%", "parent": _r(extra_parent_row["pct_good_health"]) if extra_parent_row else None,
        }
    if extra_row and extra_row["pct_economically_active"] is not None:
        demo_cards["employed"] = {
            "label": "Economically Active", "value": _r(extra_row["pct_economically_active"]),
            "unit": "%", "parent": _r(extra_parent_row["pct_economically_active"]) if extra_parent_row else None,
        }
    if extra_row and extra_row["pct_degree"] is not None:
        demo_cards["degree"] = {
            "label": "Degree Educated", "value": _r(extra_row["pct_degree"]),
            "unit": "%", "parent": _r(extra_parent_row["pct_degree"]) if extra_parent_row else None,
        }
    if wfh_row and wfh_row["pct_wfh"] is not None:
        demo_cards["wfh"] = {
            "label": "Works From Home", "value": _r(wfh_row["pct_wfh"]),
            "unit": "%", "parent": _r(wfh_parent_row["avg_wfh"]) if wfh_parent_row else None,
        }
    if extra_row and extra_row["pct_no_car"] is not None:
        demo_cards["no_car"] = {
            "label": "No Car", "value": _r(extra_row["pct_no_car"]),
            "unit": "%", "parent": _r(extra_parent_row["pct_no_car"]) if extra_parent_row else None,
        }
    if demo_cards:
        metrics.insert(0, metric(
            "demographics_overview", "Demographics Overview",
            _r(demo_row["total_population"]) if demo_row and demo_row["total_population"] else None,
            None, "people",
            details={"cards": demo_cards},
        ))

    # --- Housing Tenure & Type ---
    housing_local = await db.execute(
        text("""
            SELECT SUM(total_households) as total_households,
                   AVG(pct_owned) as pct_owned,
                   AVG(pct_social_rent) as pct_social_rent,
                   AVG(pct_private_rent) as pct_private_rent,
                   AVG(pct_detached) as pct_detached,
                   AVG(pct_semi) as pct_semi,
                   AVG(pct_terraced) as pct_terraced,
                   AVG(pct_flat) as pct_flat
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    housing_row = housing_local.mappings().first()

    housing_parent = await db.execute(
        text("""
            SELECT AVG(pct_owned) as avg_owned, AVG(pct_private_rent) as avg_priv_rent,
                   AVG(pct_detached) as avg_det, AVG(pct_semi) as avg_semi,
                   AVG(pct_terraced) as avg_terr, AVG(pct_flat) as avg_flat
            FROM core_census_lsoa h
            JOIN core_lsoa_boundaries l ON l.lsoa_code = h.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
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

    # --- Household Size (TS017) ---
    hh_size_local = await db.execute(
        text("""
            SELECT AVG(pct_1person) as pct_1person, AVG(pct_2person) as pct_2person,
                   AVG(pct_3_4person) as pct_3_4person, AVG(pct_5plus) as pct_5plus
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    hh_size_row = hh_size_local.mappings().first()

    hh_size_parent = await db.execute(
        text("""
            SELECT AVG(h.pct_1person) as pct_1person, AVG(h.pct_2person) as pct_2person,
                   AVG(h.pct_3_4person) as pct_3_4person, AVG(h.pct_5plus) as pct_5plus
            FROM core_census_lsoa h
            JOIN core_lsoa_boundaries l ON l.lsoa_code = h.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    hh_size_parent_row = hh_size_parent.mappings().first()

    if hh_size_row and hh_size_row["pct_1person"] is not None:
        metrics.append(metric(
            "household_size", "Household Size",
            _r(hh_size_row["pct_1person"]),
            _r(hh_size_parent_row["pct_1person"]) if hh_size_parent_row else None,
            "% single-person",
            details={
                "pct_1person": _r(hh_size_row["pct_1person"]),
                "pct_2person": _r(hh_size_row["pct_2person"]),
                "pct_3_4person": _r(hh_size_row["pct_3_4person"]),
                "pct_5plus": _r(hh_size_row["pct_5plus"]),
            },
        ))

    # --- Ethnicity (TS022, ward-level) ---
    ethnicity_local = await db.execute(
        text("""
            SELECT AVG(pct_white) as pct_white, AVG(pct_asian) as pct_asian,
                   AVG(pct_black) as pct_black, AVG(pct_mixed) as pct_mixed,
                   AVG(pct_other) as pct_other
            FROM core_census_ethnicity_ward WHERE ward_code = :ward
        """),
        {"ward": ward_code},
    )
    eth_row = ethnicity_local.mappings().first()

    ethnicity_parent = await db.execute(
        text("""
            SELECT AVG(e.pct_white) as pct_white, AVG(e.pct_asian) as pct_asian,
                   AVG(e.pct_black) as pct_black, AVG(e.pct_mixed) as pct_mixed,
                   AVG(e.pct_other) as pct_other
            FROM core_census_ethnicity_ward e
            JOIN core_ward_boundaries wb ON wb.ward_code = e.ward_code
            WHERE wb.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    eth_parent_row = ethnicity_parent.mappings().first()

    if eth_row and eth_row["pct_white"] is not None:
        metrics.append(metric(
            "ethnicity", "Ethnicity",
            _r(eth_row["pct_white"]),
            _r(eth_parent_row["pct_white"]) if eth_parent_row else None,
            "% White",
            details={
                "pct_white": _r(eth_row["pct_white"]),
                "pct_asian": _r(eth_row["pct_asian"]),
                "pct_black": _r(eth_row["pct_black"]),
                "pct_mixed": _r(eth_row["pct_mixed"]),
                "pct_other": _r(eth_row["pct_other"]),
            },
        ))

    # --- Schools (Bible: count Outstanding/Good within radius / in area) ---
    if is_area:
        # Area mode: schools within LSOA boundaries (containment-based)
        primary = await db.execute(
            text("""
                SELECT COUNT(*) FILTER (WHERE s.ofsted_rating IN ('Outstanding', 'Good')) as good_count,
                       COUNT(*) as total
                FROM core_schools s
                JOIN core_lsoa_boundaries lb ON ST_Within(s.geom, lb.geom)
                WHERE s.phase = 'Primary' AND s.is_open = TRUE
                  AND lb.lsoa_code = ANY(:codes)
            """),
            {"codes": lsoa_codes},
        )
        prim_row = primary.mappings().first()

        primary_list = await db.execute(
            text("""
                SELECT s.school_name, s.ofsted_rating, s.ks2_reading_pct, s.ks2_maths_pct
                FROM core_schools s
                JOIN core_lsoa_boundaries lb ON ST_Within(s.geom, lb.geom)
                WHERE s.phase = 'Primary' AND s.is_open = TRUE
                  AND lb.lsoa_code = ANY(:codes)
                ORDER BY s.school_name LIMIT 15
            """),
            {"codes": lsoa_codes},
        )
        prim_list = [
            {
                "name": r["school_name"],
                "ofsted": r["ofsted_rating"],
                "ks2_reading": _r(r["ks2_reading_pct"]),
                "ks2_maths": _r(r["ks2_maths_pct"]),
            }
            for r in primary_list.mappings().all()
        ]

        primary_good_count = int(prim_row["good_count"]) if prim_row and prim_row["good_count"] is not None else 0
        primary_total = int(prim_row["total"]) if prim_row and prim_row["total"] is not None else 0

        metrics.append(metric(
            "primary_schools", "Primary Schools in Area",
            primary_good_count,
            None, "Outstanding/Good count",
            details={"total_in_area": primary_total, "schools": prim_list},
        ))

        primary_quality = _r(primary_good_count / primary_total * 100) if primary_total > 0 else None
        if primary_quality is not None:
            primary_parent_quality_result = await db.execute(
                text("""
                    SELECT
                        COUNT(*) FILTER (WHERE s.ofsted_rating IN ('Outstanding', 'Good'))::float /
                        NULLIF(COUNT(*), 0) * 100 AS good_share
                    FROM core_schools s
                    JOIN core_lsoa_boundaries lb ON ST_Within(s.geom, lb.geom)
                    WHERE s.phase = 'Primary' AND s.is_open = TRUE
                      AND lb.lad_code = ANY(:parent_lads)
                """),
                {"parent_lads": parent_lads},
            )
            primary_parent_quality_row = primary_parent_quality_result.mappings().first()
            metrics.append(metric(
                "primary_school_quality",
                "Primary School Quality",
                primary_quality,
                _r(primary_parent_quality_row["good_share"]) if primary_parent_quality_row else None,
                "% Outstanding/Good",
                details={
                    "good_count": primary_good_count,
                    "total_count": primary_total,
                    "basis": "share of in-area primary schools rated Outstanding or Good",
                },
            ))

        # Secondary: within LSOA boundaries
        secondary = await db.execute(
            text("""
                SELECT COUNT(*) FILTER (WHERE s.ofsted_rating IN ('Outstanding', 'Good')) as good_count,
                       COUNT(*) as total
                FROM core_schools s
                JOIN core_lsoa_boundaries lb ON ST_Within(s.geom, lb.geom)
                WHERE s.phase = 'Secondary' AND s.is_open = TRUE
                  AND lb.lsoa_code = ANY(:codes)
            """),
            {"codes": lsoa_codes},
        )
        sec_row = secondary.mappings().first()

        secondary_list = await db.execute(
            text("""
                SELECT s.school_name, s.ofsted_rating, s.gcse_progress_8, s.gcse_attainment_8
                FROM core_schools s
                JOIN core_lsoa_boundaries lb ON ST_Within(s.geom, lb.geom)
                WHERE s.phase = 'Secondary' AND s.is_open = TRUE
                  AND lb.lsoa_code = ANY(:codes)
                ORDER BY s.school_name LIMIT 15
            """),
            {"codes": lsoa_codes},
        )
        sec_list = [
            {
                "name": r["school_name"],
                "ofsted": r["ofsted_rating"],
                "progress_8": _r(r["gcse_progress_8"]),
                "attainment_8": _r(r["gcse_attainment_8"]),
            }
            for r in secondary_list.mappings().all()
        ]

        secondary_good_count = int(sec_row["good_count"]) if sec_row and sec_row["good_count"] is not None else 0
        secondary_total = int(sec_row["total"]) if sec_row and sec_row["total"] is not None else 0

        metrics.append(metric(
            "secondary_schools", "Secondary Schools in Area",
            secondary_good_count,
            None, "Outstanding/Good count",
            details={"total_in_area": secondary_total, "schools": sec_list},
        ))

        secondary_quality = _r(secondary_good_count / secondary_total * 100) if secondary_total > 0 else None
        if secondary_quality is not None:
            secondary_parent_quality_result = await db.execute(
                text("""
                    SELECT
                        COUNT(*) FILTER (WHERE s.ofsted_rating IN ('Outstanding', 'Good'))::float /
                        NULLIF(COUNT(*), 0) * 100 AS good_share
                    FROM core_schools s
                    JOIN core_lsoa_boundaries lb ON ST_Within(s.geom, lb.geom)
                    WHERE s.phase = 'Secondary' AND s.is_open = TRUE
                      AND lb.lad_code = ANY(:parent_lads)
                """),
                {"parent_lads": parent_lads},
            )
            secondary_parent_quality_row = secondary_parent_quality_result.mappings().first()
            metrics.append(metric(
                "secondary_school_quality",
                "Secondary School Quality",
                secondary_quality,
                _r(secondary_parent_quality_row["good_share"]) if secondary_parent_quality_row else None,
                "% Outstanding/Good",
                details={
                    "good_count": secondary_good_count,
                    "total_count": secondary_total,
                    "basis": "share of in-area secondary schools rated Outstanding or Good",
                },
            ))

    elif lat is not None:
        # Postcode mode: distance-based
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

        primary_good_count = int(prim_row["good_count"]) if prim_row and prim_row["good_count"] is not None else 0
        primary_total = int(prim_row["total"]) if prim_row and prim_row["total"] is not None else 0

        metrics.append(metric(
            "primary_schools", "Primary Schools (1 mile)",
            primary_good_count,
            None, "Outstanding/Good count",
            details={"total_within_1mi": primary_total, "schools": prim_list},
        ))

        primary_quality = _r(primary_good_count / primary_total * 100) if primary_total > 0 else None
        if primary_quality is not None:
            primary_parent_quality_result = await db.execute(
                text("""
                    SELECT
                        COUNT(*) FILTER (WHERE s.ofsted_rating IN ('Outstanding', 'Good'))::float /
                        NULLIF(COUNT(*), 0) * 100 AS good_share
                    FROM core_schools s
                    JOIN core_lsoa_boundaries lb ON ST_Within(s.geom, lb.geom)
                    WHERE s.phase = 'Primary' AND s.is_open = TRUE
                      AND lb.lad_code = ANY(:parent_lads)
                """),
                {"parent_lads": parent_lads},
            )
            primary_parent_quality_row = primary_parent_quality_result.mappings().first()
            metrics.append(metric(
                "primary_school_quality",
                "Primary School Quality",
                primary_quality,
                _r(primary_parent_quality_row["good_share"]) if primary_parent_quality_row else None,
                "% Outstanding/Good",
                details={
                    "good_count": primary_good_count,
                    "total_count": primary_total,
                    "basis": "share of primary schools within 1 mile rated Outstanding or Good",
                },
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

        secondary_good_count = int(sec_row["good_count"]) if sec_row and sec_row["good_count"] is not None else 0
        secondary_total = int(sec_row["total"]) if sec_row and sec_row["total"] is not None else 0

        metrics.append(metric(
            "secondary_schools", "Secondary Schools (3 miles)",
            secondary_good_count,
            None, "Outstanding/Good count",
            details={"total_within_3mi": secondary_total, "schools": sec_list},
        ))

        secondary_quality = _r(secondary_good_count / secondary_total * 100) if secondary_total > 0 else None
        if secondary_quality is not None:
            secondary_parent_quality_result = await db.execute(
                text("""
                    SELECT
                        COUNT(*) FILTER (WHERE s.ofsted_rating IN ('Outstanding', 'Good'))::float /
                        NULLIF(COUNT(*), 0) * 100 AS good_share
                    FROM core_schools s
                    JOIN core_lsoa_boundaries lb ON ST_Within(s.geom, lb.geom)
                    WHERE s.phase = 'Secondary' AND s.is_open = TRUE
                      AND lb.lad_code = ANY(:parent_lads)
                """),
                {"parent_lads": parent_lads},
            )
            secondary_parent_quality_row = secondary_parent_quality_result.mappings().first()
            metrics.append(metric(
                "secondary_school_quality",
                "Secondary School Quality",
                secondary_quality,
                _r(secondary_parent_quality_row["good_share"]) if secondary_parent_quality_row else None,
                "% Outstanding/Good",
                details={
                    "good_count": secondary_good_count,
                    "total_count": secondary_total,
                    "basis": "share of secondary schools within 3 miles rated Outstanding or Good",
                },
            ))

    # --- IMD Deprivation ---
    imd_local = await db.execute(
        text("""
            SELECT AVG(imd_score) as imd_score,
                   AVG(imd_rank) as imd_rank,
                   ROUND(AVG(imd_decile)) as imd_decile,
                   AVG(income_score) as income_score,
                   AVG(employment_score) as employment_score,
                   AVG(education_score) as education_score,
                   AVG(health_score) as health_score,
                   AVG(crime_score) as crime_score,
                   AVG(barriers_score) as barriers_score,
                   AVG(living_env_score) as living_env_score
            FROM core_imd_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    imd_row = imd_local.mappings().first()

    imd_parent = await db.execute(
        text("""
            SELECT AVG(imd_score) as avg_score,
                   AVG(imd_decile) as avg_decile,
                   AVG(income_score) as avg_income,
                   AVG(employment_score) as avg_employment,
                   AVG(education_score) as avg_education,
                   AVG(health_score) as avg_health,
                   AVG(crime_score) as avg_crime,
                   AVG(barriers_score) as avg_barriers,
                   AVG(living_env_score) as avg_living_environment
            FROM core_imd_lsoa i
            JOIN core_lsoa_boundaries l ON l.lsoa_code = i.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
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
                "parent_avg_decile": round(float(imd_parent_row["avg_decile"]), 1) if imd_parent_row and imd_parent_row["avg_decile"] else None,
                "income": _r(imd_row["income_score"]),
                "employment": _r(imd_row["employment_score"]),
                "education": _r(imd_row["education_score"]),
                "health": _r(imd_row["health_score"]),
                "crime": _r(imd_row["crime_score"]),
                "barriers": _r(imd_row["barriers_score"]),
                "living_environment": _r(imd_row["living_env_score"]),
            },
        ))

        deprivation_domains = [
            ("deprivation_income", "Income Deprivation", "income_score", "avg_income"),
            ("deprivation_employment", "Employment Deprivation", "employment_score", "avg_employment"),
            ("deprivation_education", "Education Deprivation", "education_score", "avg_education"),
            ("deprivation_health", "Health Deprivation", "health_score", "avg_health"),
            ("deprivation_crime", "Crime Deprivation", "crime_score", "avg_crime"),
            ("deprivation_barriers", "Barriers to Housing and Services", "barriers_score", "avg_barriers"),
            ("deprivation_living_environment", "Living Environment Deprivation", "living_env_score", "avg_living_environment"),
        ]
        for metric_id, label, local_key, parent_key in deprivation_domains:
            local_value = _r(imd_row[local_key])
            parent_value = _r(imd_parent_row[parent_key]) if imd_parent_row else None
            if local_value is None:
                continue
            metrics.append(metric(
                metric_id,
                label,
                local_value,
                parent_value,
                "domain score (lower=less deprived)",
                details={
                    "domain": label,
                    "overall_imd_score": _r(imd_row["imd_score"]),
                    "overall_imd_decile": int(imd_row["imd_decile"]) if imd_row["imd_decile"] else None,
                    "parent_avg_imd_decile": round(float(imd_parent_row["avg_decile"]), 1) if imd_parent_row and imd_parent_row["avg_decile"] else None,
                },
            ))

    # --- NHS Facilities nearby / in area ---
    if is_area:
        # Area mode: NHS facilities within LSOA boundaries
        nhs_counts_result = await db.execute(
            text("""
                SELECT nf.facility_type, COUNT(*) as cnt
                FROM core_nhs_facilities nf
                JOIN core_lsoa_boundaries lb ON ST_Within(nf.geom, lb.geom)
                WHERE lb.lsoa_code = ANY(:codes)
                GROUP BY nf.facility_type
            """),
            {"codes": lsoa_codes},
        )
        nhs_counts = {r["facility_type"]: int(r["cnt"]) for r in nhs_counts_result.mappings().all()}
        total_nhs = sum(nhs_counts.values())

        nhs_list_result = await db.execute(
            text("""
                SELECT nf.name, nf.facility_type
                FROM core_nhs_facilities nf
                JOIN core_lsoa_boundaries lb ON ST_Within(nf.geom, lb.geom)
                WHERE lb.lsoa_code = ANY(:codes)
                ORDER BY nf.name LIMIT 15
            """),
            {"codes": lsoa_codes},
        )
        nhs_list = [
            {"name": r["name"], "type": r["facility_type"]}
            for r in nhs_list_result.mappings().all()
        ]

        type_summary = {t: {"count": nhs_counts.get(t, 0)} for t in nhs_counts}

        # Parent avg NHS count (from pre-computed LSOA table)
        nhs_area_parent_result = await db.execute(
            text("""
                SELECT AVG(n.nhs_count_2km) as avg_count
                FROM core_nhs_lsoa n
                JOIN core_lsoa_boundaries l ON l.lsoa_code = n.lsoa_code
                WHERE l.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        nhs_area_parent_row = nhs_area_parent_result.mappings().first()
        nhs_area_parent_avg = _r(nhs_area_parent_row["avg_count"]) if nhs_area_parent_row and nhs_area_parent_row["avg_count"] else None

        metrics.append(metric(
            "nhs_facilities", "NHS Facilities in Area",
            total_nhs, nhs_area_parent_avg, "count",
            details={
                "type_summary": type_summary,
                "facilities": nhs_list,
            } if (nhs_counts or nhs_list) else None,
        ))

    elif lat is not None:
        # Postcode mode: distance-based
        # Counts by type within 2km
        nhs_counts_result = await db.execute(
            text("""
                SELECT facility_type, COUNT(*) as cnt
                FROM core_nhs_facilities
                WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 2000)
                GROUP BY facility_type
            """),
            {"lat": lat, "lon": lon},
        )
        nhs_counts = {r["facility_type"]: int(r["cnt"]) for r in nhs_counts_result.mappings().all()}
        total_nhs = sum(nhs_counts.values())

        # Parent comparison: precomputed counts per LSOA (no spatial work at query time)
        nhs_parent_result = await db.execute(
            text("""
                SELECT AVG(n.nhs_count_2km) as avg_count
                FROM core_nhs_lsoa n
                JOIN core_lsoa_boundaries l ON l.lsoa_code = n.lsoa_code
                WHERE l.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        nhs_parent_row = nhs_parent_result.mappings().first()
        nhs_parent_avg = _r(nhs_parent_row["avg_count"]) if nhs_parent_row and nhs_parent_row["avg_count"] else None

        # Nearest facilities list (all types, up to 10)
        nhs_list_result = await db.execute(
            text("""
                SELECT name, facility_type,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)::int as distance_m
                FROM core_nhs_facilities
                WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 2000)
                ORDER BY distance_m
                LIMIT 10
            """),
            {"lat": lat, "lon": lon},
        )
        nhs_list = [
            {"name": r["name"], "type": r["facility_type"], "distance_m": int(r["distance_m"])}
            for r in nhs_list_result.mappings().all()
        ]

        # Per-type nearest distance
        nearest_by_type: dict = {}
        for item in nhs_list:
            t = item["type"]
            if t not in nearest_by_type:
                nearest_by_type[t] = item["distance_m"]

        # Build type_summary: {type: {count, nearest_m}}
        type_summary = {
            t: {"count": nhs_counts.get(t, 0), "nearest_m": nearest_by_type.get(t)}
            for t in nhs_counts
        }

        metrics.append(metric(
            "nhs_facilities", "NHS Facilities (2km)",
            total_nhs, nhs_parent_avg, "count",
            details={
                "type_summary": type_summary,
                "facilities": nhs_list,
            } if (nhs_counts or nhs_list) else None,
        ))

    return metrics


def _r(val):
    if val is None:
        return None
    return round(float(val), 2)
