"""
parsers/cif_parser.py — Parse ATOC-CIF timetable to extract per-station-pair metrics.

Input: ZIP file containing .MCA (CIF schedule data) and .MSN (master station names).
Output: dict[origin_crs] → list of top 5 destinations sorted by service frequency, each with:
    - dest_crs, dest_name, journey_min, trains_per_hour

Only counts weekday (Mon-Fri) schedules during AM peak (07:00-10:00) for commuter relevance.
"""

import csv
import os
import zipfile
from collections import defaultdict


def _parse_time(t):
    """Parse CIF time string 'HHMM' or 'HHMMH' (H=half-minute) → minutes since midnight."""
    t = t.strip()
    if not t or t == "0000":
        return None
    try:
        hh = int(t[0:2])
        mm = int(t[2:4])
        return hh * 60 + mm
    except (ValueError, IndexError):
        return None


def _load_tiploc_to_crs(msn_file=None, rail_ref_csv=None):
    """
    Build TIPLOC → (CRS, station_name) mapping.
    Uses MSN file from timetable ZIP if available, falls back to rail_references.csv.
    """
    mapping = {}

    # Primary: MSN file (more complete, includes bus/interchange TIPLOCs)
    if msn_file is not None:
        for raw_line in msn_file:
            line = raw_line.decode("latin-1", errors="replace").rstrip()
            if not line.startswith("A") or len(line) < 56:
                continue
            # MSN 'A' record format:
            #   0    : record type 'A'
            #   5-30 : station name (26 chars)
            #   36-42: TIPLOC (7 chars)
            #   43-45: subsidiary CRS (3 chars)
            #   49-51: main CRS (3 chars)
            name = line[5:31].strip()
            tiploc = line[36:43].strip()
            sub_crs = line[43:46].strip()
            main_crs = line[49:52].strip()
            # Use main CRS (resolves EL duplicates like LSX→LST, PDX→PAD)
            crs = main_crs if main_crs and len(main_crs) == 3 and main_crs.isalpha() else sub_crs
            if tiploc and crs and len(crs) == 3 and crs.isalpha():
                # Title-case the name (MSN uses ALL CAPS)
                name = name.title()
                # Fix common title-case issues
                for old, new in (("-On-", "-on-"), ("-Le-", "-le-"),
                                 ("-La-", "-la-"), ("-In-", "-in-"),
                                 ("-De-", "-de-"), ("'S ", "'s ")):
                    name = name.replace(old, new)
                # Strip EL/LL suffix for Elizabeth line duplicates
                if name.endswith(" El"):
                    name = name[:-3]
                if tiploc not in mapping:
                    mapping[tiploc] = (crs, name)

    # Fallback: rail_references.csv
    if rail_ref_csv and os.path.exists(rail_ref_csv):
        with open(rail_ref_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                tiploc = r.get("TiplocCode", "").strip()
                crs = r.get("CrsCode", "").strip()
                name = r.get("StationName", "").strip()
                # Strip suffix for clean name
                for suffix in (" Rail Station", " Station"):
                    if name.endswith(suffix):
                        name = name[: -len(suffix)]
                # Strip "London " prefix
                if name.startswith("London "):
                    name = name[7:]
                if tiploc and crs and tiploc not in mapping:
                    mapping[tiploc] = (crs, name)

    return mapping


def parse_timetable(zip_path, rail_ref_csv=None, top_n=None):
    """
    Parse ATOC-CIF timetable ZIP and return destinations per origin station.

    If top_n is None, returns ALL valid pairs (count >= 2).
    If top_n is set, truncates to top N by frequency per origin.

    Returns:
        dict[origin_crs] → [
            {"dest_crs": str, "dest_name": str, "journey_min": int, "trains_per_hour": float},
            ...  (up to top_n entries)
        ]
    """
    z = zipfile.ZipFile(zip_path)

    # Find the .MCA and .MSN files
    mca_name = None
    msn_name = None
    for name in z.namelist():
        if name.upper().endswith(".MCA"):
            mca_name = name
        elif name.upper().endswith(".MSN"):
            msn_name = name

    if not mca_name:
        raise FileNotFoundError("No .MCA file found in timetable ZIP")

    # Load TIPLOC mapping
    msn_file = z.open(msn_name) if msn_name else None
    tiploc_map = _load_tiploc_to_crs(msn_file, rail_ref_csv)
    if msn_file:
        msn_file.close()
    print(f"  CIF: loaded {len(tiploc_map):,} TIPLOC→CRS mappings")

    # Parse MCA: stream line-by-line to avoid loading 661MB into memory
    # Track per (origin_crs, dest_crs) → {total_journey_min, count}
    pair_stats = defaultdict(lambda: {"total_min": 0, "count": 0})

    current_schedule = None  # dict with uid, weekday, origin_tiploc, origin_dep_min
    schedule_count = 0
    pair_count = 0

    with z.open(mca_name) as f:
        for raw_line in f:
            line = raw_line.decode("latin-1", errors="replace")
            rec_type = line[0:2]

            if rec_type == "BS":
                # Basic Schedule header
                # Cols 21-27: days of week (MTWTFSS, 1/0)
                days = line[21:28]
                # Only count permanent schedules (P or empty), skip overlays/cancellations
                stp = line[79:80].strip() if len(line) > 79 else "P"
                # Check it runs on at least one weekday (Mon-Fri)
                has_weekday = any(d == "1" for d in days[0:5])

                if has_weekday and stp in ("P", "N", ""):
                    current_schedule = {"stops": []}
                    schedule_count += 1
                else:
                    current_schedule = None

            elif current_schedule is not None:
                if rec_type == "LO":
                    # Origin location
                    tiploc = line[2:9].strip()
                    dep = _parse_time(line[10:14])
                    if tiploc and dep is not None:
                        crs_info = tiploc_map.get(tiploc)
                        if crs_info:
                            current_schedule["stops"].append({
                                "crs": crs_info[0],
                                "name": crs_info[1],
                                "arr_min": None,
                                "dep_min": dep,
                            })

                elif rec_type == "LI":
                    # Intermediate location
                    tiploc = line[2:9].strip()
                    # Public arrival: cols 10-13, public departure: cols 15-18
                    arr = _parse_time(line[10:14])
                    dep = _parse_time(line[15:19])
                    if tiploc:
                        crs_info = tiploc_map.get(tiploc)
                        if crs_info and (arr is not None or dep is not None):
                            current_schedule["stops"].append({
                                "crs": crs_info[0],
                                "name": crs_info[1],
                                "arr_min": arr,
                                "dep_min": dep,
                            })

                elif rec_type == "LT":
                    # Terminating location
                    tiploc = line[2:9].strip()
                    arr = _parse_time(line[10:14])
                    if tiploc:
                        crs_info = tiploc_map.get(tiploc)
                        if crs_info and arr is not None:
                            current_schedule["stops"].append({
                                "crs": crs_info[0],
                                "name": crs_info[1],
                                "arr_min": arr,
                                "dep_min": None,
                            })

                    # End of schedule — process ALL boarding→alighting pairs
                    stops = current_schedule["stops"]
                    if len(stops) >= 2:
                        # For each stop where a passenger can board (has dep_min),
                        # count journeys to all subsequent stops where they can alight (has arr_min)
                        for i, origin in enumerate(stops):
                            board_time = origin["dep_min"]
                            if board_time is None:
                                continue
                            # Only count AM peak boarding (07:00-10:00)
                            if not (420 <= board_time < 600):
                                continue
                            for dest in stops[i + 1:]:
                                alight_time = dest["arr_min"] or dest["dep_min"]
                                if alight_time is None:
                                    continue
                                if dest["crs"] == origin["crs"]:
                                    continue
                                journey = alight_time - board_time
                                if 0 < journey < 480:  # sanity: under 8 hours
                                    key = (origin["crs"], dest["crs"])
                                    pair_stats[key]["total_min"] += journey
                                    pair_stats[key]["count"] += 1
                                    pair_stats[key]["dest_name"] = dest["name"]
                                    pair_count += 1

                    current_schedule = None

    print(f"  CIF: parsed {schedule_count:,} weekday schedules, {pair_count:,} station pairs")
    print(f"  CIF: {len(pair_stats):,} unique origin→dest pairs")

    # Aggregate: for each origin, find top N destinations by service count
    # trains_per_hour = count / 3 (AM peak is 3 hours: 07:00-10:00)
    origin_dests = defaultdict(list)
    for (orig_crs, dest_crs), stats in pair_stats.items():
        if stats["count"] >= 2:  # at least 2 services to be meaningful
            avg_journey = round(stats["total_min"] / stats["count"])
            trains_per_hr = round(stats["count"] / 3.0, 1)
            origin_dests[orig_crs].append({
                "dest_crs": dest_crs,
                "dest_name": stats["dest_name"],
                "journey_min": avg_journey,
                "trains_per_hour": trains_per_hr,
            })

    # Sort by frequency; optionally truncate
    result = {}
    for orig_crs, dests in origin_dests.items():
        dests.sort(key=lambda d: -d["trains_per_hour"])
        result[orig_crs] = dests[:top_n] if top_n else dests

    total_pairs = sum(len(v) for v in result.values())
    label = f"top-{top_n}" if top_n else "all"
    print(f"  CIF: {len(result):,} origin stations, {total_pairs:,} pairs ({label})")
    return result
