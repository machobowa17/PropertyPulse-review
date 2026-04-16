"""
sources/council_tax.py — Council-tax band charges → core_council_tax_lad

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_council_tax_lad)

Data files required in etl/data/council/ (or set env vars to override):
    COUNCIL_TAX_PATH        — England VOA ODS table (default: ctb1_table8.ods)
    COUNCIL_TAX_WALES_PATH  — Wales StatsWales CSV export (optional)
                              default: statswales_council_tax.csv

Download from:
    England (VOA / MHCLG):
      https://www.gov.uk/government/collections/council-tax-statistics
    Wales (StatsWales):
      https://stats.gov.wales/en-GB/1988b6af-2a9c-43b6-8939-83e6cceb3903
"""

import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ANNUAL, TABLE_NAMES, is_supported_lad_code
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name": "council_tax",
    "description": "England VOA council-tax bands plus optional Welsh StatsWales bands → core_council_tax_lad.",
    "schedule": SCHEDULE_ANNUAL,
    "depends_on": [],
    "tables_written": [TABLE_NAMES["council_tax_lad"]],
    "cache_key_patterns": [],
    "expected_row_range": (300, 400),
}

# England region/country summary prefixes to exclude from the VOA sheet
_ENGLAND_SKIP_PREFIXES = ("E12", "E92")
_BAND_COLUMNS = [
    "band_a",
    "band_b",
    "band_c",
    "band_d",
    "band_e",
    "band_f",
    "band_g",
    "band_h",
    "band_i",
]
_WELSH_BAND_MAP = {
    "A": "band_a",
    "B": "band_b",
    "C": "band_c",
    "D": "band_d",
    "E": "band_e",
    "F": "band_f",
    "G": "band_g",
    "H": "band_h",
    "I": "band_i",
}

# ---------------------------------------------------------------------------
# Helper: resolve data file paths
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_england_path():
    path = os.environ.get("COUNCIL_TAX_PATH")
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, "council", "ctb1_table8.ods")
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"No ctb1_table8.ods found at {candidate}. "
        "Download VOA Council Tax statistics from "
        "https://www.gov.uk/government/collections/council-tax-statistics "
        "and place the file in etl/data/council/, or set the COUNCIL_TAX_PATH env var."
    )


def _resolve_wales_path():
    path = os.environ.get("COUNCIL_TAX_WALES_PATH")
    if path:
        return path if os.path.exists(path) else None
    candidate = os.path.join(_ETL_DATA_DIR, "council", "statswales_council_tax.csv")
    return candidate if os.path.exists(candidate) else None


def _empty_band_record():
    return {column: None for column in _BAND_COLUMNS}


def _as_float(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if not value:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Source readers
# ---------------------------------------------------------------------------


def _read_england_rows(src_path: str) -> dict[str, dict[str, float | None]]:
    """Return lad_code → band values from the England VOA ODS source."""
    # The current official MHCLG workbook stores band-by-band local-authority charges
    # in Table_9, with row 3 as the header row.
    df = pd.read_excel(src_path, engine="odf", sheet_name="Table_9", header=2)
    print(f"  Read {len(df)} rows from England ODS Table_9", flush=True)

    required_columns = {
        "ONS Code",
        "Band A",
        "Band B",
        "Band C",
        "Band D",
        "Band E",
        "Band F",
        "Band G ",
        "Band H",
    }
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"England council-tax ODS missing required columns: {', '.join(missing)}")

    results: dict[str, dict[str, float | None]] = {}
    for _, r in df.iterrows():
        lad_code = str(r["ONS Code"]).strip().upper() if pd.notna(r["ONS Code"]) else ""
        if not lad_code.startswith("E"):
            continue
        if any(lad_code.startswith(prefix) for prefix in _ENGLAND_SKIP_PREFIXES):
            continue
        if not is_supported_lad_code(lad_code):
            continue

        bands = [
            _as_float(r["Band A"]),
            _as_float(r["Band B"]),
            _as_float(r["Band C"]),
            _as_float(r["Band D"]),
            _as_float(r["Band E"]),
            _as_float(r["Band F"]),
            _as_float(r["Band G "]),
            _as_float(r["Band H"]),
        ]
        if not any(value is not None for value in bands):
            continue

        record = _empty_band_record()
        for column, value in zip(_BAND_COLUMNS[:8], bands):
            record[column] = value
        results[lad_code] = record

    print(f"  Collected {len(results):,} England LAD rows", flush=True)
    return results


