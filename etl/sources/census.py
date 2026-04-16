"""
sources/census.py — Census 2021 → core_census_lsoa + core_census_ethnicity_ward

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_census_lsoa)

Consolidates ingest_census.py (TS001/TS003/TS006/TS007A/TS044/TS054),
ingest_census_extra2.py (TS017/TS022/TS058), and extra columns
(TS037 health, TS045 cars, TS066 economic activity, TS067 qualifications, TS004 country of birth).

All LSOA-level data writes to the consolidated core_census_lsoa wide table.
Ethnicity (ward-level) writes separately to core_census_ethnicity_ward.

Data files required in etl/data/census/ (or set CENSUS_DIR env var to override):
    census2021-ts001-lsoa.csv  — TS001 Population (total residents)
    census2021-ts006-lsoa.csv  — TS006 Population density
    census2021-ts003-lsoa.csv  — TS003 Household composition
    census2021-ts007a-lsoa.csv — TS007A Age bands (5-year)
    census2021-ts054-lsoa.csv  — TS054 Tenure of household
    census2021-ts044-lsoa.csv  — TS044 Accommodation type
    census2021-ts017-lsoa.csv  — TS017 Household size distribution
    census2021-ts022-ward.csv  — TS022 Ethnicity (detailed) by ward
    census2021-ts058-lsoa.csv  — TS058 Distance to work
    census2021-ts037-lsoa.csv  — TS037 General health (for pct_good_health)
    census2021-ts045-lsoa.csv  — TS045 Car/van availability (for pct_no_car)
    census2021-ts066-lsoa.csv  — TS066 Economic activity (for pct_economically_active)
    census2021-ts067-lsoa.csv  — TS067 Qualifications (for pct_degree)
    census2021-ts004-lsoa.csv  — TS004 Country of birth (for pct_born_abroad)

Download from:
    https://www.nomisweb.co.uk/sources/census_2021_bulk
"""

import csv
import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from constants import SCHEDULE_ONE_TIME, TABLE_NAMES
from utils import blue_green_swap


_EW_CENSUS_PREFIXES = ("E", "W")

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":           "census",
    "description":    "Census 2021 (TS001/003/004/006/007A/017/022/027/031/037/044/045/054/058/066/067) → core_census_lsoa + core_census_ethnicity_ward + core_census_religion_ward.",
    "schedule":       SCHEDULE_ONE_TIME,
    "depends_on":     [],
    "tables_written": [
        TABLE_NAMES["census_lsoa"],
        TABLE_NAMES["census_ethnicity_ward"],
        TABLE_NAMES["census_religion_ward"],
    ],
    "cache_key_patterns": [],
    "expected_row_range": (32_000, 36_000),   # census_lsoa row count (primary)
}

# ---------------------------------------------------------------------------
# Helper: resolve census data directory
# ---------------------------------------------------------------------------

_ETL_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _resolve_census_dir():
    path = os.environ.get("CENSUS_DIR")
    if path:
        return path
    return os.path.join(_ETL_DATA_DIR, "census")


def _read_census_csv(census_dir, filename):
    """Load a census CSV, filtering to England-and-Wales geographies only."""
    df = pd.read_csv(os.path.join(census_dir, filename))
    return df[df["geography code"].str.startswith(_EW_CENSUS_PREFIXES, na=False)]


# ---------------------------------------------------------------------------
# Median age estimation from 5-year age bands
# ---------------------------------------------------------------------------

def _estimate_median_age(row):
    """Estimate median age from 5-year band counts using linear interpolation."""
    bands = [
        (0,  4,  row.get("Age: Aged 4 years and under", 0) or 0),
        (5,  9,  row.get("Age: Aged 5 to 9 years", 0) or 0),
        (10, 14, row.get("Age: Aged 10 to 14 years", 0) or 0),
        (15, 19, row.get("Age: Aged 15 to 19 years", 0) or 0),
        (20, 24, row.get("Age: Aged 20 to 24 years", 0) or 0),
        (25, 29, row.get("Age: Aged 25 to 29 years", 0) or 0),
        (30, 34, row.get("Age: Aged 30 to 34 years", 0) or 0),
        (35, 39, row.get("Age: Aged 35 to 39 years", 0) or 0),
        (40, 44, row.get("Age: Aged 40 to 44 years", 0) or 0),
        (45, 49, row.get("Age: Aged 45 to 49 years", 0) or 0),
        (50, 54, row.get("Age: Aged 50 to 54 years", 0) or 0),
        (55, 59, row.get("Age: Aged 55 to 59 years", 0) or 0),
        (60, 64, row.get("Age: Aged 60 to 64 years", 0) or 0),
        (65, 69, row.get("Age: Aged 65 to 69 years", 0) or 0),
        (70, 74, row.get("Age: Aged 70 to 74 years", 0) or 0),
        (75, 79, row.get("Age: Aged 75 to 79 years", 0) or 0),
        (80, 84, row.get("Age: Aged 80 to 84 years", 0) or 0),
        (85, 90, row.get("Age: Aged 85 years and over", 0) or 0),
    ]
    total = sum(c for _, _, c in bands)
    if total == 0:
        return None
    half = total / 2
    cumulative = 0
    for low, high, count in bands:
        if cumulative + count >= half:
            fraction = (half - cumulative) / count if count > 0 else 0
            return round(low + fraction * (high - low + 1), 1)
        cumulative += count
    return None


