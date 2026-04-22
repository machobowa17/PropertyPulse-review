"""
parsers/fares_parser.py — Parse NR fares ZIP to extract fares per station pair.

Input:  ZIP file containing .FFL, .LOC, .FSC files
Output: (season_prices, single_fares) tuple:
    season_prices: dict[(origin_crs, dest_crs)] → annual_season_ticket_gbp
    single_fares:  dict[(origin_crs, dest_crs)] → {"peak_pence": int, "offpeak_pence": int}

Resolves NLC codes through three layers:
1. Direct station NLCs (LOC L records with CRS codes)
2. FSC clusters (non-numeric NLC prefixes → expand to member stations)
3. LOC groups (numeric NLCs with G records → expand via M records)

Takes the LOWEST fare when multiple flows resolve to the same CRS pair.

Direction handling: F records have a direction flag at position 19:
  'R' = reversible (fare applies in both directions)
  'S' = single direction only
For 'R' flows, fares are mapped to both (origin→dest) and (dest→origin).
Forward-specific fares always take priority over reverse-inferred fares.

Season tickets: 7DS/7TS = weekly season ticket price in pence. Annual = weekly × 40.
Single fares: SDS = peak single, SOS/SVS/CDS = off-peak single (cheapest kept).
"""

import zipfile


def _build_nlc_to_crs(loc_file):
    """Parse LOC L records to build NLC → CRS mapping.

    Returns dict[str, str] with ~3,400 entries.
    """
    nlc_to_crs = {}
    for raw_line in loc_file:
        line = raw_line.decode("latin-1", errors="replace").rstrip("\n")
        if len(line) < 59 or line[1] != "L":
            continue
        nlc = line[4:8]
        crs = line[56:59].strip()
        # Only map numeric NLCs to valid 3-char alpha CRS codes
        if nlc and crs and len(crs) == 3 and crs.isalpha() and nlc[0].isdigit():
            nlc_to_crs[nlc] = crs
    return nlc_to_crs


def _build_fsc_clusters(fsc_file):
    """Parse FSC file to build cluster_id → set of member NLCs.

    FSC record (25 chars): [2:6] = cluster_id, [6:10] = member_nlc
    Returns dict[str, set[str]] with ~2,400 clusters.
    """
    clusters = {}
    for raw_line in fsc_file:
        line = raw_line.decode("latin-1", errors="replace").rstrip("\n")
        if len(line) < 10 or line[1] != "R":
            continue
        cluster_id = line[2:6]
        member_nlc = line[6:10]
        if cluster_id and member_nlc:
            if cluster_id not in clusters:
                clusters[cluster_id] = set()
            clusters[cluster_id].add(member_nlc)
    return clusters


def _build_loc_groups(loc_file):
    """Parse LOC M records to build group_nlc → set of member NLCs.

    M record (27 chars): [4:8] = group NLC, [19:23] = member NLC, [24:27] = CRS
    Returns dict[str, set[str]] with ~734 groups.
    """
    groups = {}
    for raw_line in loc_file:
        line = raw_line.decode("latin-1", errors="replace").rstrip("\n")
        if len(line) < 23 or line[1] != "M":
            continue
        group_nlc = line[4:8]
        member_nlc = line[19:23]
        if group_nlc and member_nlc and member_nlc[0].isdigit():
            if group_nlc not in groups:
                groups[group_nlc] = set()
            groups[group_nlc].add(member_nlc)
    return groups


def _resolve_nlc(nlc, nlc_to_crs, fsc_clusters, loc_groups):
    """Resolve an NLC code to a set of CRS codes.

    Resolution order:
    1. Direct station lookup (NLC → CRS)
    2. FSC cluster expansion (cluster → member NLCs → CRS)
    3. LOC group expansion (group → member NLCs → CRS)
    4. Return empty set if unresolvable
    """
    # Layer 1: direct station
    if nlc in nlc_to_crs:
        return {nlc_to_crs[nlc]}

    # Layer 2: FSC cluster
    if nlc in fsc_clusters:
        crs_set = set()
        for member in fsc_clusters[nlc]:
            if member in nlc_to_crs:
                crs_set.add(nlc_to_crs[member])
        return crs_set

    # Layer 3: LOC group
    if nlc in loc_groups:
        crs_set = set()
        for member in loc_groups[nlc]:
            if member in nlc_to_crs:
                crs_set.add(nlc_to_crs[member])
        return crs_set

    return set()


