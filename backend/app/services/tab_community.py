"""Tab 4: Community & Education — Bible Part 4, Tab 4.
Queries: core_census_lsoa (consolidated), core_census_ethnicity_ward, core_census_religion_ward,
         Hetzner School API, core_imd_lsoa, core_nhs_facilities.
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
                   SUM(total_population * population_density) / NULLIF(SUM(total_population), 0) as population_density,
                   SUM(total_population * median_age) / NULLIF(SUM(total_population), 0) as median_age,
                   SUM(total_population * pct_age_0_15) / NULLIF(SUM(total_population), 0) as pct_age_0_15,
                   SUM(total_population * pct_age_16_64) / NULLIF(SUM(total_population), 0) as pct_age_16_64,
                   SUM(total_population * pct_age_65_plus) / NULLIF(SUM(total_population), 0) as pct_age_65_plus,
                   SUM(total_households * pct_families) / NULLIF(SUM(total_households), 0) as pct_families,
                   SUM(total_households * pct_singles) / NULLIF(SUM(total_households), 0) as pct_singles,
                   SUM(total_households * pct_sharers) / NULLIF(SUM(total_households), 0) as pct_sharers
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    demo_row = demo_local.mappings().first()

    # Parent averages (parent comparison group — e.g. all London boroughs)
    demo_parent = await db.execute(
        text("""
            SELECT SUM(d.total_population * d.population_density) / NULLIF(SUM(d.total_population), 0) as avg_density,
                   SUM(d.total_population * d.median_age) / NULLIF(SUM(d.total_population), 0) as avg_age,
                   SUM(d.total_households * d.pct_families) / NULLIF(SUM(d.total_households), 0) as avg_families,
                   SUM(d.total_households * d.pct_singles) / NULLIF(SUM(d.total_households), 0) as avg_singles,
                   SUM(d.total_households * d.pct_sharers) / NULLIF(SUM(d.total_households), 0) as avg_sharers,
                   SUM(d.total_population * d.pct_age_0_15) / NULLIF(SUM(d.total_population), 0) as avg_0_15,
                   SUM(d.total_population * d.pct_age_16_64) / NULLIF(SUM(d.total_population), 0) as avg_16_64,
                   SUM(d.total_population * d.pct_age_65_plus) / NULLIF(SUM(d.total_population), 0) as avg_65plus,
                   SUM(d.total_population) as total_population
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
                "0–15 years": _r(demo_row["pct_age_0_15"]),
                "16–64 years": _r(demo_row["pct_age_16_64"]),
                "65+ years": _r(demo_row["pct_age_65_plus"]),
                "detail_unit": "%",
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
            SELECT SUM(total_population * pct_good_health) / NULLIF(SUM(total_population), 0) as pct_good_health,
                   SUM(total_population * pct_economically_active) / NULLIF(SUM(total_population), 0) as pct_economically_active,
                   SUM(total_population * pct_degree) / NULLIF(SUM(total_population), 0) as pct_degree,
                   SUM(total_households * pct_no_car) / NULLIF(SUM(total_households), 0) as pct_no_car,
                   SUM(total_population * pct_born_abroad) / NULLIF(SUM(total_population), 0) as pct_born_abroad
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    extra_row = extra_result.mappings().first()

    extra_parent = await db.execute(
        text("""
            SELECT SUM(e.total_population * e.pct_good_health) / NULLIF(SUM(e.total_population), 0) as pct_good_health,
                   SUM(e.total_population * e.pct_economically_active) / NULLIF(SUM(e.total_population), 0) as pct_economically_active,
                   SUM(e.total_population * e.pct_degree) / NULLIF(SUM(e.total_population), 0) as pct_degree,
                   SUM(e.total_households * e.pct_no_car) / NULLIF(SUM(e.total_households), 0) as pct_no_car,
                   SUM(e.total_population * e.pct_born_abroad) / NULLIF(SUM(e.total_population), 0) as pct_born_abroad
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
    if extra_row and extra_row["pct_no_car"] is not None:
        demo_cards["no_car"] = {
            "label": "No Car", "value": _r(extra_row["pct_no_car"]),
            "unit": "%", "parent": _r(extra_parent_row["pct_no_car"]) if extra_parent_row else None,
        }
    if demo_cards:
        parent_pop = _r(demo_parent_row["total_population"]) if demo_parent_row and demo_parent_row["total_population"] else None
        metrics.insert(0, metric(
            "demographics_overview", "Demographics Overview",
            _r(demo_row["total_population"]) if demo_row and demo_row["total_population"] else None,
            parent_pop, "people",
            details={"cards": demo_cards},
        ))

    # --- Household Size (TS017) ---
    hh_size_local = await db.execute(
        text("""
            SELECT SUM(total_households * pct_1person) / NULLIF(SUM(total_households), 0) as pct_1person,
                   SUM(total_households * pct_2person) / NULLIF(SUM(total_households), 0) as pct_2person,
                   SUM(total_households * pct_3_4person) / NULLIF(SUM(total_households), 0) as pct_3_4person,
                   SUM(total_households * pct_5plus) / NULLIF(SUM(total_households), 0) as pct_5plus
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    hh_size_row = hh_size_local.mappings().first()

    hh_size_parent = await db.execute(
        text("""
            SELECT SUM(h.total_households * h.pct_1person) / NULLIF(SUM(h.total_households), 0) as pct_1person,
                   SUM(h.total_households * h.pct_2person) / NULLIF(SUM(h.total_households), 0) as pct_2person,
                   SUM(h.total_households * h.pct_3_4person) / NULLIF(SUM(h.total_households), 0) as pct_3_4person,
                   SUM(h.total_households * h.pct_5plus) / NULLIF(SUM(h.total_households), 0) as pct_5plus
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
                "1 person": _r(hh_size_row["pct_1person"]),
                "2 people": _r(hh_size_row["pct_2person"]),
                "3–4 people": _r(hh_size_row["pct_3_4person"]),
                "5+ people": _r(hh_size_row["pct_5plus"]),
                "detail_unit": "%",
            },
        ))

    # --- Ward codes for LSOA-based searches (reused by ethnicity + religion) ---
    # Derive once, use twice — avoids redundant core_postcodes scans.
    _derived_ward_codes: list[str] | None = None
    if not (ward_code and ward_code != "_") and lsoa_codes and len(lsoa_codes) > 0:
        _ward_rows = await db.execute(
            text("""
                SELECT DISTINCT p.ward_code FROM core_postcodes p
                WHERE p.lsoa_code = ANY(:codes) AND p.ward_code IS NOT NULL
            """),
            {"codes": lsoa_codes},
        )
        _derived_ward_codes = [r[0] for r in _ward_rows.all()]

    # --- Ethnicity (TS022, ward-level) ---
    # For postcode/ward: use single ward. For place/LAD/county: derive wards from
    # the session's LSOA set so that place searches reflect the actual area's
    # ethnic profile, not the entire LAD average.
    if ward_code and ward_code != "_":
        ethnicity_local = await db.execute(
            text("""
                SELECT AVG(pct_white) as pct_white, AVG(pct_asian) as pct_asian,
                       AVG(pct_black) as pct_black, AVG(pct_mixed) as pct_mixed,
                       AVG(pct_other) as pct_other
                FROM core_census_ethnicity_ward WHERE ward_code = :ward
            """),
            {"ward": ward_code},
        )
    elif _derived_ward_codes:
        ethnicity_local = await db.execute(
            text("""
                SELECT SUM(e.total_pop * e.pct_white) / NULLIF(SUM(e.total_pop), 0) as pct_white,
                       SUM(e.total_pop * e.pct_asian) / NULLIF(SUM(e.total_pop), 0) as pct_asian,
                       SUM(e.total_pop * e.pct_black) / NULLIF(SUM(e.total_pop), 0) as pct_black,
                       SUM(e.total_pop * e.pct_mixed) / NULLIF(SUM(e.total_pop), 0) as pct_mixed,
                       SUM(e.total_pop * e.pct_other) / NULLIF(SUM(e.total_pop), 0) as pct_other
                FROM core_census_ethnicity_ward e
                WHERE e.ward_code = ANY(:ward_codes)
            """),
            {"ward_codes": _derived_ward_codes},
        )
    else:
        # Fallback: average across all wards in the LAD
        ethnicity_local = await db.execute(
            text("""
                SELECT SUM(e.total_pop * e.pct_white) / NULLIF(SUM(e.total_pop), 0) as pct_white,
                       SUM(e.total_pop * e.pct_asian) / NULLIF(SUM(e.total_pop), 0) as pct_asian,
                       SUM(e.total_pop * e.pct_black) / NULLIF(SUM(e.total_pop), 0) as pct_black,
                       SUM(e.total_pop * e.pct_mixed) / NULLIF(SUM(e.total_pop), 0) as pct_mixed,
                       SUM(e.total_pop * e.pct_other) / NULLIF(SUM(e.total_pop), 0) as pct_other
                FROM core_census_ethnicity_ward e
                JOIN core_ward_boundaries wb ON wb.ward_code = e.ward_code
                WHERE wb.lad_code = ANY(:local_lads)
            """),
            {"local_lads": local_lads or [lad_code]},
        )
    eth_row = ethnicity_local.mappings().first()

    ethnicity_parent = await db.execute(
        text("""
            SELECT SUM(e.total_pop * e.pct_white) / NULLIF(SUM(e.total_pop), 0) as pct_white,
                   SUM(e.total_pop * e.pct_asian) / NULLIF(SUM(e.total_pop), 0) as pct_asian,
                   SUM(e.total_pop * e.pct_black) / NULLIF(SUM(e.total_pop), 0) as pct_black,
                   SUM(e.total_pop * e.pct_mixed) / NULLIF(SUM(e.total_pop), 0) as pct_mixed,
                   SUM(e.total_pop * e.pct_other) / NULLIF(SUM(e.total_pop), 0) as pct_other
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

    # --- Religion (Census 2021 TS031, ward-level) ---
    # Same ward-derivation strategy as ethnicity.
    if ward_code and ward_code != "_":
        religion_local = await db.execute(
            text("""
                SELECT AVG(pct_christian) as pct_christian, AVG(pct_muslim) as pct_muslim,
                       AVG(pct_hindu) as pct_hindu, AVG(pct_sikh) as pct_sikh,
                       AVG(pct_jewish) as pct_jewish, AVG(pct_buddhist) as pct_buddhist,
                       AVG(pct_no_religion) as pct_no_religion, AVG(pct_other) as pct_other
                FROM core_census_religion_ward WHERE ward_code = :ward
            """),
            {"ward": ward_code},
        )
    elif _derived_ward_codes:
        religion_local = await db.execute(
            text("""
                SELECT SUM(r.total_pop * r.pct_christian) / NULLIF(SUM(r.total_pop), 0) as pct_christian,
                       SUM(r.total_pop * r.pct_muslim) / NULLIF(SUM(r.total_pop), 0) as pct_muslim,
                       SUM(r.total_pop * r.pct_hindu) / NULLIF(SUM(r.total_pop), 0) as pct_hindu,
                       SUM(r.total_pop * r.pct_sikh) / NULLIF(SUM(r.total_pop), 0) as pct_sikh,
                       SUM(r.total_pop * r.pct_jewish) / NULLIF(SUM(r.total_pop), 0) as pct_jewish,
                       SUM(r.total_pop * r.pct_buddhist) / NULLIF(SUM(r.total_pop), 0) as pct_buddhist,
                       SUM(r.total_pop * r.pct_no_religion) / NULLIF(SUM(r.total_pop), 0) as pct_no_religion,
                       SUM(r.total_pop * r.pct_other) / NULLIF(SUM(r.total_pop), 0) as pct_other
                FROM core_census_religion_ward r
                WHERE r.ward_code = ANY(:ward_codes)
            """),
            {"ward_codes": _derived_ward_codes},
        )
    else:
        religion_local = await db.execute(
            text("""
                SELECT SUM(r.total_pop * r.pct_christian) / NULLIF(SUM(r.total_pop), 0) as pct_christian,
                       SUM(r.total_pop * r.pct_muslim) / NULLIF(SUM(r.total_pop), 0) as pct_muslim,
                       SUM(r.total_pop * r.pct_hindu) / NULLIF(SUM(r.total_pop), 0) as pct_hindu,
                       SUM(r.total_pop * r.pct_sikh) / NULLIF(SUM(r.total_pop), 0) as pct_sikh,
                       SUM(r.total_pop * r.pct_jewish) / NULLIF(SUM(r.total_pop), 0) as pct_jewish,
                       SUM(r.total_pop * r.pct_buddhist) / NULLIF(SUM(r.total_pop), 0) as pct_buddhist,
                       SUM(r.total_pop * r.pct_no_religion) / NULLIF(SUM(r.total_pop), 0) as pct_no_religion,
                       SUM(r.total_pop * r.pct_other) / NULLIF(SUM(r.total_pop), 0) as pct_other
                FROM core_census_religion_ward r
                JOIN core_ward_boundaries wb ON wb.ward_code = r.ward_code
                WHERE wb.lad_code = ANY(:local_lads)
            """),
            {"local_lads": local_lads or [lad_code]},
        )
    rel_row = religion_local.mappings().first()

    religion_parent = await db.execute(
        text("""
            SELECT SUM(r.total_pop * r.pct_christian) / NULLIF(SUM(r.total_pop), 0) as pct_christian,
                   SUM(r.total_pop * r.pct_muslim) / NULLIF(SUM(r.total_pop), 0) as pct_muslim,
                   SUM(r.total_pop * r.pct_hindu) / NULLIF(SUM(r.total_pop), 0) as pct_hindu,
                   SUM(r.total_pop * r.pct_sikh) / NULLIF(SUM(r.total_pop), 0) as pct_sikh,
                   SUM(r.total_pop * r.pct_jewish) / NULLIF(SUM(r.total_pop), 0) as pct_jewish,
                   SUM(r.total_pop * r.pct_buddhist) / NULLIF(SUM(r.total_pop), 0) as pct_buddhist,
                   SUM(r.total_pop * r.pct_no_religion) / NULLIF(SUM(r.total_pop), 0) as pct_no_religion,
                   SUM(r.total_pop * r.pct_other) / NULLIF(SUM(r.total_pop), 0) as pct_other
            FROM core_census_religion_ward r
            JOIN core_ward_boundaries wb ON wb.ward_code = r.ward_code
            WHERE wb.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    rel_parent_row = religion_parent.mappings().first()

    if rel_row and rel_row["pct_christian"] is not None:
        # Find dominant religion for headline
        _religion_map = {
            "Christian": _r(rel_row["pct_christian"]),
            "Muslim": _r(rel_row["pct_muslim"]),
            "Hindu": _r(rel_row["pct_hindu"]),
            "Sikh": _r(rel_row["pct_sikh"]),
            "Jewish": _r(rel_row["pct_jewish"]),
            "Buddhist": _r(rel_row["pct_buddhist"]),
            "No religion": _r(rel_row["pct_no_religion"]),
        }
        _valid_religions = [(name, val) for name, val in _religion_map.items() if val is not None]
        if not _valid_religions:
            _dominant_name, _dominant_val = "Christian", 0.0
        else:
            _dominant_name, _dominant_val = max(_valid_religions, key=lambda x: x[1])
        _parent_key_map = {
            "Christian": "pct_christian", "Muslim": "pct_muslim",
            "Hindu": "pct_hindu", "Sikh": "pct_sikh",
            "Jewish": "pct_jewish", "Buddhist": "pct_buddhist",
            "No religion": "pct_no_religion",
        }
        _parent_val = _r(rel_parent_row[_parent_key_map[_dominant_name]]) if rel_parent_row else None

        metrics.append(metric(
            "religion", "Religion",
            _dominant_val,
            _parent_val,
            f"% {_dominant_name}",
            details={
                "Christian": _r(rel_row["pct_christian"]),
                "Muslim": _r(rel_row["pct_muslim"]),
                "Hindu": _r(rel_row["pct_hindu"]),
                "Sikh": _r(rel_row["pct_sikh"]),
                "Jewish": _r(rel_row["pct_jewish"]),
                "Buddhist": _r(rel_row["pct_buddhist"]),
                "No religion": _r(rel_row["pct_no_religion"]),
                "Other": _r(rel_row["pct_other"]),
                "detail_unit": "%",
            },
        ))

    # --- Schools (from Hetzner School API) ---
    try:
        from etl_lib import schools_api
    except ImportError:
        schools_api = None

    if schools_api and lat is not None:
        # Fetch all nearby schools from Hetzner API (all phases combined)
        if is_area:
            # For area mode, use lad_codes (more efficient than LSOA→postcode join)
            area_lads = local_lads if local_lads else ([lad_code] if lad_code else [])
            schools_data = schools_api.schools_by_lsoa(lad_codes=area_lads, lat=lat, lon=lon, limit=100)
        else:
            schools_data = schools_api.nearby_schools(lat, lon, radius_m=5000, limit=100)

        # Also get quality summary
        if is_area and lad_code:
            summary_data = schools_api.quality_summary(lad_code=lad_code)
        else:
            summary_data = schools_api.quality_summary(lat=lat, lon=lon, radius_m=5000)

        all_schools = (schools_data or {}).get("schools", [])
        summary = summary_data or {}

        # Split by phase for metrics
        for phase_key, phase_label, radius_label in [
            ("Primary", "Primary Schools", "(1 mile)" if not is_area else ""),
            ("Secondary", "Secondary Schools", "(3 miles)" if not is_area else ""),
        ]:
            phase_schools = [s for s in all_schools if s.get("phase") == phase_key]
            phase_total = len(phase_schools)
            phase_good = sum(1 for s in phase_schools if s.get("ofsted_rating") in (1, 2))

            phase_quality = _r(phase_good / phase_total * 100) if phase_total > 0 else None

            school_list = [
                {
                    "name": s.get("name", ""),
                    "ofsted": {1: "Outstanding", 2: "Good", 3: "Requires Improvement", 4: "Inadequate"}.get(s.get("ofsted_rating"), "Not inspected"),
                    "distance_m": s.get("distance_m"),
                    "urn": s.get("urn"),
                }
                for s in phase_schools[:15]
            ]

            label = f"{phase_label} {radius_label}".strip()
            metrics.append(metric(
                f"{phase_key.lower()}_schools", label,
                phase_total,
                None, "schools",
                details={
                    "total_in_area": phase_total,
                    "good_count": phase_good,
                    "quality_pct": phase_quality,
                    "schools": school_list,
                    "all_schools": phase_schools,
                    "summary": summary,
                },
            ))

    # --- Outstanding schools within walking distance (postcode only) ---
    if schools_api and lat is not None and not is_area:
        walk_nearby = schools_api.nearby_schools(lat, lon, radius_m=1500, limit=50)
        walk_schools = (walk_nearby or {}).get("schools", [])
        outstanding = [s for s in walk_schools if s.get("ofsted_rating") == 1]
        metrics.append(metric(
            "outstanding_schools_walk", "Outstanding Schools (walkable)",
            len(outstanding),
            None, "schools",
            details={
                "schools": [
                    {
                        "name": s.get("name"),
                        "phase": s.get("phase"),
                        "distance_m": s.get("distance_m"),
                        "urn": s.get("urn"),
                    }
                    for s in outstanding
                ],
                "search_radius_m": 1500,
                "context_note": "Ofsted 'Outstanding' schools within ~15 minute walk (1.5 km radius).",
            },
        ))

    # --- Nurseries & Childcare (from Hetzner School API) ---
    if schools_api and lat is not None:
        nurseries_data = schools_api.nearby_nurseries(lat, lon, radius_m=2000, limit=50)
        nurs_summary = schools_api.nursery_summary(lat=lat, lon=lon, radius_m=2000)

        all_nurseries = (nurseries_data or {}).get("nurseries", [])
        nurs_total = len(all_nurseries)
        nurs_good = sum(1 for n in all_nurseries if n.get("ofsted_rating") in ("Outstanding", "Good"))

        if nurs_total > 0:
            metrics.append(metric(
                "nurseries", "Nurseries & Childcare",
                nurs_total,
                None, "providers",
                details={
                    "total_providers": nurs_total,
                    "good_count": nurs_good,
                    "quality_pct": _r(nurs_good / nurs_total * 100) if nurs_total > 0 else None,
                    "nurseries": all_nurseries,
                    "nursery_summary": nurs_summary,
                },
            ))

    # --- SEND / SEN2 LA-level EHCP statistics ---
    if schools_api and lad_code:
        sen2 = schools_api.sen2_la_stats(lad_code)
        if sen2 and sen2.get("total_ehcps"):
            pct_20wk = sen2.get("pct_within_20wk")
            nat_20wk = sen2.get("nat_pct_within_20wk")
            pct_refused = sen2.get("pct_refused")
            nat_refused = sen2.get("nat_pct_refused")

            # Headline: timeliness gauge
            headline_val = pct_20wk
            headline_label = "EHCP Timeliness"
            if pct_20wk is not None and nat_20wk is not None:
                if pct_20wk >= nat_20wk + 10:
                    quality = "good"
                elif pct_20wk <= nat_20wk - 10:
                    quality = "poor"
                else:
                    quality = "average"
            else:
                quality = None

            metrics.append(metric(
                "sen2_ehcp", "SEND — EHCP Assessment",
                headline_val,
                nat_20wk, "%",
                details={
                    "la_name": sen2.get("la_name"),
                    "year": sen2.get("year"),
                    "quality": quality,
                    # Timeliness
                    "pct_within_20wk": pct_20wk,
                    "nat_pct_within_20wk": nat_20wk,
                    "plans_issued_total": sen2.get("plans_issued_total"),
                    "plans_issued_within_20wk": sen2.get("plans_issued_within_20wk"),
                    "plans_issued_20wk_to_1yr": sen2.get("plans_issued_20wk_to_1yr"),
                    "plans_issued_over_1yr": sen2.get("plans_issued_over_1yr"),
                    # Refusal rate
                    "requests_received": sen2.get("requests_received"),
                    "requests_refused": sen2.get("requests_refused"),
                    "pct_refused": pct_refused,
                    "nat_pct_refused": nat_refused,
                    # Tribunal
                    "tribunal_on_request": sen2.get("tribunal_on_request"),
                    "tribunal_on_assessment": sen2.get("tribunal_on_assessment"),
                    "tribunal_other": sen2.get("tribunal_other"),
                    "mediation_on_request": sen2.get("mediation_on_request"),
                    # Assessment outcomes
                    "pct_plan_issued": sen2.get("pct_plan_issued"),
                    "nat_pct_plan_issued": sen2.get("nat_pct_plan_issued"),
                    # Caseload
                    "total_ehcps": sen2.get("total_ehcps"),
                    "mainstream_pct": sen2.get("mainstream_pct"),
                    "special_pct": sen2.get("special_pct"),
                    "nat_mainstream_pct": sen2.get("nat_mainstream_pct"),
                    "nat_special_pct": sen2.get("nat_special_pct"),
                    # Primary need breakdown
                    "need_asd_pct": sen2.get("need_asd_pct"),
                    "need_slcn_pct": sen2.get("need_slcn_pct"),
                    "need_semh_pct": sen2.get("need_semh_pct"),
                    "need_mld_pct": sen2.get("need_mld_pct"),
                    "need_sld_pct": sen2.get("need_sld_pct"),
                    "need_pmld_pct": sen2.get("need_pmld_pct"),
                    "need_spld_pct": sen2.get("need_spld_pct"),
                    "need_pd_pct": sen2.get("need_pd_pct"),
                    "need_hi_pct": sen2.get("need_hi_pct"),
                    "need_vi_pct": sen2.get("need_vi_pct"),
                    "nat_need_asd_pct": sen2.get("nat_need_asd_pct"),
                    "nat_need_slcn_pct": sen2.get("nat_need_slcn_pct"),
                    "nat_need_semh_pct": sen2.get("nat_need_semh_pct"),
                    "detail_unit": "%",
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
            SELECT SUM(i.imd_score * c.total_population) / NULLIF(SUM(c.total_population), 0) as avg_score,
                   SUM(i.imd_decile * c.total_population) / NULLIF(SUM(c.total_population), 0) as avg_decile,
                   SUM(i.income_score * c.total_population) / NULLIF(SUM(c.total_population), 0) as avg_income,
                   SUM(i.employment_score * c.total_population) / NULLIF(SUM(c.total_population), 0) as avg_employment,
                   SUM(i.education_score * c.total_population) / NULLIF(SUM(c.total_population), 0) as avg_education,
                   SUM(i.health_score * c.total_population) / NULLIF(SUM(c.total_population), 0) as avg_health,
                   SUM(i.crime_score * c.total_population) / NULLIF(SUM(c.total_population), 0) as avg_crime,
                   SUM(i.barriers_score * c.total_population) / NULLIF(SUM(c.total_population), 0) as avg_barriers,
                   SUM(i.living_env_score * c.total_population) / NULLIF(SUM(c.total_population), 0) as avg_living_environment
            FROM core_imd_lsoa i
            JOIN core_lsoa_boundaries l ON l.lsoa_code = i.lsoa_code
            LEFT JOIN core_census_lsoa c ON c.lsoa_code = i.lsoa_code
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
                JOIN core_postcodes p ON p.postcode_compact = REPLACE(nf.postcode, ' ', '')
                WHERE p.lsoa_code = ANY(:codes)
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
                JOIN core_postcodes p ON p.postcode_compact = REPLACE(nf.postcode, ' ', '')
                WHERE p.lsoa_code = ANY(:codes)
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
                SELECT SUM(n.nhs_count_2km * c.total_population) / NULLIF(SUM(c.total_population), 0) as avg_count
                FROM core_nhs_lsoa n
                JOIN core_lsoa_boundaries l ON l.lsoa_code = n.lsoa_code
                JOIN core_census_lsoa c ON c.lsoa_code = n.lsoa_code
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
                SELECT SUM(n.nhs_count_2km * c.total_population) / NULLIF(SUM(c.total_population), 0) as avg_count
                FROM core_nhs_lsoa n
                JOIN core_lsoa_boundaries l ON l.lsoa_code = n.lsoa_code
                JOIN core_census_lsoa c ON c.lsoa_code = n.lsoa_code
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

    # ------------------------------------------------------------------
    # Median Annual Earnings (ONS ASHE — LAD level)
    # ------------------------------------------------------------------
    earn_result = await db.execute(
        text("SELECT SUM(e.median_annual_earnings * p.total_pop) / NULLIF(SUM(p.total_pop), 0) AS median_annual_earnings FROM core_earnings_lad e LEFT JOIN mv_lad_population p ON p.lad_code = e.lad_code WHERE e.lad_code = ANY(:lads)"),
        {"lads": local_lads},
    )
    earn_row = earn_result.mappings().first()
    earn_parent_result = await db.execute(
        text("SELECT SUM(e.median_annual_earnings * p.total_pop) / NULLIF(SUM(p.total_pop), 0) AS avg_earn FROM core_earnings_lad e LEFT JOIN mv_lad_population p ON p.lad_code = e.lad_code WHERE e.lad_code = ANY(:lads)"),
        {"lads": parent_lads},
    )
    earn_parent_row = earn_parent_result.mappings().first()
    if earn_row and earn_row["median_annual_earnings"]:
        parent_earn_val = round(float(earn_parent_row["avg_earn"])) if earn_parent_row and earn_parent_row["avg_earn"] else None
        metrics.append(
            metric(
                "median_earnings",
                "Median Annual Earnings",
                round(float(earn_row["median_annual_earnings"])),
                parent_earn_val,
                "GBP/year",
                details={
                    "data_note": "Source: ONS ASHE. Residence-based annual earnings are only published at local-authority level, so sub-LAD searches inherit the relevant LAD value.",
                },
            )
        )

    return metrics


def _r(val):
    if val is None:
        return None
    return round(float(val), 2)