# ---------------------------------------------------------------------------
# Part helpers
# ---------------------------------------------------------------------------

def _ingest_demographics(cur, census_dir):
    """TS001 + TS006 + TS003 + TS007A → demographics columns in core_census_lsoa."""
    print("  Ingesting census demographics (TS001/006/003/007A)...", flush=True)

    ts001 = _read_census_csv(census_dir, "census2021-ts001-lsoa.csv")
    ts001 = ts001.rename(columns={"geography code": "lsoa_code"})
    ts001["total_population"] = pd.to_numeric(
        ts001["Residence type: Total; measures: Value"], errors="coerce"
    ).astype("Int64")

    ts006 = _read_census_csv(census_dir, "census2021-ts006-lsoa.csv")
    ts006 = ts006.rename(columns={"geography code": "lsoa_code"})
    ts006["population_density"] = pd.to_numeric(
        ts006["Population Density: Persons per square kilometre; measures: Value"], errors="coerce"
    )

    ts003 = _read_census_csv(census_dir, "census2021-ts003-lsoa.csv")
    ts003 = ts003.rename(columns={"geography code": "lsoa_code"})
    hh_total = ts003["Household composition: Total; measures: Value"]
    ts003["pct_families"] = (ts003["Household composition: Single family household; measures: Value"]     / hh_total * 100).round(2)
    ts003["pct_singles"]  = (ts003["Household composition: One person household; measures: Value"]         / hh_total * 100).round(2)
    ts003["pct_sharers"]  = (100 - ts003["pct_families"] - ts003["pct_singles"]).round(2)

    ts007a = _read_census_csv(census_dir, "census2021-ts007a-lsoa.csv")
    ts007a = ts007a.rename(columns={"geography code": "lsoa_code"})
    age_total = pd.to_numeric(ts007a["Age: Total"], errors="coerce")
    age_0_14  = (pd.to_numeric(ts007a["Age: Aged 4 years and under"],  errors="coerce") +
                 pd.to_numeric(ts007a["Age: Aged 5 to 9 years"],       errors="coerce") +
                 pd.to_numeric(ts007a["Age: Aged 10 to 14 years"],     errors="coerce"))
    age_15    = pd.to_numeric(ts007a["Age: Aged 15 to 19 years"], errors="coerce") / 5
    age_0_15  = age_0_14 + age_15
    age_65_plus = (pd.to_numeric(ts007a["Age: Aged 65 to 69 years"], errors="coerce") +
                   pd.to_numeric(ts007a["Age: Aged 70 to 74 years"], errors="coerce") +
                   pd.to_numeric(ts007a["Age: Aged 75 to 79 years"], errors="coerce") +
                   pd.to_numeric(ts007a["Age: Aged 80 to 84 years"], errors="coerce") +
                   pd.to_numeric(ts007a["Age: Aged 85 years and over"], errors="coerce"))
    age_16_64 = age_total - age_0_15 - age_65_plus
    ts007a["pct_age_0_15"]    = (age_0_15    / age_total * 100).round(2)
    ts007a["pct_age_16_64"]   = (age_16_64   / age_total * 100).round(2)
    ts007a["pct_age_65_plus"] = (age_65_plus / age_total * 100).round(2)
    ts007a["median_age"]      = ts007a.apply(_estimate_median_age, axis=1)

    merged = (
        ts001[["lsoa_code", "total_population"]]
        .merge(ts006[["lsoa_code", "population_density"]], on="lsoa_code", how="left")
        .merge(ts007a[["lsoa_code", "median_age", "pct_age_0_15", "pct_age_16_64", "pct_age_65_plus"]], on="lsoa_code", how="left")
        .merge(ts003[["lsoa_code", "pct_families", "pct_singles", "pct_sharers"]], on="lsoa_code", how="left")
    )

    def _f(v):
        return round(float(v), 2) if pd.notna(v) else None

    rows = []
    for _, r in merged.iterrows():
        rows.append((
            r["lsoa_code"],
            int(r["total_population"]) if pd.notna(r["total_population"]) else None,
            _f(r.get("population_density")),
            round(float(r["median_age"]), 1) if pd.notna(r.get("median_age")) else None,
            _f(r.get("pct_age_0_15")),
            _f(r.get("pct_age_16_64")),
            _f(r.get("pct_age_65_plus")),
            _f(r.get("pct_families")),
            _f(r.get("pct_singles")),
            _f(r.get("pct_sharers")),
        ))

    # First ingest function: plain INSERT (table was truncated in run())
    execute_values(
        cur,
        f"""
        INSERT INTO {TABLE_NAMES['census_lsoa']}
            (lsoa_code, total_population, population_density, median_age,
             pct_age_0_15, pct_age_16_64, pct_age_65_plus,
             pct_families, pct_singles, pct_sharers)
        VALUES %s ON CONFLICT (lsoa_code) DO UPDATE SET
            total_population = EXCLUDED.total_population,
            population_density = EXCLUDED.population_density,
            median_age = EXCLUDED.median_age,
            pct_age_0_15 = EXCLUDED.pct_age_0_15,
            pct_age_16_64 = EXCLUDED.pct_age_16_64,
            pct_age_65_plus = EXCLUDED.pct_age_65_plus,
            pct_families = EXCLUDED.pct_families,
            pct_singles = EXCLUDED.pct_singles,
            pct_sharers = EXCLUDED.pct_sharers
        """,
        rows,
        page_size=5_000,
    )
    print(f"  Inserted {len(rows):,} demographics rows", flush=True)


