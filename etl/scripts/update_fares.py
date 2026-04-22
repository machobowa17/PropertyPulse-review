#!/usr/bin/env python3
"""
Standalone script to backfill season_ticket_gbp in core_station_destinations.

Downloads NR fares ZIP (if not cached), parses it, and updates existing rows.
Does NOT re-run the full pipeline — only updates the season_ticket_gbp column.

Usage:
    python3 etl/scripts/update_fares.py [--db-url URL]

Default DB URL: postgresql://postgres@localhost:5432/ukproperty
"""

import json
import os
import ssl
import sys
import urllib.request

# Add parent dirs to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from parsers.fares_parser import parse_fares

_NR_EMAIL = "machobowa17@gmail.com"
_NR_PASSWORD = "!rpKQc6uRQLVgvt"
_FARES_ZIP = "/tmp/nr_fares.zip"
_DEFAULT_DB_URL = "postgresql://postgres@localhost:5432/ukproperty"


def _download_fares():
    """Download NR fares ZIP from data portal."""
    ctx = ssl._create_unverified_context()
    payload = json.dumps({"username": _NR_EMAIL, "password": _NR_PASSWORD}).encode()
    req = urllib.request.Request(
        "https://opendata.nationalrail.co.uk/authenticate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        token = json.loads(resp.read())["token"]

    print("Downloading fares ZIP (~46 MB)...")
    req2 = urllib.request.Request(
        "https://opendata.nationalrail.co.uk/api/staticfeeds/2.0/fares",
        headers={"X-Auth-Token": token},
    )
    with urllib.request.urlopen(req2, timeout=300, context=ctx) as resp2:
        with open(_FARES_ZIP, "wb") as f:
            while True:
                chunk = resp2.read(65536)
                if not chunk:
                    break
                f.write(chunk)
    print(f"Saved to {_FARES_ZIP}")


def main():
    import psycopg2

    db_url = _DEFAULT_DB_URL
    if "--db-url" in sys.argv:
        idx = sys.argv.index("--db-url")
        db_url = sys.argv[idx + 1]

    # Step 1: Download fares if not cached
    if not os.path.exists(_FARES_ZIP):
        _download_fares()
    else:
        print(f"Using cached fares at {_FARES_ZIP}")

    # Step 2: Parse fares
    fares_lookup = parse_fares(_FARES_ZIP)
    print(f"\n{len(fares_lookup):,} CRS pairs with season ticket prices")

    # Step 3: Update DB
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Get pairs that need prices
    cur.execute(
        "SELECT origin_crs, dest_crs FROM core_station_destinations "
        "WHERE season_ticket_gbp IS NULL"
    )
    pairs = cur.fetchall()
    print(f"{len(pairs):,} rows need season ticket prices")

    updated = 0
    for origin_crs, dest_crs in pairs:
        price = fares_lookup.get((origin_crs, dest_crs))
        if price is not None:
            cur.execute(
                "UPDATE core_station_destinations "
                "SET season_ticket_gbp = %s, updated_at = now() "
                "WHERE origin_crs = %s AND dest_crs = %s",
                (price, origin_crs, dest_crs),
            )
            updated += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nUpdated {updated:,} rows with season ticket prices")
    print(f"Coverage: {updated}/{len(pairs)} ({updated / max(len(pairs), 1) * 100:.1f}%)")


if __name__ == "__main__":
    main()
