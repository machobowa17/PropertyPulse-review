-- Migration 001: core_pipeline_runs
-- Tracks every ETL source/derived run: status, row counts, validation, errors.
-- This is the central audit log for all data ingestion activity.

CREATE TABLE IF NOT EXISTS core_pipeline_runs (
    id              SERIAL PRIMARY KEY,
    source_name     TEXT        NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT        NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'success', 'failed', 'validation_failed')),
    rows_before     BIGINT,
    rows_after      BIGINT,
    source_url      TEXT,
    source_version  TEXT,
    validation_notes TEXT,
    error_msg       TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_source
    ON core_pipeline_runs (source_name, started_at DESC);
