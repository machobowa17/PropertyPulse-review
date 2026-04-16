"""
sources/broadband.py — Ofcom Connected Nations → core_broadband_postcode + core_broadband_lad

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_broadband_postcode)

Data files required in etl/data/broadband/ (or set env vars to override):
    BROADBAND_POSTCODE_DIR  — directory of postcode-level CSV files
                              (default: etl/data/broadband/postcode_files/postcode_files/)
    BROADBAND_COVERAGE_PATH — fixed_coverage_laua CSV
                              (default: etl/data/broadband/fixed_coverage_laua/*.csv)
    BROADBAND_PERFORMANCE_PATH — fixed_performance_laua CSV
                              (default: etl/data/broadband/fixed_performance_laua/*.csv)

Download from Ofcom Connected Nations:
    https://www.ofcom.org.uk/research-and-data/telecoms-research/connected-nations
"""

import csv
import glob
import io
import os

import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ANNUAL, TABLE_NAMES, supported_country_prefixes
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

_SUPPORTED_PREFIXES = supported_country_prefixes()

METADATA = {
    "name":               "broadband",
    "description":        "Ofcom Connected Nations → core_broadband_postcode (1.7M postcodes) + core_broadband_lad (supported-country LAD-level speeds/coverage).",
    "schedule":           SCHEDULE_ANNUAL,
    "depends_on":         [],
    "tables_written":     [TABLE_NAMES["broadband_postcode"], TABLE_NAMES["broadband_lad"]],
    "cache_key_patterns": [],
    "expected_row_range": (1_500_000, 2_000_000),
}

# ---------------------------------------------------------------------------
# Helper: resolve data file paths
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_postcode_dir():
    path = os.environ.get("BROADBAND_POSTCODE_DIR")
    if path:
        return path
    candidate = os.path.join(_ETL_DATA_DIR, "broadband", "postcode_files", "postcode_files")
    if os.path.isdir(candidate):
        return candidate
    raise FileNotFoundError(
        f"Broadband postcode directory not found at {candidate}. "
        "Download Ofcom Connected Nations postcode files and extract to etl/data/broadband/, "
        "or set the BROADBAND_POSTCODE_DIR env var."
    )


def _resolve_coverage_path():
    path = os.environ.get("BROADBAND_COVERAGE_PATH")
    if path:
        return path
    matches = glob.glob(os.path.join(_ETL_DATA_DIR, "broadband", "fixed_coverage_laua", "*.csv"))
    if matches:
        return sorted(matches)[-1]
    raise FileNotFoundError(
        f"No coverage CSV found in etl/data/broadband/fixed_coverage_laua/. "
        "Set the BROADBAND_COVERAGE_PATH env var or place the file there."
    )


def _resolve_performance_path():
    path = os.environ.get("BROADBAND_PERFORMANCE_PATH")
    if path:
        return path
    matches = glob.glob(os.path.join(_ETL_DATA_DIR, "broadband", "fixed_performance_laua", "*.csv"))
    if matches:
        return sorted(matches)[-1]
    raise FileNotFoundError(
        f"No performance CSV found in etl/data/broadband/fixed_performance_laua/. "
        "Set the BROADBAND_PERFORMANCE_PATH env var or place the file there."
    )


# ---------------------------------------------------------------------------
# Helpers for LAD speed calculation
# ---------------------------------------------------------------------------

