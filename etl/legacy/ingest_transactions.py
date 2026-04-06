"""
ETL: HM Land Registry Price Paid → core_property_transactions (individual records)
Source: https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads
Licence: OGL v3.0 — free for commercial use

Downloads recent yearly CSVs and stores individual transaction records with geocoding
via core_postcodes for map pin display.

CSV format (no headers):
  0: Transaction ID  1: Price  2: Date  3: Postcode
  4: Property Type (D/S/T/F/O)  5: Old/New (Y/N)  6: Duration (F/L)
  7: PAON  8: SAON  9: Street  10: Locality  11: Town/City
  12: District  13: County  14: PPD Category  15: Record Status
"""
import csv
import io
import os
import sys

import requests
import psycopg2

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres@localhost:5432/ukproperty",
)

DATA_DIR = os.path.expanduser("~/Desktop/Manus Take 2/etl/data")
BASE_URL = "http://prod.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com"

# Only ingest recent years — sufficient for map pins
YEARS = [2024, 2025]


def download_file(year):
    os.makedirs(DATA_DIR, exist_ok=True)
    fname = f"pp-{year}.csv"
    fpath = os.path.join(DATA_DIR, fname)
    if os.path.exists(fpath):
        print(f"  {fname} already exists, skipping download")
        return fpath

    url = f"{BASE_URL}/pp-{year}.csv"
    print(f"  Downloading {url}...")
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()
    with open(fpath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"  Saved {fname}")
    return fpath


def build_postcode_lookup(conn):
    """Load postcode → (lat, lon, lsoa_code) from core_postcodes."""
    cur = conn.cursor()
    cur.execute(
        "SELECT postcode_compact, latitude, longitude, lsoa_code FROM core_postcodes"
    )
    lookup = {}
    for row in cur:
        lookup[row[0]] = (row[1], row[2], row[3])
    cur.close()
    print(f"  Loaded {len(lookup):,} postcode mappings")
    return lookup


def parse_and_load(conn, files, pc_lookup):
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE core_property_transactions")
    conn.commit()

    total = 0
    skipped = 0

    for fpath in files:
        print(f"  Parsing {os.path.basename(fpath)}...")
        rows = []

        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 12:
                    continue

                txn_id = row[0].strip('"').strip("{}")
                try:
                    price = int(row[1].strip('"'))
                except (ValueError, IndexError):
                    skipped += 1
                    continue

                date_str = row[2].strip('"')[:10]  # "2024-01-19"
                postcode_raw = row[3].strip('"')
                postcode_compact = postcode_raw.replace(" ", "").upper()
                prop_type = row[4].strip('"')
                old_new = row[5].strip('"')
                duration = row[6].strip('"')
                paon = row[7].strip('"')
                saon = row[8].strip('"')
                street = row[9].strip('"')
                locality = row[10].strip('"')
                town = row[11].strip('"')

                if prop_type not in ("D", "S", "T", "F", "O"):
                    prop_type = "O"

                # Skip commercial/other
                if prop_type == "O":
                    skipped += 1
                    continue

                geo = pc_lookup.get(postcode_compact)
                if not geo:
                    skipped += 1
                    continue

                lat, lon, lsoa_code = geo
                if lat is None or lon is None:
                    skipped += 1
                    continue

                rows.append((
                    txn_id, price, date_str, postcode_raw,
                    prop_type, old_new, duration,
                    paon or None, saon or None,
                    street or None, locality or None, town or None,
                    lat, lon, lsoa_code,
                ))

        if rows:
            print(f"    Writing {len(rows):,} rows via COPY...")
            buf = io.StringIO()
            for r in rows:
                # tab-separated: transaction_id, price, date, postcode, type, old_new, duration,
                # paon, saon, street, locality, town, lat, lon, geom(WKT), lsoa_code
                vals = list(r)
                lat_v, lon_v = vals[12], vals[13]
                geom_wkt = f"SRID=4326;POINT({lon_v} {lat_v})"
                line_vals = []
                for v in vals:
                    if v is None:
                        line_vals.append("\\N")
                    else:
                        line_vals.append(str(v).replace("\t", " ").replace("\n", " "))
                line_vals.append(geom_wkt)  # geom column
                buf.write("\t".join(line_vals) + "\n")
            buf.seek(0)
            cur.copy_from(
                buf, "core_property_transactions", sep="\t", null="\\N",
                columns=(
                    "transaction_id", "price", "date_of_transfer", "postcode",
                    "property_type", "old_new", "duration",
                    "paon", "saon", "street", "locality", "town",
                    "latitude", "longitude", "lsoa_code", "geom",
                ),
            )
            conn.commit()
            total += len(rows)

        skipped_in_file = skipped
        print(f"    Committed. Running total: {total:,} rows")

    print(f"  Total ingested: {total:,}, skipped: {skipped:,}")
    return total


def ingest():
    sys.stdout.reconfigure(line_buffering=True)
    print("=== Land Registry Individual Transactions Ingestion ===")

    files = []
    for year in YEARS:
        files.append(download_file(year))

    conn = psycopg2.connect(DB_URL)
    print("Building postcode lookup...")
    pc_lookup = build_postcode_lookup(conn)

    print("Parsing and loading transactions...")
    total = parse_and_load(conn, files, pc_lookup)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM core_property_transactions")
    count = cur.fetchone()[0]
    print(f"Done. core_property_transactions: {count:,} rows")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ingest()
