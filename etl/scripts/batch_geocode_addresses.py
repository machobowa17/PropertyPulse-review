"""
Batch geocode core_addresses via self-hosted Nominatim → precise lat/lon.

Reads addresses from EC2 core_addresses (postcode + paon + street),
geocodes each via Nominatim structured search, writes results to CSV
for loading back into core_addresses.

Usage (from local machine with SSH tunnels):
    # 1. Export addresses from EC2
    ssh ec2-user@16.60.67.248 "docker exec ukproperty_api psql -U ukproperty -d ukproperty -c \"
        COPY (SELECT postcode, paon, saon, street FROM core_addresses)
        TO '/tmp/addresses_to_geocode.csv' CSV HEADER\""
    scp ec2-user@16.60.67.248:/tmp/addresses_to_geocode.csv ./addresses_to_geocode.csv

    # 2. Run batch geocoding (against Hetzner Nominatim)
    python3 batch_geocode_addresses.py \
        --input addresses_to_geocode.csv \
        --output geocoded_addresses.csv \
        --nominatim-url http://128.140.103.160:8088

    # 3. Load results back to EC2 (done by address_lookup.py ETL)

Checkpoints every 10,000 rows so it can be resumed after interruption.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed


def geocode_address(nominatim_url, postcode, paon, street):
    """
    Geocode a UK address via Nominatim structured search.
    Returns (lat, lon, osm_type, osm_id, place_rank) or None.
    """
    params = {
        "format": "jsonv2",
        "countrycodes": "gb",
        "limit": "1",
        "addressdetails": "0",
    }

    # Build structured query
    # Nominatim structured: street=<housenumber> <street>&postalcode=<postcode>
    if paon and street:
        params["street"] = f"{paon} {street}"
    elif street:
        params["street"] = street

    if postcode:
        params["postalcode"] = postcode

    url = f"{nominatim_url}/search?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PropertyPulse/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data:
                r = data[0]
                return (
                    float(r["lat"]),
                    float(r["lon"]),
                    r.get("osm_type", ""),
                    r.get("osm_id", ""),
                    r.get("place_rank", 0),
                )
    except Exception:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description="Batch geocode UK addresses via Nominatim")
    parser.add_argument("--input", required=True, help="Input CSV (postcode, paon, saon, street)")
    parser.add_argument("--output", required=True, help="Output CSV with geocoded coordinates")
    parser.add_argument("--nominatim-url", default="http://128.140.103.160:8088",
                        help="Nominatim base URL")
    parser.add_argument("--workers", type=int, default=8,
                        help="Concurrent geocoding threads")
    parser.add_argument("--checkpoint-interval", type=int, default=10000,
                        help="Write checkpoint every N rows")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from existing output file")
    args = parser.parse_args()

    # Load already-geocoded rows if resuming
    done_keys = set()
    if args.resume and os.path.exists(args.output):
        with open(args.output, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["postcode"], row["paon"], row.get("saon", ""), row.get("street", ""))
                done_keys.add(key)
        print(f"Resuming: {len(done_keys):,} already geocoded")

    # Read input
    with open(args.input, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    total = len(rows)
    print(f"Total addresses: {total:,}")

    # Filter out already-done
    if done_keys:
        rows = [r for r in rows if (r["postcode"], r["paon"], r.get("saon", ""), r.get("street", "")) not in done_keys]
        print(f"Remaining to geocode: {len(rows):,}")

    # Open output for append
    write_header = not (args.resume and os.path.exists(args.output))
    outf = open(args.output, "a" if args.resume else "w", newline="")
    writer = csv.writer(outf)
    if write_header:
        writer.writerow(["postcode", "paon", "saon", "street",
                         "precise_lat", "precise_lon", "osm_type", "osm_id", "place_rank"])

    geocoded = 0
    matched = 0
    batch = []
    t0 = time.time()

    def process_row(row):
        postcode = row.get("postcode", "")
        paon = row.get("paon", "")
        street = row.get("street", "")
        result = geocode_address(args.nominatim_url, postcode, paon, street)
        return row, result

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for i, row in enumerate(rows):
            fut = pool.submit(process_row, row)
            futures[fut] = i

            # Process completed futures as they finish
            if len(futures) >= args.workers * 2:
                for done_fut in as_completed(list(futures.keys())[:args.workers]):
                    row_data, result = done_fut.result()
                    geocoded += 1
                    out_row = [
                        row_data.get("postcode", ""),
                        row_data.get("paon", ""),
                        row_data.get("saon", ""),
                        row_data.get("street", ""),
                    ]
                    if result:
                        matched += 1
                        out_row.extend([result[0], result[1], result[2], result[3], result[4]])
                    else:
                        out_row.extend(["", "", "", "", ""])
                    batch.append(out_row)
                    del futures[done_fut]

                    # Checkpoint
                    if len(batch) >= args.checkpoint_interval:
                        writer.writerows(batch)
                        outf.flush()
                        elapsed = time.time() - t0
                        rate = geocoded / elapsed if elapsed > 0 else 0
                        pct = matched / geocoded * 100 if geocoded > 0 else 0
                        print(f"  {geocoded:,}/{len(rows):,} geocoded "
                              f"({pct:.1f}% matched, {rate:.0f}/sec)", flush=True)
                        batch = []

        # Drain remaining futures
        for fut in as_completed(futures):
            row_data, result = fut.result()
            geocoded += 1
            out_row = [
                row_data.get("postcode", ""),
                row_data.get("paon", ""),
                row_data.get("saon", ""),
                row_data.get("street", ""),
            ]
            if result:
                matched += 1
                out_row.extend([result[0], result[1], result[2], result[3], result[4]])
            else:
                out_row.extend(["", "", "", "", ""])
            batch.append(out_row)

    # Final flush
    if batch:
        writer.writerows(batch)
    outf.close()

    elapsed = time.time() - t0
    rate = geocoded / elapsed if elapsed > 0 else 0
    pct = matched / geocoded * 100 if geocoded > 0 else 0
    print(f"\nDone: {geocoded:,} geocoded, {matched:,} matched ({pct:.1f}%), "
          f"{elapsed:.0f}s ({rate:.0f}/sec)")


if __name__ == "__main__":
    main()
