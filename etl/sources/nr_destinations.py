"""
sources/nr_destinations.py — Populate core_station_destinations with multi-modal commute data.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns number of rows written)

Pipeline:
  Phase A — Parse NR CIF timetable to get candidate destination pairs.
            Score using data-driven importance (how many origins serve each dest).
            Filter by 120 min journey cap, keep up to 10 per origin (smart cutoff).
  Phase B — Enrich with MOTIS API (multi-modal routes, legs, modes).
            Self-hosted on Hetzner (env: MOTIS_BASE_URL).
            2 req/sec rate limit, checkpointable. Skip with SKIP_ROUTING=1.
  Phase C — Parse NR fares for season ticket prices, insert all rows.
  Phase D — (Optional) Fetch HSP punctuality. Skip with SKIP_HSP=1.

Run AFTER station_enrichment (needs CRS codes populated).
"""

import json
import os
import ssl
import time
import urllib.request

import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ANNUAL, TABLE_NAMES
from lib.motis import motis_journey, MOTIS_BASE_URL

# Maximum journey time for commute relevance (minutes).
MAX_JOURNEY_MIN = 120

# Smart cutoff: stop adding destinations when score drops below this
# fraction of the top-scoring destination.
SCORE_CUTOFF_RATIO = 0.05

# Maximum destinations per origin station.
MAX_DESTINATIONS = 10

# Working days per year for annual fare estimates.
WORKING_DAYS_PER_YEAR = 230

