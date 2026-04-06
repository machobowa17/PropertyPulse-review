-- Migration 002: schema_migrations
-- Tracks which migration files have been applied.
-- migrate.py reads this table to know which migrations are pending.
-- NOTE: This table must be created before any other migrations are tracked,
-- so migrate.py handles its own bootstrap by creating it if absent.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER     PRIMARY KEY,
    filename    TEXT        NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
