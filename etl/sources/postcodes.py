"""
sources/postcodes.py — ONS Postcode Directory (ONSPD) → core_postcodes

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_postcodes)

This loader is intentionally resilient for developer handover:
- It accepts either the official ONSPD ZIP archive or extracted CSV files.
- It searches stable local paths before failing.
- It treats auxiliary lookup files as optional rather than mandatory.
- It supports both the older ONSPD field names used in the official February 2024
  multi-CSV ZIP and the newer extracted CSV field names seen in some local exports.
"""

from __future__ import annotations

import csv
import glob
import io
import json
import os
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd
import psycopg2

from constants import (
    COUNTRY_NAME_BY_PREFIX,
    PLANNED_COUNTRY_PREFIXES,
    SCHEDULE_FOUNDATION,
    SUPPORTED_COUNTRY_PREFIXES,
    TABLE_NAMES,
)


METADATA = {
    "name": "postcodes",
    "description": "ONS Postcode Directory (ONSPD) → core_postcodes. Foundation for all geographic joins.",
    "schedule": SCHEDULE_FOUNDATION,
    "depends_on": [],
    "tables_written": [TABLE_NAMES["postcodes"]],
    "cache_key_patterns": ["lsoa_sess:*", "area:*", "resolve:*"],
    "expected_row_range": (1_400_000, 2_800_000),
}


_REGION_NAMES = {
    "E12000001": "North East",
    "E12000002": "North West",
    "E12000003": "Yorkshire and The Humber",
    "E12000004": "East Midlands",
    "E12000005": "West Midlands",
    "E12000006": "East of England",
    "E12000007": "London",
    "E12000008": "South East",
    "E12000009": "South West",
}

_ETL_DIR = Path(__file__).resolve().parent.parent
_ETL_DATA_DIR = _ETL_DIR / "data"
_REPO_ROOT = _ETL_DIR.parent
_STABLE_CACHE_DIR = _REPO_ROOT / ".cache" / "onspd"


def _existing(paths: Iterable[Path]) -> list[Path]:
    return [p for p in paths if p.exists()]


