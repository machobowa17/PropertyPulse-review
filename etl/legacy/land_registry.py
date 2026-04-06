"""
sources/land_registry.py — HM Land Registry Price Paid Data

Builds three tables:
    core_property_prices_lsoa  — LSOA-level monthly aggregates (START_YEAR–present)
    core_property_prices_lad   — LAD-level monthly aggregates  (START_YEAR–present)
    core_property_transactions — Individual transactions (all years, from 1995)

If ~/Downloads/pp-complete.csv is present it is used as the data source for all
three tables in a single streaming pass (memory-efficient: transactions are written
to a temp file rather than held in RAM).  Otherwise individual yearly files are
downloaded from the LR S3 bucket.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_property_prices_lsoa)

Licence: HM Land Registry Open Government Licence v3.0 — free for commercial use.
"""

import csv
import io
import os
import statistics
import tempfile
from collections import defaultdict
from datetime import datetime

import psycopg2
import requests

from constants import (
    PROPERTY_TYPES,
    PRICE_TYPES,
    SCHEDULE_MONTHLY,
    TABLE_NAMES,
)

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "land_registry",
    "description": (
        "HM Land Registry PPD → core_property_prices_lsoa, "
        "core_property_prices_lad, core_property_transactions."
    ),
    "schedule":           SCHEDULE_MONTHLY,
    "depends_on":         ["postcodes"],
    "tables_written":     [
        TABLE_NAMES["property_prices_lsoa"],
        TABLE_NAMES["property_prices_lad"],
        TABLE_NAMES["property_transactions"],
    ],
    "cache_key_patterns": ["area:*", "price_history:*", "price_by_type:*", "pois:*"],
    "expected_row_range": (5_500_000, 60_000_000),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_BASE_URL      = "http://prod.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com"
_CURR_YEAR     = datetime.now().year
_START_YEAR    = 2015   # earliest year included in LSOA/LAD aggregates
_DATA_DIR      = os.path.join(os.path.dirname(__file__), "..", "data")
_COMPLETE_CSV  = os.path.expanduser("~/Downloads/pp-complete.csv")

_ALL_TYPES   = set(PROPERTY_TYPES)
_PRICE_TYPES = set(PRICE_TYPES)

# Columns for COPY into core_property_transactions
_TXN_COLUMNS = (
    "transaction_id", "price", "date_of_transfer", "postcode",
    "property_type", "old_new", "duration",
    "paon", "saon", "street", "locality", "town",
    "latitude", "longitude", "lsoa_code", "lad_code", "geom",
)

# ---------------------------------------------------------------------------
# Download (used when pp-complete.csv is not present)
# ---------------------------------------------------------------------------

