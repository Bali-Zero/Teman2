"""
Migration 070: Legal Ingest Jobs Queue

Creates job queue table for async legal document ingestion pipeline.
Pattern: PostgreSQL SKIP LOCKED (per ADR in NB-9: zero new services).
"""

UPGRADE_SQL = """
CREATE TABLE IF NOT EXISTS legal_ingest_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key TEXT UNIQUE NOT NULL,
    tipo            TEXT NOT NULL,
    nomor           TEXT NOT NULL,
    anno            TEXT NOT NULL,
    titolo          TEXT,
    source_url      TEXT,
    nb_target       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    qdrant_chunks   INTEGER,
    drive_file_id   TEXT,
    drive_url       TEXT,
    nlm_source_id   TEXT,
    sheets_row      TEXT,
    error           TEXT,
    visibility_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_legal_ingest_jobs_queue
    ON legal_ingest_jobs (status, visibility_at)
    WHERE status NOT IN ('complete', 'failed');

COMMENT ON TABLE legal_ingest_jobs IS
    'Async job queue for legal document ingestion pipeline (Qdrant+KG->Drive->NLM->Sheets)';
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS legal_ingest_jobs;
"""