def _ingest_housing(cur, census_dir):
    """TS054 + TS044 → housing columns in core_census_lsoa."""
    print("  Ingesting census housing (TS054/044)...", flush=True)

    ts054 = _read_census_csv(census_dir, "census2021-ts054-lsoa.csv")
    ts054 = ts054.rename(columns={"geography code": "lsoa_code"})
    total = ts054["Tenure of household: Total: All households"]
    ts054["total_households"] = total
    ts054["pct_owned"]        = (ts054["Tenure of household: Owned"]          / total * 100).round(2)
    ts054["pct_social_rent"]  = (ts054["Tenure of household: Social rented"]  / total * 100).round(2)
    ts054["pct_private_rent"] = (ts054["Tenure of household: Private rented"] / total * 100).round(2)

    ts044 = _read_census_csv(census_dir, "census2021-ts044-lsoa.csv")
    ts044 = ts044.rename(columns={"geography code": "lsoa_code"})
    hh_total = ts044["Accommodation type: Total: All households"]
    ts044["pct_detached"] = (ts044["Accommodation type: Detached"]      / hh_total * 100).round(2)
    ts044["pct_semi"]     = (ts044["Accommodation type: Semi-detached"] / hh_total * 100).round(2)
    ts044["pct_terraced"] = (ts044["Accommodation type: Terraced"]      / hh_total * 100).round(2)
    flat_cols = [c for c in ts044.columns if "flat" in c.lower() or "purpose-built" in c.lower() or "converted" in c.lower()]
    ts044["pct_flat"] = (ts044[flat_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1) / hh_total * 100).round(2)

    merged = ts054[["lsoa_code", "total_households", "pct_owned", "pct_social_rent", "pct_private_rent"]].merge(
        ts044[["lsoa_code", "pct_detached", "pct_semi", "pct_terraced", "pct_flat"]],
        on="lsoa_code", how="left",
    )

    def _f(v):
        return round(float(v), 2) if pd.notna(v) else None

    rows = [
        (r["lsoa_code"], int(r["total_households"]),
         _f(r["pct_owned"]), _f(r["pct_social_rent"]), _f(r["pct_private_rent"]),
         _f(r.get("pct_detached")), _f(r.get("pct_semi")),
         _f(r.get("pct_terraced")), _f(r.get("pct_flat")))
        for _, r in merged.iterrows()
    ]

    execute_values(
        cur,
        f"""
        INSERT INTO {TABLE_NAMES['census_lsoa']}
            (lsoa_code, total_households, pct_owned, pct_social_rent, pct_private_rent,
             pct_detached, pct_semi, pct_terraced, pct_flat)
        VALUES %s ON CONFLICT (lsoa_code) DO UPDATE SET
            total_households = EXCLUDED.total_households,
            pct_owned = EXCLUDED.pct_owned,
            pct_social_rent = EXCLUDED.pct_social_rent,
            pct_private_rent = EXCLUDED.pct_private_rent,
            pct_detached = EXCLUDED.pct_detached,
            pct_semi = EXCLUDED.pct_semi,
            pct_terraced = EXCLUDED.pct_terraced,
            pct_flat = EXCLUDED.pct_flat
        """,
        rows,
        page_size=5_000,
    )
    print(f"  Inserted {len(rows):,} housing rows", flush=True)


