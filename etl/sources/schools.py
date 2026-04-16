"""
sources/schools.py — DfE GIAS + Ofsted + KS2/KS4 + StatsWales → core_schools

England + Wales school ingestion:
  1. Download GIAS JSON from GitHub (cached in etl/data/).
  2. Load KS2 progress scores (etl/data/ks2_school_2024.csv) — optional.
  3. Load KS4 progress/attainment scores (etl/data/ks4_school_2024.csv) — optional.
  4. Load Ofsted ratings from etl/data/ofsted_latest.csv (England only).
  5. Load Welsh school phases from etl/data/statswales_schools.csv (optional).
     GIAS marks all Welsh schools as phase "Not applicable"; the StatsWales
     PLASC dataset provides the actual sector (Primary/Secondary/etc.).
     Matching is by school name + local authority with normalization.
     Welsh schools have no Ofsted/KS scores (Estyn abolished gradings in 2022).
  6. Upsert all open E+W schools into core_schools (ON CONFLICT DO UPDATE).
  7. Mark schools absent from the open set as is_open = false.
  8. Rebuild PostGIS geometry column.

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns open school count in core_schools)

Data files in etl/data/ (required):
    ofsted_latest.csv        — from https://www.gov.uk/government/statistics/
                                 state-funded-schools-inspections-and-outcomes-as-at-31-august

Data files in etl/data/ (optional — scores/phases will be NULL if absent):
    ks2_school_2024.csv      — from DfE key stage 2 performance tables
    ks4_school_2024.csv      — from DfE key stage 4 performance tables
    statswales_schools.csv   — from https://stats.gov.wales/ (PLASC school census)

GIAS JSON is auto-downloaded from:
    https://dfe-digital.github.io/gias-data/schools.json
"""

import csv
import json
import os
import re

import psycopg2
import requests
from psycopg2.extras import execute_values

from constants import SCHEDULE_MONTHLY, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

