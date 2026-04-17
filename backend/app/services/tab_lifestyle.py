"""Tab 2: Lifestyle & Connectivity — Bible Part 4, Tab 2.
Queries: core_osm_amenities, core_transport_stops, core_ev_chargers, core_broadband_postcode.
Spatial queries use area centroid. Bible Rule 4: multi-LSOA aggregation for non-postcode searches."""
from sqlalchemy import text
from app.constants import TABLE_NAMES
from app.services.helpers import metric


# Bible Section 3.1: exact OSM amenity types
AMENITY_TYPES = [
    "supermarket", "cafe", "restaurant", "pub", "gym",
    "park", "pharmacy", "dentist", "hospital", "doctors",
]


async def fetch_lifestyle_connectivity(db, *, lad_code, ward_code, lsoa_codes, centroid_lat, centroid_lon, search_mode="postcode", local_lads=None, parent_lads=None, parent_name="England", boundary_source="lad"):
    metrics = []
    lat, lon = centroid_lat, centroid_lon
    if lat is None and search_mode == "postcode":
        return metrics
    if parent_lads is None:
        parent_lads = []
    is_area = search_mode == "area"

    # local_lads is passed from session via area endpoint
    if local_lads is None:
        local_lads = [lad_code] if lad_code and lad_code != "_" else []

    # --- 15-Minute Neighbourhood ---
    if is_area:
        # Area mode: count amenities within boundary (LSOA union)
        amenity_counts = await db.execute(
            text("""
                SELECT a.amenity_type, COUNT(*) as cnt
                FROM core_osm_amenities a
                JOIN core_lsoa_boundaries lb ON ST_Within(a.geom, lb.geom)
                WHERE lb.lsoa_code = ANY(:codes)
                GROUP BY a.amenity_type
            """),
            {"codes": lsoa_codes},
        )
    else:
        amenity_counts = await db.execute(
            text("""
                SELECT amenity_type, COUNT(*) as cnt
                FROM core_osm_amenities
                WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1000)
                GROUP BY amenity_type
            """),
            {"lat": lat, "lon": lon},
        )
    local_amenities = {r["amenity_type"]: int(r["cnt"]) for r in amenity_counts.mappings().all()}
    total_local = sum(local_amenities.values())

    # Nearest amenity of each type
    if is_area:
        # Area mode: list amenities within boundary, no distance
        amenity_list_result = await db.execute(
            text("""
                SELECT DISTINCT ON (a.amenity_type) a.amenity_type, a.name
                FROM core_osm_amenities a
                JOIN core_lsoa_boundaries lb ON ST_Within(a.geom, lb.geom)
                WHERE lb.lsoa_code = ANY(:codes)
                  AND a.amenity_type = ANY(:types)
                ORDER BY a.amenity_type, a.name
            """),
            {"codes": lsoa_codes, "types": AMENITY_TYPES},
        )
    else:
        amenity_list_result = await db.execute(
            text("""
                SELECT DISTINCT ON (amenity_type) amenity_type, name,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)::int AS distance_m
                FROM core_osm_amenities
                WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1500)
                  AND amenity_type = ANY(:types)
                ORDER BY amenity_type, ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)
            """),
            {"lat": lat, "lon": lon, "types": AMENITY_TYPES},
        )
    if is_area:
        amenity_nearest = [
            {"type": r["amenity_type"], "name": r["name"]}
            for r in amenity_list_result.mappings().all()
        ]
    else:
        amenity_nearest = [
            {"type": r["amenity_type"], "name": r["name"], "distance_m": int(r["distance_m"])}
            for r in amenity_list_result.mappings().all()
        ]

    # Parent average: count amenities within parent comparison group / number of LSOAs
    parent_avg_result = await db.execute(
        text("""
            SELECT COUNT(a.id)::float / NULLIF((SELECT COUNT(*) FROM core_lsoa_boundaries WHERE lad_code = ANY(:parent_lads)), 0) as avg_count
            FROM core_osm_amenities a
            JOIN core_lad_boundaries l ON ST_Intersects(a.geom, l.geom)
            WHERE l.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    parent_amenity_row = parent_avg_result.mappings().first()
    parent_amenity_avg = round(float(parent_amenity_row["avg_count"]), 1) if parent_amenity_row and parent_amenity_row["avg_count"] else None

    amenity_label = "Amenities in Area" if is_area else "15-Minute Amenities (1km)"
    metrics.append(metric(
        "amenities_15min", amenity_label,
        total_local, parent_amenity_avg, "count",
        details={"counts": local_amenities, "nearest": amenity_nearest} if local_amenities else None,
    ))

    # --- Transport & Commuting ---
    # Parent average nearest station (pre-computed in core_lsoa_transport)
    parent_station_m = None
    if parent_lads:
        parent_station_res = await db.execute(
            text("""
                SELECT AVG(t.nearest_station_m) AS avg_station_m
                FROM core_lsoa_transport t
                JOIN core_lsoa_boundaries l ON l.lsoa_code = t.lsoa_code
                WHERE l.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        ps_row = parent_station_res.mappings().first()
        parent_station_m = round(float(ps_row["avg_station_m"])) if ps_row and ps_row["avg_station_m"] else None

    if is_area:
        # Area mode: stations within boundary
        rail_result = await db.execute(
            text("""
                SELECT DISTINCT ON (base_name)
                       REGEXP_REPLACE(t.stop_name,
                           ' (Rail Station|Underground Station|DLR Station|Overground Station|Tram Stop|Station)$',
                           '', 'i') AS base_name,
                       t.stop_name, t.stop_type
                FROM core_transport_stops t
                JOIN core_lsoa_boundaries lb ON ST_Within(t.geom, lb.geom)
                WHERE t.stop_type IN ('RSE', 'RLY', 'MET', 'TMU')
                  AND lb.lsoa_code = ANY(:codes)
                ORDER BY base_name, t.stop_name LIMIT 15
            """),
            {"codes": lsoa_codes},
        )
        rail_rows = rail_result.mappings().all()

        mode_result = await db.execute(
            text("""
                SELECT
                  COUNT(*) FILTER (WHERE t.stop_type IN ('BCT','BCS','BCE','BCQ','BST','FBT')) AS bus_count,
                  COUNT(*) FILTER (WHERE t.stop_type IN ('RLY','RSE','RPL'))                  AS rail_count,
                  COUNT(*) FILTER (WHERE t.stop_type IN ('MET','PLT'))                        AS metro_count,
                  COUNT(*) FILTER (WHERE t.stop_type IN ('TMU','STR'))                        AS tram_count,
                  COUNT(*) FILTER (WHERE t.stop_type IN ('FER','FTD'))                        AS ferry_count
                FROM core_transport_stops t
                JOIN core_lsoa_boundaries lb ON ST_Within(t.geom, lb.geom)
                WHERE lb.lsoa_code = ANY(:codes)
            """),
            {"codes": lsoa_codes},
        )
        mode_row = mode_result.mappings().first()
    else:
        rail_result = await db.execute(
            text("""
                SELECT DISTINCT ON (base_name)
                       REGEXP_REPLACE(stop_name,
                           ' (Rail Station|Underground Station|DLR Station|Overground Station|Tram Stop|Station)$',
                           '', 'i') AS base_name,
                       stop_name, stop_type,
                       ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) as distance_m
                FROM core_transport_stops
                WHERE stop_type IN ('RSE', 'RLY', 'MET', 'TMU')
                  AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 2000)
                ORDER BY base_name, distance_m LIMIT 5
            """),
            {"lat": lat, "lon": lon},
        )
        rail_rows = rail_result.mappings().all()

        mode_result = await db.execute(
            text("""
                SELECT
                  COUNT(*) FILTER (WHERE stop_type IN ('BCT','BCS','BCE','BCQ','BST','FBT')) AS bus_count,
                  COUNT(*) FILTER (WHERE stop_type IN ('RLY','RSE','RPL'))                  AS rail_count,
                  COUNT(*) FILTER (WHERE stop_type IN ('MET','PLT'))                        AS metro_count,
                  COUNT(*) FILTER (WHERE stop_type IN ('TMU','STR'))                        AS tram_count,
                  COUNT(*) FILTER (WHERE stop_type IN ('FER','FTD'))                        AS ferry_count
                FROM core_transport_stops
                WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1000)
            """),
            {"lat": lat, "lon": lon},
        )
        mode_row = mode_result.mappings().first()

    # Bus stops within 500m (kept for backward compat display)
    bus_count = int(mode_row["bus_count"]) if mode_row and mode_row["bus_count"] else 0

    if is_area:
        stations_detail = [{"name": r["base_name"], "type": r["stop_type"]} for r in rail_rows]
        nearest_station_m = None
    else:
        stations_detail = sorted(
            [{"name": r["base_name"], "type": r["stop_type"], "distance_m": round(float(r["distance_m"]))}
             for r in rail_rows],
            key=lambda x: x["distance_m"],
        )
        nearest_station_m = stations_detail[0]["distance_m"] if stations_detail else None

    mode_counts = {}
    if mode_row:
        if mode_row["bus_count"]:   mode_counts["bus"]   = int(mode_row["bus_count"])
        if mode_row["rail_count"]:  mode_counts["rail"]  = int(mode_row["rail_count"])
        if mode_row["metro_count"]: mode_counts["metro"] = int(mode_row["metro_count"])
        if mode_row["tram_count"]:  mode_counts["tram"]  = int(mode_row["tram_count"])
        if mode_row["ferry_count"]: mode_counts["ferry"] = int(mode_row["ferry_count"])

    if is_area:
        metrics.append(metric(
            "stations_in_area", "Rail/Metro Stations in Area",
            len(stations_detail), None, "count",
            details={
                "stations": stations_detail,
                "bus_stops": bus_count,
                "mode_counts": mode_counts if mode_counts else None,
            },
        ))
    else:
        metrics.append(metric(
            "nearest_station", "Nearest Station",
            nearest_station_m, parent_station_m, "metres",
            details={
                "stations": stations_detail,
                "bus_stops_500m": bus_count,
                "mode_counts_1km": mode_counts if mode_counts else None,
            },
        ))

    # --- PTAL Score ---
    ptal_result = await db.execute(
        text("""
            SELECT
                COALESCE(p.avg_ptai, p.computed_ptai)       AS ptai,
                COALESCE(p.ptal_band, p.computed_band)       AS band,
                p.avg_ptai                                   AS official_ptai,
                p.computed_ptai,
                p.computed_band,
                p.bus_count_640m,
                p.heavy_count_960m
            FROM core_ptal_lsoa p
            WHERE p.lsoa_code = ANY(:codes)
            ORDER BY COALESCE(p.avg_ptai, p.computed_ptai) DESC
            LIMIT 1
        """),
        {"codes": lsoa_codes},
    )
    ptal_row = ptal_result.mappings().first()

    ptal_parent = await db.execute(
        text("""
            SELECT AVG(COALESCE(p.avg_ptai, p.computed_ptai)) AS avg_ptai
            FROM core_ptal_lsoa p
            JOIN core_lsoa_boundaries l ON l.lsoa_code = p.lsoa_code
            WHERE l.lad_code = ANY(:parent_lads)
              AND COALESCE(p.avg_ptai, p.computed_ptai) IS NOT NULL
        """),
        {"parent_lads": parent_lads},
    )
    ptal_parent_row = ptal_parent.mappings().first()
    parent_ptai = round(float(ptal_parent_row["avg_ptai"]), 1) if ptal_parent_row and ptal_parent_row["avg_ptai"] else None

    ptal_score_emitted = False
    if ptal_row and ptal_row["band"] and ptal_row["official_ptai"] is not None:
        ptai_val = float(ptal_row["ptai"]) if ptal_row["ptai"] else None
        band = ptal_row["band"]
        # Numeric level 0–6 for display (6b→6, 6a→6, 1b→1, 1a→1)
        band_num = int(band[0]) if band and band[0].isdigit() else 0
        metrics.append(metric(
            "ptal_score", "Public Transport Accessibility (PTAL)",
            band, parent_ptai, "level",
            details={
                "ptai_score": round(ptai_val, 1) if ptai_val else None,
                "band": band,
                "band_num": band_num,
                "bus_stops_640m": int(ptal_row["bus_count_640m"]) if ptal_row["bus_count_640m"] else None,
                "heavy_stops_960m": int(ptal_row["heavy_count_960m"]) if ptal_row["heavy_count_960m"] else None,
                "parent_avg_ptai": parent_ptai,
                "tfl_data": ptal_row["official_ptai"] is not None,
            },
        ))
        ptal_score_emitted = True

    # --- Official DfT destination-reach context ---
    connectivity_result = await db.execute(
        text(f"""
            SELECT AVG(overall_score) AS overall_score,
                   AVG(overall_public_transport) AS overall_public_transport,
                   AVG(overall_walking) AS overall_walking,
                   AVG(overall_cycling) AS overall_cycling,
                   AVG(overall_driving) AS overall_driving,
                   AVG(employment_overall) AS employment_overall,
                   AVG(education_overall) AS education_overall,
                   AVG(healthcare_overall) AS healthcare_overall,
                   AVG(leisure_community_overall) AS leisure_community_overall,
                   AVG(shopping_overall) AS shopping_overall,
                   AVG(residential_overall) AS residential_overall,
                   MIN(source_release) AS source_release
            FROM {TABLE_NAMES['connectivity_lsoa']}
            WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    connectivity_row = connectivity_result.mappings().first()

    if connectivity_row and connectivity_row["overall_score"] is not None:
        connectivity_parent = await db.execute(
            text(f"""
                SELECT AVG(c.overall_score) AS overall_score
                FROM {TABLE_NAMES['connectivity_lsoa']} c
                JOIN core_lsoa_boundaries l ON l.lsoa_code = c.lsoa_code
                WHERE l.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        connectivity_parent_row = connectivity_parent.mappings().first()

        metrics.append(metric(
            "commuter_connectivity", "Commuter Connectivity",
            _r(connectivity_row["overall_score"]),
            _r(connectivity_parent_row["overall_score"]) if connectivity_parent_row else None,
            "score /100",
            details={
                "overall_public_transport": _r(connectivity_row["overall_public_transport"]),
                "overall_walking": _r(connectivity_row["overall_walking"]),
                "overall_cycling": _r(connectivity_row["overall_cycling"]),
                "overall_driving": _r(connectivity_row["overall_driving"]),
                "employment_overall": _r(connectivity_row["employment_overall"]),
                "education_overall": _r(connectivity_row["education_overall"]),
                "healthcare_overall": _r(connectivity_row["healthcare_overall"]),
                "leisure_community_overall": _r(connectivity_row["leisure_community_overall"]),
                "shopping_overall": _r(connectivity_row["shopping_overall"]),
                "residential_overall": _r(connectivity_row["residential_overall"]),
                "source_release": connectivity_row["source_release"],
                "methodology_note": "Official DfT contextual accessibility score showing structural reach to employment and everyday destinations; not a bespoke journey-time estimate.",
                "search_mode": search_mode,
            },
        ))

    # --- EV Chargers ---
    if is_area:
        ev_result = await db.execute(
            text("""
                SELECT COUNT(*) as cnt
                FROM core_ev_chargers e
                JOIN core_lsoa_boundaries lb ON ST_Within(e.geom, lb.geom)
                WHERE lb.lsoa_code = ANY(:codes)
            """),
            {"codes": lsoa_codes},
        )
    else:
        ev_result = await db.execute(
            text("""
                SELECT COUNT(*) as cnt
                FROM core_ev_chargers
                WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1000)
            """),
            {"lat": lat, "lon": lon},
        )
    ev_row = ev_result.mappings().first()
    ev_count = int(ev_row["cnt"]) if ev_row else 0

    # Parent average EV chargers per LSOA (parent comparison group)
    ev_parent = await db.execute(
        text("""
            SELECT COUNT(e.id)::float / NULLIF((SELECT COUNT(*) FROM core_lsoa_boundaries WHERE lad_code = ANY(:parent_lads)), 0) as avg_ev
            FROM core_ev_chargers e
            JOIN core_lad_boundaries l ON ST_Intersects(e.geom, l.geom)
            WHERE l.lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    ev_parent_row = ev_parent.mappings().first()
    ev_parent_avg = round(float(ev_parent_row["avg_ev"]), 1) if ev_parent_row and ev_parent_row["avg_ev"] else None

    ev_label = "EV Chargers in Area" if is_area else "EV Chargers (1km)"
    metrics.append(metric(
        "ev_chargers", ev_label,
        ev_count, ev_parent_avg, "count",
        details={"map_note": "EV charger locations are shown on the map above (green pins). Make sure the Lifestyle & Connectivity tab is active to see them."} if ev_count > 0 else None,
    ))

    # --- Digital Connectivity (Broadband) ---
    # Source: Ofcom Connected Nations 2024 postcode-level coverage data.
    # superfast_pct = SFBB ≥30 Mbit/s; gigabit_pct = ≥1000 Mbit/s; fttp_pct = UFBB ≥300 Mbit/s (ultrafast/full-fibre).
    # Avg download/upload speeds are NOT published by Ofcom at postcode/LSOA level — not included.
    bb_result = await db.execute(
        text("""
            SELECT AVG(b.superfast_pct) as sfbb, AVG(b.ultrafast_pct) as ufbb,
                   AVG(b.gigabit_pct) as gigabit, AVG(b.fttp_pct) as fttp
            FROM core_broadband_postcode b
            JOIN core_postcodes p ON p.postcode = b.postcode
            WHERE p.lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    bb_row = bb_result.mappings().first()

    # Parent broadband average — use pre-aggregated LAD table for speed
    bb_parent = await db.execute(
        text("""
            SELECT AVG(superfast_pct) as sfbb, AVG(ultrafast_pct) as ufbb,
                   AVG(gigabit_pct) as gigabit, AVG(full_fibre_pct) as fttp
            FROM core_broadband_lad
            WHERE lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    bb_parent_row = bb_parent.mappings().first()

    if bb_row:
        local_gigabit = round(float(bb_row["gigabit"]), 1) if bb_row["gigabit"] else None
        parent_gigabit = round(float(bb_parent_row["gigabit"]), 1) if bb_parent_row and bb_parent_row["gigabit"] else None
        local_full_fibre = round(float(bb_row["fttp"]), 1) if bb_row["fttp"] else None
        parent_full_fibre = round(float(bb_parent_row["fttp"]), 1) if bb_parent_row and bb_parent_row["fttp"] else None
        local_superfast = round(float(bb_row["sfbb"]), 1) if bb_row["sfbb"] else None
        parent_superfast = round(float(bb_parent_row["sfbb"]), 1) if bb_parent_row and bb_parent_row["sfbb"] else None

        metrics.append(metric(
            "broadband", "Broadband Coverage",
            local_gigabit, parent_gigabit, "% gigabit",
            details={
                "full_fibre_pct": local_full_fibre,
                "superfast_pct": round(float(bb_row["sfbb"]), 1) if bb_row["sfbb"] else None,
                "ultrafast_pct": round(float(bb_row["ufbb"]), 1) if bb_row["ufbb"] else None,
                "gigabit_pct": local_gigabit,
                "parent_full_fibre_pct": parent_full_fibre,
                "parent_superfast_pct": round(float(bb_parent_row["sfbb"]), 1) if bb_parent_row and bb_parent_row["sfbb"] else None,
                "parent_gigabit_pct": parent_gigabit,
            },
        ))

        if local_full_fibre is not None:
            metrics.append(metric(
                "full_fibre", "Full-Fibre Coverage",
                local_full_fibre, parent_full_fibre, "%",
                details={
                    "gigabit_pct": local_gigabit,
                    "parent_gigabit_pct": parent_gigabit,
                    "source_note": "Surfaced from the same Ofcom Connected Nations coverage dataset used for the headline broadband row.",
                },
            ))

        if local_superfast is not None:
            metrics.append(metric(
                "superfast_broadband", "Superfast Broadband Coverage",
                local_superfast, parent_superfast, "%",
                details={
                    "gigabit_pct": local_gigabit,
                    "full_fibre_pct": local_full_fibre,
                    "parent_gigabit_pct": parent_gigabit,
                    "parent_full_fibre_pct": parent_full_fibre,
                    "source_note": "Uses the same Ofcom Connected Nations postcode-to-area coverage dataset as the headline broadband row, but focuses on baseline superfast availability.",
                },
            ))

    # --- Cycling ---
    cycling_result = await db.execute(
        text("SELECT SUM(total_workers * pct_cycling) / NULLIF(SUM(total_workers), 0) as pct_cycling FROM core_cycling_lsoa WHERE lsoa_code = ANY(:codes)"),
        {"codes": lsoa_codes},
    )
    cycling_row = cycling_result.mappings().first()
    if cycling_row and cycling_row["pct_cycling"] is not None:
        cycling_parent = await db.execute(
            text("""
                SELECT SUM(c.total_workers * c.pct_cycling) / NULLIF(SUM(c.total_workers), 0) as avg_pct
                FROM core_cycling_lsoa c
                JOIN core_lsoa_boundaries l ON l.lsoa_code = c.lsoa_code
                WHERE l.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        cp_row = cycling_parent.mappings().first()
        metrics.append(metric(
            "cycling", "Cycling to Work",
            round(float(cycling_row["pct_cycling"]), 1),
            round(float(cp_row["avg_pct"]), 1) if cp_row and cp_row["avg_pct"] else None,
            "% commuters",
        ))

    # --- Commute Distance (TS058) ---
    commute_result = await db.execute(
        text("""
            SELECT SUM(total_workers * pct_lt2km) / NULLIF(SUM(total_workers), 0) as pct_lt2km,
                   SUM(total_workers * pct_2_10km) / NULLIF(SUM(total_workers), 0) as pct_2_10km,
                   SUM(total_workers * pct_10_30km) / NULLIF(SUM(total_workers), 0) as pct_10_30km,
                   SUM(total_workers * pct_30plus) / NULLIF(SUM(total_workers), 0) as pct_30plus,
                   SUM(total_workers * pct_wfh) / NULLIF(SUM(total_workers), 0) as pct_wfh
            FROM core_census_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    commute_row = commute_result.mappings().first()

    if commute_row and commute_row["pct_wfh"] is not None:
        commute_parent = await db.execute(
            text("""
                SELECT SUM(c.total_workers * c.pct_wfh) / NULLIF(SUM(c.total_workers), 0) as pct_wfh,
                       SUM(c.total_workers * c.pct_lt2km) / NULLIF(SUM(c.total_workers), 0) as pct_lt2km,
                       SUM(c.total_workers * c.pct_10_30km) / NULLIF(SUM(c.total_workers), 0) as pct_10_30km
                FROM core_census_lsoa c
                JOIN core_lsoa_boundaries l ON l.lsoa_code = c.lsoa_code
                WHERE l.lad_code = ANY(:parent_lads)
            """),
            {"parent_lads": parent_lads},
        )
        commute_parent_row = commute_parent.mappings().first()
        metrics.append(metric(
            "commute_distance", "Work From Home Rate",
            _r(commute_row["pct_wfh"]),
            _r(commute_parent_row["pct_wfh"]) if commute_parent_row else None,
            "% of workers",
            details={
                "pct_lt2km": _r(commute_row["pct_lt2km"]),
                "pct_2_10km": _r(commute_row["pct_2_10km"]),
                "pct_10_30km": _r(commute_row["pct_10_30km"]),
                "pct_30plus": _r(commute_row["pct_30plus"]),
                "pct_wfh": _r(commute_row["pct_wfh"]),
            },
        ))

    # --- Mobile Coverage ---
    # Bible: "Default shows 4G/5G availability (Indoor/Outdoor)"
    mobile_result = await db.execute(
        text("SELECT AVG(pct_4g_outdoor) AS pct_4g_outdoor, AVG(pct_4g_indoor) AS pct_4g_indoor, AVG(pct_5g_outdoor) AS pct_5g_outdoor FROM core_mobile_coverage_lad WHERE lad_code = ANY(:lads)"),
        {"lads": local_lads},
    )
    mobile_row = mobile_result.mappings().first()
    if mobile_row and mobile_row["pct_4g_outdoor"] is not None:
        mobile_parent = await db.execute(
            text("SELECT AVG(pct_4g_outdoor) as avg_4g, AVG(pct_4g_indoor) as avg_4g_indoor, AVG(pct_5g_outdoor) as avg_5g FROM core_mobile_coverage_lad WHERE lad_code = ANY(:lads)"),
            {"lads": parent_lads},
        )
        mp_row = mobile_parent.mappings().first()
        parent_4g = round(float(mp_row["avg_4g"]), 1) if mp_row and mp_row["avg_4g"] else None
        local_4g_indoor = round(float(mobile_row["pct_4g_indoor"]), 1) if mobile_row["pct_4g_indoor"] else None
        parent_4g_indoor = round(float(mp_row["avg_4g_indoor"]), 1) if mp_row and mp_row["avg_4g_indoor"] else None
        local_5g = round(float(mobile_row["pct_5g_outdoor"]), 1) if mobile_row["pct_5g_outdoor"] else None
        parent_5g = round(float(mp_row["avg_5g"]), 1) if mp_row and mp_row["avg_5g"] else None

        metrics.append(metric(
            "mobile_coverage", "Mobile Coverage (4G/5G)",
            round(float(mobile_row["pct_4g_outdoor"]), 1) if mobile_row["pct_4g_outdoor"] else None,
            parent_4g, "% 4G outdoor",
                details={
                    "pct_4g_indoor": local_4g_indoor,
                    "pct_5g_outdoor": local_5g,
                    "parent_4g_indoor": parent_4g_indoor,
                    "parent_5g_outdoor": parent_5g,
                },
            ))

        if local_4g_indoor is not None:
            metrics.append(metric(
                "mobile_4g_indoor", "4G Indoor Coverage",
                local_4g_indoor, parent_4g_indoor, "%",
                details={
                    "pct_4g_outdoor": round(float(mobile_row["pct_4g_outdoor"]), 1) if mobile_row["pct_4g_outdoor"] else None,
                    "pct_5g_outdoor": local_5g,
                    "parent_4g_outdoor": parent_4g,
                    "parent_5g_outdoor": parent_5g,
                    "source_note": "Uses the same Ofcom Connected Nations LAD-level coverage model as the headline mobile row, but focuses on indoor 4G reliability.",
                },
            ))

        if local_5g is not None:

            metrics.append(metric(
                "mobile_5g_outdoor", "5G Outdoor Coverage",
                local_5g, parent_5g, "%",
                details={
                    "pct_4g_outdoor": round(float(mobile_row["pct_4g_outdoor"]), 1) if mobile_row["pct_4g_outdoor"] else None,
                    "parent_4g_outdoor": parent_4g,
                    "source_note": "Uses the same Ofcom Connected Nations LAD-level coverage model as the headline mobile row.",
                },
            ))

    return metrics


def _r(val):
    if val is None:
        return None
    return round(float(val), 2)
