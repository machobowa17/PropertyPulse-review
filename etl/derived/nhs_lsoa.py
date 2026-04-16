"""
derived/nhs_lsoa.py — Aggregate core_nhs_facilities to LSOA level → core_nhs_lsoa

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_nhs_lsoa)

For each LSOA, counts the number of NHS facilities within 2km of the LSOA centroid,
broken down by facility type (GP, Hospital, Dentist).

Spatial proximity query: ST_DWithin(facility.geom, lsoa_centroid, 2000m).

Expected row count (verify after rebuild):
    core_nhs_lsoa: ~33,755 rows (one per LSOA)
"""

import psycopg2

from constants import SCHEDULE_ANNUAL, TABLE_NAMES
from utils import blue_green_swap

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":           "nhs_lsoa",
    "description":    "Aggregate core_nhs_facilities within 2km of each LSOA centroid → core_nhs_lsoa.",
    "schedule":       SCHEDULE_ANNUAL,
    "depends_on":     ["nhs", "boundaries"],
    "tables_written": [TABLE_NAMES["nhs_lsoa"]],
    "cache_key_patterns": [],
    "expected_row_range": (30_000, 38_000),
}

# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Aggregate NHS facilities per LSOA (2km radius from LSOA centroid).

    Steps:
    1. Truncate core_nhs_lsoa.
    2. For each LSOA, count NHS facilities within 2km of the LSOA centroid,
       broken down by facility_type (GP, Hospital, Dentist) and as a total.
    3. Return final row count.
    """
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    print("  Creating staging table core_nhs_lsoa_new...", flush=True)
    cur.execute(f"CREATE UNLOGGED TABLE {TABLE_NAMES['nhs_lsoa']}_new (LIKE {TABLE_NAMES['nhs_lsoa']} INCLUDING ALL)")
    conn.commit()

    print("  Aggregating NHS facilities within 2km of each LSOA centroid...", flush=True)
    cur.execute(
        f"""
        INSERT INTO {TABLE_NAMES['nhs_lsoa']}_new
            (lsoa_code, nhs_count_2km, gp_count_2km, hospital_count_2km,
             dentist_count_2km, pharmacy_count_2km, optician_count_2km, care_home_count_2km)
        SELECT
            lb.lsoa_code,
            COUNT(f.org_code)                                                   AS nhs_count_2km,
            COUNT(f.org_code) FILTER (WHERE f.facility_type = 'GP')             AS gp_count_2km,
            COUNT(f.org_code) FILTER (WHERE f.facility_type = 'Hospital')       AS hospital_count_2km,
            COUNT(f.org_code) FILTER (WHERE f.facility_type = 'Dentist')        AS dentist_count_2km,
            COUNT(f.org_code) FILTER (WHERE f.facility_type = 'Pharmacy')       AS pharmacy_count_2km,
            COUNT(f.org_code) FILTER (WHERE f.facility_type = 'Optician')       AS optician_count_2km,
            COUNT(f.org_code) FILTER (WHERE f.facility_type = 'Care Home')      AS care_home_count_2km
        FROM {TABLE_NAMES['lsoa_boundaries']} lb
        LEFT JOIN {TABLE_NAMES['nhs_facilities']} f
            ON ST_DWithin(
                f.geom::geography,
                ST_Centroid(lb.geom)::geography,
                2000
            )
        GROUP BY lb.lsoa_code
        ON CONFLICT (lsoa_code) DO UPDATE SET
            nhs_count_2km      = EXCLUDED.nhs_count_2km,
            gp_count_2km       = EXCLUDED.gp_count_2km,
            hospital_count_2km = EXCLUDED.hospital_count_2km,
            dentist_count_2km  = EXCLUDED.dentist_count_2km,
            pharmacy_count_2km = EXCLUDED.pharmacy_count_2km,
            optician_count_2km = EXCLUDED.optician_count_2km,
            care_home_count_2km = EXCLUDED.care_home_count_2km
        """
    )
    inserted = cur.rowcount
    conn.commit()
    print(f"  Inserted {inserted:,} LSOA rows", flush=True)

    blue_green_swap(conn, TABLE_NAMES['nhs_lsoa'])

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['nhs_lsoa']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count
