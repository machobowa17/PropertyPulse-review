"""Tab 2: Lifestyle & Connectivity — Bible Part 4, Tab 2.
Queries: core_osm_amenities, core_transport_stops, core_ev_chargers, core_broadband_postcode.
Spatial queries use LSOA centroid coordinates. Bible Rule 4: ST_DWithin for 15-min amenities."""
from sqlalchemy import text
from app.services.helpers import metric, get_lsoa_centroid


# Bible Section 3.1: exact OSM amenity types
AMENITY_TYPES = [
    "supermarket", "cafe", "restaurant", "pub", "gym",
    "park", "pharmacy", "dentist", "hospital", "doctors",
]


async def fetch_lifestyle_connectivity(db, *, lad_code, ward_code, lsoa_code):
    metrics = []
    lat, lon = await get_lsoa_centroid(db, lsoa_code)
    if lat is None:
        return metrics

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

    # Parent average: count amenities within LAD boundary / number of LSOAs
    parent_avg_result = await db.execute(
        text("""
            SELECT COUNT(a.id)::float / NULLIF((SELECT COUNT(*) FROM core_lsoa_boundaries WHERE lad_code = :lad), 0) as avg_count
            FROM core_osm_amenities a
            JOIN core_lad_boundaries l ON ST_Intersects(a.geom, l.geom)
            WHERE l.lad_code = :lad
        """),
        {"lad": lad_code},
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
        total_local, parent_amenity_avg, "count",
        details=local_amenities or None,
    ))

    # --- Transport & Commuting ---
    # Nearest stations (rail) within 2km
    rail_result = await db.execute(
        text("""
            SELECT stop_name, stop_type,
                   ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) as distance_m
            FROM core_transport_stops
            WHERE stop_type IN ('RSE', 'RLY', 'MET', 'TMU')
              AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 2000)
            ORDER BY distance_m LIMIT 5
        """),
        {"lat": lat, "lon": lon},
    )
    rail_rows = rail_result.mappings().all()

    # Bus stops within 500m
    bus_result = await db.execute(
        text("""
            SELECT COUNT(*) as cnt
            FROM core_transport_stops
            WHERE stop_type IN ('BCE', 'BCT', 'BCS', 'BCQ')
              AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 500)
        """),
        {"lat": lat, "lon": lon},
    )
    bus_row = bus_result.mappings().first()
    bus_count = int(bus_row["cnt"]) if bus_row else 0

    stations_detail = [
        {"name": r["stop_name"], "type": r["stop_type"], "distance_m": round(float(r["distance_m"]))}
        for r in rail_rows
    ]
    nearest_station_m = stations_detail[0]["distance_m"] if stations_detail else None

    metrics.append(metric(
        "nearest_station", "Nearest Station",
        nearest_station_m, None, "metres",
        details={"stations": stations_detail, "bus_stops_500m": bus_count},
    ))

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

    # Parent average EV chargers per LSOA
    ev_parent = await db.execute(
        text("""
            SELECT COUNT(e.id)::float / NULLIF((SELECT COUNT(*) FROM core_lsoa_boundaries WHERE lad_code = :lad), 0) as avg_ev
            FROM core_ev_chargers e
            JOIN core_lad_boundaries l ON ST_Intersects(e.geom, l.geom)
            WHERE l.lad_code = :lad
        """),
        {"lad": lad_code},
    )
    ev_parent_row = ev_parent.mappings().first()
    ev_parent_avg = round(float(ev_parent_row["avg_ev"]), 1) if ev_parent_row and ev_parent_row["avg_ev"] else None

    metrics.append(metric(
        "ev_chargers", "EV Chargers (1km)",
        ev_count, ev_parent_avg, "count",
    ))

    # --- Digital Connectivity (Broadband) ---
    # Get postcodes in this LSOA, then average broadband stats
    bb_result = await db.execute(
        text("""
            SELECT AVG(b.superfast_pct) as sfbb, AVG(b.ultrafast_pct) as ufbb,
                   AVG(b.gigabit_pct) as gigabit, AVG(b.avg_download_mbps) as avg_dl
            FROM core_broadband_postcode b
            JOIN core_postcodes p ON p.postcode = b.postcode
            WHERE p.lsoa_code = :lsoa
        """),
        {"lsoa": lsoa_code},
    )
    bb_row = bb_result.mappings().first()

    # Parent broadband average (LAD)
    bb_parent = await db.execute(
        text("""
            SELECT AVG(b.superfast_pct) as sfbb, AVG(b.ultrafast_pct) as ufbb,
                   AVG(b.gigabit_pct) as gigabit, AVG(b.avg_download_mbps) as avg_dl
            FROM core_broadband_postcode b
            JOIN core_postcodes p ON p.postcode = b.postcode
            WHERE p.lad_code = :lad
        """),
        {"lad": lad_code},
    )
    bb_parent_row = bb_parent.mappings().first()

    if bb_row:
        local_gigabit = round(float(bb_row["gigabit"]), 1) if bb_row["gigabit"] else None
        parent_gigabit = round(float(bb_parent_row["gigabit"]), 1) if bb_parent_row and bb_parent_row["gigabit"] else None

        metrics.append(metric(
            "broadband", "Broadband Coverage",
            local_gigabit, parent_gigabit, "% gigabit",
            details={
                "superfast_pct": round(float(bb_row["sfbb"]), 1) if bb_row["sfbb"] else None,
                "ultrafast_pct": round(float(bb_row["ufbb"]), 1) if bb_row["ufbb"] else None,
                "gigabit_pct": local_gigabit,
                "avg_download_mbps": round(float(bb_row["avg_dl"]), 1) if bb_row["avg_dl"] else None,
            },
        ))

    # --- PTAL / Connectivity Index ---
    # London: core_ptal_lsoa; outside London: not available
    ptal_result = await db.execute(
        text("SELECT avg_ptai, ptal_band FROM core_ptal_lsoa WHERE lsoa_code = :lsoa"),
        {"lsoa": lsoa_code},
    )
    ptal_row = ptal_result.mappings().first()
    if ptal_row:
        ptal_parent = await db.execute(
            text("""
                SELECT AVG(p.avg_ptai) as avg_ptai
                FROM core_ptal_lsoa p
                JOIN core_lsoa_boundaries l ON l.lsoa_code = p.lsoa_code
                WHERE l.lad_code = :lad
            """),
            {"lad": lad_code},
        )
        pp_row = ptal_parent.mappings().first()
        metrics.append(metric(
            "ptal", "PTAL Score (London)",
            round(float(ptal_row["avg_ptai"]), 1),
            round(float(pp_row["avg_ptai"]), 1) if pp_row and pp_row["avg_ptai"] else None,
            "score",
            details={"ptal_band": ptal_row["ptal_band"]},
        ))

    # --- Cycling ---
    cycling_result = await db.execute(
        text("SELECT pct_cycling FROM core_cycling_lsoa WHERE lsoa_code = :lsoa"),
        {"lsoa": lsoa_code},
    )
    cycling_row = cycling_result.mappings().first()
    if cycling_row and cycling_row["pct_cycling"] is not None:
        cycling_parent = await db.execute(
            text("""
                SELECT AVG(c.pct_cycling) as avg_pct
                FROM core_cycling_lsoa c
                JOIN core_lsoa_boundaries l ON l.lsoa_code = c.lsoa_code
                WHERE l.lad_code = :lad
            """),
            {"lad": lad_code},
        )
        cp_row = cycling_parent.mappings().first()
        metrics.append(metric(
            "cycling", "Cycling to Work",
            round(float(cycling_row["pct_cycling"]), 1),
            round(float(cp_row["avg_pct"]), 1) if cp_row and cp_row["avg_pct"] else None,
            "% commuters",
        ))

    # --- Mobile Coverage ---
    mobile_result = await db.execute(
        text("SELECT pct_4g_outdoor, pct_4g_indoor, pct_5g_outdoor FROM core_mobile_coverage_lad WHERE lad_code = :lad"),
        {"lad": lad_code},
    )
    mobile_row = mobile_result.mappings().first()
    if mobile_row:
        metrics.append(metric(
            "mobile_coverage", "Mobile Coverage (4G/5G)",
            round(float(mobile_row["pct_4g_outdoor"]), 1) if mobile_row["pct_4g_outdoor"] else None,
            None, "% 4G outdoor",
            details={
                "pct_4g_indoor": round(float(mobile_row["pct_4g_indoor"]), 1) if mobile_row["pct_4g_indoor"] else None,
                "pct_5g_outdoor": round(float(mobile_row["pct_5g_outdoor"]), 1) if mobile_row["pct_5g_outdoor"] else None,
            },
        ))

    return metrics
