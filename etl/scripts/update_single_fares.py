"""
update_single_fares.py — Download NR fares and backfill single fare prices.

Updates existing core_station_destinations rows with peak/offpeak single fares
WITHOUT truncating the table or re-running the full pipeline.

Safe to run while HSP punctuality fetch is in progress.

Usage (inside API container):
    python3 /app/scripts/update_single_fares.py
"""

import json
import os
import ssl
import sys
import urllib.request

import psycopg2

# Add parent paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from parsers.fares_parser import parse_fares

DB_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://ukproperty:ukproperty_dev@db:5432/ukproperty",
)
_NR_EMAIL = os.environ.get("NR_EMAIL", "")
_NR_PASSWORD = os.environ.get("NR_PASSWORD", "")
_FARES_ZIP = "/tmp/nr_fares.zip"


def _nr_authenticate():
    """Authenticate with NR Open Data portal, return token."""
    if not _NR_EMAIL or not _NR_PASSWORD:
        raise RuntimeError("NR_EMAIL and NR_PASSWORD env vars must be set")
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


def _download_fares():
    """Download NR fares ZIP (~46 MB)."""
    ctx = ssl._create_unverified_context()
    token = _nr_authenticate()
    print("Downloading fares (~46 MB)...")
    req = urllib.request.Request(
        "https://opendata.nationalrail.co.uk/api/staticfeeds/2.0/fares",
        headers={"X-Auth-Token": token},
    )
    with urllib.request.urlopen(req, timeout=300, context=ctx) as resp:
        with open(_FARES_ZIP, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
    size_mb = os.path.getsize(_FARES_ZIP) / 1024 / 1024
    print(f"Fares saved to {_FARES_ZIP} ({size_mb:.1f} MB)")


def main():
    # Download fares if not cached
    if not os.path.exists(_FARES_ZIP):
        _download_fares()
    else:
        size_mb = os.path.getsize(_FARES_ZIP) / 1024 / 1024
        print(f"Using cached fares at {_FARES_ZIP} ({size_mb:.1f} MB)")

    # Parse fares
    season_lookup, single_lookup = parse_fares(_FARES_ZIP)
    print(f"\nSeason tickets: {len(season_lookup):,} pairs")
    print(f"Single fares:   {len(single_lookup):,} pairs")

    # Connect and update
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Get existing pairs
    cur.execute(
        "SELECT origin_crs, dest_crs FROM core_station_destinations"
    )
    existing = set(cur.fetchall())
    print(f"\nExisting destination rows: {len(existing):,}")

    # Update single fares
    updated_single = 0
    for (orig, dest), fares in single_lookup.items():
        if (orig, dest) not in existing:
            continue
        peak = fares.get("peak_pence")
        offpeak = fares.get("offpeak_pence")
        if peak or offpeak:
            cur.execute(
                "UPDATE core_station_destinations "
                "SET peak_fare_pence = COALESCE(%s, peak_fare_pence), "
                "    offpeak_fare_pence = COALESCE(%s, offpeak_fare_pence) "
                "WHERE origin_crs = %s AND dest_crs = %s "
                "AND (peak_fare_pence IS NULL OR offpeak_fare_pence IS NULL)",
                (peak, offpeak, orig, dest),
            )
            if cur.rowcount > 0:
                updated_single += 1

    # Also update season tickets where missing
    updated_season = 0
    for (orig, dest), annual_gbp in season_lookup.items():
        if (orig, dest) not in existing:
            continue
        cur.execute(
            "UPDATE core_station_destinations "
            "SET season_ticket_gbp = %s "
            "WHERE origin_crs = %s AND dest_crs = %s "
            "AND season_ticket_gbp IS NULL",
            (annual_gbp, orig, dest),
        )
        if cur.rowcount > 0:
            updated_season += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nResults:")
    print(f"  Single fares updated: {updated_single:,}")
    print(f"  Season tickets updated: {updated_season:,}")
    print("Done.")


if __name__ == "__main__":
    main()
