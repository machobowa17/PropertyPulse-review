"""
etl/utils.py — Shared ETL utilities.

blue_green_swap: atomic table rename to avoid TRUNCATE downtime.
create_staging_table: create _new table without indexes (fast bulk inserts).
recreate_indexes: copy indexes from live table to staging table after data load.
"""

import time


def create_staging_table(conn, table_name: str) -> str:
    """
    Create an UNLOGGED staging table '{table_name}_new' with the same columns
    and constraints as the live table, but WITHOUT indexes.

    This is critical for large tables (>1M rows): inserting into a table with
    active indexes forces PostgreSQL to update B-Tree/GiST structures row-by-row.
    Creating indexes after the bulk insert is orders of magnitude faster.

    Returns the staging table name ('{table_name}_new').
    """
    new_name = f"{table_name}_new"
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {new_name}")
    cur.execute(
        f"CREATE UNLOGGED TABLE {new_name} "
        f"(LIKE {table_name} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)"
    )
    conn.commit()
    cur.close()
    return new_name


def recreate_indexes(conn, table_name: str) -> int:
    """
    Copy all indexes from the live table to the staging table '{table_name}_new'.

    Reads index definitions from pg_indexes for {table_name}, rewrites them to
    target {table_name}_new, and executes them. Skips any indexes that are part
    of a constraint (those are handled by INCLUDING CONSTRAINTS).

    Call this AFTER bulk data load and BEFORE blue_green_swap().
    Returns the number of indexes created.
    """
    new_name = f"{table_name}_new"
    cur = conn.cursor()

    # Get all index definitions for the live table
    cur.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = %s
    """, (table_name,))
    indexes = cur.fetchall()

    created = 0
    for idx_name, idx_def in indexes:
        # Skip primary key and unique constraint indexes — already handled by INCLUDING CONSTRAINTS
        cur.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conrelid = %s::regclass
              AND conindid = (SELECT oid FROM pg_class WHERE relname = %s)
        """, (table_name, idx_name))
        if cur.fetchone():
            continue

        # Rewrite the CREATE INDEX to target the staging table
        # Original: CREATE INDEX idx_foo ON public.table_name USING ...
        # Rewrite:  CREATE INDEX idx_foo_new ON public.table_name_new USING ...
        new_idx_name = f"{idx_name}_new"
        new_def = idx_def.replace(f" {idx_name} ", f" {new_idx_name} ", 1)
        new_def = new_def.replace(f" {table_name} ", f" {new_name} ", 1)
        # Also handle schema-qualified: public.table_name → public.table_name_new
        new_def = new_def.replace(f"public.{table_name} ", f"public.{new_name} ", 1)

        t0 = time.time()
        try:
            cur.execute(new_def)
            conn.commit()
            elapsed = time.time() - t0
            print(f"    Index {new_idx_name}: {elapsed:.1f}s", flush=True)
            created += 1
        except Exception as e:
            conn.rollback()
            print(f"    Index {new_idx_name} FAILED: {e}", flush=True)

    cur.close()
    return created


def blue_green_swap(conn, table_name: str) -> None:
    """
    Atomically swap <table>_new → <table>, relegating the live table to <table>_old.

    Usage pattern (preferred — index-deferred):
        1. create_staging_table(conn, table_name) — creates _new WITHOUT indexes.
        2. Bulk-insert data into <table>_new.
        3. recreate_indexes(conn, table_name) — copies indexes from live to _new.
        4. blue_green_swap(conn, table_name) — atomic rename.

    Legacy pattern (still supported — index-eager):
        1. CREATE UNLOGGED TABLE <table>_new (LIKE <table> INCLUDING ALL)
        2. Bulk-insert data into <table>_new (slower due to index maintenance).
        3. blue_green_swap(conn, table_name) — atomic rename.

    The rename is inside a single transaction so the table is never absent.
    autocommit must be False on conn before calling this.
    """
    old_name = f"{table_name}_old"
    new_name = f"{table_name}_new"

    cur = conn.cursor()

    # Ensure the staging table exists before we attempt the swap
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s AND table_schema = 'public'",
        (new_name,),
    )
    if not cur.fetchone():
        raise RuntimeError(
            f"blue_green_swap: staging table '{new_name}' does not exist. "
            "Populate it before calling swap."
        )

    # Atomic rename — live table is replaced in one transaction
    cur.execute(f"DROP TABLE IF EXISTS {old_name}")
    cur.execute(f"ALTER TABLE {table_name} RENAME TO {old_name}")
    cur.execute(f"ALTER TABLE {new_name} RENAME TO {table_name}")
    conn.commit()

    # Clean up old table (non-critical, outside the swap transaction)
    cur.execute(f"DROP TABLE IF EXISTS {old_name}")
    conn.commit()

    cur.close()