def _ingest_hh_size(cur, census_dir):
    """TS017 → household size columns in core_census_lsoa."""
    print("  Ingesting household size (TS017)...", flush=True)
    path = os.path.join(census_dir, "census2021-ts017-lsoa.csv")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lsoa = r["geography code"].strip()
            if not lsoa.startswith(_EW_CENSUS_PREFIXES):
                continue
            try:
                total = int(r["Household size: Total: All household spaces; measures: Value"] or 0)
                if total == 0:
                    continue
                n1     = int(r["Household size: 1 person in household; measures: Value"] or 0)
                n2     = int(r["Household size: 2 people in household; measures: Value"] or 0)
                n3     = int(r["Household size: 3 people in household; measures: Value"] or 0)
                n4     = int(r["Household size: 4 people in household; measures: Value"] or 0)
                n5plus = (sum(int(r.get(f"Household size: {n} people in household; measures: Value") or 0)
                              for n in ["5", "6", "7"]) +
                          int(r.get("Household size: 8 or more people in household; measures: Value") or 0))
                rows.append((
                    lsoa, total,
                    round(n1 / total * 100, 2),
                    round(n2 / total * 100, 2),
                    round((n3 + n4) / total * 100, 2),
                    round(n5plus / total * 100, 2),
                ))
            except (ValueError, KeyError):
                continue

    execute_values(
        cur,
        f"""
        INSERT INTO {TABLE_NAMES['census_lsoa']}
            (lsoa_code, total_hh, pct_1person, pct_2person, pct_3_4person, pct_5plus)
        VALUES %s ON CONFLICT (lsoa_code) DO UPDATE SET
            total_hh = EXCLUDED.total_hh,
            pct_1person = EXCLUDED.pct_1person,
            pct_2person = EXCLUDED.pct_2person,
            pct_3_4person = EXCLUDED.pct_3_4person,
            pct_5plus = EXCLUDED.pct_5plus
        """,
        rows,
        page_size=5_000,
    )
    print(f"  Inserted {len(rows):,} household size rows", flush=True)


def _ingest_ethnicity(cur, census_dir, conn):
    """TS022 → core_census_ethnicity_ward."""
    print("  Ingesting ethnicity (TS022 ward)...", flush=True)
    path = os.path.join(census_dir, "census2021-ts022-ward.csv")

    _COL_TOTAL     = "Ethnic group (detailed): Total: All usual residents"
    _COL_ASIAN     = "Ethnic group (detailed): Asian, Asian British or Asian Welsh"
    _COL_BLACK_AF  = "Ethnic group (detailed): Black, Black British, Black Welsh of African background"
    _COL_BLACK_CAR = "Ethnic group (detailed): Black, Black British, Black Welsh or Caribbean background"
    _COL_MIXED     = "Ethnic group (detailed): Mixed or Multiple ethnic groups"
    _COL_WHITE     = "Ethnic group (detailed): White"
    _COL_OTHER     = "Ethnic group (detailed): Other ethnic group"

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ward = r["geography code"].strip()
            if not ward.startswith(_EW_CENSUS_PREFIXES):
                continue
            try:
                total = int(r[_COL_TOTAL] or 0)
                if total == 0:
                    continue
                asian = int(r.get(_COL_ASIAN) or 0)
                black = int(r.get(_COL_BLACK_AF) or 0) + int(r.get(_COL_BLACK_CAR) or 0)
                mixed = int(r.get(_COL_MIXED) or 0)
                white = int(r.get(_COL_WHITE) or 0)
                other = int(r.get(_COL_OTHER) or 0)
                rows.append((
                    ward, total,
                    round(white / total * 100, 2),
                    round(asian / total * 100, 2),
                    round(black / total * 100, 2),
                    round(mixed / total * 100, 2),
                    round(other / total * 100, 2),
                ))
            except (ValueError, KeyError):
                continue

    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['census_ethnicity_ward']}_new (LIKE {TABLE_NAMES['census_ethnicity_ward']} INCLUDING ALL)")
    conn.commit()
    execute_values(
        cur,
        f"""
        INSERT INTO {TABLE_NAMES['census_ethnicity_ward']}_new
            (ward_code, total_pop, pct_white, pct_asian, pct_black, pct_mixed, pct_other)
        VALUES %s
        """,
        rows,
        page_size=5_000,
    )
    blue_green_swap(conn, TABLE_NAMES['census_ethnicity_ward'])
    print(f"  Inserted {len(rows):,} ethnicity rows", flush=True)


