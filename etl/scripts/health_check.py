#!/usr/bin/env python3
"""
health_check.py -- Travel module data health check.

Queries the database and reports coverage, freshness, and anomalies.
Designed to run after ETL cron jobs so operators can verify data integrity
without manually inspecting tables.

Usage (inside API container):
    python3 /app/scripts/health_check.py

Exit codes:
    0 = healthy
    1 = warnings (some metrics below target but not critical)
    2 = critical (data missing or severely degraded)
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import psycopg2

DB_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://ukproperty:ukproperty_dev@db:5432/ukproperty",
)

# Thresholds
MIN_DESTINATIONS = 10_000       # Critical if below
MIN_MOTIS_PCT = 90.0            # Warning if below
MIN_FARE_PCT = 40.0             # Warning if below
MIN_HSP_PCT = 5.0               # Warning if below (HSP is sparse)
MAX_STALE_DAYS = 90             # Warning if last update older than this
MAX_ZERO_FARES = 50             # Warning if more than this many zero-fare rows


def _pct(num, denom):
    return (num / denom * 100) if denom > 0 else 0.0


def _icon(ok):
    return "\u2713" if ok else "\u26a0"


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    warnings = []
    critical = []

    # 1. Destination row count
    cur.execute("SELECT COUNT(*) FROM core_station_destinations")
    dest_count = cur.fetchone()[0]
    if dest_count < MIN_DESTINATIONS:
        critical.append(f"Destinations: {dest_count:,} (critical, min {MIN_DESTINATIONS:,})")

    # 2. MOTIS coverage (legs populated)
    cur.execute("SELECT COUNT(*) FROM core_station_destinations WHERE legs IS NOT NULL")
    motis_count = cur.fetchone()[0]
    motis_pct = _pct(motis_count, dest_count)
    if motis_pct < MIN_MOTIS_PCT:
        warnings.append(f"MOTIS legs: {motis_pct:.1f}% (target: {MIN_MOTIS_PCT}%+)")

    # 3. Fare coverage (any pricing)
    cur.execute("""
        SELECT COUNT(*) FROM core_station_destinations
        WHERE peak_fare_pence IS NOT NULL
           OR season_ticket_gbp IS NOT NULL
    """)
    fare_count = cur.fetchone()[0]
    fare_pct = _pct(fare_count, dest_count)
    if fare_pct < MIN_FARE_PCT:
        warnings.append(f"Fares: {fare_pct:.1f}% (target: {MIN_FARE_PCT}%+)")

    # 4. HSP punctuality
    cur.execute("SELECT COUNT(*) FROM core_station_destinations WHERE pct_on_time IS NOT NULL")
    hsp_count = cur.fetchone()[0]
    hsp_pct = _pct(hsp_count, dest_count)
    if hsp_pct < MIN_HSP_PCT:
        warnings.append(f"HSP punctuality: {hsp_pct:.1f}% (target: {MIN_HSP_PCT}%+)")

    # 5. Travelcard count
    cur.execute("SELECT COUNT(*) FROM core_station_destinations WHERE is_travelcard = TRUE")
    tc_count = cur.fetchone()[0]

    # 6. Station counts by type
    cur.execute("""
        SELECT stop_type, COUNT(*)
        FROM core_transport_stops
        WHERE stop_type IN ('RLY', 'MET', 'PLT', 'BUS', 'FER')
        GROUP BY stop_type
        ORDER BY stop_type
    """)
    station_counts = dict(cur.fetchall())

    # 7. Data freshness
    cur.execute("SELECT MAX(updated_at) FROM core_station_destinations")
    last_updated = cur.fetchone()[0]
    stale = False
    if last_updated:
        now = datetime.now(timezone.utc) if last_updated.tzinfo else datetime.now()
        age_days = (now - last_updated).days
        if age_days > MAX_STALE_DAYS:
            stale = True
            warnings.append(f"Data stale: last updated {age_days} days ago (max {MAX_STALE_DAYS})")
    else:
        stale = True
        critical.append("No updated_at timestamps found")

    # 8. Zero-fare anomalies
    cur.execute("""
        SELECT COUNT(*) FROM core_station_destinations
        WHERE peak_fare_pence = 0 AND offpeak_fare_pence = 0
    """)
    zero_fares = cur.fetchone()[0]
    if zero_fares > MAX_ZERO_FARES:
        warnings.append(f"Zero-fare rows: {zero_fares} (max {MAX_ZERO_FARES})")

    cur.close()
    conn.close()

    # Format output
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep = "\u2500" * 50

    print(f"\nTRAVEL HEALTH CHECK \u2014 {now}")
    print(sep)
    print(f"  Destinations:     {dest_count:,} rows {_icon(dest_count >= MIN_DESTINATIONS)}")
    print(f"  MOTIS legs:       {motis_count:,} / {dest_count:,} ({motis_pct:.1f}%) {_icon(motis_pct >= MIN_MOTIS_PCT)}")
    print(f"  Fares (any):      {fare_count:,} / {dest_count:,} ({fare_pct:.1f}%) {_icon(fare_pct >= MIN_FARE_PCT)}")
    print(f"  HSP punctuality:  {hsp_count:,} / {dest_count:,} ({hsp_pct:.1f}%) {_icon(hsp_pct >= MIN_HSP_PCT)}")
    print(f"  Travelcard:       {tc_count:,} {_icon(tc_count > 0)}")
    if last_updated:
        print(f"  Last updated:     {last_updated.strftime('%Y-%m-%d %H:%M:%S')} {_icon(not stale)}")
    else:
        print(f"  Last updated:     UNKNOWN {_icon(False)}")
    print(f"  Zero-fare rows:   {zero_fares} {_icon(zero_fares <= MAX_ZERO_FARES)}")

    station_parts = [f"{t}={c:,}" for t, c in sorted(station_counts.items())]
    print(f"  Stations:         {', '.join(station_parts)}")
    print(sep)

    if critical:
        print(f"  STATUS: CRITICAL ({len(critical)} issue{'s' if len(critical) != 1 else ''})")
        for c in critical:
            print(f"    \u2717 {c}")
        if warnings:
            for w in warnings:
                print(f"    \u26a0 {w}")
        print(sep)
        return 2
    elif warnings:
        print(f"  STATUS: HEALTHY ({len(warnings)} warning{'s' if len(warnings) != 1 else ''})")
        for w in warnings:
            print(f"    \u26a0 {w}")
        print(sep)
        return 1
    else:
        print("  STATUS: HEALTHY")
        print(sep)
        return 0


if __name__ == "__main__":
    sys.exit(main())
