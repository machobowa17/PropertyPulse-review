"""
ETL: HM Land Registry Price Paid Data → core_property_prices_lsoa + core_property_prices_lad
Source: https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads
Schema: Build Bible Part 2, Section 2.1

Downloads yearly CSVs (pp-2015.csv through pp-2025.csv) from Land Registry.
Aggregates to LSOA level using postcode→LSOA mapping from core_postcodes.
Also computes LAD-level aggregates for parent comparison.

CSV format (no headers, columns by position):
  0: Transaction ID  1: Price  2: Date  3: Postcode
  4: Property Type (D/S/T/F/O)  5: Old/New (Y/N)  6: Duration (F/L)
"""
import csv
import os
import statistics
import sys
from collections import defaultdict
from datetime import date

import requests
import psycopg2
from psycopg2.extras import execute_values

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres@localhost:5432/ukproperty",
)

DATA_DIR = os.path.expanduser("~/Desktop/Manus Take 2/etl/data")

BASE_URL = "http://prod.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com"

START_YEAR = 2015
END_YEAR = 2025


def download_yearly_files():
    """Download yearly Price Paid CSVs from Land Registry."""
    os.makedirs(DATA_DIR, exist_ok=True)
    files = []
    for year in range(START_YEAR, END_YEAR + 1):
        fname = f"pp-{year}.csv"
        fpath = os.path.join(DATA_DIR, fname)
        if os.path.exists(fpath):
            print(f"  {fname} already exists, skipping download")
            files.append(fpath)
            continue

        url = f"{BASE_URL}/pp-{year}.csv"
        print(f"  Downloading {url}...")
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
        with open(fpath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        files.append(fpath)
        print(f"  Saved {fname}")

    return files


def build_postcode_lookup(conn):
    """Load postcode → (lsoa_code, lad_code) mapping from core_postcodes."""
    cur = conn.cursor()
    cur.execute("SELECT postcode_compact, lsoa_code, lad_code FROM core_postcodes")
    lookup = {}
    for row in cur:
        lookup[row[0]] = (row[1], row[2])
    cur.close()
    print(f"  Loaded {len(lookup):,} postcode→LSOA mappings")
    return lookup


def parse_and_aggregate(files, pc_lookup):
    """
    Parse Price Paid CSVs and aggregate to LSOA-level monthly.
    Key: (lsoa_code, year_month, property_type)
    """
    # LSOA aggregation: key → list of prices + counters
    lsoa_data = defaultdict(lambda: {
        "prices": [], "freehold_prices": [], "leasehold_prices": [],
        "new_build": 0, "freehold": 0, "leasehold": 0,
    })
    # LAD aggregation
    lad_data = defaultdict(lambda: {"prices": []})

    skipped = 0
    processed = 0

    for fpath in files:
        print(f"  Parsing {os.path.basename(fpath)}...")
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 7:
                    continue

                try:
                    price = int(row[1].strip('"'))
                except (ValueError, IndexError):
                    skipped += 1
                    continue

                date_str = row[2].strip('"')  # e.g., "2024-01-19 00:00"
                postcode = row[3].strip('"').replace(" ", "").upper()
                prop_type = row[4].strip('"')  # D/S/T/F/O
                old_new = row[5].strip('"')    # Y=new, N=old
                duration = row[6].strip('"')   # F=freehold, L=leasehold

                if prop_type not in ("D", "S", "T", "F", "O"):
                    prop_type = "O"

                # Resolve postcode to LSOA/LAD
                geo = pc_lookup.get(postcode)
                if not geo:
                    skipped += 1
                    continue

                lsoa_code, lad_code = geo

                # Year-month key (first of month)
                try:
                    year_month = date_str[:7] + "-01"  # "2024-01-01"
                except (IndexError, TypeError):
                    skipped += 1
                    continue

                # LSOA aggregation
                lsoa_key = (lsoa_code, year_month, prop_type)
                lsoa_data[lsoa_key]["prices"].append(price)
                if old_new == "Y":
                    lsoa_data[lsoa_key]["new_build"] += 1
                if duration == "F":
                    lsoa_data[lsoa_key]["freehold"] += 1
                    lsoa_data[lsoa_key]["freehold_prices"].append(price)
                elif duration == "L":
                    lsoa_data[lsoa_key]["leasehold"] += 1
                    lsoa_data[lsoa_key]["leasehold_prices"].append(price)

                # LAD aggregation
                lad_key = (lad_code, year_month, prop_type)
                lad_data[lad_key]["prices"].append(price)

                processed += 1

    print(f"  Processed {processed:,} transactions, skipped {skipped:,}")
    return lsoa_data, lad_data


def ingest():
    sys.stdout.reconfigure(line_buffering=True)
    print("=== Land Registry Price Paid Ingestion ===")

    # Download
    print("Downloading yearly files...")
    files = download_yearly_files()

    # Connect and load lookup
    conn = psycopg2.connect(DB_URL)
    print("Building postcode lookup...")
    pc_lookup = build_postcode_lookup(conn)

    # Parse and aggregate
    print("Parsing and aggregating...")
    lsoa_data, lad_data = parse_and_aggregate(files, pc_lookup)

    cur = conn.cursor()

    # Insert LSOA-level data
    print(f"Inserting {len(lsoa_data):,} LSOA-level aggregations...")
    cur.execute("TRUNCATE TABLE core_property_prices_lsoa CASCADE")
    conn.commit()

    lsoa_rows = []
    for (lsoa_code, year_month, prop_type), d in lsoa_data.items():
        prices = d["prices"]
        if not prices:
            continue
        fh_prices = d["freehold_prices"]
        lh_prices = d["leasehold_prices"]
        lsoa_rows.append((
            lsoa_code, year_month, prop_type,
            round(sum(prices) / len(prices), 2),                # avg_price
            round(statistics.median(prices), 2),                 # median_price
            min(prices),                                          # min_price
            max(prices),                                          # max_price
            len(prices),                                          # transaction_count
            d["new_build"],                                       # new_build_count
            d["freehold"],                                        # freehold_count
            d["leasehold"],                                       # leasehold_count
            round(sum(fh_prices) / len(fh_prices), 2) if fh_prices else None,  # avg_freehold_price
            round(sum(lh_prices) / len(lh_prices), 2) if lh_prices else None,  # avg_leasehold_price
        ))

    if lsoa_rows:
        import io
        print(f"  Writing {len(lsoa_rows):,} rows via COPY...")
        buf = io.StringIO()
        for row in lsoa_rows:
            buf.write('\t'.join('' if v is None else str(v) for v in row) + '\n')
        buf.seek(0)
        cur.copy_from(buf, 'core_property_prices_lsoa', sep='\t', null='',
                       columns=('lsoa_code', 'year_month', 'property_type',
                                'avg_price', 'median_price', 'min_price', 'max_price',
                                'transaction_count', 'new_build_count', 'freehold_count', 'leasehold_count',
                                'avg_freehold_price', 'avg_leasehold_price'))
        conn.commit()
        print("  LSOA COPY committed.")

    # Insert LAD-level data
    print(f"Inserting {len(lad_data):,} LAD-level aggregations...")
    cur.execute("TRUNCATE TABLE core_property_prices_lad CASCADE")
    conn.commit()

    lad_rows = []
    for (lad_code, year_month, prop_type), d in lad_data.items():
        prices = d["prices"]
        if not prices:
            continue
        lad_rows.append((
            lad_code, year_month, prop_type,
            round(sum(prices) / len(prices), 2),
            round(statistics.median(prices), 2),
            len(prices),
        ))

    if lad_rows:
        buf = io.StringIO()
        for row in lad_rows:
            buf.write('\t'.join('' if v is None else str(v) for v in row) + '\n')
        buf.seek(0)
        cur.copy_from(buf, 'core_property_prices_lad', sep='\t', null='',
                       columns=('lad_code', 'year_month', 'property_type',
                                'avg_price', 'median_price', 'transaction_count'))
        conn.commit()
        print("  LAD COPY committed.")

    cur.execute("SELECT COUNT(*) FROM core_property_prices_lsoa")
    lsoa_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM core_property_prices_lad")
    lad_count = cur.fetchone()[0]
    print(f"Done. core_property_prices_lsoa: {lsoa_count:,} rows, core_property_prices_lad: {lad_count:,} rows")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ingest()
