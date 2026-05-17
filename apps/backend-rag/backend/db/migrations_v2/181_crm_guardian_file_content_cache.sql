-- ============================================================
-- 181_crm_guardian_file_content_cache.sql
-- CRM-Guardian Phase 1.5 — OCR / text-extraction cache layer
--
-- Phase 1 bulk paused 2026-05-18 01:32 WITA after smartness audit
-- revealed Gemini hallucinated identity from filename tokens (Sofia
-- Mueller → Andrey Pozdnyakov) because the worker passed only file
-- metadata, not PDF content. Phase 1.5 pre-extracts text from each
-- Drive file via tesseract (printed) or qwen2.5vl Ollama (scanned)
-- and feeds it to Gemini alongside metadata.
--
-- This cache table holds one row per Drive file_id with the extracted
-- text + content_hash + extractor provenance. Subsequent re-enqueues
-- of the same client SKIP re-OCR when the Drive modifiedTime matches
-- the cached row.
--
-- Soft-delete policy (Antonello decision 2026-05-18 02:00 WITA): when
-- a file is removed from Drive, `deleted_at` is set instead of DELETE
-- so the OCR text remains for forensic audit. Cron purges rows older
-- than 365 days with deleted_at not null (out of scope this migration).
--
-- UU PDP posture: text_content contains PII (passport scans, NPWP, akta,
-- capital). Existing posture inherits from clients.ai_summary (Fly PG
-- encryption-at-rest baseline + RBAC table-level via backend RLS).
-- Retention is linked to clients.status='active' (purge cron, future PR).
--
-- Decision memo: research/crm-guardian/2026-05-18-phase-1.5-ocr-layer-plan.md
-- Depends on: 129_crm_guardian.sql (defined CRM-Guardian invariants)
--             130_crm_guardian_summary_queue.sql (defines queue table)
--             180_crm_guardian_phase1_enable.sql (Phase 1 enable flags)
-- Date: 2026-05-18
-- ============================================================

-- Guard against ordering hazards: 130 + 180 MUST be applied first.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'crm_guardian_summary_queue'
    ) THEN
        RAISE EXCEPTION 'crm_guardian_summary_queue not found — apply migration 130 first';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM crm_guardian_state WHERE invariant_id = 'I10_summary_l1'
    ) THEN
        RAISE EXCEPTION 'I10_summary_l1 not found — apply migration 180 first';
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS crm_guardian_file_content_cache (
    id                BIGSERIAL PRIMARY KEY,
    file_id           TEXT        NOT NULL,
    modified_time_ms  BIGINT      NOT NULL,
    content_hash      TEXT        NOT NULL,
    text_content      TEXT        NOT NULL,
    text_length       INTEGER     NOT NULL,
    extractor         TEXT        NOT NULL,
    confidence        REAL,
    page_count        INTEGER,
    pii_redacted      BOOLEAN     NOT NULL DEFAULT false,
    extracted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at        TIMESTAMPTZ,
    notes             TEXT,
    CONSTRAINT ck_file_content_extractor CHECK (
        extractor IN ('pdfminer', 'tesseract', 'qwen25vl', 'mixed', 'skipped')
    ),
    CONSTRAINT ck_file_content_text_length CHECK (text_length >= 0),
    CONSTRAINT ck_file_content_confidence CHECK (
        confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)
    )
);

COMMENT ON TABLE crm_guardian_file_content_cache IS
  'CRM-Guardian Phase 1.5 OCR cache. One row per Drive file_id. Soft-delete via deleted_at.';
COMMENT ON COLUMN crm_guardian_file_content_cache.file_id IS
  'Google Drive file_id. Unique alive (active rows) — see ux_file_content_alive partial index.';
COMMENT ON COLUMN crm_guardian_file_content_cache.modified_time_ms IS
  'Drive modifiedTime in milliseconds. Worker skips re-OCR when (file_id, modified_time_ms) match.';
COMMENT ON COLUMN crm_guardian_file_content_cache.content_hash IS
  'sha256 of text_content (hex). For change detection across re-extractions.';
COMMENT ON COLUMN crm_guardian_file_content_cache.text_content IS
  'Extracted text. May contain PII (passport, NPWP). UU PDP scope.';
COMMENT ON COLUMN crm_guardian_file_content_cache.extractor IS
  'pdfminer = native PDF text layer. tesseract = OCR printed. qwen25vl = vision fallback. mixed = both. skipped = file too large or unsupported.';
COMMENT ON COLUMN crm_guardian_file_content_cache.confidence IS
  'Self-reported 0.0-1.0 by extractor. NULL for pdfminer (no scoring).';
COMMENT ON COLUMN crm_guardian_file_content_cache.deleted_at IS
  'Soft-delete: file removed from Drive. NULL = alive.';

-- Unique active row per Drive file_id (allows replays via soft-delete cycle).
CREATE UNIQUE INDEX IF NOT EXISTS ux_file_content_alive
    ON crm_guardian_file_content_cache (file_id)
    WHERE deleted_at IS NULL;

-- Fast skip lookup: worker queries (file_id, modified_time_ms) to decide cache hit.
CREATE INDEX IF NOT EXISTS ix_file_content_skip_lookup
    ON crm_guardian_file_content_cache (file_id, modified_time_ms)
    WHERE deleted_at IS NULL;

-- Forensic / retention sweep: find stale soft-deleted rows.
CREATE INDEX IF NOT EXISTS ix_file_content_deleted_at
    ON crm_guardian_file_content_cache (deleted_at)
    WHERE deleted_at IS NOT NULL;

-- Audit Phase 1.5 cache activation.
INSERT INTO crm_guardian_events (
    invariant_id, action, target_type, target_id, client_id,
    before_state, after_state, status, dry_run
)
VALUES (
    'I10_summary_l1',
    'enable_phase1.5_cache',
    'system',
    'crm_guardian_file_content_cache',
    NULL,
    jsonb_build_object('table_exists', false),
    jsonb_build_object(
        'table_exists', true,
        'migration', '181_crm_guardian_file_content_cache',
        'soft_delete', true,
        'extractors', jsonb_build_array('pdfminer', 'tesseract', 'qwen25vl', 'mixed', 'skipped'),
        'note', 'Phase 1.5 OCR cache layer ready. Worker integration follows.'
    ),
    'success',
    false
);

-- === ROLLBACK ===
-- Drop the cache table. Cached OCR text is destroyed — recoverable only via
-- next bulk re-OCR pass (cost: full Phase 1.5 throughput hit).

DROP INDEX IF EXISTS ix_file_content_deleted_at;
DROP INDEX IF EXISTS ix_file_content_skip_lookup;
DROP INDEX IF EXISTS ux_file_content_alive;

DROP TABLE IF EXISTS crm_guardian_file_content_cache;

INSERT INTO crm_guardian_events (
    invariant_id, action, target_type, target_id, client_id,
    before_state, after_state, status, dry_run
)
VALUES (
    'I10_summary_l1',
    'disable_phase1.5_cache',
    'system',
    'crm_guardian_file_content_cache',
    NULL,
    jsonb_build_object('table_exists', true),
    jsonb_build_object('table_exists', false, 'migration', '181_crm_guardian_file_content_cache', 'rolled_back', true),
    'success',
    false
);
