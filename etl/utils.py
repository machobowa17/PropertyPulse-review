"""
etl/utils.py — Shared ETL utilities.

blue_green_swap: atomic table rename to avoid TRUNCATE downtime.
"""


def blue_green_swap(conn, table_name: str) -> None:
    """
    Atomically swap <table>_new → <table>, relegating the live table to <table>_old.

    Usage pattern:
        1. Create and fully populate <table>_new (UNLOGGED, no FKs).
        2. Add all indexes and update geom column on <table>_new.
        3. Call blue_green_swap(conn, table_name) — does the rename in one transaction.
        4. DROP TABLE <table>_old (done inside this function after the swap).

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