def _resolve_onspd_path() -> Path:
    env_path = os.environ.get("ONSPD_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(f"ONSPD_PATH is set but missing: {path}")

    candidates = _existing(
        [
            *_sorted_paths(_STABLE_CACHE_DIR.glob("ONSPD_*.zip")),
            *_sorted_paths(_ETL_DATA_DIR.glob("ONSPD_*.zip")),
            *_sorted_paths(_ETL_DATA_DIR.glob("ONSPD_*.csv")),
        ]
    )
    if candidates:
        return candidates[-1]

    raise FileNotFoundError(
        "No ONSPD source found. Place the official ONSPD ZIP in "
        f"{_STABLE_CACHE_DIR} or { _ETL_DATA_DIR }, or set ONSPD_PATH explicitly."
    )


def _sorted_paths(paths: Iterable[Path]) -> list[Path]:
    return sorted(paths, key=lambda p: p.name)


def _resolve_optional_json(name: str) -> Path | None:
    env_name = name.upper().replace(".", "_") + "_PATH"
    env_path = os.environ.get(env_name)
    if env_path:
        path = Path(env_path).expanduser()
        return path if path.exists() else None
    candidate = _ETL_DATA_DIR / name
    return candidate if candidate.exists() else None


def _resolve_optional_lad_ctyua_path() -> Path | None:
    env_path = os.environ.get("LAD_CTYUA_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        return path if path.exists() else None
    for name in ("lad_to_ctyua_2025.csv", "lad_to_ctyua_2024.csv"):
        candidate = _ETL_DATA_DIR / name
        if candidate.exists():
            return candidate
    return None


def _load_catchment_names() -> tuple[dict[str, str], dict[str, str]]:
    path = _resolve_optional_json("catchment_names.json")
    if not path:
        return {}, {}
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return payload.get("ward", {}) or {}, payload.get("lad", {}) or {}


def _load_county_lookup() -> dict[str, tuple[str | None, str | None]]:
    path = _resolve_optional_lad_ctyua_path()
    if not path:
        return {}

    lookup: dict[str, tuple[str | None, str | None]] = {}
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    for _, row in df.iterrows():
        lad_code = str(row.get("LAD25CD", "") or "").strip()
        cty_code = str(row.get("CTYUA25CD", "") or "").strip() or None
        cty_name = str(row.get("CTYUA25NM", "") or "").strip() or None
        if not lad_code:
            continue
        if cty_code == lad_code:
            lookup[lad_code] = (None, None)
        else:
            lookup[lad_code] = (cty_code, cty_name)
    return lookup


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = df.rename(columns={c: c.strip().lower() for c in df.columns})
    return renamed


def _first_present(df: pd.DataFrame, options: list[str], default: str = "") -> pd.Series:
    for col in options:
        if col in df.columns:
            return df[col].fillna("")
    return pd.Series([default] * len(df), index=df.index, dtype="object")


def _iter_source_frames(source_path: Path) -> Iterable[pd.DataFrame]:
    if source_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(source_path) as zf:
            members = [
                name
                for name in zf.namelist()
                if name.lower().endswith(".csv")
                and "/" in name
                and "data/multi_csv/" in name.lower()
            ]
            if not members:
                raise FileNotFoundError(f"No multi-CSV ONSPD members found in {source_path}")
            for member in sorted(members):
                with zf.open(member) as handle:
                    yield pd.read_csv(handle, dtype=str, low_memory=False)
        return

    yield pd.read_csv(source_path, dtype=str, chunksize=500_000, low_memory=False)


def _iter_frames(source_path: Path) -> Iterable[pd.DataFrame]:
    if source_path.suffix.lower() == ".zip":
        for df in _iter_source_frames(source_path):
            yield df
        return

    for chunk in pd.read_csv(source_path, dtype=str, chunksize=500_000, low_memory=False):
        yield chunk


def run(db_url: str) -> int:
    source_path = _resolve_onspd_path()
    ward_names, lad_names = _load_catchment_names()
    county_lookup = _load_county_lookup()

    print(f"  ONSPD source: {source_path}", flush=True)
    if not ward_names or not lad_names:
        print("  catchment_names.json not found or incomplete; postcode names will be left blank where no lookup exists.", flush=True)
    if not county_lookup:
        print("  LAD county lookup not found; county names will be left blank where not derivable from source.", flush=True)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS _stg_postcodes")
    cur.execute(
        """
        CREATE UNLOGGED TABLE _stg_postcodes (
            postcode         TEXT,
            postcode_compact TEXT,
            latitude         DOUBLE PRECISION,
            longitude        DOUBLE PRECISION,
            lsoa_code        TEXT,
            lsoa_name        TEXT,
            msoa_code        TEXT,
            msoa_name        TEXT,
            ward_code        TEXT,
            ward_name        TEXT,
            lad_code         TEXT,
            lad_name         TEXT,
            county_code      TEXT,
            county_name      TEXT,
            region_code      TEXT,
            region_name      TEXT,
            nation           CHAR(1)
        )
        """
    )
    conn.commit()

    total_staged = 0
    for raw_df in _iter_frames(source_path):
        chunk = _normalise_columns(raw_df)

        postcode = _first_present(chunk, ["pcds", "pcd"]).astype(str).str.strip()
        doterm = _first_present(chunk, ["doterm"]).astype(str).str.strip()
        lat = _first_present(chunk, ["lat"]).astype(str).str.strip()
        lon = _first_present(chunk, ["long"]).astype(str).str.strip()
        lsoa = _first_present(chunk, ["lsoa21", "lsoa21cd"]).astype(str).str.strip()
        msoa = _first_present(chunk, ["msoa21", "msoa21cd"]).astype(str).str.strip()
        ward = _first_present(chunk, ["osward", "wd25cd"]).astype(str).str.strip()
        lad = _first_present(chunk, ["oslaua", "lad25cd"]).astype(str).str.strip()
        county = _first_present(chunk, ["oscty", "cty25cd"]).astype(str).str.strip()
        region = _first_present(chunk, ["rgn", "rgn25cd"]).astype(str).str.strip()
        country = _first_present(chunk, ["ctry", "ctry25cd"]).astype(str).str.strip()

        working = pd.DataFrame(
            {
                "postcode": postcode,
                "doterm": doterm,
                "latitude": lat,
                "longitude": lon,
                "lsoa_code": lsoa,
                "msoa_code": msoa,
                "ward_code": ward,
                "lad_code": lad,
                "county_code_source": county,
                "region_code": region,
                "country_raw": country,
            }
        )

        working = working[
            (working["postcode"] != "")
            & ((working["doterm"] == "") | working["doterm"].isna())
        ].copy()
        if working.empty:
            continue

        working["nation"] = working["country_raw"].str[:1].str.upper()
        working = working[working["nation"].isin(SUPPORTED_COUNTRY_PREFIXES)].copy()
        if working.empty:
            continue

        working["postcode_compact"] = working["postcode"].str.replace(" ", "", regex=False).str.upper()
        working["ward_name"] = working["ward_code"].map(ward_names).fillna("")
        working["lad_name"] = working["lad_code"].map(lad_names).fillna("")
        working["region_code"] = working["region_code"].replace({"S99999999": "", "W99999999": "", "N99999999": "", "E99999999": ""})
        working["region_name"] = working["region_code"].map(_REGION_NAMES).fillna("")
        planned_mask = working["region_name"].eq("") & working["nation"].isin(PLANNED_COUNTRY_PREFIXES)
        working.loc[planned_mask, "region_name"] = working.loc[planned_mask, "nation"].map(COUNTRY_NAME_BY_PREFIX).fillna("")

        if county_lookup:
            county_pairs = working["lad_code"].map(county_lookup)
            working["county_code"] = county_pairs.map(lambda v: v[0] if isinstance(v, tuple) else None).fillna(working["county_code_source"]).fillna("")
            working["county_name"] = county_pairs.map(lambda v: v[1] if isinstance(v, tuple) else None).fillna("")
        else:
            working["county_code"] = working["county_code_source"].fillna("")
            working["county_name"] = ""

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter="\t")
        for row in working.itertuples(index=False):
            try:
                lat_value = float(row.latitude) if row.latitude else ""
            except (TypeError, ValueError):
                lat_value = ""
            try:
                lon_value = float(row.longitude) if row.longitude else ""
            except (TypeError, ValueError):
                lon_value = ""

            writer.writerow(
                [
                    row.postcode,
                    row.postcode_compact,
                    lat_value,
                    lon_value,
                    row.lsoa_code or "",
                    "",
                    row.msoa_code or "",
                    "",
                    row.ward_code or "",
                    row.ward_name or "",
                    row.lad_code or "",
                    row.lad_name or "",
                    row.county_code or "",
                    row.county_name or "",
                    row.region_code or "",
                    row.region_name or "",
                    row.nation or "",
                ]
            )

        buf.seek(0)
        cur.copy_from(buf, "_stg_postcodes", sep="\t", null="")
        conn.commit()
        total_staged += len(working)
        print(f"    Staged {total_staged:,} rows...", flush=True)

    print("  Upserting into core_postcodes...", flush=True)
    cur.execute(
        """
        INSERT INTO core_postcodes (
            postcode, postcode_compact, latitude, longitude,
            lsoa_code, lsoa_name, msoa_code, msoa_name,
            ward_code, ward_name, lad_code, lad_name,
            county_code, county_name, region_code, region_name, nation
        )
        SELECT
            postcode, postcode_compact,
            NULLIF(latitude::text,  '')::double precision,
            NULLIF(longitude::text, '')::double precision,
            NULLIF(lsoa_code,   ''), NULLIF(lsoa_name,   ''),
            NULLIF(msoa_code,   ''), NULLIF(msoa_name,   ''),
            NULLIF(ward_code,   ''), NULLIF(ward_name,   ''),
            NULLIF(lad_code,    ''), NULLIF(lad_name,    ''),
            NULLIF(county_code, ''), NULLIF(county_name, ''),
            NULLIF(region_code, ''), NULLIF(region_name, ''),
            nation
        FROM _stg_postcodes
        ON CONFLICT (postcode) DO UPDATE SET
            postcode_compact = EXCLUDED.postcode_compact,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            lsoa_code = EXCLUDED.lsoa_code,
            lsoa_name = COALESCE(EXCLUDED.lsoa_name, core_postcodes.lsoa_name),
            msoa_code = EXCLUDED.msoa_code,
            msoa_name = COALESCE(EXCLUDED.msoa_name, core_postcodes.msoa_name),
            ward_code = EXCLUDED.ward_code,
            ward_name = COALESCE(NULLIF(EXCLUDED.ward_name, ''), core_postcodes.ward_name),
            lad_code = EXCLUDED.lad_code,
            lad_name = COALESCE(NULLIF(EXCLUDED.lad_name, ''), core_postcodes.lad_name),
            county_code = COALESCE(NULLIF(EXCLUDED.county_code, ''), core_postcodes.county_code),
            county_name = COALESCE(NULLIF(EXCLUDED.county_name, ''), core_postcodes.county_name),
            region_code = COALESCE(NULLIF(EXCLUDED.region_code, ''), core_postcodes.region_code),
            region_name = COALESCE(NULLIF(EXCLUDED.region_name, ''), core_postcodes.region_name),
            nation = EXCLUDED.nation
        """
    )
    conn.commit()

    print("  Building PostGIS geometry...", flush=True)
    cur.execute(
        """
        UPDATE core_postcodes
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND geom IS NULL
        """
    )
    cur.execute(
        """
        UPDATE core_postcodes
        SET is_active = TRUE,
            last_updated = CURRENT_DATE
        WHERE is_active IS NULL
        """
    )
    conn.commit()

    cur.execute("DROP TABLE IF EXISTS _stg_postcodes")
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['postcodes']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