def _ingest_commute(cur, census_dir):
    """TS058 → commute distance columns in core_census_lsoa."""
    print("  Ingesting commute distance (TS058)...", flush=True)
    path = os.path.join(census_dir, "census2021-ts058-lsoa.csv")

    _COL_TOTAL = "Distance travelled to work: Total: All usual residents aged 16 years and over in employment the week before the census"

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lsoa = r["geography code"].strip()
            if not lsoa.startswith(_EW_CENSUS_PREFIXES):
                continue
            try:
                total    = int(r[_COL_TOTAL] or 0)
                if total == 0:
                    continue
                lt2      = int(r["Distance travelled to work: Less than 2km"] or 0)
                km2_5    = int(r["Distance travelled to work: 2km to less than 5km"] or 0)
                km5_10   = int(r["Distance travelled to work: 5km to less than 10km"] or 0)
                km10_20  = int(r["Distance travelled to work: 10km to less than 20km"] or 0)
                km20_30  = int(r["Distance travelled to work: 20km to less than 30km"] or 0)
                km30_40  = int(r.get("Distance travelled to work: 30km to less than 40km") or 0)
                km40_60  = int(r.get("Distance travelled to work: 40km to less than 60km") or 0)
                km60plus = int(r.get("Distance travelled to work: 60km and over") or 0)
                wfh      = int(r.get("Distance travelled to work: Works mainly from home") or 0)
                rows.append((
                    lsoa, total,
                    round(lt2 / total * 100, 2),
                    round((km2_5 + km5_10) / total * 100, 2),
                    round((km10_20 + km20_30) / total * 100, 2),
                    round((km30_40 + km40_60 + km60plus) / total * 100, 2),
                    round(wfh / total * 100, 2),
                ))
            except (ValueError, KeyError):
                continue

    execute_values(
        cur,
        f"""
        INSERT INTO {TABLE_NAMES['census_lsoa']}
            (lsoa_code, total_workers, pct_lt2km, pct_2_10km, pct_10_30km, pct_30plus, pct_wfh)
        VALUES %s ON CONFLICT (lsoa_code) DO UPDATE SET
            total_workers = EXCLUDED.total_workers,
            pct_lt2km = EXCLUDED.pct_lt2km,
            pct_2_10km = EXCLUDED.pct_2_10km,
            pct_10_30km = EXCLUDED.pct_10_30km,
            pct_30plus = EXCLUDED.pct_30plus,
            pct_wfh = EXCLUDED.pct_wfh
        """,
        rows,
        page_size=5_000,
    )
    print(f"  Inserted {len(rows):,} commute rows", flush=True)


