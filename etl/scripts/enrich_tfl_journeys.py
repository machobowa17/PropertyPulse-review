"""
Standalone script to enrich existing core_station_destinations rows with
TfL Journey Planner data.

Run on EC2:
    python3 enrich_tfl_journeys.py

Reads existing rows, calls TfL API for each pair, updates in-place.
Checkpointable — safe to interrupt and resume.

Expects crs_naptan_mapping.json to exist in etl/data/.
"""

import datetime
import json
import os
import re
import sys
import time
import urllib.request

import psycopg2

DB_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    os.environ.get(
        "DATABASE_URL",
        "postgresql://ukproperty:ukproperty_dev@db:5432/ukproperty"
    ),
)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_MAPPING_PATH = os.path.join(_DATA_DIR, "crs_naptan_mapping.json")
_CHECKPOINT_PATH = "/tmp/tfl_enrich_checkpoint.json"
_TFL_BASE = "https://api.tfl.gov.uk/Journey/JourneyResults"
WORKING_DAYS_PER_YEAR = 230


def load_mapping():
    with open(_MAPPING_PATH) as f:
        return json.load(f)


def tfl_journey(from_lat, from_lon, to_lat, to_lon, depart_time="0800"):
    """Call TfL Journey Planner, return parsed dict or None."""
    now = datetime.date.today()
    if now.weekday() >= 5:
        now += datetime.timedelta(days=(7 - now.weekday()))
    date_str = now.strftime("%Y%m%d")

    url = (
        "%s/%s,%s/to/%s,%s?date=%s&time=%s&timeIs=Departing"
        % (_TFL_BASE, from_lat, from_lon, to_lat, to_lon, date_str, depart_time)
    )

    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; PropertyPulse/1.0)",
        })
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None

    journeys = data.get("journeys", [])
    if not journeys:
        return None

    best = min(journeys, key=lambda j: j.get("duration", 999))

    legs = []
    modes_set = set()
    for leg in best.get("legs", []):
        mode_id = leg.get("mode", {}).get("id", "unknown")
        modes_set.add(mode_id)
        ld = {
            "mode": mode_id,
            "summary": leg.get("instruction", {}).get("summary", ""),
            "duration": leg.get("duration", 0),
        }
        route_opts = leg.get("routeOptions", [])
        if route_opts:
            ld["line"] = route_opts[0].get("name", "")
        dep = leg.get("departurePoint", {})
        arr = leg.get("arrivalPoint", {})
        if dep.get("commonName"):
            ld["from"] = dep["commonName"]
        if arr.get("commonName"):
            ld["to"] = arr["commonName"]
        dt = leg.get("departureTime", "")
        at = leg.get("arrivalTime", "")
        if dt and len(dt) > 16:
            ld["depart"] = dt[11:16]
        if at and len(at) > 16:
            ld["arrive"] = at[11:16]
        if leg.get("distance"):
            ld["distance_m"] = round(leg["distance"])
        legs.append(ld)

    transport_legs = [l for l in legs if l["mode"] not in ("walking", "cycle")]
    num_changes = max(0, len(transport_legs) - 1)

    fare_obj = best.get("fare", {})
    peak_fare = fare_obj.get("totalCost")
    offpeak_fare = None
    fare_zones = None
    fare_caveats = []

    for fi in fare_obj.get("fares", []):
        if fi.get("peak") is not None:
            peak_fare = fi["peak"]
        if fi.get("offPeak") is not None:
            offpeak_fare = fi["offPeak"]
        lz = fi.get("lowZone")
        hz = fi.get("highZone")
        if lz is not None and hz is not None:
            fare_zones = "%s-%s" % (lz, hz) if lz != hz else str(lz)

    for cav in fare_obj.get("caveats", []):
        txt = cav.get("text", "")
        if txt:
            txt = re.sub(r"<[^>]+>", "", txt).strip()
            if txt:
                fare_caveats.append(txt)

    return {
        "duration": best.get("duration"),
        "num_changes": num_changes,
        "modes": sorted(modes_set),
        "peak_fare_pence": peak_fare,
        "offpeak_fare_pence": offpeak_fare,
        "fare_zones": fare_zones,
        "fare_caveats": fare_caveats,
        "legs": legs,
    }


def main():
    mapping = load_mapping()
    print("Loaded CRS mapping: %d stations" % len(mapping))

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get all pairs that need enrichment
    cur.execute(
        "SELECT origin_crs, dest_crs FROM core_station_destinations "
        "WHERE journey_type = 'direct' OR journey_type IS NULL "
        "ORDER BY origin_crs, dest_crs"
    )
    pairs = cur.fetchall()
    total = len(pairs)
    print("Pairs to enrich: %d" % total)

    # Load checkpoint
    completed = set()
    if os.path.exists(_CHECKPOINT_PATH):
        with open(_CHECKPOINT_PATH) as f:
            completed = set(tuple(x) for x in json.load(f))
        print("Resuming from checkpoint: %d done" % len(completed))

    enriched = 0
    skipped = 0
    errors = 0
    processed = len(completed)

    for orig, dest in pairs:
        if (orig, dest) in completed:
            continue

        from_entry = mapping.get(orig, {})
        to_entry = mapping.get(dest, {})
        from_lat = from_entry.get("lat")
        from_lon = from_entry.get("lon")
        to_lat = to_entry.get("lat")
        to_lon = to_entry.get("lon")

        if not from_lat or not to_lat:
            completed.add((orig, dest))
            skipped += 1
            processed += 1
            continue

        result = tfl_journey(from_lat, from_lon, to_lat, to_lon)

        if result:
            season_est = None
            if result["peak_fare_pence"]:
                season_est = round(result["peak_fare_pence"] / 100.0 * WORKING_DAYS_PER_YEAR, 2)

            cur.execute(
                """UPDATE core_station_destinations SET
                    journey_type = 'multi_modal',
                    journey_min = %s,
                    num_changes = %s,
                    modes = %s,
                    peak_fare_pence = %s,
                    offpeak_fare_pence = %s,
                    fare_zones = %s,
                    legs = %s,
                    fare_caveats = %s,
                    season_ticket_gbp = COALESCE(season_ticket_gbp, %s)
                WHERE origin_crs = %s AND dest_crs = %s""",
                (
                    result["duration"],
                    result["num_changes"],
                    result["modes"],
                    result["peak_fare_pence"],
                    result["offpeak_fare_pence"],
                    result["fare_zones"],
                    json.dumps(result["legs"]),
                    result["fare_caveats"] or None,
                    season_est,
                    orig, dest,
                )
            )
            enriched += 1
        else:
            errors += 1

        completed.add((orig, dest))
        processed += 1

        # Checkpoint + commit every 100
        if processed % 100 == 0:
            conn.commit()
            with open(_CHECKPOINT_PATH, "w") as f:
                json.dump(list(completed), f)
            pct = processed / total * 100
            print("  %d/%d (%.1f%%) — %d enriched, %d skipped, %d errors"
                  % (processed, total, pct, enriched, skipped, errors))

        time.sleep(0.15)  # ~6 req/sec (well under 500/min)

        # Print progress every 10 pairs
        if processed % 10 == 0:
            sys.stdout.write(".")
            sys.stdout.flush()

    conn.commit()
    cur.close()
    conn.close()

    if os.path.exists(_CHECKPOINT_PATH):
        os.remove(_CHECKPOINT_PATH)

    print("Done: %d enriched, %d skipped (no coords), %d API errors" % (enriched, skipped, errors))


if __name__ == "__main__":
    main()
