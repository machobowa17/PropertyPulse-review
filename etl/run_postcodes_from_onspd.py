from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2

from sources import postcodes


def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "postgresql:///ukproperty")
    onspd_path = os.environ.get("ONSPD_PATH")
    if not onspd_path:
        onspd_path = str((Path(__file__).resolve().parent.parent / ".cache" / "onspd" / "ONSPD_FEB_2024_UK.zip"))
        os.environ["ONSPD_PATH"] = onspd_path

    print(f"DATABASE_URL={db_url}", flush=True)
    print(f"ONSPD_PATH={onspd_path}", flush=True)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM core_postcodes")
    before_total = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(nation,'NULL'), COUNT(*) FROM core_postcodes GROUP BY COALESCE(nation,'NULL') ORDER BY 1")
    before_by_nation = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM core_postcodes WHERE lsoa_code LIKE 'W%'")
    before_welsh_lsoa_rows = cur.fetchone()[0]
    conn.close()

    print(f"before_total={before_total}", flush=True)
    print(f"before_by_nation={before_by_nation}", flush=True)
    print(f"before_welsh_lsoa_rows={before_welsh_lsoa_rows}", flush=True)

    final_count = postcodes.run(db_url)
    print(f"final_count={final_count}", flush=True)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(nation,'NULL'), COUNT(*) FROM core_postcodes GROUP BY COALESCE(nation,'NULL') ORDER BY 1")
    after_by_nation = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM core_postcodes WHERE lsoa_code LIKE 'W%'")
    after_welsh_lsoa_rows = cur.fetchone()[0]
    cur.execute("SELECT postcode, nation, lsoa_code, lad_code FROM core_postcodes WHERE nation='W' OR lsoa_code LIKE 'W%' ORDER BY postcode LIMIT 15")
    after_welsh_samples = cur.fetchall()
    conn.close()

    print(f"after_by_nation={after_by_nation}", flush=True)
    print(f"after_welsh_lsoa_rows={after_welsh_lsoa_rows}", flush=True)
    print(f"after_welsh_samples={after_welsh_samples}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