def _ingest_extra(cur, census_dir):
    """TS037 + TS045 + TS066 + TS067 + TS004 → extra columns in core_census_lsoa.

    Columns: pct_good_health, pct_economically_active, pct_degree, pct_no_car, pct_born_abroad.

    Each CSV is processed independently — if a file is missing, those columns are
    skipped with a warning (the existing data in core_census_lsoa is preserved via
    ON CONFLICT DO UPDATE).
    """
    print("  Ingesting census extra (TS037/045/066/067/004)...", flush=True)

    # --- TS037: General health → pct_good_health ---
    ts037_path = os.path.join(census_dir, "census2021-ts037-lsoa.csv")
    if os.path.exists(ts037_path):
        rows = []
        with open(ts037_path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                lsoa = r["geography code"].strip()
                if not lsoa.startswith(_EW_CENSUS_PREFIXES):
                    continue
                try:
                    total = int(r["General health: Total: All usual residents"] or 0)
                    if total == 0:
                        continue
                    good = (int(r["General health: Very good health"] or 0) +
                            int(r["General health: Good health"] or 0))
                    rows.append((lsoa, round(good / total * 100, 2)))
                except (ValueError, KeyError):
                    continue
        if rows:
            execute_values(
                cur,
                f"""INSERT INTO {TABLE_NAMES['census_lsoa']} (lsoa_code, pct_good_health)
                    VALUES %s ON CONFLICT (lsoa_code) DO UPDATE SET
                    pct_good_health = EXCLUDED.pct_good_health""",
                rows, page_size=5_000,
            )
            print(f"    TS037 health: {len(rows):,} rows", flush=True)
    else:
        print(f"    TS037 SKIPPED — {ts037_path} not found", flush=True)

    # --- TS045: Car/van availability → pct_no_car ---
    ts045_path = os.path.join(census_dir, "census2021-ts045-lsoa.csv")
    if os.path.exists(ts045_path):
        rows = []
        with open(ts045_path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                lsoa = r["geography code"].strip()
                if not lsoa.startswith(_EW_CENSUS_PREFIXES):
                    continue
                try:
                    total = int(r["Number of cars or vans: Total: All households"] or 0)
                    if total == 0:
                        continue
                    no_car = int(r["Number of cars or vans: No cars or vans in household"] or 0)
                    rows.append((lsoa, round(no_car / total * 100, 2)))
                except (ValueError, KeyError):
                    continue
        if rows:
            execute_values(
                cur,
                f"""INSERT INTO {TABLE_NAMES['census_lsoa']} (lsoa_code, pct_no_car)
                    VALUES %s ON CONFLICT (lsoa_code) DO UPDATE SET
                    pct_no_car = EXCLUDED.pct_no_car""",
                rows, page_size=5_000,
            )
            print(f"    TS045 cars: {len(rows):,} rows", flush=True)
    else:
        print(f"    TS045 SKIPPED — {ts045_path} not found", flush=True)

    # --- TS066: Economic activity → pct_economically_active ---
    ts066_path = os.path.join(census_dir, "census2021-ts066-lsoa.csv")
    if os.path.exists(ts066_path):
        rows = []
        with open(ts066_path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                lsoa = r["geography code"].strip()
                if not lsoa.startswith(_EW_CENSUS_PREFIXES):
                    continue
                try:
                    total = int(r["Economic activity status: Total: All usual residents aged 16 years and over"] or 0)
                    if total == 0:
                        continue
                    active = int(r["Economic activity status: Economically active (excluding full-time students)"] or 0)
                    rows.append((lsoa, round(active / total * 100, 2)))
                except (ValueError, KeyError):
                    continue
        if rows:
            execute_values(
                cur,
                f"""INSERT INTO {TABLE_NAMES['census_lsoa']} (lsoa_code, pct_economically_active)
                    VALUES %s ON CONFLICT (lsoa_code) DO UPDATE SET
                    pct_economically_active = EXCLUDED.pct_economically_active""",
                rows, page_size=5_000,
            )
            print(f"    TS066 economic: {len(rows):,} rows", flush=True)
    else:
        print(f"    TS066 SKIPPED — {ts066_path} not found", flush=True)

    # --- TS067: Qualifications → pct_degree ---
    ts067_path = os.path.join(census_dir, "census2021-ts067-lsoa.csv")
    if os.path.exists(ts067_path):
        rows = []
        with open(ts067_path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                lsoa = r["geography code"].strip()
                if not lsoa.startswith(_EW_CENSUS_PREFIXES):
                    continue
                try:
                    total = int(r.get("Highest level of qualification: Total: All usual residents aged 16 years and over")
                              or r.get("Highest level of qualification: Total: All usual residents aged 16 years and over; measures: Value")
                              or 0)
                    if total == 0:
                        continue
                    degree = int(r.get("Highest level of qualification: Level 4 qualifications or above")
                                or r.get("Highest level of qualification: Level 4 qualifications and above")
                                or 0)
                    rows.append((lsoa, round(degree / total * 100, 2)))
                except (ValueError, KeyError):
                    continue
        if rows:
            execute_values(
                cur,
                f"""INSERT INTO {TABLE_NAMES['census_lsoa']} (lsoa_code, pct_degree)
                    VALUES %s ON CONFLICT (lsoa_code) DO UPDATE SET
                    pct_degree = EXCLUDED.pct_degree""",
                rows, page_size=5_000,
            )
            print(f"    TS067 qualifications: {len(rows):,} rows", flush=True)
    else:
        print(f"    TS067 SKIPPED — {ts067_path} not found", flush=True)

    # --- TS004: Country of birth → pct_born_abroad ---
    ts004_path = os.path.join(census_dir, "census2021-ts004-lsoa.csv")
    if os.path.exists(ts004_path):
        rows = []
        with open(ts004_path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                lsoa = r["geography code"].strip()
                if not lsoa.startswith(_EW_CENSUS_PREFIXES):
                    continue
                try:
                    total = int(r.get("Country of birth: Total: All usual residents")
                              or r.get("Country of birth: Total; measures: Value")
                              or 0)
                    if total == 0:
                        continue
                    uk = int(r.get("Country of birth: Europe: United Kingdom")
                            or r.get("Country of birth: Europe: United Kingdom; measures: Value")
                            or 0)
                    born_abroad = total - uk
                    rows.append((lsoa, round(born_abroad / total * 100, 2)))
                except (ValueError, KeyError):
                    continue
        if rows:
            execute_values(
                cur,
                f"""INSERT INTO {TABLE_NAMES['census_lsoa']} (lsoa_code, pct_born_abroad)
                    VALUES %s ON CONFLICT (lsoa_code) DO UPDATE SET
                    pct_born_abroad = EXCLUDED.pct_born_abroad""",
                rows, page_size=5_000,
            )
            print(f"    TS004 born abroad: {len(rows):,} rows", flush=True)
    else:
        print(f"    TS004 SKIPPED — {ts004_path} not found", flush=True)


def _ingest_identity(cur, census_dir):
    """TS027 → pct_uk_identity column in core_census_lsoa.

    Sums all UK-only identity categories (British, English, Welsh, Scottish,
    Northern Irish, Cornish) as a percentage of all usual residents.
    """
    print("  Ingesting national identity (TS027)...", flush=True)
    path = os.path.join(census_dir, "census2021-ts027-lsoa.csv")
    if not os.path.exists(path):
        print(f"    TS027 SKIPPED — {path} not found", flush=True)
        return

    _COL_TOTAL = "National identity: Total: All usual residents"
    _UK_COLS = [
        "National identity: British only identity",
        "National identity: English only identity",
        "National identity: English and British only identity",
        "National identity: Welsh only identity",
        "National identity: Welsh and British only identity",
        "National identity: Scottish only identity",
        "National identity: Scottish and British only identity",
        "National identity: Northern Irish only identity",
        "National identity: Northern Irish and British only identity",
        "National identity: Cornish only identity",
        "National identity: Cornish and British only identity",
        "National identity: Any other combination of only UK identities",
    ]

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lsoa = r["geography code"].strip()
            if not lsoa.startswith(_EW_CENSUS_PREFIXES):
                continue
            try:
                total = int(r[_COL_TOTAL] or 0)
                if total == 0:
                    continue
                uk_sum = sum(int(r.get(c) or 0) for c in _UK_COLS)
                rows.append((lsoa, round(uk_sum / total * 100, 2)))
            except (ValueError, KeyError):
                continue

    if rows:
        execute_values(
            cur,
            f"""INSERT INTO {TABLE_NAMES['census_lsoa']} (lsoa_code, pct_uk_identity)
                VALUES %s ON CONFLICT (lsoa_code) DO UPDATE SET
                pct_uk_identity = EXCLUDED.pct_uk_identity""",
            rows, page_size=5_000,
        )
        print(f"    TS027 identity: {len(rows):,} rows", flush=True)


def _ingest_religion(cur, census_dir, conn):
    """TS031 → core_census_religion_ward (ward-level, same pattern as ethnicity).

    Creates the table if it doesn't exist, then TRUNCATE + INSERT.
    Columns: ward_code, total_pop, pct_christian, pct_muslim, pct_hindu,
             pct_sikh, pct_jewish, pct_buddhist, pct_no_religion, pct_other.
    """
    print("  Ingesting religion (TS031 ward)...", flush=True)
    path = os.path.join(census_dir, "census2021-ts031-ward.csv")
    if not os.path.exists(path):
        print(f"    TS031 SKIPPED — {path} not found", flush=True)
        return

    # Ensure table exists
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAMES['census_religion_ward']} (
            ward_code       TEXT PRIMARY KEY,
            total_pop       INT,
            pct_christian   NUMERIC(5,2),
            pct_muslim      NUMERIC(5,2),
            pct_hindu       NUMERIC(5,2),
            pct_sikh        NUMERIC(5,2),
            pct_jewish      NUMERIC(5,2),
            pct_buddhist    NUMERIC(5,2),
            pct_no_religion NUMERIC(5,2),
            pct_other       NUMERIC(5,2)
        )
    """)

    _COL_TOTAL     = "Religion (detailed): Total: All Usual Residents"
    _COL_CHRISTIAN = "Religion (detailed): Christian"
    _COL_MUSLIM    = "Religion (detailed): Muslim "   # trailing space in ONS header
    _COL_HINDU     = "Religion (detailed): Hindu"
    _COL_SIKH      = "Religion (detailed): Sikh"
    _COL_JEWISH    = "Religion (detailed): Jewish"
    _COL_BUDDHIST  = "Religion (detailed): Buddhist"
    _COL_NORELIG   = "Religion (detailed): No religion"
    _COL_OTHER     = "Religion (detailed): Other religion"

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ward = r["geography code"].strip()
            if not ward.startswith(_EW_CENSUS_PREFIXES):
                continue
            try:
                total = int(r[_COL_TOTAL] or 0)
                if total == 0:
                    continue
                christian = int(r.get(_COL_CHRISTIAN) or 0)
                muslim    = int(r.get(_COL_MUSLIM) or r.get(_COL_MUSLIM.rstrip()) or 0)
                hindu     = int(r.get(_COL_HINDU) or 0)
                sikh      = int(r.get(_COL_SIKH) or 0)
                jewish    = int(r.get(_COL_JEWISH) or 0)
                buddhist  = int(r.get(_COL_BUDDHIST) or 0)
                no_relig  = int(r.get(_COL_NORELIG) or 0)
                other     = int(r.get(_COL_OTHER) or 0)
                rows.append((
                    ward, total,
                    round(christian / total * 100, 2),
                    round(muslim / total * 100, 2),
                    round(hindu / total * 100, 2),
                    round(sikh / total * 100, 2),
                    round(jewish / total * 100, 2),
                    round(buddhist / total * 100, 2),
                    round(no_relig / total * 100, 2),
                    round(other / total * 100, 2),
                ))
            except (ValueError, KeyError):
                continue

    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['census_religion_ward']}_new (LIKE {TABLE_NAMES['census_religion_ward']} INCLUDING ALL)")
    conn.commit()
    execute_values(
        cur,
        f"""
        INSERT INTO {TABLE_NAMES['census_religion_ward']}_new
            (ward_code, total_pop, pct_christian, pct_muslim, pct_hindu,
             pct_sikh, pct_jewish, pct_buddhist, pct_no_religion, pct_other)
        VALUES %s
        """,
        rows,
        page_size=5_000,
    )
    blue_green_swap(conn, TABLE_NAMES['census_religion_ward'])
    print(f"  Inserted {len(rows):,} religion rows", flush=True)


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Ingest Census 2021 → core_census_lsoa + core_census_ethnicity_ward.

    Strategy (upsert — no TRUNCATE, preserves columns from domains not re-run):
    1. Load TS001/003/006/007A → demographics columns.
    2. Load TS054/044 → housing columns.
    3. Load TS017 → household size columns.
    4. Load TS058 → commute distance columns.
    5. Load TS037/045/066/067/004 → extra columns (health, cars, econ, degree, born abroad).
    6. Load TS022 → core_census_ethnicity_ward (separate table, ward-level).
    7. Load TS027 → pct_uk_identity column in core_census_lsoa.
    8. Load TS031 → core_census_religion_ward (separate table, ward-level).
    9. Return final row count in core_census_lsoa.

    Note: Each domain uses INSERT ... ON CONFLICT DO UPDATE, so only the
    columns for that domain are touched. Extra columns are preserved even if
    their source CSVs are unavailable.
    """
    census_dir = _resolve_census_dir()
    print(f"  Census data dir: {census_dir}", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    _ingest_demographics(cur, census_dir)
    conn.commit()

    _ingest_housing(cur, census_dir)
    conn.commit()

    _ingest_hh_size(cur, census_dir)
    conn.commit()

    _ingest_commute(cur, census_dir)
    conn.commit()

    _ingest_extra(cur, census_dir)
    conn.commit()

    _ingest_ethnicity(cur, census_dir, conn)
    conn.commit()

    _ingest_identity(cur, census_dir)
    conn.commit()

    _ingest_religion(cur, census_dir, conn)
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['census_lsoa']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
