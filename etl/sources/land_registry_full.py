"""
sources/land_registry_full.py — Full HM Land Registry PPD ingest

Streams ~/Downloads/pp-complete.csv (~30M rows, 1995–present) into
core_property_transactions including all three columns added in migration 004:
    district, county, ppd_category

Uses copy_expert with a streaming file-like object — no intermediate temp file,
so disk usage is only the PostgreSQL table storage itself.

Standard pipeline interface:
    METADATA  dict
    run(db_url: str) -> int   (returns row count in core_property_transactions)

Licence: HM Land Registry Open Government Licence v3.0 — free for commercial use.
Source:  http://prod.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com/pp-complete.csv
"""

import csv
import io
import os

import psycopg2

from constants import (
    PROPERTY_TYPES,
    SCHEDULE_MONTHLY,
    TABLE_NAMES,
)

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "land_registry_full",
    "description": (
        "Full PPD → core_property_transactions (all years 1995–present, "
        "including district / county / ppd_category columns)."
    ),
    "schedule":           SCHEDULE_MONTHLY,
    "depends_on":         ["postcodes"],
    "tables_written":     [TABLE_NAMES["property_transactions"]],
    "cache_key_patterns": ["area:*", "price_history:*", "price_by_type:*", "pois:*"],
    "expected_row_range": (20_000_000, 40_000_000),
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_COMPLETE_CSV = os.path.expanduser("~/Downloads/pp-complete.csv")
_ALL_TYPES    = set(PROPERTY_TYPES)

# COPY column order — must match _tsv_row() field order
_TXN_COLS = (
    "transaction_id", "price", "date_of_transfer", "postcode",
    "property_type", "old_new", "duration",
    "paon", "saon", "street", "locality", "town",
    "district", "county", "ppd_category",
    "latitude", "longitude", "lsoa_code", "lad_code", "geom",
)