def _load_performance(performance_path):
    """Return dict: lad_code → (dl_bands list, ul_bands list) — avg speed per band."""
    perf = {}
    with open(performance_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lad = r["laua"].strip()

            def flt(v):
                try:
                    return float(v) if v and v.strip() else None
                except (ValueError, TypeError):
                    return None

            dl = [
                flt(r.get("Average max download speed (Mbit/s) for lines <10Mbit/s")),
                flt(r.get("Average max download speed (Mbit/s) for lines 10<30Mbit/s")),
                flt(r.get("Average max download speed (Mbit/s) for lines 30<100Mbit/s")),
                flt(r.get("Average max download speed (Mbit/s) for lines 100<300Mbit/s")),
                flt(r.get("Average max download speed (Mbit/s) for lines 300<900Mbit/s")),
                flt(r.get("Average max download speed (Mbit/s) for lines >=900Mbit/s")),
            ]
            ul = [
                flt(r.get("Average max upload speed (Mbit/s) for lines <10Mbit/s")),
                flt(r.get("Average max upload speed (Mbit/s) for lines 10<30Mbit/s")),
                flt(r.get("Average max upload speed (Mbit/s) for lines 30<100Mbit/s")),
                flt(r.get("Average max upload speed (Mbit/s) for lines 100<300Mbit/s")),
                flt(r.get("Average max upload speed (Mbit/s) for lines 300<900Mbit/s")),
                flt(r.get("Average max upload speed (Mbit/s) for lines >=900Mbit/s")),
            ]
            perf[lad] = (dl, ul)
    return perf


def _weighted_avg(counts, speeds):
    """Compute weighted average speed given premise counts per band and avg speed per band."""
    total_w = 0.0
    total_ws = 0.0
    for cnt, spd in zip(counts, speeds):
        if cnt and spd and cnt > 0:
            total_w += cnt
            total_ws += cnt * spd
    return round(total_ws / total_w, 1) if total_w > 0 else None


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest Ofcom Connected Nations → core_broadband_postcode + core_broadband_lad.

    Strategy:
    1. Truncate both tables.
    2. Stream postcode-level CSV files (one per postcode area) via COPY into
       core_broadband_postcode.
    3. Load LAD coverage + performance CSVs; compute weighted average speeds;
       bulk insert into core_broadband_lad.
    4. Return final row count in core_broadband_postcode.
    """
    postcode_dir     = _resolve_postcode_dir()
    coverage_path    = _resolve_coverage_path()
    performance_path = _resolve_performance_path()

    print(f"  Postcode dir:    {postcode_dir}", flush=True)
    print(f"  Coverage path:   {coverage_path}", flush=True)
    print(f"  Performance path:{performance_path}", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    # ------------------------------------------------------------------
    # Part 1: core_broadband_postcode
    # ------------------------------------------------------------------
    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['broadband_postcode']}_new (LIKE {TABLE_NAMES['broadband_postcode']} INCLUDING ALL)")
    conn.commit()

    csv_files = sorted(
        os.path.join(postcode_dir, f)
        for f in os.listdir(postcode_dir)
        if f.endswith(".csv")
    )
    print(f"  Found {len(csv_files)} postcode area files", flush=True)

    total_postcode = 0
    for csv_path in csv_files:
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter="\t")

        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for r in reader:
                pc = r.get("postcode_space", "").strip()
                if not pc:
                    continue
                try:
                    sfbb    = float(r.get("SFBB availability (% premises)", "") or 0)
                    ufbb    = float(r.get("UFBB availability (% premises)", "") or 0)
                    gigabit = float(r.get("Gigabit availability (% premises)", "") or 0)
                    fttp    = ufbb   # Ofcom ultrafast ≈ full fibre
                except (ValueError, TypeError):
                    continue

                # avg_download_mbps and avg_upload_mbps are postcode-level NULL
                # (only available at LAD level from the performance file)
                writer.writerow([pc, "", "", sfbb, ufbb, gigabit, fttp])

        buf.seek(0)
        cur.copy_from(
            buf,
            f"{TABLE_NAMES['broadband_postcode']}_new",
            sep="\t",
            null="",
            columns=["postcode", "avg_download_mbps", "avg_upload_mbps",
                     "superfast_pct", "ultrafast_pct", "gigabit_pct", "fttp_pct"],
        )
        conn.commit()
        total_postcode += buf.getvalue().count("\n")

    print(f"  Loaded ~{total_postcode:,} postcode rows", flush=True)
    blue_green_swap(conn, TABLE_NAMES['broadband_postcode'])

    # ------------------------------------------------------------------
    # Part 2: core_broadband_lad
    # ------------------------------------------------------------------
    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['broadband_lad']}_new (LIKE {TABLE_NAMES['broadband_lad']} INCLUDING ALL)")
    conn.commit()

    perf = _load_performance(performance_path)
    print(f"  Performance data loaded for {len(perf):,} LADs", flush=True)

    lad_rows = []
    with open(coverage_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lad = r["laua"].strip()
            if not lad[:1].upper() in _SUPPORTED_PREFIXES:
                continue

            def flt(v):
                try:
                    return float(v.strip()) if v and v.strip() else None
                except (ValueError, TypeError):
                    return None

            def nt(v):
                try:
                    return int(float(v.strip())) if v and v.strip() else 0
                except (ValueError, TypeError):
                    return 0

            # Map coverage band premise counts to the 6 performance speed bands
            # Coverage bands: 0<2, 2<5, 5<10 → <10 performance band
            # 10<30 → 10<30 band
            # 30<300 → split evenly across 30<100, 100<300, 300<900
            # >=300 → >=900 band
            n_lt10    = (nt(r.get("Number of premises with 0<2Mbit/s download speed",   "")) +
                         nt(r.get("Number of premises with 2<5Mbit/s download speed",   "")) +
                         nt(r.get("Number of premises with 5<10Mbit/s download speed",  "")))
            n_10_30   = nt(r.get("Number of premises with 10<30Mbit/s download speed",  ""))
            n_30_300  = nt(r.get("Number of premises with 30<300Mbit/s download speed", ""))
            n_gte300  = nt(r.get("Number of premises with >=300Mbit/s download speed",  ""))

            n_30_100  = n_30_300 // 3
            n_100_300 = n_30_300 // 3
            n_300_900 = n_30_300 - n_30_100 - n_100_300
            n_gte900  = n_gte300

            counts = [n_lt10, n_10_30, n_30_100, n_100_300, n_300_900, n_gte900]

            dl_avg = ul_avg = None
            if lad in perf:
                dl_bands, ul_bands = perf[lad]
                dl_avg = _weighted_avg(counts, dl_bands)
                ul_avg = _weighted_avg(counts, ul_bands)

            lad_rows.append((
                lad,
                r.get("laua_name", "").strip(),
                dl_avg,
                ul_avg,
                flt(r.get("Full Fibre availability (% premises)", "")),
                flt(r.get("SFBB availability (% premises)", "")),
                flt(r.get("Gigabit availability (% premises)", "")),
                flt(r.get("UFBB availability (% premises)", "")),
            ))

    execute_values(
        cur,
        f"""
        INSERT INTO {TABLE_NAMES['broadband_lad']}_new
            (lad_code, lad_name, avg_download_mbps, avg_upload_mbps,
             full_fibre_pct, superfast_pct, gigabit_pct, ultrafast_pct)
        VALUES %s
        ON CONFLICT (lad_code) DO UPDATE SET
            lad_name         = EXCLUDED.lad_name,
            avg_download_mbps = EXCLUDED.avg_download_mbps,
            avg_upload_mbps  = EXCLUDED.avg_upload_mbps,
            full_fibre_pct   = EXCLUDED.full_fibre_pct,
            superfast_pct    = EXCLUDED.superfast_pct,
            gigabit_pct      = EXCLUDED.gigabit_pct,
            ultrafast_pct    = EXCLUDED.ultrafast_pct
        """,
        lad_rows,
        page_size=500,
    )
    conn.commit()
    print(f"  Loaded {len(lad_rows):,} LAD rows", flush=True)
    blue_green_swap(conn, TABLE_NAMES['broadband_lad'])

    # Return final row count in core_broadband_postcode
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['broadband_postcode']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
