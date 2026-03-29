"""Tab 2: Lifestyle & Connectivity — Bible Part 4, Tab 2.
Queries: core_osm_amenities, core_transport_stops, core_ev_chargers, core_broadband_postcode.
Spatial queries use area centroid. Bible Rule 4: multi-LSOA aggregation for non-postcode searches."""
from sqlalchemy import text
from app.services.helpers import metric, get_parent_lad_codes


# Bible Section 3.1: exact OSM amenity types
AMENITY_TYPES = [
    "supermarket", "cafe", "restaurant", "pub", "gym",
    "park", "pharmacy", "dentist", "hospital", "doctors",
]


async def fetch_lifestyle_connectivity(db, *, lad_code, ward_code, lsoa_codes, centroid_lat, centroid_lon):
    metrics = []
    lat, lon = centroid_lat, centroid_lon
    if lat is None:
        return metrics
    parent_lads = await get_parent_lad_codes(db, lad_code)

    # --- 15-Minute Neighbourhood (1km radius ≈ 15 min walk) ---
    # Bible Rule 4: ST_DWithin(geom, ST_SetSRID(ST_MakePoint(lon, lat), 4326), 1000)
    # Note: ST_DWithin with geography type uses metres
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

    # Bible: "Expandable shows list with distances" — nearest of each amenity type
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

    # Bible: Composite Score 0-100 (each of 10 amenity types present = 10 points)
    types_present = sum(1 for t in AMENITY_TYPES if local_amenities.get(t, 0) > 0)
    composite_score = types_present * 10

    metrics.append(metric(
        "fifteen_min_score", "15-Minute Score",
        composite_score, None, "score /100",
        details=local_amenities or None,
    ))

    metrics.append(metric(
        "amenities_15min", "15-Minute Amenities (1km)",
        total_local, None, "count",
        details={"counts": local_amenities, "nearest": amenity_nearest} if local_amenities else None,
    ))

    # --- Transport & Commuting ---
    # Nearest stations (rail/metro/tram) within 2km
    # NaPTAN stores "Brixton", "Brixton Rail Station", "Brixton Underground Station" as separate
    # records for the same physical station. Normalise by stripping standard suffixes, then
    # DISTINCT ON the base name keeping the closest record.
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

    # Mode counts within 1km — bus, rail, metro, tram, ferry
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

    metrics.append(metric(
        "nearest_station", "Nearest Station",
        nearest_station_m, None, "metres",
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
            band, None, "level",
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

    # --- EV Chargers within 1km ---
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

    metrics.append(metric(
        "ev_chargers", "EV Chargers (1km)",
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

        metrics.append(metric(
            "broadband", "Broadband Coverage",
            local_gigabit, parent_gigabit, "% gigabit",
            details={
                "full_fibre_pct": round(float(bb_row["fttp"]), 1) if bb_row["fttp"] else None,
                "superfast_pct": round(float(bb_row["sfbb"]), 1) if bb_row["sfbb"] else None,
                "ultrafast_pct": round(float(bb_row["ufbb"]), 1) if bb_row["ufbb"] else None,
                "gigabit_pct": local_gigabit,
                "parent_full_fibre_pct": round(float(bb_parent_row["fttp"]), 1) if bb_parent_row and bb_parent_row["fttp"] else None,
                "parent_superfast_pct": round(float(bb_parent_row["sfbb"]), 1) if bb_parent_row and bb_parent_row["sfbb"] else None,
                "parent_gigabit_pct": parent_gigabit,
            },
        ))

    # --- Connectivity Index (non-London only) ---
    # London areas already have ptal_score from the block above; only compute
    # connectivity_index for areas where official TfL PTAL data is unavailable.
    if not ptal_score_emitted:
        # Bible: "Connectivity Index" for non-London areas
        # - Rail stations within 2km (max 25 pts: 5 per station, cap at 5)
        # - Bus stops within 500m (max 25 pts: 1 per stop, cap at 25)
        # - Gigabit broadband coverage % (max 25 pts: 25 * gigabit_pct / 100)
        # - Amenity score (max 25 pts: composite_score / 4)
        rail_score = min(len(stations_detail) * 5, 25) if stations_detail else 0
        bus_score = min(bus_count, 25)
        bb_gigabit = float(bb_row["gigabit"]) if bb_row and bb_row["gigabit"] else 0
        bb_score = round(25 * bb_gigabit / 100, 1)
        amenity_component = round(composite_score / 4, 1)
        connectivity_index = round(rail_score + bus_score + bb_score + amenity_component, 1)

        metrics.append(metric(
            "connectivity_index", "Connectivity Index",
            connectivity_index, None, "score /100",
            details={
                "rail_stations_2km": len(stations_detail) if stations_detail else 0,
                "bus_stops_500m": bus_count,
                "gigabit_pct": round(bb_gigabit, 1),
                "amenity_score": composite_score,
            },
        ))

    # --- Cycling ---
    cycling_result = await db.execute(
        text("SELECT AVG(pct_cycling) as pct_cycling FROM core_cycling_lsoa WHERE lsoa_code = ANY(:codes)"),
        {"codes": lsoa_codes},
    )
    cycling_row = cycling_result.mappings().first()
    if cycling_row and cycling_row["pct_cycling"] is not None:
        cycling_parent = await db.execute(
            text("""
                SELECT AVG(c.pct_cycling) as avg_pct
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
            SELECT AVG(pct_lt2km) as pct_lt2km, AVG(pct_2_10km) as pct_2_10km,
                   AVG(pct_10_30km) as pct_10_30km, AVG(pct_30plus) as pct_30plus,
                   AVG(pct_wfh) as pct_wfh
            FROM core_census_commute_lsoa WHERE lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    commute_row = commute_result.mappings().first()

    if commute_row and commute_row["pct_wfh"] is not None:
        commute_parent = await db.execute(
            text("""
                SELECT AVG(c.pct_wfh) as pct_wfh, AVG(c.pct_lt2km) as pct_lt2km,
                       AVG(c.pct_10_30km) as pct_10_30km
                FROM core_census_commute_lsoa c
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
        text("SELECT pct_4g_outdoor, pct_4g_indoor, pct_5g_outdoor FROM core_mobile_coverage_lad WHERE lad_code = :lad"),
        {"lad": lad_code},
    )
    mobile_row = mobile_result.mappings().first()
    if mobile_row:
        mobile_parent = await db.execute(
            text("SELECT AVG(pct_4g_outdoor) as avg_4g FROM core_mobile_coverage_lad WHERE lad_code = ANY(:lads)"),
            {"lads": parent_lads},
        )
        mp_row = mobile_parent.mappings().first()
        parent_4g = round(float(mp_row["avg_4g"]), 1) if mp_row and mp_row["avg_4g"] else None

        metrics.append(metric(
            "mobile_coverage", "Mobile Coverage (4G/5G)",
            round(float(mobile_row["pct_4g_outdoor"]), 1) if mobile_row["pct_4g_outdoor"] else None,
            parent_4g, "% 4G outdoor",
            details={
                "pct_4g_indoor": round(float(mobile_row["pct_4g_indoor"]), 1) if mobile_row["pct_4g_indoor"] else None,
                "pct_5g_outdoor": round(float(mobile_row["pct_5g_outdoor"]), 1) if mobile_row["pct_5g_outdoor"] else None,
            },
        ))

    return metrics


def _r(val):
    if val is None:
        return None
    return round(float(val), 2)
