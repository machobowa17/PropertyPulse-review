"""
derived/address_lookup.py — Build core_addresses from core_property_transactions

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_addresses)

Deduplicates ~30M transaction rows into ~14M unique addresses with:
- Normalised PAON, SAON, street, postcode, locality, town
- Most recent lat/lon and lsoa_code per address
- precise_lat/precise_lon from Nominatim geocoding (when CSV is available)
- Indexed for sub-50ms autocomplete and address resolution

Indexes:
    idx_addresses_postcode        — B-tree on postcode (exact postcode match)
    idx_addresses_paon_street     — B-tree on (UPPER(paon), postcode) for address resolution
    idx_addresses_street_trgm     — GIN trigram on street for fuzzy/prefix suggest
    idx_addresses_locality_trgm   — GIN trigram on locality+town for area hint filtering
"""

import os
import psycopg2

from constants import SCHEDULE_MONTHLY, TABLE_NAMES
from utils import blue_green_swap

# Optional geocoded coordinates CSV (from batch_geocode_addresses.py)
GEOCODED_CSV_PATH = os.environ.get(
    "GEOCODED_CSV_PATH",
    "/tmp/geocoded_addresses.csv",
)

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":           "address_lookup",
    "description":    "Deduplicate transactions → core_addresses for fast address search.",
    "schedule":       SCHEDULE_MONTHLY,
    "depends_on":     ["land_registry_full"],
    "tables_written": ["core_addresses"],
    "cache_key_patterns": [],
    "expected_row_range": (10_000_000, 20_000_000),
}

# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Aggregate core_property_transactions → core_addresses.

    Uses DISTINCT ON to keep the most recent transaction per unique address,
    then builds optimised indexes for autocomplete and resolution.
    """
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    staging = "core_addresses_staging"

    # 1. Create UNLOGGED staging table (fast inserts, no WAL)
    cur.execute(f"DROP TABLE IF EXISTS {staging}")
    cur.execute(f"""
        CREATE UNLOGGED TABLE {staging} (
            postcode        TEXT NOT NULL,
            paon            TEXT NOT NULL,
            saon            TEXT,
            street          TEXT,
            locality        TEXT,
            town            TEXT,
            latitude        DOUBLE PRECISION NOT NULL,
            longitude       DOUBLE PRECISION NOT NULL,
            lsoa_code       TEXT,
            lad_code        TEXT,
            precise_lat     DOUBLE PRECISION,
            precise_lon     DOUBLE PRECISION
        )
    """)

    # 2. Populate: one row per unique (postcode, paon, saon, street),
    #    keeping the most recent transaction's coordinates and codes.
    #    SAON = 'N' means "no sub-address" in PPD data — normalise to NULL.
    print("Populating core_addresses from core_property_transactions...")
    cur.execute(f"""
        INSERT INTO {staging}
            (postcode, paon, saon, street, locality, town,
             latitude, longitude, lsoa_code, lad_code)
        SELECT DISTINCT ON (postcode, UPPER(paon), UPPER(NULLIF(saon, 'N')), UPPER(street))
            postcode,
            UPPER(paon),
            CASE WHEN saon = 'N' THEN NULL ELSE UPPER(saon) END,
            UPPER(street),
            UPPER(locality),
            UPPER(town),
            latitude,
            longitude,
            lsoa_code,
            lad_code
        FROM core_property_transactions
        WHERE latitude IS NOT NULL
          AND postcode IS NOT NULL
          AND paon IS NOT NULL
        ORDER BY postcode, UPPER(paon), UPPER(NULLIF(saon, 'N')), UPPER(street),
                 date_of_transfer DESC
    """)
    row_count = cur.rowcount
    print(f"  Inserted {row_count:,} rows")

    # 2b. Enrich with precise coordinates from Nominatim geocoding (if CSV available)
    if os.path.isfile(GEOCODED_CSV_PATH):
        print(f"Enriching with geocoded coordinates from {GEOCODED_CSV_PATH}...")
        cur.execute("DROP TABLE IF EXISTS tmp_geocoded_coords")
        cur.execute("""
            CREATE TEMP TABLE tmp_geocoded_coords (
                postcode    TEXT,
                paon        TEXT,
                saon        TEXT,
                street      TEXT,
                precise_lat DOUBLE PRECISION,
                precise_lon DOUBLE PRECISION,
                osm_type    TEXT,
                osm_id      TEXT,
                place_rank  INT
            )
        """)
        with open(GEOCODED_CSV_PATH, "r") as f:
            # Skip header line
            next(f)
            cur.copy_expert(
                "COPY tmp_geocoded_coords FROM STDIN WITH CSV",
                f,
            )
        geocoded_count = cur.rowcount
        print(f"  Loaded {geocoded_count:,} geocoded rows")

        # Only use results with building/address-level precision (place_rank >= 26)
        # place_rank 26 = house number, 28 = building, 30 = POI
        # Skip street-level (22) or postcode-level (25) results
        cur.execute(f"""
            UPDATE {staging} a
            SET precise_lat = g.precise_lat,
                precise_lon = g.precise_lon
            FROM tmp_geocoded_coords g
            WHERE a.postcode = g.postcode
              AND a.paon     = g.paon
              AND COALESCE(a.saon, '') = COALESCE(g.saon, '')
              AND COALESCE(a.street, '') = COALESCE(g.street, '')
              AND g.precise_lat IS NOT NULL
              AND g.place_rank >= 26
        """)
        enriched = cur.rowcount
        print(f"  Enriched {enriched:,} addresses with precise coordinates")
        cur.execute("DROP TABLE IF EXISTS tmp_geocoded_coords")
    else:
        print(f"No geocoded CSV at {GEOCODED_CSV_PATH} — skipping coordinate enrichment")

    # 3. Build indexes
    print("Building indexes...")

    # Primary lookup: exact postcode match (for "42 High Street, SW1A 1PH")
    cur.execute(f"""
        CREATE INDEX idx_addresses_postcode
        ON {staging} (postcode)
    """)
    print("  idx_addresses_postcode done")

    # Address resolution: PAON + postcode (for exact address match)
    cur.execute(f"""
        CREATE INDEX idx_addresses_paon_postcode
        ON {staging} (paon, postcode)
    """)
    print("  idx_addresses_paon_postcode done")

    # Autocomplete: trigram GIN on street for '%high st%' prefix matching
    cur.execute(f"""
        CREATE INDEX idx_addresses_street_trgm
        ON {staging} USING gin (street gin_trgm_ops)
    """)
    print("  idx_addresses_street_trgm done")

    # Area hint: trigram GIN on town for locality/town filtering in suggest
    cur.execute(f"""
        CREATE INDEX idx_addresses_town_trgm
        ON {staging} USING gin (town gin_trgm_ops)
    """)
    print("  idx_addresses_town_trgm done")

    # Broader search: PAON + street pattern (for "42 High Street" without postcode)
    cur.execute(f"""
        CREATE INDEX idx_addresses_paon_street
        ON {staging} (paon, street text_pattern_ops)
    """)
    print("  idx_addresses_paon_street done")

    # 4. Set LOGGED and blue-green swap
    print("Setting table LOGGED...")
    cur.execute(f"ALTER TABLE {staging} SET LOGGED")

    print("Swapping to core_addresses...")
    blue_green_swap(cur, "core_addresses", staging)

    cur.close()
    conn.close()

    print(f"Done. core_addresses: {row_count:,} rows")
    return row_count