def parse_fares(zip_path):
    """Parse NR fares ZIP and return season ticket + single fare prices per CRS pair.

    Returns:
        tuple of (season_prices, single_fares):
        - season_prices: dict[(origin_crs, dest_crs)] → annual_season_ticket_gbp (float)
        - single_fares:  dict[(origin_crs, dest_crs)] → {"peak_pence": int, "offpeak_pence": int}

    Takes the lowest fare when multiple flows resolve to the same pair.
    """
    z = zipfile.ZipFile(zip_path)

    # Find required files
    ffl_name = None
    loc_name = None
    fsc_name = None
    for name in z.namelist():
        upper = name.upper()
        if upper.endswith(".FFL"):
            ffl_name = name
        elif upper.endswith(".LOC"):
            loc_name = name
        elif upper.endswith(".FSC"):
            fsc_name = name

    if not ffl_name:
        raise FileNotFoundError("No .FFL file found in fares ZIP")
    if not loc_name:
        raise FileNotFoundError("No .LOC file found in fares ZIP")
    if not fsc_name:
        raise FileNotFoundError("No .FSC file found in fares ZIP")

    # Step 1: Build lookup dictionaries
    print("  Fares: building NLC→CRS mapping...")
    with z.open(loc_name) as f:
        nlc_to_crs = _build_nlc_to_crs(f)
    print(f"  Fares: {len(nlc_to_crs):,} NLC→CRS mappings")

    print("  Fares: building FSC clusters...")
    with z.open(fsc_name) as f:
        fsc_clusters = _build_fsc_clusters(f)
    print(f"  Fares: {len(fsc_clusters):,} clusters")

    print("  Fares: building LOC groups...")
    with z.open(loc_name) as f:
        loc_groups = _build_loc_groups(f)
    print(f"  Fares: {len(loc_groups):,} groups")

    # Step 2: First pass — collect fares from T records (flow_id → fare_pence)
    # Season: 7DS/7TS = weekly season ticket
    # Peak single: SDS = Standard Day Single
    # Off-peak single: SOS = Standard Off-peak Single, SVS = Super Off-peak Single,
    #                  CDS = Cheapest Day Single
    season_codes = {"7DS", "7TS"}
    peak_single_codes = {"SDS"}
    offpeak_single_codes = {"SOS", "SVS", "CDS"}
    all_codes = season_codes | peak_single_codes | offpeak_single_codes
    print(f"  Fares: scanning T records for {'/'.join(sorted(all_codes))} fares...")

    season_fares = {}       # flow_id → fare_pence (int)
    peak_single_fares = {}  # flow_id → fare_pence (int)
    offpeak_single_fares = {}  # flow_id → fare_pence (int)

    with z.open(ffl_name) as f:
        for raw_line in f:
            line = raw_line.decode("latin-1", errors="replace")
            if len(line) < 20 or line[1] != "T":
                continue
            ticket_code = line[9:12]
            if ticket_code not in all_codes:
                continue
            flow_id = line[2:9]
            try:
                fare_pence = int(line[12:20].strip())
            except (ValueError, IndexError):
                continue
            if fare_pence <= 0:
                continue

            # Keep lowest fare per flow_id for each category
            if ticket_code in season_codes:
                if flow_id not in season_fares or fare_pence < season_fares[flow_id]:
                    season_fares[flow_id] = fare_pence
            elif ticket_code in peak_single_codes:
                if flow_id not in peak_single_fares or fare_pence < peak_single_fares[flow_id]:
                    peak_single_fares[flow_id] = fare_pence
            elif ticket_code in offpeak_single_codes:
                if flow_id not in offpeak_single_fares or fare_pence < offpeak_single_fares[flow_id]:
                    offpeak_single_fares[flow_id] = fare_pence

    print(f"  Fares: {len(season_fares):,} flows with season fares, "
          f"{len(peak_single_fares):,} peak single, {len(offpeak_single_fares):,} off-peak single")

    # Step 3: Second pass — resolve F records to CRS pairs
    # Collect all flow_ids that have ANY fare type
    all_fare_flows = set(season_fares) | set(peak_single_fares) | set(offpeak_single_fares)

    print("  Fares: resolving flows to CRS pairs (with reverse-direction support)...")
    pair_prices = {}   # (origin_crs, dest_crs) → annual_gbp (lowest season)
    pair_singles = {}  # (origin_crs, dest_crs) → {"peak_pence": int, "offpeak_pence": int}
    # Track which pairs were set by a forward (direct) flow so reverse never overwrites
    forward_season = set()   # set of (o_crs, d_crs) set by a direct F record
    forward_peak = set()
    forward_offpeak = set()
    resolved = 0
    unresolved = 0
    reverse_added = 0

    with z.open(ffl_name) as f:
        for raw_line in f:
            line = raw_line.decode("latin-1", errors="replace")
            if len(line) < 49 or line[1] != "F":
                continue
            flow_id = line[42:49]
            if flow_id not in all_fare_flows:
                continue

            origin_nlc = line[2:6]
            dest_nlc = line[6:10]
            # Direction flag: 'R' = reversible, 'S' = single direction
            direction = line[19] if len(line) > 19 else "S"

            origin_crs_set = _resolve_nlc(origin_nlc, nlc_to_crs, fsc_clusters, loc_groups)
            dest_crs_set = _resolve_nlc(dest_nlc, nlc_to_crs, fsc_clusters, loc_groups)

            if not origin_crs_set or not dest_crs_set:
                unresolved += 1
                continue

            # Build list of direction pairs to process
            # Forward direction always included; reverse only for 'R' flows
            dir_pairs = []
            for o_crs in origin_crs_set:
                for d_crs in dest_crs_set:
                    if o_crs == d_crs:
                        continue
                    dir_pairs.append(((o_crs, d_crs), False))  # (key, is_reverse)
                    if direction == "R":
                        dir_pairs.append(((d_crs, o_crs), True))

            for key, is_reverse in dir_pairs:
                # Season ticket: annual = weekly pence / 100 * 40
                if flow_id in season_fares:
                    annual_gbp = round(season_fares[flow_id] / 100.0 * 40, 2)
                    # Forward always wins; reverse only fills gaps or beats existing reverse
                    if is_reverse and key in forward_season:
                        pass  # don't overwrite a forward-specific fare
                    elif key not in pair_prices or annual_gbp < pair_prices[key]:
                        pair_prices[key] = annual_gbp
                        if not is_reverse:
                            forward_season.add(key)
                        resolved += 1

                # Single fares (keep lowest per pair; forward wins over reverse)
                if flow_id in peak_single_fares or flow_id in offpeak_single_fares:
                    if key not in pair_singles:
                        pair_singles[key] = {}

                    if flow_id in peak_single_fares:
                        peak = peak_single_fares[flow_id]
                        if is_reverse and key in forward_peak:
                            pass
                        elif "peak_pence" not in pair_singles[key] or peak < pair_singles[key]["peak_pence"]:
                            pair_singles[key]["peak_pence"] = peak
                            if not is_reverse:
                                forward_peak.add(key)

                    if flow_id in offpeak_single_fares:
                        offpeak = offpeak_single_fares[flow_id]
                        if is_reverse and key in forward_offpeak:
                            pass
                        elif "offpeak_pence" not in pair_singles[key] or offpeak < pair_singles[key]["offpeak_pence"]:
                            pair_singles[key]["offpeak_pence"] = offpeak
                            if not is_reverse:
                                forward_offpeak.add(key)

    # Count how many pairs were added purely from reverse flows
    reverse_season = len(pair_prices) - len(forward_season)
    reverse_singles = len(pair_singles) - len(forward_peak | forward_offpeak)

    print(f"  Fares: {len(pair_prices):,} CRS pairs with season tickets "
          f"({reverse_season:,} from reverse flows), "
          f"{len(pair_singles):,} with single fares "
          f"({reverse_singles:,} from reverse flows), "
          f"{unresolved:,} unresolvable flows skipped")

    z.close()
    return pair_prices, pair_singles