_COPY_SQL = (
    f"COPY {TABLE_NAMES['property_transactions']} "
    f"({', '.join(_TXN_COLS)}) "
    f"FROM STDIN WITH (FORMAT TEXT, DELIMITER E'\\t', NULL '\\\\N')"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_postcode_lookup(conn):
    cur = conn.cursor()
    cur.execute(
        f"SELECT postcode_compact, lsoa_code, lad_code, latitude, longitude "
        f"FROM {TABLE_NAMES['postcodes']}"
    )
    lookup = {}
    for pc, lsoa, lad, lat, lon in cur:
        lookup[pc] = (lsoa, lad, lat, lon)
    cur.close()
    print(f"  Loaded {len(lookup):,} postcode mappings", flush=True)
    return lookup


def _tsv(v):
    """Escape a value for PostgreSQL COPY TEXT format."""
    if v is None or v == "":
        return "\\N"
    return str(v).replace("\\", "\\\\").replace("\t", " ").replace("\n", " ")


# ---------------------------------------------------------------------------
# Streaming file-like object: generates TSV rows on the fly
# ---------------------------------------------------------------------------

class _CSVtoTSV(io.RawIOBase):
    """
    A file-like object that reads pp-complete.csv and yields TSV rows
    suitable for PostgreSQL COPY FROM STDIN.  No intermediate file written.
    """

    def __init__(self, csv_path, pc_lookup):
        self._gen    = self._generate(csv_path, pc_lookup)
        self._buf    = b""
        self.count   = 0
        self.skipped = 0

    def _generate(self, csv_path, pc_lookup):
        with open(csv_path, "r", encoding="utf-8", errors="replace") as fin:
            reader = csv.reader(fin)
            reported = 0
            for row in reader:
                if len(row) < 12:
                    self.skipped += 1
                    continue

                # col 15 = record_status: skip 'D' (deleted/cancelled)
                if len(row) >= 16 and row[15].strip().strip('"') == "D":
                    self.skipped += 1
                    continue

                try:
                    price = int(row[1].strip('"'))
                except (ValueError, IndexError):
                    self.skipped += 1
                    continue

                txn_id       = row[0].strip('"').strip("{}")
                date_str     = row[2].strip('"')
                postcode_raw = row[3].strip('"')
                pc_compact   = postcode_raw.replace(" ", "").upper()
                prop_type    = row[4].strip('"')
                old_new      = row[5].strip('"')
                duration     = row[6].strip('"')
                paon         = row[7].strip('"')
                saon         = row[8].strip('"')  if len(row) > 8  else ""
                street       = row[9].strip('"')  if len(row) > 9  else ""
                locality     = row[10].strip('"') if len(row) > 10 else ""
                town         = row[11].strip('"') if len(row) > 11 else ""
                district     = row[12].strip('"') if len(row) > 12 else ""
                county       = row[13].strip('"') if len(row) > 13 else ""
                ppd_category = row[14].strip('"') if len(row) > 14 else ""

                if prop_type not in _ALL_TYPES:
                    prop_type = "O"

                if prop_type == "O":          # skip non-residential
                    self.skipped += 1
                    continue

                geo = pc_lookup.get(pc_compact)
                if not geo:
                    self.skipped += 1
                    continue

                lsoa_code, lad_code, lat, lon = geo
                if lat is None or lon is None:
                    self.skipped += 1
                    continue

                try:
                    date_val = date_str[:10]
                except (IndexError, TypeError):
                    self.skipped += 1
                    continue

                geom_ewkt = f"SRID=4326;POINT({lon} {lat})"

                line = "\t".join([
                    _tsv(txn_id),
                    str(price),
                    date_val,
                    _tsv(postcode_raw),
                    prop_type,
                    _tsv(old_new),
                    _tsv(duration),
                    _tsv(paon),
                    _tsv(saon),
                    _tsv(street),
                    _tsv(locality),
                    _tsv(town),
                    _tsv(district),
                    _tsv(county),
                    _tsv(ppd_category),
                    str(lat),
                    str(lon),
                    _tsv(lsoa_code),
                    _tsv(lad_code),
                    geom_ewkt,
                ]) + "\n"

                self.count += 1
                reported   += 1
                if reported % 5_000_000 == 0:
                    print(f"    ... {reported:,} rows read, {self.count:,} written", flush=True)

                yield line.encode("utf-8")

    def readinto(self, b):
        """Required for RawIOBase — fills buffer b, returns bytes written."""
        while len(self._buf) < len(b):
            try:
                self._buf += next(self._gen)
            except StopIteration:
                break

        if not self._buf:
            return 0

        n = min(len(b), len(self._buf))
        b[:n] = self._buf[:n]
        self._buf = self._buf[n:]
        return n

    def readable(self):
        return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Full PPD ingest.  Streams pp-complete.csv directly into core_property_transactions
    via COPY FROM STDIN — no intermediate temp file.

    Returns final row count.
    """
    if not os.path.isfile(_COMPLETE_CSV):
        raise FileNotFoundError(
            f"pp-complete.csv not found at {_COMPLETE_CSV}. "
            "Download from the Land Registry S3 bucket."
        )

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    print("  Building postcode lookup...", flush=True)
    pc_lookup = _build_postcode_lookup(conn)

    print(f"  Streaming {_COMPLETE_CSV} → PostgreSQL (no temp file)...", flush=True)
    stream = _CSVtoTSV(_COMPLETE_CSV, pc_lookup)
    buf    = io.BufferedReader(stream, buffer_size=65_536)

    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['property_transactions']}")
    conn.commit()
    print(f"  Truncated {TABLE_NAMES['property_transactions']}", flush=True)

    cur.copy_expert(_COPY_SQL, buf)
    conn.commit()
    cur.close()

    print(f"  Streamed {stream.count:,} rows, skipped {stream.skipped:,}", flush=True)

    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['property_transactions']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  Final row count: {count:,}", flush=True)
    return count
