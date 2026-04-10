from __future__ import annotations

import os

import psycopg2

from sources import crime


SQL_BEFORE = [
    ("crime_total_before", "SELECT COUNT(*) FROM core_crime_lsoa"),
    ("crime_welsh_before", "SELECT COUNT(*) FROM core_crime_lsoa WHERE lsoa_code LIKE 'W%'"),
    ("lsoa_welsh_boundaries", "SELECT COUNT(*) FROM core_lsoa_boundaries WHERE lsoa_code LIKE 'W%'"),
]

SQL_AFTER = [
    ("crime_total_after", "SELECT COUNT(*) FROM core_crime_lsoa"),
    ("crime_welsh_after", "SELECT COUNT(*) FROM core_crime_lsoa WHERE lsoa_code LIKE 'W%'"),
    ("crime_english_after", "SELECT COUNT(*) FROM core_crime_lsoa WHERE lsoa_code LIKE 'E%'"),
]

SAMPLE_SQL = {
    "welsh_crime_samples": "SELECT lsoa_code, month, crime_type, crime_count FROM core_crime_lsoa WHERE lsoa_code LIKE 'W%' ORDER BY month DESC, lsoa_code, crime_type LIMIT 20",
}


def collect(cur, items: list[tuple[str, str]]) -> None:
    for label, sql in items:
        cur.execute(sql)
        print(f"{label}={cur.fetchone()[0]}", flush=True)


def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "postgresql:///ukproperty")
    crime_zip_path = os.environ.get(
        "CRIME_ZIP_PATH",
        "/home/ubuntu/PropertyPulse/.cache/police/police_latest.zip",
    )
    print(f"DATABASE_URL={db_url}", flush=True)
    print(f"CRIME_ZIP_PATH={crime_zip_path}", flush=True)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    collect(cur, SQL_BEFORE)
    conn.close()

    result = crime.run(db_url)
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