METADATA = {
    "name":        "schools",
    "description": "DfE GIAS + Ofsted ratings + KS2/KS4 scores + Welsh Gov phases → core_schools (E+W).",
    "schedule":           SCHEDULE_MONTHLY,
    "depends_on":         ["postcodes"],
    "tables_written":     [TABLE_NAMES["schools"]],
    "cache_key_patterns": ["area:*"],
    "expected_row_range": (20_000, 36_500),  # ~23K England + ~1.4K Wales
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DATA_DIR         = os.path.join(os.path.dirname(__file__), "..", "data")
_GIAS_PATH        = os.path.join(_DATA_DIR, "gias_schools.json")
_OFSTED_PATH      = os.path.join(_DATA_DIR, "ofsted_latest.csv")
_KS2_PATH         = os.path.join(_DATA_DIR, "ks2_school_2024.csv")
_KS4_PATH         = os.path.join(_DATA_DIR, "ks4_school_2024.csv")
_WELSH_DIR_PATH   = os.path.join(_DATA_DIR, "welsh_schools_directory.ods")

_GIAS_JSON_URL    = "https://dfe-digital.github.io/gias-data/schools.json"

# Phase labels accepted as valid school phases (English education system)
_PHASE_MAP = {
    "Primary":                    "Primary",
    "Secondary":                  "Secondary",
    "All-through":                "All-through",
    "Middle deemed primary":      "Middle deemed primary",
    "Middle deemed secondary":    "Middle deemed secondary",
    "16 plus":                    "16 plus",
    "Not applicable":             "Not applicable",   # nurseries, special, AP
    "Nursery":                    "Nursery",
}

# Welsh Government sector → our phase label
_WELSH_SECTOR_TO_PHASE = {
    "Primary":   "Primary",
    "Secondary": "Secondary",
    "Middle":    "All-through",
    "Special":   "Not applicable",
    "Nursery":   "Nursery",
}

# Ofsted numeric code → readable label
_OFSTED_NUM_TO_TEXT = {
    "1": "Outstanding",
    "2": "Good",
    "3": "Requires Improvement",
    "4": "Inadequate",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _download_gias():
    if os.path.exists(_GIAS_PATH):
        print(f"  GIAS JSON present ({_GIAS_PATH}), skipping download", flush=True)
        return
    print(f"  Downloading GIAS JSON from {_GIAS_JSON_URL}...", flush=True)
    resp = requests.get(_GIAS_JSON_URL, timeout=120)
    resp.raise_for_status()
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_GIAS_PATH, "wb") as f:
        f.write(resp.content)
    print(f"  Downloaded {len(resp.content) / 1_048_576:.1f} MB", flush=True)


def _load_ks2():
    """Load KS2 progress scores: {urn: {reading: float, maths: float}}."""
    ks2 = {}
    if not os.path.exists(_KS2_PATH):
        print(f"  KS2 file not found at {_KS2_PATH} — scores will be NULL", flush=True)
        return ks2
    with open(_KS2_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            urn_str = r.get("school_urn", "").strip()
            if not urn_str:
                continue
            try:
                urn     = int(urn_str)
                subject = r.get("subject", "").lower()
                score   = r.get("progress_measure_score", "")
                score_f = float(score) if score and score != "x" else None
            except (ValueError, TypeError):
                continue
            if urn not in ks2:
                ks2[urn] = {}
            if "reading" in subject and score_f is not None:
                ks2[urn]["reading"] = score_f
            elif "math" in subject and score_f is not None:
                ks2[urn]["maths"] = score_f
    print(f"  KS2 scores loaded: {len(ks2):,}", flush=True)
    return ks2


def _load_ks4():
    """Load KS4 progress/attainment scores: {urn: {p8: float, a8: float}}."""
    ks4 = {}
    if not os.path.exists(_KS4_PATH):
        print(f"  KS4 file not found at {_KS4_PATH} — scores will be NULL", flush=True)
        return ks4
    _supressed = {"x", "SUPP", "NE", "z", "c"}
    with open(_KS4_PATH, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            urn_str = r.get("school_urn", "").strip()
            if not urn_str:
                continue
            if r.get("breakdown", "") != "Total":
                continue
            try:
                urn = int(urn_str)
                p8  = r.get("avg_p8score", "")
                a8  = r.get("avg_att8", "")
                p8_f = float(p8) if p8 and p8 not in _supressed else None
                a8_f = float(a8) if a8 and a8 not in _supressed else None
            except (ValueError, TypeError):
                continue
            if p8_f is not None or a8_f is not None:
                ks4[urn] = {"p8": p8_f, "a8": a8_f}
    print(f"  KS4 scores loaded: {len(ks4):,}", flush=True)
    return ks4


def _load_ofsted():
    """Load Ofsted ratings: {urn: (rating_text, inspection_date)}."""
    if not os.path.exists(_OFSTED_PATH):
        raise FileNotFoundError(
            f"Ofsted CSV not found: {_OFSTED_PATH}. "
            "Download from https://www.gov.uk/government/statistics/"
            "state-funded-schools-inspections-and-outcomes-as-at-31-august"
        )
    ratings = {}
    with open(_OFSTED_PATH, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for r in reader:
            urn_str = r.get("URN", "").strip()
            if not urn_str or not urn_str.isdigit():
                continue
            num        = r.get("Overall effectiveness", "").strip()
            text_rating = _OFSTED_NUM_TO_TEXT.get(num)
            if not text_rating:
                continue
            date_str  = r.get("Inspection start date", "").strip()
            date_iso  = None
            if date_str and date_str != "NULL":
                parts = date_str.split("/")
                if len(parts) == 3:
                    date_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"
            ratings[int(urn_str)] = (text_rating, date_iso)
    print(f"  Ofsted ratings loaded: {len(ratings):,}", flush=True)
    return ratings


def _load_welsh_phases(gias_schools: list[dict]) -> dict[int, str]:
    """
    Load Welsh school phases from the Welsh Government maintained schools
    directory ODS. Returns {urn: phase_label} for Welsh schools that can be
    matched to GIAS by postcode+LA, name+LA, or partial name+LA.

    The Welsh directory has authoritative sector labels (Primary, Secondary,
    Middle, Special, Nursery). GIAS marks all Welsh schools as phase
    "Not applicable", so this lookup is the only way to assign correct phases.

    Download from:
        https://www.gov.wales/addresses-and-phone-numbers-schools-and-pupil-referral-units
    """
    if not os.path.exists(_WELSH_DIR_PATH):
        print(f"  Welsh schools directory not found at {_WELSH_DIR_PATH} — "
              "Welsh schools will have phase 'Not applicable'", flush=True)
        return {}

    import pandas as pd

    wd = pd.read_excel(_WELSH_DIR_PATH, sheet_name="Maintained",
                        header=0, engine="odf")
    print(f"  Welsh directory loaded: {len(wd):,} schools", flush=True)

    def norm_pc(pc):
        return str(pc).strip().upper().replace(" ", "") if pd.notna(pc) else ""

    def norm_name(n):
        return re.sub(r"[^a-z0-9]", "", str(n).strip().lower())

    # Build GIAS indexes for Welsh schools only
    welsh_gias = [s for s in gias_schools
                  if s.get("administritive_district_code", "").startswith("W")
                  and s.get("status") in ("Open", "Open, but proposed to close")]

    gias_by_pc_la: dict[tuple[str, str], list[dict]] = {}
    gias_by_name_la: dict[tuple[str, str], list[dict]] = {}
    for s in welsh_gias:
        pc = norm_pc(s.get("postcode", ""))
        la = str(s.get("local_authority_code", "")).strip()
        name = norm_name(s.get("name", ""))
        gias_by_pc_la.setdefault((pc, la), []).append(s)
        gias_by_name_la.setdefault((name, la), []).append(s)

    result: dict[int, str] = {}

    for _, row in wd.iterrows():
        sector_raw = str(row.get("Sector", "")).strip()
        phase = _WELSH_SECTOR_TO_PHASE.get(sector_raw)
        if not phase:
            continue

        pc = norm_pc(row.get("Postcode", ""))
        la_raw = row.get("LA Code")
        la = str(int(la_raw)).strip() if pd.notna(la_raw) else ""
        name = norm_name(row.get("School Name", ""))

        matched_urn = None

        # Strategy 1: unique postcode + LA match
        candidates = gias_by_pc_la.get((pc, la), [])
        if len(candidates) == 1:
            matched_urn = candidates[0]["urn"]
        elif len(candidates) > 1:
            # Strategy 2: postcode + LA + exact name
            for c in candidates:
                if norm_name(c["name"]) == name:
                    matched_urn = c["urn"]
                    break
            else:
                # Strategy 2b: postcode + LA + name containment
                for c in candidates:
                    cn = norm_name(c["name"])
                    if name in cn or cn in name:
                        matched_urn = c["urn"]
                        break

        if matched_urn is None:
            # Strategy 3: exact name + LA
            candidates = gias_by_name_la.get((name, la), [])
            if len(candidates) == 1:
                matched_urn = candidates[0]["urn"]

        if matched_urn is None:
            # Strategy 4: partial name + LA (for renamed/merged schools)
            for s in welsh_gias:
                if str(s.get("local_authority_code", "")).strip() != la:
                    continue
                cn = norm_name(s.get("name", ""))
                if len(name) >= 8 and (name in cn or cn in name):
                    if s["urn"] not in result:
                        matched_urn = s["urn"]
                        break

        if matched_urn is not None:
            result[int(matched_urn)] = phase

    print(f"  Welsh phases matched: {len(result):,} URNs "
          f"(Primary={sum(1 for v in result.values() if v == 'Primary')}, "
          f"Secondary={sum(1 for v in result.values() if v == 'Secondary')}, "
          f"other={sum(1 for v in result.values() if v not in ('Primary', 'Secondary'))})",
          flush=True)
    return result


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest GIAS + KS2/KS4 + Ofsted + Welsh phases → core_schools.
    Returns count of open schools.
    """
    _download_gias()
    ks2    = _load_ks2()
    ks4    = _load_ks4()
    ofsted = _load_ofsted()

    with open(_GIAS_PATH, "r", encoding="utf-8") as f:
        schools = json.load(f)
    print(f"  GIAS schools: {len(schools):,}", flush=True)

    # Load Welsh school phases from Welsh Government directory
    welsh_phases = _load_welsh_phases(schools)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    rows = []
    welsh_included = 0
    welsh_skipped = 0
    for s in schools:
        status = s.get("status", "")
        if status not in ("Open", "Open, but proposed to close"):
            continue

        urn_raw = s.get("urn")
        if not urn_raw:
            continue
        try:
            urn = int(urn_raw)
        except (ValueError, TypeError):
            continue

        lad_code = s.get("administritive_district_code", "")
        if not (lad_code.startswith("E") or lad_code.startswith("W")):
            continue

        # Resolve phase: English schools use GIAS phase_of_education,
        # Welsh schools use the Welsh Government directory lookup.
        if lad_code.startswith("W"):
            phase = welsh_phases.get(urn)
            if not phase:
                welsh_skipped += 1
                continue  # Not in Welsh maintained directory — skip
            welsh_included += 1
        else:
            phase = s.get("phase_of_education", "")
            if phase not in _PHASE_MAP:
                continue
            phase = _PHASE_MAP[phase]

        try:
            lat_f = float(s["latitude"])  if s.get("latitude")  else None
            lon_f = float(s["longitude"]) if s.get("longitude") else None
        except (ValueError, TypeError):
            lat_f = lon_f = None

        # Skip schools without coordinates — cannot place on map
        if lat_f is None or lon_f is None:
            continue

        ofsted_rating, ofsted_date = ofsted.get(urn, (None, None))
        k2 = ks2.get(urn, {})
        k4 = ks4.get(urn, {})

        rows.append((
            urn,
            s.get("name", ""),
            s.get("type", ""),
            phase,
            s.get("postcode", ""),
            lat_f, lon_f,
            lad_code,
            ofsted_rating,
            ofsted_date,
            k2.get("reading"),
            k2.get("maths"),
            k4.get("p8"),
            k4.get("a8"),
            True,   # is_open
        ))

    print(f"  Prepared {len(rows):,} rows for upsert "
          f"(Welsh: {welsh_included:,} included, {welsh_skipped:,} skipped — "
          f"not in maintained directory)", flush=True)

    execute_values(
        cur,
        f"""INSERT INTO {TABLE_NAMES['schools']} (
                urn, school_name, school_type, phase, postcode,
                latitude, longitude, lad_code,
                ofsted_rating, ofsted_date,
                ks2_reading_pct, ks2_maths_pct,
                gcse_progress_8, gcse_attainment_8,
                is_open
            ) VALUES %s
            ON CONFLICT (urn) DO UPDATE SET
                school_name    = EXCLUDED.school_name,
                school_type    = EXCLUDED.school_type,
                phase          = EXCLUDED.phase,
                postcode       = EXCLUDED.postcode,
                latitude       = EXCLUDED.latitude,
                longitude      = EXCLUDED.longitude,
                lad_code       = EXCLUDED.lad_code,
                ofsted_rating  = COALESCE(EXCLUDED.ofsted_rating,
                                          {TABLE_NAMES['schools']}.ofsted_rating),
                ofsted_date    = COALESCE(EXCLUDED.ofsted_date,
                                          {TABLE_NAMES['schools']}.ofsted_date),
                ks2_reading_pct = COALESCE(EXCLUDED.ks2_reading_pct,
                                           {TABLE_NAMES['schools']}.ks2_reading_pct),
                ks2_maths_pct  = COALESCE(EXCLUDED.ks2_maths_pct,
                                           {TABLE_NAMES['schools']}.ks2_maths_pct),
                gcse_progress_8  = COALESCE(EXCLUDED.gcse_progress_8,
                                             {TABLE_NAMES['schools']}.gcse_progress_8),
                gcse_attainment_8 = COALESCE(EXCLUDED.gcse_attainment_8,
                                              {TABLE_NAMES['schools']}.gcse_attainment_8),
                is_open        = EXCLUDED.is_open""",
        rows,
        page_size=5000,
    )
    conn.commit()

    # Mark schools absent from the open GIAS set as closed
    open_urns = [r[0] for r in rows]
    cur.execute(
        f"UPDATE {TABLE_NAMES['schools']} SET is_open = false WHERE urn != ALL(%s)",
        (open_urns,),
    )
    closed_count = cur.rowcount
    conn.commit()
    print(f"  Marked {closed_count:,} schools as closed", flush=True)

    # Rebuild PostGIS geometry
    cur.execute(f"""
        UPDATE {TABLE_NAMES['schools']}
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL
          AND (geom IS NULL
               OR ST_X(geom) != longitude
               OR ST_Y(geom) != latitude)
    """)
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['schools']} WHERE is_open = true")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  core_schools: {count:,} open schools", flush=True)
    return count