METADATA = {
    "name":               "nr_destinations",
    "description":        "Multi-modal commute destinations per NR station (timetable + MOTIS)",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         ["station_enrichment"],
    "tables_written":     [TABLE_NAMES["station_destinations"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (5_000, 30_000),
}

_NR_EMAIL = os.environ.get("NR_EMAIL", "")
_NR_PASSWORD = os.environ.get("NR_PASSWORD", "")
_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_TIMETABLE_ZIP = "/tmp/nr_timetable.zip"
_FARES_ZIP = "/tmp/nr_fares.zip"
_ROUTING_CHECKPOINT_PATH = "/tmp/motis_journey_checkpoint.json"
_CRS_NAPTAN_PATH = os.path.join(_ETL_DATA_DIR, "crs_naptan_mapping.json")


# ── NR feed download helpers ──��──────────────────────────────────────────────

def _nr_authenticate():
    """Authenticate with NR Open Data portal, return token."""
    if not _NR_EMAIL or not _NR_PASSWORD:
        raise RuntimeError("NR_EMAIL and NR_PASSWORD env vars must be set for NR API access")
    ctx = ssl._create_unverified_context()
    payload = json.dumps({"username": _NR_EMAIL, "password": _NR_PASSWORD}).encode()
    req = urllib.request.Request(
        "https://opendata.nationalrail.co.uk/authenticate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        return json.loads(resp.read())["token"]


def _download_feed(url, dest_path, label):
    """Download a static feed from NR Open Data portal."""
    ctx = ssl._create_unverified_context()
    token = _nr_authenticate()
    print(f"  Downloading {label}...")
    req = urllib.request.Request(url, headers={"X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=300, context=ctx) as resp:
        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
    print(f"  {label} saved to {dest_path}")


def _download_timetable():
    _download_feed(
        "https://opendata.nationalrail.co.uk/api/staticfeeds/3.0/timetable",
        _TIMETABLE_ZIP,
        "timetable (~70 MB)",
    )


def _download_fares():
    _download_feed(
        "https://opendata.nationalrail.co.uk/api/staticfeeds/2.0/fares",
        _FARES_ZIP,
        "fares (~46 MB)",
    )


# ── Phase A: Candidate selection with data-driven scoring ─────────────────

def _select_candidates(all_pairs):
    """
    Score destinations by frequency × importance, apply journey cap and smart cutoff.
    Returns dict: {origin_crs: [dest_dicts]} with up to MAX_DESTINATIONS per origin.
    """
    # Compute data-driven importance: how many distinct origins serve each destination.
    dest_origin_count = {}
    for origin_crs, dests in all_pairs.items():
        for d in dests:
            dc = d["dest_crs"]
            if dc not in dest_origin_count:
                dest_origin_count[dc] = set()
            dest_origin_count[dc].add(origin_crs)
    importance = {crs: len(origins) for crs, origins in dest_origin_count.items()}

    total_pairs = sum(len(v) for v in all_pairs.values())
    print(f"  Importance computed: {len(importance):,} destinations from {total_pairs:,} pairs")
    top_5 = sorted(importance.items(), key=lambda x: -x[1])[:5]
    print(f"  Top 5 by importance: {', '.join(f'{c}={n}' for c, n in top_5)}")

    result = {}
    for origin_crs, dests in all_pairs.items():
        # Filter by journey time cap
        scored = []
        for d in dests:
            if d["journey_min"] is not None and d["journey_min"] > MAX_JOURNEY_MIN:
                continue
            w = importance.get(d["dest_crs"], 1)
            d["score"] = d["trains_per_hour"] * w
            scored.append(d)

        if not scored:
            continue

        scored.sort(key=lambda d: -d["score"])

        # Smart cutoff: stop when score drops below threshold
        top_score = scored[0]["score"]
        cutoff = top_score * SCORE_CUTOFF_RATIO
        selected = []
        for d in scored[:MAX_DESTINATIONS]:
            if d["score"] < cutoff and len(selected) >= 3:
                break
            selected.append(d)

        result[origin_crs] = selected

    total = sum(len(v) for v in result.values())
    print(f"  Candidates: {len(result):,} origins, {total:,} destination rows "
          f"(max {MAX_DESTINATIONS}/origin, {MAX_JOURNEY_MIN} min cap)")
    return result


# ── Phase B: MOTIS journey enrichment ─────────────────────────────────────

def _load_crs_mapping():
    """Load CRS → {atco, lat, lon} mapping from JSON file."""
    if not os.path.exists(_CRS_NAPTAN_PATH):
        print(f"  WARNING: {_CRS_NAPTAN_PATH} not found — run build_tfl_mapping.py first")
        return {}
    with open(_CRS_NAPTAN_PATH) as f:
        return json.load(f)


def _enrich_with_motis(candidates, crs_mapping, rate_limit=0.5):
    """
    Enrich candidate destinations with MOTIS journey data.
    Modifies candidates in-place. Checkpoints progress.

    Args:
        candidates: dict {origin_crs: [dest_dicts]}
        crs_mapping: dict {crs: {"atco": str, "lat": float, "lon": float}}
        rate_limit: seconds between API calls (0.5 = 2/sec)

    Returns:
        (enriched_count, skipped_count, error_count)
    """
    # Build flat list of all pairs for progress tracking
    all_pairs = []
    for origin_crs, dests in candidates.items():
        for d in dests:
            all_pairs.append((origin_crs, d["dest_crs"]))
    total = len(all_pairs)

    # Load checkpoint
    completed = {}
    if os.path.exists(_ROUTING_CHECKPOINT_PATH):
        with open(_ROUTING_CHECKPOINT_PATH) as f:
            completed = json.load(f)
        print(f"  MOTIS: resuming from checkpoint ({len(completed):,}/{total:,} done)")

    enriched = 0
    skipped = 0
    errors = 0
    processed = len(completed)

    for origin_crs, dests in candidates.items():
        for d in dests:
            pair_key = f"{origin_crs}:{d['dest_crs']}"
            if pair_key in completed:
                # Apply cached result
                cached = completed[pair_key]
                if cached:
                    d.update(cached)
                    d["journey_type"] = "multi_modal"
                    enriched += 1
                else:
                    d["journey_type"] = "direct"
                    skipped += 1
                continue

            from_entry = crs_mapping.get(origin_crs, {})
            to_entry = crs_mapping.get(d["dest_crs"], {})
            from_lat = from_entry.get("lat")
            from_lon = from_entry.get("lon")
            to_lat = to_entry.get("lat")
            to_lon = to_entry.get("lon")

            if not from_lat or not to_lat:
                completed[pair_key] = None
                d["journey_type"] = "direct"
                skipped += 1
                processed += 1
                continue

            result = motis_journey(from_lat, from_lon, to_lat, to_lon)

            if result:
                d.update(result)
                # Overwrite journey_min with MOTIS total duration
                if result.get("journey_min"):
                    d["journey_min"] = result["journey_min"]
                d["journey_type"] = "multi_modal"
                completed[pair_key] = {
                    k: result[k] for k in ("journey_min", "num_changes", "modes", "legs")
                }
                enriched += 1
            else:
                completed[pair_key] = None
                d["journey_type"] = "direct"
                errors += 1

            processed += 1

            # Checkpoint every 200 requests
            if processed % 200 == 0:
                with open(_ROUTING_CHECKPOINT_PATH, "w") as f:
                    json.dump(completed, f)
                pct = processed / total * 100
                print(f"  MOTIS: {processed:,}/{total:,} ({pct:.1f}%) — "
                      f"{enriched} enriched, {skipped} no coords, {errors} API errors")

            time.sleep(rate_limit)

    # Final checkpoint cleanup
    if os.path.exists(_ROUTING_CHECKPOINT_PATH):
        os.remove(_ROUTING_CHECKPOINT_PATH)

    print(f"  MOTIS: done — {enriched:,} enriched, {skipped:,} skipped, {errors:,} errors")
    return enriched, skipped, errors


# ── Main run function ───────────���──────────────��──────────────────────────

def run(db_url):
    """Parse timetable, score, enrich with MOTIS, insert into DB."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from parsers.cif_parser import parse_timetable
    from parsers.fares_parser import parse_fares
    from parsers.hsp_fetcher import fetch_all_punctuality

    # ── Phase A: Parse timetable + select candidates ──────────────────────

    if not os.path.exists(_TIMETABLE_ZIP):
        _download_timetable()
    else:
        print(f"  Using cached timetable at {_TIMETABLE_ZIP}")

    rail_ref_csv = os.path.join(_ETL_DATA_DIR, "rail_references.csv")
    all_pairs = parse_timetable(_TIMETABLE_ZIP, rail_ref_csv=rail_ref_csv, top_n=None)
    candidates = _select_candidates(all_pairs)

    # ── Phase B: MOTIS journey enrichment ─────────────────────────────────

    skip_routing = os.environ.get("SKIP_ROUTING", "0") == "1"
    if not skip_routing:
        crs_mapping = _load_crs_mapping()
        if crs_mapping:
            print(f"  Loaded CRS mapping: {len(crs_mapping):,} stations")
            print(f"  MOTIS endpoint: {MOTIS_BASE_URL}")
            _enrich_with_motis(candidates, crs_mapping, rate_limit=0.5)
        else:
            print("  Skipping MOTIS enrichment (no mapping file)")
    else:
        print("  Skipping MOTIS enrichment (SKIP_ROUTING=1)")

    # ── Phase C: Fares + DB insert ────────────────────────────────────────

    if not os.path.exists(_FARES_ZIP):
        _download_fares()
    else:
        print(f"  Using cached fares at {_FARES_ZIP}")
    season_lookup, single_lookup = parse_fares(_FARES_ZIP)
    print(f"  Fares: {len(season_lookup):,} season ticket pairs, "
          f"{len(single_lookup):,} single fare pairs")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(f"TRUNCATE {TABLE_NAMES['station_destinations']}")

    rows = []
    season_matched = 0
    single_matched = 0
    for origin_crs, dests in candidates.items():
        for rank, d in enumerate(dests, 1):
            pair_key = (origin_crs, d["dest_crs"])

            # Season ticket from NR fares parser (Travelcard backfill runs separately)
            season_ticket = season_lookup.get(pair_key)
            if season_ticket is not None:
                season_matched += 1

            # Single fares from NR fares parser
            singles = single_lookup.get(pair_key, {})
            peak_pence = singles.get("peak_pence")
            offpeak_pence = singles.get("offpeak_pence")
            if peak_pence or offpeak_pence:
                single_matched += 1

            journey_type = d.get("journey_type", "direct")
            num_changes = d.get("num_changes", 0)
            modes = d.get("modes")
            legs = json.dumps(d.get("legs")) if d.get("legs") else None

            rows.append((
                origin_crs, d["dest_crs"], d["dest_name"],
                d["journey_min"], d["trains_per_hour"],
                None, season_ticket, rank,
                journey_type, num_changes, modes,
                peak_pence, offpeak_pence, None, legs, None,
            ))

    execute_values(
        cur,
        f"""INSERT INTO {TABLE_NAMES['station_destinations']}
            (origin_crs, dest_crs, dest_name, journey_min, trains_per_hour,
             pct_on_time, season_ticket_gbp, rank,
             journey_type, num_changes, modes,
             peak_fare_pence, offpeak_fare_pence, fare_zones, legs, fare_caveats)
            VALUES %s""",
        rows,
        template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
    )
    conn.commit()
    print(f"  Inserted {len(rows):,} destination rows "
          f"({season_matched:,} with season ticket, {single_matched:,} with single fares)")

    cur.close()
    conn.close()

    # ── Phase D: HSP punctuality (optional, ~1.8 hours) ───────────────────

    skip_hsp = os.environ.get("SKIP_HSP", "0") == "1"
    if not skip_hsp:
        print("  Starting HSP punctuality fetch (this takes ~1-2 hours)...")
        fetch_all_punctuality(db_url, rate_limit=0.5)
    else:
        print("  Skipping HSP fetch (SKIP_HSP=1)")

    return len(rows)
