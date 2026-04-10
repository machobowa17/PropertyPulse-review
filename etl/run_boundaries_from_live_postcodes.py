from __future__ import annotations

import os

import psycopg2

from sources import boundaries


SQL_BEFORE = [
    ("lsoa_total_before", "SELECT COUNT(*) FROM core_lsoa_boundaries"),
    ("lsoa_welsh_before", "SELECT COUNT(*) FROM core_lsoa_boundaries WHERE lsoa_code LIKE 'W%'"),
    ("ward_total_before", "SELECT COUNT(*) FROM core_ward_boundaries"),
    ("ward_welsh_before", "SELECT COUNT(*) FROM core_ward_boundaries WHERE ward_code LIKE 'W%'"),
    ("lad_total_before", "SELECT COUNT(*) FROM core_lad_boundaries"),
    ("lad_welsh_before", "SELECT COUNT(*) FROM core_lad_boundaries WHERE lad_code LIKE 'W%'"),
    ("county_total_before", "SELECT COUNT(*) FROM core_county_boundaries"),
    ("crime_welsh_before", "SELECT COUNT(*) FROM core_crime_lsoa WHERE lsoa_code LIKE 'W%'"),
]

SQL_AFTER = [
    ("lsoa_total_after", "SELECT COUNT(*) FROM core_lsoa_boundaries"),
    ("lsoa_welsh_after", "SELECT COUNT(*) FROM core_lsoa_boundaries WHERE lsoa_code LIKE 'W%'"),
    ("ward_total_after", "SELECT COUNT(*) FROM core_ward_boundaries"),
    ("ward_welsh_after", "SELECT COUNT(*) FROM core_ward_boundaries WHERE ward_code LIKE 'W%'"),
    ("lad_total_after", "SELECT COUNT(*) FROM core_lad_boundaries"),
    ("lad_welsh_after", "SELECT COUNT(*) FROM core_lad_boundaries WHERE lad_code LIKE 'W%'"),
    ("county_total_after", "SELECT COUNT(*) FROM core_county_boundaries"),
    ("crime_welsh_after", "SELECT COUNT(*) FROM core_crime_lsoa WHERE lsoa_code LIKE 'W%'"),
]

SAMPLE_SQL = {
    "lsoa_welsh_samples": "SELECT lsoa_code, lsoa_name, msoa_code, lad_code FROM core_lsoa_boundaries WHERE lsoa_code LIKE 'W%' ORDER BY lsoa_code LIMIT 10",
    "ward_welsh_samples": "SELECT ward_code, ward_name, lad_code FROM core_ward_boundaries WHERE ward_code LIKE 'W%' ORDER BY ward_code LIMIT 10",
    "lad_welsh_samples": "SELECT lad_code, lad_name, county_name, region_name FROM core_lad_boundaries WHERE lad_code LIKE 'W%' ORDER BY lad_code LIMIT 10",
}


def collect(cur, items: list[tuple[str, str]]) -> None:
    for label, sql in items:
        cur.execute(sql)
        print(f"{label}={cur.fetchone()[0]}", flush=True)


def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "postgresql:///ukproperty")
    print(f"DATABASE_URL={db_url}", flush=True)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    collect(cur, SQL_BEFORE)
    conn.close()

    result = boundaries.run(db_url)
    print(f"run_result={result}", flush=True)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    collect(cur, SQL_AFTER)
    for label, sql in SAMPLE_SQL.items():
        cur.execute(sql)
        print(f"{label}={cur.fetchall()}", flush=True)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
