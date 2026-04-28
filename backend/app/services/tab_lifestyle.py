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

# NaPTAN stop type → frontend category mapping (fallback when SQL cat column absent)
_STOP_CATEGORY = {
    'RSE': 'rail', 'RLY': 'rail', 'RPL': 'rail',
    'MET': 'tram', 'PLT': 'tram',   # MET/PLT default; SQL CASE refines by ATCO
    'TMU': 'tram', 'STR': 'tram',
    'BCT': 'bus', 'BCS': 'bus', 'BCE': 'bus', 'BCQ': 'bus', 'BST': 'bus', 'FBT': 'bus',
    'FER': 'ferry', 'FTD': 'ferry',
}

# SQL fragment that classifies stops into UK-correct categories.
# NaPTAN stop_type alone is not enough — MET/PLT/TMU are shared across
# Underground, DLR, Overground, and tram systems.  ATCO code prefix
# disambiguates: ZZLU = Underground, ZZDL = DLR, ZZLO = London Overground.
# Everything else MET/PLT/TMU/STR = tram (Metrolink, Supertram, Tramlink, etc.)
# {a} is the table alias prefix (e.g. "t." or "").
_CAT_CASE = """
    CASE
      WHEN {a}stop_type IN ('RSE','RLY','RPL') THEN 'rail'
      WHEN {a}atco_code LIKE '%ZZLU%'          THEN 'underground'
      WHEN {a}atco_code LIKE '%ZZDL%'          THEN 'dlr'
      WHEN {a}atco_code LIKE '%ZZLO%'          THEN 'overground'
      WHEN {a}stop_type IN ('MET','PLT','STR') THEN 'tram'
      WHEN {a}stop_type = 'TMU'
           AND {a}atco_code LIKE '%ZZ%'        THEN 'tram'
      WHEN {a}stop_type IN ('FER','FTD')       THEN 'ferry'
      WHEN {a}stop_type IN ('BCT','BCS','BCE','BCQ','BST','FBT') THEN 'bus'
    END"""


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

    is_lad_or_coarser = boundary_source in ("lad", "county")

    # --- 15-Minute Neighbourhood ---
    if is_area and is_lad_or_coarser and local_lads:
        # LAD/county: use pre-aggregated MV (avoids expensive spatial join)
        amenity_mv = await db.execute(
            text("""
                SELECT amenity_type, SUM(cnt) as cnt
                FROM mv_lad_amenity_counts
                WHERE lad_code = ANY(:lads)
                GROUP BY amenity_type
            """),
            {"lads": local_lads},
        )
        local_amenities = {r["amenity_type"]: int(r["cnt"]) for r in amenity_mv.mappings().all()}
        total_local = sum(local_amenities.values())
        amenity_nearest = []  # No individual nearest for county-scale
    elif is_area:
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
        local_amenities = {r["amenity_type"]: int(r["cnt"]) for r in amenity_counts.mappings().all()}
        total_local = sum(local_amenities.values())

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
        amenity_nearest = [
            {"type": r["amenity_type"], "name": r["name"]}
            for r in amenity_list_result.mappings().all()
        ]
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
            SELECT SUM(cnt)::float / NULLIF((SELECT COUNT(*) FROM core_lsoa_boundaries WHERE lad_code = ANY(:parent_lads)), 0) as avg_count
            FROM mv_lad_amenity_counts
            WHERE lad_code = ANY(:parent_lads)
        """),
        {"parent_lads": parent_lads},
    )
    parent_amenity_row = parent_avg_result.mappings().first()
    parent_amenity_avg = round(float(parent_amenity_row["avg_count"]), 1) if parent_amenity_row and parent_amenity_row["avg_count"] else None

    amenity_label = "Amenities in Area" if is_area else "Local Amenities (within 1 km)"
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

    if is_area and is_lad_or_coarser and local_lads:
        # LAD/county: use pre-aggregated MV for mode counts + LAD join for station list
        all_stops_result = await db.execute(
            text(f"""
                SELECT * FROM (
                    SELECT DISTINCT ON (cat, base_name)
                           {_CAT_CASE.format(a='t.')} AS cat,
                           REGEXP_REPLACE(
                             REGEXP_REPLACE(
                               REGEXP_REPLACE(t.stop_name,
                                   ' (Rail Station|Underground Station|DLR Station|Overground Station|Tram Stop|Station|Bus Station)$',
                                   '', 'i'),
                               '^London ', '', 'i'),
                             ' \\(London\\)$', '', 'i') AS base_name,
                           t.stop_name, t.stop_type, t.atco_code,
                           t.street, t.indicator, t.locality_name,
                           t.parent_locality, t.suburb, t.status,
                           t.crs_code, t.lines, t.operator, t.zone,
                           t.step_free, t.facilities
                    FROM core_transport_stops t
                    JOIN core_lad_boundaries lb ON ST_Within(t.geom, lb.geom)
                    WHERE lb.lad_code = ANY(:lads)
                    ORDER BY cat, base_name,
                             CASE WHEN t.stop_type = 'RLY' THEN 0
                                  WHEN t.stop_type = 'RSE' THEN 1
                                  ELSE 2 END,
                             t.stop_name
                ) deduped
                WHERE cat IS NOT NULL
                ORDER BY base_name
                LIMIT 500
            """),
            {"lads": local_lads},
        )
        all_stop_rows = all_stops_result.mappings().all()
        rail_rows = [r for r in all_stop_rows if r.get("cat", "") in ('rail', 'underground', 'dlr', 'overground', 'tram')]

        # Mode counts from pre-aggregated MV (instant)
        transport_mv = await db.execute(
            text("""
                SELECT cat, SUM(cnt) as cnt
                FROM mv_lad_transport_mode_counts
                WHERE lad_code = ANY(:lads)
                GROUP BY cat
            """),
            {"lads": local_lads},
        )
        mv_counts = {r["cat"]: int(r["cnt"]) for r in transport_mv.mappings().all()}
        mode_row = {
            "bus_count": mv_counts.get("bus", 0),
            "rail_count": mv_counts.get("rail", 0),
            "underground_count": mv_counts.get("underground", 0),
            "dlr_count": mv_counts.get("dlr", 0),
            "overground_count": mv_counts.get("overground", 0),
            "tram_count": mv_counts.get("tram", 0),
            "ferry_count": mv_counts.get("ferry", 0),
        }

    elif is_area:
        # Area mode: all stop types within boundary
        # Dedup by (category, base_name) so bus "Green Park" doesn't shadow
        # the tube station "Green Park Underground Station".
        # Priority sort: rail/metro/tram/ferry first, bus last.
        all_stops_result = await db.execute(
            text(f"""
                SELECT * FROM (
                    SELECT DISTINCT ON (cat, base_name)
                           {_CAT_CASE.format(a='t.')} AS cat,
                           REGEXP_REPLACE(
                             REGEXP_REPLACE(
                               REGEXP_REPLACE(t.stop_name,
                                   ' (Rail Station|Underground Station|DLR Station|Overground Station|Tram Stop|Station|Bus Station)$',
                                   '', 'i'),
                               '^London ', '', 'i'),
                             ' \\(London\\)$', '', 'i') AS base_name,
                           t.stop_name, t.stop_type, t.atco_code,
                           t.street, t.indicator, t.locality_name,
                           t.parent_locality, t.suburb, t.status,
                           t.crs_code, t.lines, t.operator, t.zone,
                           t.step_free, t.facilities
                    FROM core_transport_stops t
                    JOIN core_lsoa_boundaries lb ON ST_Within(t.geom, lb.geom)
                    WHERE lb.lsoa_code = ANY(:codes)
                    ORDER BY cat, base_name,
                             CASE WHEN t.stop_type = 'RLY' THEN 0
                                  WHEN t.stop_type = 'RSE' THEN 1
                                  ELSE 2 END,
                             t.stop_name
                ) deduped
                WHERE cat IS NOT NULL
                ORDER BY base_name
                LIMIT 500
            """),
            {"codes": lsoa_codes},
        )
        all_stop_rows = all_stops_result.mappings().all()
        # Rail rows for backward compat headline (rail + tube/dlr/overground/tram)
        rail_rows = [r for r in all_stop_rows if r.get("cat", "") in ('rail', 'underground', 'dlr', 'overground', 'tram')]

        mode_result = await db.execute(
            text(f"""
                SELECT
                  COUNT(*) FILTER (WHERE t.stop_type IN ('BCT','BCS','BCE','BCQ','BST','FBT')) AS bus_count,
                  COUNT(*) FILTER (WHERE t.stop_type IN ('RLY','RSE','RPL'))                  AS rail_count,
                  COUNT(*) FILTER (WHERE {_CAT_CASE.format(a='t.')} = 'underground')          AS underground_count,
                  COUNT(*) FILTER (WHERE {_CAT_CASE.format(a='t.')} = 'dlr')                  AS dlr_count,
                  COUNT(*) FILTER (WHERE {_CAT_CASE.format(a='t.')} = 'overground')           AS overground_count,
                  COUNT(*) FILTER (WHERE {_CAT_CASE.format(a='t.')} = 'tram')                 AS tram_count,
                  COUNT(*) FILTER (WHERE t.stop_type IN ('FER','FTD'))                        AS ferry_count
                FROM core_transport_stops t
                JOIN core_lsoa_boundaries lb ON ST_Within(t.geom, lb.geom)
                WHERE lb.lsoa_code = ANY(:codes)
            """),
            {"codes": lsoa_codes},
        )
        mode_row = mode_result.mappings().first()
    else:
        # Postcode mode: all stop types within 2km
        # Dedup by (category, base_name) to prevent bus/rail name collisions.
        # Inner query deduplicates; outer query re-sorts by distance with LIMIT.
        all_stops_result = await db.execute(
            text(f"""
                SELECT * FROM (
                    SELECT DISTINCT ON (cat, base_name)
                           {_CAT_CASE.format(a='')} AS cat,
                           REGEXP_REPLACE(
                             REGEXP_REPLACE(
                               REGEXP_REPLACE(stop_name,
                                   ' (Rail Station|Underground Station|DLR Station|Overground Station|Tram Stop|Station|Bus Station)$',
                                   '', 'i'),
                               '^London ', '', 'i'),
                             ' \\(London\\)$', '', 'i') AS base_name,
                           stop_name, stop_type, atco_code,
                           street, indicator, locality_name,
                           parent_locality, suburb, status,
                           crs_code, lines, operator, zone,
                           step_free, facilities,
                           ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) as distance_m
                    FROM core_transport_stops
                    WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 2000)
                    ORDER BY cat, base_name,
                             CASE WHEN stop_type = 'RLY' THEN 0
                                  WHEN stop_type = 'RSE' THEN 1
                                  ELSE 2 END,
                             distance_m
                ) deduped
                WHERE cat IS NOT NULL
                ORDER BY distance_m
                LIMIT 150
            """),
            {"lat": lat, "lon": lon},
        )
        all_stop_rows = all_stops_result.mappings().all()
        # Rail rows for backward compat headline (all non-bus, non-ferry)
        rail_rows = [r for r in all_stop_rows if r.get("cat", "") in ('rail', 'underground', 'dlr', 'overground', 'tram')]

        mode_result = await db.execute(
            text(f"""
                SELECT
                  COUNT(*) FILTER (WHERE stop_type IN ('BCT','BCS','BCE','BCQ','BST','FBT')) AS bus_count,
                  COUNT(*) FILTER (WHERE stop_type IN ('RLY','RSE','RPL'))                  AS rail_count,
                  COUNT(*) FILTER (WHERE {_CAT_CASE.format(a='')} = 'underground')          AS underground_count,
                  COUNT(*) FILTER (WHERE {_CAT_CASE.format(a='')} = 'dlr')                  AS dlr_count,
                  COUNT(*) FILTER (WHERE {_CAT_CASE.format(a='')} = 'overground')           AS overground_count,
                  COUNT(*) FILTER (WHERE {_CAT_CASE.format(a='')} = 'tram')                 AS tram_count,
                  COUNT(*) FILTER (WHERE stop_type IN ('FER','FTD'))                        AS ferry_count
                FROM core_transport_stops
                WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 1000)
            """),
            {"lat": lat, "lon": lon},
        )
        mode_row = mode_result.mappings().first()

    # Bus stops within 500m (kept for backward compat display)
    bus_count = int(mode_row["bus_count"]) if mode_row and mode_row["bus_count"] else 0

    def _station_row(r, include_distance=False):
        """Build a station detail dict from a DB row."""
        cat = r.get("cat") or _STOP_CATEGORY.get(r["stop_type"], "other")
        d = {
            "name": r["base_name"],
            "type": r["stop_type"],
            "category": cat,
            "atco_code": r["atco_code"],
        }
        if r.get("street"):          d["street"] = r["street"]
        if r.get("indicator"):       d["indicator"] = r["indicator"]
        if r.get("locality_name"):   d["locality"] = r["locality_name"]
        if r.get("parent_locality"): d["parent_locality"] = r["parent_locality"]
        if r.get("suburb"):          d["suburb"] = r["suburb"]
        if r.get("status"):          d["status"] = r["status"]
        # Enrichment columns (may be NULL until enrichment ETL runs)
        if r.get("crs_code"):        d["crs_code"] = r["crs_code"]
        if r.get("lines"):           d["lines"] = r["lines"]
        if r.get("operator"):        d["operator"] = r["operator"]
        if r.get("zone"):            d["zone"] = r["zone"]
        if r.get("step_free") is not None: d["step_free"] = bool(r["step_free"])
        if r.get("facilities"):
            fac = r["facilities"]
            d["facilities"] = fac if isinstance(fac, dict) else {}
        if include_distance and r.get("distance_m") is not None:
            d["distance_m"] = round(float(r["distance_m"]))
        return d

    if is_area:
        # Rail/metro/tram for headline (backward compat)
        stations_detail = [_station_row(r) for r in rail_rows]
        # ALL stops categorised for the detail table
        all_stations = [_station_row(r) for r in all_stop_rows]
        nearest_station_m = None
    else:
        stations_detail = sorted(
            [_station_row(r, include_distance=True) for r in rail_rows],
            key=lambda x: x.get("distance_m", 0),
        )
        all_stations = sorted(
            [_station_row(r, include_distance=True) for r in all_stop_rows],
            key=lambda x: x.get("distance_m", 0),
        )
        nearest_station_m = stations_detail[0]["distance_m"] if stations_detail else None

    # Attach top commute destinations to National Rail stations
    rail_crs_codes = [s["crs_code"] for s in all_stations if s.get("category") == "rail" and s.get("crs_code")]
    if rail_crs_codes:
        dest_result = await db.execute(
            text(f"""
                SELECT origin_crs, dest_crs, dest_name, journey_min,
                       trains_per_hour, pct_on_time, season_ticket_gbp, rank,
                       COALESCE(is_travelcard, FALSE) AS is_travelcard,
                       travelcard_zones,
                       journey_type, num_changes, modes, peak_fare_pence,
                       offpeak_fare_pence, fare_zones, legs, fare_caveats
                FROM {TABLE_NAMES['station_destinations']}
                WHERE origin_crs = ANY(:crs_codes)
                ORDER BY origin_crs, rank
            """),
            {"crs_codes": rail_crs_codes},
        )
        # Group by origin
        dest_by_origin = {}
        for row in dest_result.mappings().all():
            origin = row["origin_crs"]
            if origin not in dest_by_origin:
                dest_by_origin[origin] = []
            dest_entry = {
                "dest_crs": row["dest_crs"],
                "dest_name": row["dest_name"],
                "journey_min": int(row["journey_min"]) if row["journey_min"] else None,
                "trains_per_hour": float(row["trains_per_hour"]) if row["trains_per_hour"] else None,
                "pct_on_time": float(row["pct_on_time"]) if row["pct_on_time"] else None,
                "season_ticket_gbp": float(row["season_ticket_gbp"]) if row["season_ticket_gbp"] else None,
                "journey_type": row["journey_type"] or "direct",
                "num_changes": int(row["num_changes"]) if row["num_changes"] else 0,
                "modes": list(row["modes"]) if row["modes"] else [],
                "peak_fare_pence": int(row["peak_fare_pence"]) if row["peak_fare_pence"] else None,
                "offpeak_fare_pence": int(row["offpeak_fare_pence"]) if row["offpeak_fare_pence"] else None,
                "fare_zones": row["fare_zones"],
                "legs": row["legs"],
                "fare_caveats": list(row["fare_caveats"]) if row["fare_caveats"] else [],
            }
            if row["is_travelcard"]:
                dest_entry["is_travelcard"] = True
                if row["travelcard_zones"]:
                    dest_entry["travelcard_zones"] = row["travelcard_zones"]
            dest_by_origin[origin].append(dest_entry)
        # Attach to station dicts (both lists are separate objects)
        for station_list in (all_stations, stations_detail):
            for s in station_list:
                if s.get("crs_code") and s["crs_code"] in dest_by_origin:
                    s["destinations"] = dest_by_origin[s["crs_code"]]

    mode_counts = {}
    if mode_row:
        if mode_row["bus_count"]:         mode_counts["bus"]         = int(mode_row["bus_count"])
        if mode_row["rail_count"]:        mode_counts["rail"]        = int(mode_row["rail_count"])
        if mode_row["underground_count"]: mode_counts["underground"] = int(mode_row["underground_count"])
        if mode_row["dlr_count"]:         mode_counts["dlr"]         = int(mode_row["dlr_count"])
        if mode_row["overground_count"]:  mode_counts["overground"]  = int(mode_row["overground_count"])
        if mode_row["tram_count"]:        mode_counts["tram"]        = int(mode_row["tram_count"])
        if mode_row["ferry_count"]:       mode_counts["ferry"]       = int(mode_row["ferry_count"])

    if is_area:
        metrics.append(metric(
            "stations_in_area", "Rail/Metro Stations in Area",
            len(stations_detail), None, "count",
            details={
                "stations": stations_detail,
                "all_stations": all_stations,
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
                "all_stations": all_stations,
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
    if is_area and is_lad_or_coarser and local_lads:
        ev_result = await db.execute(
            text("""
                SELECT COUNT(*) as cnt
                FROM core_ev_chargers e
                JOIN core_lad_boundaries lb ON ST_Within(e.geom, lb.geom)
                WHERE lb.lad_code = ANY(:lads)
            """),
            {"lads": local_lads},
        )
    elif is_area:
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

    # --- Cycling ---
    cycling_result = await db.execute(
        text("""
            SELECT SUM(c.total_workers * c.pct_cycling) / NULLIF(SUM(c.total_workers), 0) AS pct_cycling,
                   SUM(c.cycling_count) AS cycling_count,
                   SUM(c.total_workers) AS total_workers,
                   (SELECT AVG(cs.pct_no_car) FROM core_census_lsoa cs WHERE cs.lsoa_code = ANY(:codes)) AS pct_no_car
            FROM core_cycling_lsoa c
            WHERE c.lsoa_code = ANY(:codes)
        """),
        {"codes": lsoa_codes},
    )
    cycling_row = cycling_result.mappings().first()
    if cycling_row and cycling_row["pct_cycling"] is not None:
        local_pct = round(float(cycling_row["pct_cycling"]), 1)
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
        # National percentile — what % of LSOAs have a lower cycling rate?
        pct_result = await db.execute(
            text("""
                SELECT COUNT(*) FILTER (WHERE pct_cycling < :local_pct)::float
                     / NULLIF(COUNT(*)::float, 0) * 100 AS percentile
                FROM core_cycling_lsoa
            """),
            {"local_pct": float(cycling_row["pct_cycling"])},
        )
        pct_row = pct_result.mappings().first()
        national_percentile = round(float(pct_row["percentile"]), 0) if pct_row and pct_row["percentile"] is not None else None

        metrics.append(metric(
            "cycling", "Cycling to Work",
            local_pct,
            round(float(cp_row["avg_pct"]), 1) if cp_row and cp_row["avg_pct"] else None,
            "% commuters",
            details={
                "cycling_count": int(cycling_row["cycling_count"]) if cycling_row["cycling_count"] else None,
                "total_workers": int(cycling_row["total_workers"]) if cycling_row["total_workers"] else None,
                "national_percentile": national_percentile,
                "pct_no_car": round(float(cycling_row["pct_no_car"]), 1) if cycling_row["pct_no_car"] else None,
                "context_note": "Census 2021 method of travel to work. Higher cycling rates correlate with flat terrain, cycle infrastructure, and shorter commutes.",
            },
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
                "Under 2 km": _r(commute_row["pct_lt2km"]),
                "2–10 km": _r(commute_row["pct_2_10km"]),
                "10–30 km": _r(commute_row["pct_10_30km"]),
                "30+ km": _r(commute_row["pct_30plus"]),
                "Work from home": _r(commute_row["pct_wfh"]),
                "detail_unit": "%",
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

    return metrics


def _r(val):
    if val is None:
        return None
    return round(float(val), 2)
