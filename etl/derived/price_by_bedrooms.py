"""
derived/price_by_bedrooms.py — Price by bedrooms → core_price_by_bedrooms_lad

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_price_by_bedrooms_lad)

Aggregates core_property_transactions (which has EPC columns absorbed since
Phase 13 Step 2) to compute average sale price by LAD, year, property type,
and estimated bedroom count.

Only residential property types (D, S, T, F) are included.

Schema of core_price_by_bedrooms_lad:
    lad_code          TEXT
    year              SMALLINT
    property_type     CHAR(1)
    bedrooms          SMALLINT
    avg_price         INTEGER
    transaction_count INTEGER
    PRIMARY KEY (lad_code, year, property_type, bedrooms)
"""

import psycopg2

from constants import PRICE_TYPES, SCHEDULE_MONTHLY, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":           "price_by_bedrooms",
    "description":    "Aggregate master table by LAD/year/type/bedrooms → core_price_by_bedrooms_lad.",
    "schedule":       SCHEDULE_MONTHLY,
    "depends_on":     ["land_registry_full"],
    "tables_written": [TABLE_NAMES["price_by_bedrooms_lad"]],
    "cache_key_patterns": [],
    "expected_row_range": (5_000, 100_000),
}

# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Aggregate core_property_transactions → core_price_by_bedrooms_lad.

    Uses bedrooms_estimated column (absorbed from EPC in Phase 13 Step 2)
    and lad_code column (added in Step 1) directly from the master table.

    Strategy:
    1. Create table if it doesn't exist.
    2. Truncate and rebuild from full transaction history.
    3. Return final row count.
    """
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor()

    # Create table if it doesn't yet exist (first run)
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAMES['price_by_bedrooms_lad']} (
            lad_code          TEXT     NOT NULL,
            year              SMALLINT NOT NULL,
            property_type     CHAR(1)  NOT NULL,
            bedrooms          SMALLINT NOT NULL,
            avg_price         INTEGER,
            transaction_count INTEGER,
            PRIMARY KEY (lad_code, year, property_type, bedrooms)
        )
        """
    )
    conn.commit()

    print("  Truncating core_price_by_bedrooms_lad...", flush=True)
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['price_by_bedrooms_lad']} CASCADE")
    conn.commit()

    print("  Aggregating price by bedroom from master table...", flush=True)
    cur.execute(
        f"""
        INSERT INTO {TABLE_NAMES['price_by_bedrooms_lad']}
            (lad_code, year, property_type, bedrooms, avg_price, transaction_count)
        SELECT
            t.lad_code,
            EXTRACT(YEAR FROM t.date_of_transfer)::SMALLINT AS year,
            t.property_type,
            t.bedrooms_estimated                            AS bedrooms,
            ROUND(AVG(t.price))::INTEGER                    AS avg_price,
            COUNT(*)                                        AS transaction_count
        FROM {TABLE_NAMES['property_transactions']} t
        WHERE t.property_type = ANY(%s)
          AND t.bedrooms_estimated IS NOT NULL
          AND t.lad_code IS NOT NULL
        GROUP BY t.lad_code, year, t.property_type, t.bedrooms_estimated
        HAVING COUNT(*) >= 3      -- suppress cells with fewer than 3 transactions
        """,
        (list(PRICE_TYPES),),
    )
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['price_by_bedrooms_lad']}")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"  Inserted {count:,} rows into core_price_by_bedrooms_lad", flush=True)
    return count
