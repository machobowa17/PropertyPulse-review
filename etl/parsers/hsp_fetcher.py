"""
parsers/hsp_fetcher.py — Fetch HSP (Historical Service Performance) punctuality data.

For each station pair in core_station_destinations, queries the NR HSP API
to get the % on-time (5-minute tolerance) for weekday AM peak services.

Rate-limited to 2 requests/second to stay within NR fair usage.
Checkpoints progress to disk for resumability.
"""

import base64
import json
import logging
import os
import ssl
import time
import urllib.request

logger = logging.getLogger(__name__)

_NR_EMAIL = os.environ.get("NR_EMAIL", "")
_NR_PASSWORD = os.environ.get("NR_PASSWORD", "")
_HSP_URL = "https://hsp-prod.rockshore.net/api/v1/serviceMetrics"
_CHECKPOINT_PATH = "/tmp/hsp_checkpoint.json"


def _hsp_request(from_crs, to_crs, creds_b64):
    """Query HSP for one station pair. Returns pct_on_time or None."""
    import datetime
    # Rolling 6-month lookback from today
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
        _HSP_URL,
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
        logger.warning("HSP HTTP %d for %s→%s", e.code, from_crs, to_crs)
        return None
    except Exception as e:
        logger.warning("HSP error for %s→%s: %s", from_crs, to_crs, e)
        return None

    services = result.get("Services", [])
    if not services:
        return None

    # Weighted average across all services at 5-min tolerance
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


def fetch_all_punctuality(db_url, rate_limit=0.5):
    """
    Fetch HSP punctuality for all pairs in core_station_destinations.
    Updates pct_on_time column in-place. Checkpoints progress.

    Args:
        db_url: PostgreSQL connection string
        rate_limit: seconds between requests (default 0.5 = 2/sec)

    Returns:
        int: number of pairs updated
    """
    import psycopg2

    if not _NR_EMAIL or not _NR_PASSWORD:
        raise RuntimeError("NR_EMAIL and NR_PASSWORD env vars must be set for HSP API access")
    creds_b64 = base64.b64encode(
        f"{_NR_EMAIL}:{_NR_PASSWORD}".encode()
    ).decode()

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Get all pairs that need punctuality data
    cur.execute(
        "SELECT origin_crs, dest_crs FROM core_station_destinations "
        "WHERE pct_on_time IS NULL ORDER BY origin_crs, dest_crs"
    )
    pairs = cur.fetchall()
    total = len(pairs)
    print(f"  HSP: {total:,} pairs to fetch")

    # Load checkpoint
    completed = set()
    if os.path.exists(_CHECKPOINT_PATH):
        with open(_CHECKPOINT_PATH, "r") as f:
            completed = set(tuple(x) for x in json.load(f))
        print(f"  HSP: resuming from checkpoint ({len(completed):,} already done)")

    updated = 0
    errors = 0

    for i, (orig, dest) in enumerate(pairs):
        if (orig, dest) in completed:
            continue

        pct = _hsp_request(orig, dest, creds_b64)

        if pct is not None:
            cur.execute(
                "UPDATE core_station_destinations SET pct_on_time = %s "
                "WHERE origin_crs = %s AND dest_crs = %s",
                (pct, orig, dest),
            )
            updated += 1
        else:
            errors += 1

        completed.add((orig, dest))

        # Checkpoint every 100 requests
        if len(completed) % 100 == 0:
            conn.commit()
            with open(_CHECKPOINT_PATH, "w") as f:
                json.dump(list(completed), f)
            elapsed_pct = len(completed) / total * 100
            print(f"  HSP: {len(completed):,}/{total:,} ({elapsed_pct:.1f}%) — "
                  f"{updated} updated, {errors} errors")

        time.sleep(rate_limit)

    conn.commit()
    cur.close()
    conn.close()

    # Clean up checkpoint
    if os.path.exists(_CHECKPOINT_PATH):
        os.remove(_CHECKPOINT_PATH)

    print(f"  HSP: done — {updated:,} pairs updated, {errors:,} no data")
    return updated