def _download_year(year):
    """Download pp-YYYY.csv from LR S3 to etl/data/, skip if already present."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    fpath = os.path.join(_DATA_DIR, f"pp-{year}.csv")
    if os.path.exists(fpath):
        print(f"    pp-{year}.csv already present, skipping download", flush=True)
        return fpath
    url = f"{_BASE_URL}/pp-{year}.csv"
    print(f"    Downloading {url}...", flush=True)
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()
    with open(fpath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65_536):
            f.write(chunk)
    print(f"    Saved pp-{year}.csv", flush=True)
    return fpath


# ---------------------------------------------------------------------------
# Postcode lookup
# ---------------------------------------------------------------------------

def _build_postcode_lookup(conn):
    """Load postcode_compact → (lsoa_code, lad_code, lat, lon) from core_postcodes."""
    cur = conn.cursor()
    cur.execute(
        f"SELECT postcode_compact, lsoa_code, lad_code, latitude, longitude "
        f"FROM {TABLE_NAMES['postcodes']}"
    )
    lookup = {}
    for pc, lsoa, lad, lat, lon in cur:
        lookup[pc] = (lsoa, lad, lat, lon)
    cur.close()
    print(f"  Loaded {len(lookup):,} postcode→LSOA/LAD mappings", flush=True)
    return lookup


# ---------------------------------------------------------------------------
# TSV helpers for COPY
# ---------------------------------------------------------------------------

def _tsv_val(v):
    """Format a value for PostgreSQL COPY TEXT format."""
    if v is None or v == "":
        return "\\N"
    return str(v).replace("\t", " ").replace("\n", " ")


# ---------------------------------------------------------------------------
# Parse: complete CSV (streaming, memory-efficient)
# ---------------------------------------------------------------------------

def _parse_complete_csv(csv_path, pc_lookup, txn_filepath):
    """
    Single-pass parse of pp-complete.csv (all years).

    Transactions for all years are streamed directly to txn_filepath in TSV
    format, avoiding holding 30M rows in RAM.

    LSOA/LAD aggregates are accumulated in dicts for years >= _START_YEAR only.
    Records with status 'D' (deleted/cancelled) are skipped.

    Returns (lsoa_data, lad_data, txn_count, skipped).
    """
    lsoa_data = defaultdict(lambda: {
        "prices":           [],
        "freehold_prices":  [],
        "leasehold_prices": [],
        "new_build":  0,
        "freehold":   0,
        "leasehold":  0,
    })
    lad_data  = defaultdict(lambda: {"prices": []})
    txn_count = 0
    skipped   = 0
    reported  = 0

    print(f"  Streaming {csv_path} ...", flush=True)
    with open(csv_path, "r", encoding="utf-8", errors="replace") as fin, \
         open(txn_filepath, "w", encoding="utf-8") as fout:

        reader = csv.reader(fin)
        for row in reader:
            if len(row) < 12:
                skipped += 1
                continue

            # pp-complete.csv col 15 = record status: A=add, C=change, D=delete
            if len(row) >= 16 and row[15].strip().strip('"') == "D":
                skipped += 1
                continue

            try:
                price = int(row[1].strip('"'))
            except (ValueError, IndexError):
                skipped += 1
                continue

            date_str     = row[2].strip('"')
            postcode_raw = row[3].strip('"')
            pc_compact   = postcode_raw.replace(" ", "").upper()
            prop_type    = row[4].strip('"')
            old_new      = row[5].strip('"')
            duration     = row[6].strip('"')
            paon         = row[7].strip('"')
            saon         = row[8].strip('"') if len(row) > 8  else ""
            street       = row[9].strip('"') if len(row) > 9  else ""
            locality     = row[10].strip('"') if len(row) > 10 else ""
            town         = row[11].strip('"') if len(row) > 11 else ""
            txn_id       = row[0].strip('"').strip("{}")

            if prop_type not in _ALL_TYPES:
                prop_type = "O"

            geo = pc_lookup.get(pc_compact)
            if not geo:
                skipped += 1
                continue

            lsoa_code, lad_code, lat, lon = geo

            try:
                year_month = date_str[:7] + "-01"
                year       = int(date_str[:4])
            except (IndexError, TypeError, ValueError):
                skipped += 1
                continue

            # ── LSOA / LAD aggregates (START_YEAR+ only, PRICE_TYPES only) ─
            if year >= _START_YEAR and prop_type in _PRICE_TYPES:
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

                lad_key = (lad_code, year_month, prop_type)
                lad_data[lad_key]["prices"].append(price)

            # ── Individual transaction (all years, skip O, skip missing geo) ─
            if prop_type != "O" and lat is not None and lon is not None:
                geom_ewkt = f"SRID=4326;POINT({lon} {lat})"
                fout.write("\t".join([
                    txn_id,
                    str(price),
                    date_str[:10],
                    _tsv_val(postcode_raw),
                    prop_type,
                    _tsv_val(old_new),
                    _tsv_val(duration),
                    _tsv_val(paon),
                    _tsv_val(saon),
                    _tsv_val(street),
                    _tsv_val(locality),
                    _tsv_val(town),
                    str(lat),
                    str(lon),
                    _tsv_val(lsoa_code),
                    _tsv_val(lad_code),
                    geom_ewkt,
                ]) + "\n")
                txn_count += 1

            # Progress report every 5M rows
            reported += 1
            if reported % 5_000_000 == 0:
                print(f"    ... {reported:,} rows parsed, {txn_count:,} transactions", flush=True)

    print(f"  Parsed {reported:,} rows → {txn_count:,} transactions, {skipped:,} skipped", flush=True)
    return lsoa_data, lad_data, txn_count, skipped


# ---------------------------------------------------------------------------
# Parse: year files (fallback when pp-complete.csv is absent)
# ---------------------------------------------------------------------------

def _parse_files(files, pc_lookup):
    """
    Parse per-year pp-YYYY.csv files; returns:
        lsoa_data  dict  (lsoa_code, year_month, prop_type) → price stats
        lad_data   dict  (lad_code, year_month, prop_type)  → price list
        txn_rows   list  of individual transaction tuples for COPY
    """
    lsoa_data = defaultdict(lambda: {
        "prices":           [],
        "freehold_prices":  [],
        "leasehold_prices": [],
        "new_build":  0,
        "freehold":   0,
        "leasehold":  0,
    })
    lad_data  = defaultdict(lambda: {"prices": []})
    txn_rows  = []
    skipped   = 0
    processed = 0

    for fpath in files:
        print(f"    Parsing {os.path.basename(fpath)}...", flush=True)
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 12:
                    continue

                try:
                    price = int(row[1].strip('"'))
                except (ValueError, IndexError):
                    skipped += 1
                    continue

                date_str     = row[2].strip('"')
                postcode_raw = row[3].strip('"')
                pc_compact   = postcode_raw.replace(" ", "").upper()
                prop_type    = row[4].strip('"')
                old_new      = row[5].strip('"')
                duration     = row[6].strip('"')
                paon         = row[7].strip('"')
                saon         = row[8].strip('"') if len(row) > 8  else ""
                street       = row[9].strip('"') if len(row) > 9  else ""
                locality     = row[10].strip('"') if len(row) > 10 else ""
                town         = row[11].strip('"') if len(row) > 11 else ""
                txn_id       = row[0].strip('"').strip("{}")

                if prop_type not in _ALL_TYPES:
                    prop_type = "O"

                geo = pc_lookup.get(pc_compact)
                if not geo:
                    skipped += 1
                    continue

                lsoa_code, lad_code, lat, lon = geo

                try:
                    year_month = date_str[:7] + "-01"
                except (IndexError, TypeError):
                    skipped += 1
                    continue

                # ── LSOA aggregation ──────────────────────────────────────
                if prop_type in _PRICE_TYPES:
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

                    lad_key = (lad_code, year_month, prop_type)
                    lad_data[lad_key]["prices"].append(price)

                # ── Individual transaction ─────────────────────────────────
                if prop_type != "O" and lat is not None and lon is not None:
                    txn_rows.append((
                        txn_id, price, date_str[:10], postcode_raw,
                        prop_type, old_new, duration,
                        paon or None, saon or None,
                        street or None, locality or None, town or None,
                        lat, lon, lsoa_code, lad_code,
                    ))

                processed += 1

    print(f"  Processed {processed:,} transactions, skipped {skipped:,}", flush=True)
    return lsoa_data, lad_data, txn_rows


# ---------------------------------------------------------------------------
# Load: LSOA aggregates
# ---------------------------------------------------------------------------

def _load_lsoa(conn, lsoa_data):
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['property_prices_lsoa']} CASCADE")
    conn.commit()

    lsoa_rows = []
    for (lsoa_code, year_month, prop_type), d in lsoa_data.items():
        prices = d["prices"]
        if not prices:
            continue
        fh = d["freehold_prices"]
        lh = d["leasehold_prices"]
        lsoa_rows.append((
            lsoa_code, year_month, prop_type,
            round(sum(prices) / len(prices), 2),
            round(statistics.median(prices), 2),
            min(prices),
            max(prices),
            len(prices),
            d["new_build"],
            d["freehold"],
            d["leasehold"],
            round(sum(fh) / len(fh), 2) if fh else None,
            round(sum(lh) / len(lh), 2) if lh else None,
        ))

    if lsoa_rows:
        buf = io.StringIO()
        for r in lsoa_rows:
            buf.write("\t".join("" if v is None else str(v) for v in r) + "\n")
        buf.seek(0)
        cur.copy_from(
            buf, TABLE_NAMES["property_prices_lsoa"], sep="\t", null="",
            columns=(
                "lsoa_code", "year_month", "property_type",
                "avg_price", "median_price", "min_price", "max_price",
                "transaction_count", "new_build_count", "freehold_count",
                "leasehold_count", "avg_freehold_price", "avg_leasehold_price",
            ),
        )
        conn.commit()
    cur.close()
    print(f"  Loaded {len(lsoa_rows):,} LSOA-level rows", flush=True)


# ---------------------------------------------------------------------------
# Load: LAD aggregates
# ---------------------------------------------------------------------------

def _load_lad(conn, lad_data):
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['property_prices_lad']} CASCADE")
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
        for r in lad_rows:
            buf.write("\t".join("" if v is None else str(v) for v in r) + "\n")
        buf.seek(0)
        cur.copy_from(
            buf, TABLE_NAMES["property_prices_lad"], sep="\t", null="",
            columns=(
                "lad_code", "year_month", "property_type",
                "avg_price", "median_price", "transaction_count",
            ),
        )
        conn.commit()
    cur.close()
    print(f"  Loaded {len(lad_rows):,} LAD-level rows", flush=True)


# ---------------------------------------------------------------------------
# Load: transactions from temp file (streaming COPY)
# ---------------------------------------------------------------------------

def _load_transactions_from_file(conn, txn_filepath):
    """COPY pre-written TSV file into core_property_transactions."""
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['property_transactions']}")
    conn.commit()
    with open(txn_filepath, "r", encoding="utf-8") as f:
        cur.copy_from(
            f, TABLE_NAMES["property_transactions"], sep="\t", null="\\N",
            columns=_TXN_COLUMNS,
        )
    conn.commit()
    cur.close()


# ---------------------------------------------------------------------------
# Load: transactions from in-memory list (year-file fallback)
# ---------------------------------------------------------------------------

def _load_transactions(conn, txn_rows):
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['property_transactions']}")
    conn.commit()

    buf = io.StringIO()
    for r in txn_rows:
        lat, lon = r[12], r[13]
        geom_ewkt = f"SRID=4326;POINT({lon} {lat})"
        vals = list(r)
        line_vals = []
        for v in vals:
            if v is None:
                line_vals.append("\\N")
            else:
                line_vals.append(str(v).replace("\t", " ").replace("\n", " "))
        line_vals.append(geom_ewkt)
        buf.write("\t".join(line_vals) + "\n")

    buf.seek(0)
    cur.copy_from(
        buf, TABLE_NAMES["property_transactions"], sep="\t", null="\\N",
        columns=_TXN_COLUMNS,
    )
    conn.commit()
    cur.close()
    print(f"  Loaded {len(txn_rows):,} individual transactions", flush=True)


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Load LR Price Paid data into LSOA/LAD aggregates and the master transactions
    table.  If ~/Downloads/pp-complete.csv is present it is used as the source
    for all three tables in a single streaming pass.  Otherwise individual yearly
    files are downloaded from the LR S3 bucket (aggregates + transactions for
    START_YEAR onwards only).

    Returns row count in core_property_prices_lsoa.
    """
    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    print("  Building postcode lookup...", flush=True)
    pc_lookup = _build_postcode_lookup(conn)

    if os.path.isfile(_COMPLETE_CSV):
        print(f"  pp-complete.csv found — using full historical dataset", flush=True)
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".tsv", prefix="lr_txn_")
        os.close(tmp_fd)
        try:
            lsoa_data, lad_data, txn_count, _ = _parse_complete_csv(
                _COMPLETE_CSV, pc_lookup, tmp_path
            )
            print(f"  Loading {len(lsoa_data):,} LSOA aggregation keys...", flush=True)
            _load_lsoa(conn, lsoa_data)
            print(f"  Loading {len(lad_data):,} LAD aggregation keys...", flush=True)
            _load_lad(conn, lad_data)
            print(f"  Loading {txn_count:,} transactions via COPY...", flush=True)
            _load_transactions_from_file(conn, tmp_path)
        finally:
            os.unlink(tmp_path)
    else:
        print("  pp-complete.csv not found — downloading yearly files...", flush=True)
        files = [_download_year(y) for y in range(_START_YEAR, _CURR_YEAR + 1)]
        print("  Parsing and aggregating...", flush=True)
        lsoa_data, lad_data, txn_rows = _parse_files(files, pc_lookup)
        print(f"  Loading {len(lsoa_data):,} LSOA aggregation keys...", flush=True)
        _load_lsoa(conn, lsoa_data)
        print(f"  Loading {len(lad_data):,} LAD aggregation keys...", flush=True)
        _load_lad(conn, lad_data)
        print(f"  Loading {len(txn_rows):,} individual transaction rows...", flush=True)
        _load_transactions(conn, txn_rows)

    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['property_prices_lsoa']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