def _read_wales_rows(src_path: str | None) -> dict[str, dict[str, float | None]]:
    """Return lad_code → band values from an optional Welsh StatsWales CSV export."""
    if not src_path:
        print("  No Welsh council-tax CSV present; leaving Wales unchanged for now", flush=True)
        return {}

    df = pd.read_csv(src_path)
    print(f"  Read {len(df)} rows from Welsh CSV", flush=True)

    authority_col = "Authority_reference"
    year_ref_col = "Year_reference"
    value_col = "Data values"
    value_sort_col = "Data values_sort"    # clean numeric column from StatsWales
    band_col = "Band_reference"
    description_col = "Data description"

    required_columns = {authority_col, year_ref_col, value_col, band_col}
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"Welsh council-tax CSV missing required columns: {', '.join(missing)}")

    working = df.copy()
    if description_col in working.columns:
        working = working[working[description_col].astype(str).str.strip().eq("Council tax in £")]

    working[authority_col] = working[authority_col].astype(str).str.strip().str.upper()
    working[band_col] = working[band_col].astype(str).str.strip().str.upper()
    working[year_ref_col] = pd.to_numeric(working[year_ref_col], errors="coerce")
    # StatsWales CSV has formatted "Data values" (e.g. "1,255.961") that fails
    # to_numeric. Prefer the clean "Data values_sort" column when present.
    if value_sort_col in working.columns:
        working[value_col] = pd.to_numeric(working[value_sort_col], errors="coerce")
    else:
        working[value_col] = pd.to_numeric(working[value_col], errors="coerce")

    working = working[
        working[authority_col].map(lambda code: code.startswith("W") and is_supported_lad_code(code))
    ]
    working = working[working[band_col].isin(_WELSH_BAND_MAP.keys())]
    working = working[working[year_ref_col].notna()]
    working = working[working[value_col].notna()]

    if working.empty:
        print("  Welsh CSV present but no supported LAD rows were found", flush=True)
        return {}

    latest_year_ref = int(working[year_ref_col].max())
    working = working[working[year_ref_col] == latest_year_ref]

    results: dict[str, dict[str, float | None]] = {}
    for _, row in working.iterrows():
        lad_code = row[authority_col]
        band_code = row[band_col]
        record = results.setdefault(lad_code, _empty_band_record())
        record[_WELSH_BAND_MAP[band_code]] = float(row[value_col])

    print(f"  Collected {len(results):,} Wales LAD rows for latest year {latest_year_ref}", flush=True)
    return results


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------


def run(db_url: str) -> int:
    """
    Ingest council-tax band charges → core_council_tax_lad.

    Strategy:
    1. Read the England VOA ODS file.
    2. Optionally read the Welsh StatsWales CSV if present.
    3. Truncate core_council_tax_lad and bulk insert the combined supported LAD rows.
    4. Return the final row count.
    """
    england_path = _resolve_england_path()
    wales_path = _resolve_wales_path()
    print(f"  England council-tax source: {england_path}", flush=True)
    print(f"  Wales council-tax source:   {wales_path or 'not provided'}", flush=True)

    combined = _read_england_rows(england_path)
    combined.update(_read_wales_rows(wales_path))

    rows = [
        (
            lad_code,
            values["band_a"],
            values["band_b"],
            values["band_c"],
            values["band_d"],
            values["band_e"],
            values["band_f"],
            values["band_g"],
            values["band_h"],
            values["band_i"],
        )
        for lad_code, values in sorted(combined.items())
        if any(values[column] is not None for column in _BAND_COLUMNS)
    ]

    print(f"  Prepared {len(rows):,} combined LAD rows", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['council_tax_lad']}_new (LIKE {TABLE_NAMES['council_tax_lad']} INCLUDING ALL)")
    conn.commit()

    if rows:
        execute_values(
            cur,
            f"""
            INSERT INTO {TABLE_NAMES['council_tax_lad']}_new
                (lad_code, band_a, band_b, band_c, band_d, band_e, band_f, band_g, band_h, band_i)
            VALUES %s
            ON CONFLICT (lad_code) DO UPDATE SET
                band_a = EXCLUDED.band_a,
                band_b = EXCLUDED.band_b,
                band_c = EXCLUDED.band_c,
                band_d = EXCLUDED.band_d,
                band_e = EXCLUDED.band_e,
                band_f = EXCLUDED.band_f,
                band_g = EXCLUDED.band_g,
                band_h = EXCLUDED.band_h,
                band_i = EXCLUDED.band_i
            """,
            rows,
        )
        conn.commit()

    blue_green_swap(conn, TABLE_NAMES['council_tax_lad'])

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['council_tax_lad']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_council_tax_lad: {count:,} rows", flush=True)
    return count
