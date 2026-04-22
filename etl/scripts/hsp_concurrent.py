"""
hsp_concurrent.py — Fetch HSP punctuality data using concurrent requests.

Uses ThreadPoolExecutor to run 20 parallel requests, reducing total time
from ~33 hours (sequential) to ~1-2 hours.

Usage (inside API container):
    python3 /app/scripts/hsp_concurrent.py
"""

import base64
import json
import logging
import os
import ssl
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

DB_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://ukproperty:ukproperty_dev@db:5432/ukproperty",
)
NR_EMAIL = os.environ.get("NR_EMAIL", "")
NR_PASSWORD = os.environ.get("NR_PASSWORD", "")
HSP_URL = "https://hsp-prod.rockshore.net/api/v1/serviceMetrics"
WORKERS = 20
CHECKPOINT_PATH = "/tmp/hsp_checkpoint.json"
CHECKPOINT_INTERVAL = 200


def _hsp_request(from_crs, to_crs, creds_b64):
    """Query HSP for one station pair. Returns pct_on_time or None."""
    import datetime
    today = datetime.date.today()
    to_date = today.strftime("%Y-%m-%d")
    from_date = (today - datetime.timedelta(days=182)).strftime("%Y-%m-%d")

    ctx = ssl._create_unverified_context()
    payload = json.dumps({
        "from_loc": from_crs,
        "to_loc": to_crs,
        "from_time": "0700",
        "to_time": "1000",
        "from_date": from_date,
        "to_date": to_date,
        "days": "WEEKDAY",
        "tolerance": ["5"],
    }).encode()

    req = urllib.request.Request(
        HSP_URL,
        data=payload,
        headers={
            "Authorization": f"Basic {creds_b64}",
            "Content-Type": "application/json",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30, context=ctx)
        result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            logger.warning("Rate limited! Backing off...")
            time.sleep(5)
        return None
    except Exception:
        return None

    services = result.get("Services", [])
    if not services:
        return None

    total_matched = 0
    total_on_time = 0.0
    for s in services:
        matched = int(s.get("serviceAttributesMetrics", {}).get("matched_services", 0))
        for m in s.get("Metrics", []):
            if m.get("tolerance_value") == "5":
                pct = float(m.get("percent_tolerance", 0))
                total_on_time += pct * matched
                total_matched += matched
                break

    if total_matched == 0:
        return None
    return round(total_on_time / total_matched, 1)


def _fetch_one(pair, creds_b64):
    """Fetch one pair, return (origin, dest, pct_on_time)."""
    orig, dest = pair
    pct = _hsp_request(orig, dest, creds_b64)
    return (orig, dest, pct)


def main():
    if not NR_EMAIL or not NR_PASSWORD:
        print("ERROR: NR_EMAIL and NR_PASSWORD env vars must be set")
        sys.exit(1)

    creds_b64 = base64.b64encode(f"{NR_EMAIL}:{NR_PASSWORD}".encode()).decode()

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get all pairs needing punctuality
    cur.execute(
        "SELECT origin_crs, dest_crs FROM core_station_destinations "
        "WHERE pct_on_time IS NULL ORDER BY origin_crs, dest_crs"
    )
    all_pairs = cur.fetchall()
    total = len(all_pairs)

    # Load checkpoint
    completed = set()
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, "r") as f:
            completed = set(tuple(x) for x in json.load(f))
        print(f"Resuming from checkpoint: {len(completed):,} already done")

    # Filter out completed pairs
    pairs = [(o, d) for o, d in all_pairs if (o, d) not in completed]
    print(f"HSP concurrent: {len(pairs):,} pairs to fetch ({WORKERS} workers)")

    updated = 0
    processed = 0
    t0 = time.time()
    batch_size = WORKERS * 5  # Process in batches of 100

    for batch_start in range(0, len(pairs), batch_size):
        batch = pairs[batch_start:batch_start + batch_size]

        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {
                executor.submit(_fetch_one, pair, creds_b64): pair
                for pair in batch
            }

            for future in as_completed(futures):
                orig, dest, pct = future.result()

                if pct is not None:
                    cur.execute(
                        "UPDATE core_station_destinations SET pct_on_time = %s "
                        "WHERE origin_crs = %s AND dest_crs = %s",
                        (pct, orig, dest),
                    )
                    updated += 1

                completed.add((orig, dest))
                processed += 1

        # Checkpoint after each batch
        conn.commit()
        with open(CHECKPOINT_PATH, "w") as f:
            json.dump(list(completed), f)
        elapsed = time.time() - t0
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = (len(pairs) - processed) / rate if rate > 0 else 0
        pct_done = len(completed) / (total + len(completed) - len(pairs)) * 100
        print(
            f"  {processed:,}/{len(pairs):,} ({pct_done:.1f}%) — "
            f"{updated:,} updated — "
            f"{rate:.1f} req/s — "
            f"ETA {remaining/60:.0f} min",
            flush=True,
        )

    conn.commit()
    cur.close()
    conn.close()

    # Clean up checkpoint
    if os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)

    elapsed = time.time() - t0
    print(f"\nHSP COMPLETE: {updated:,} pairs updated, "
          f"{total - updated:,} no data, "
          f"{elapsed/60:.1f} minutes total")


if __name__ == "__main__":
    main()
