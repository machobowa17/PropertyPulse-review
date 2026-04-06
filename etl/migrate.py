#!/usr/bin/env python3
"""
Database migration runner for PropertyPulse ETL.

Reads numbered SQL files from etl/migrations/, applies any that have not
yet been recorded in schema_migrations, and records each applied migration.

Usage:
    python3 migrate.py                  # apply all pending migrations
    python3 migrate.py --dry-run        # show pending migrations without applying
    python3 migrate.py --status         # show applied migrations

Design:
- Migrations are numbered SQL files: 001_*.sql, 002_*.sql, ...
- Applied in strict numeric order.
- Idempotent: safe to re-run. Already-applied migrations are skipped.
- schema_migrations table is bootstrapped automatically if absent.
- Any migration failure stops the run immediately (fail-fast).
"""

import argparse
import os
import re
import sys

import psycopg2

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")
DB_DSN = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/ukproperty")

BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER     PRIMARY KEY,
    filename    TEXT        NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def get_migration_files():
    """Return sorted list of (version, filename) tuples from migrations dir."""
    files = []
    for fname in os.listdir(MIGRATIONS_DIR):
        m = re.match(r"^(\d+)_.*\.sql$", fname)
        if m:
            files.append((int(m.group(1)), fname))
    return sorted(files)


def get_applied_versions(conn):
    """Return set of version numbers already applied."""
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations ORDER BY version")
        return {row[0] for row in cur.fetchall()}


def apply_migration(conn, version, filename):
    """Read and execute a single SQL migration file, then record it."""
    filepath = os.path.join(MIGRATIONS_DIR, filename)
    with open(filepath, "r") as f:
        sql = f.read()
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            "INSERT INTO schema_migrations (version, filename) VALUES (%s, %s)",
            (version, filename),
        )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="PropertyPulse database migration runner")
    parser.add_argument("--dry-run", action="store_true", help="Show pending migrations without applying")
    parser.add_argument("--status", action="store_true", help="Show all applied migrations")
    args = parser.parse_args()

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False

    # Bootstrap: ensure schema_migrations table exists
    with conn.cursor() as cur:
        cur.execute(BOOTSTRAP_SQL)
    conn.commit()

    if args.status:
        with conn.cursor() as cur:
            cur.execute("SELECT version, filename, applied_at FROM schema_migrations ORDER BY version")
            rows = cur.fetchall()
        if not rows:
            print("No migrations applied yet.")
        else:
            print(f"{'Version':<10} {'File':<45} {'Applied At'}")
            print("-" * 80)
            for version, filename, applied_at in rows:
                print(f"{version:<10} {filename:<45} {applied_at}")
        conn.close()
        return

    all_migrations = get_migration_files()
    applied = get_applied_versions(conn)
    pending = [(v, f) for v, f in all_migrations if v not in applied]

    if not pending:
        print("All migrations already applied. Nothing to do.")
        conn.close()
        return

    print(f"Pending migrations: {len(pending)}")
    for version, filename in pending:
        print(f"  [{version:03d}] {filename}")

    if args.dry_run:
        print("\n--dry-run: no changes made.")
        conn.close()
        return

    for version, filename in pending:
        print(f"Applying [{version:03d}] {filename} ...", end=" ", flush=True)
        try:
            apply_migration(conn, version, filename)
            print("OK")
        except Exception as e:
            conn.rollback()
            print(f"FAILED: {e}")
            print("Migration run aborted. Fix the error and re-run.")
            conn.close()
            sys.exit(1)

    print(f"\n{len(pending)} migration(s) applied successfully.")
    conn.close()


if __name__ == "__main__":
    main()
