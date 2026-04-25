-- ============================================================
-- 130_crm_guardian_summary_queue.sql
-- CRM-Guardian S0 — work queue for Gemini Panel Side L1 extraction.
-- Depends on 129_crm_guardian.sql (clients.ai_summary, crm_guardian_events).
-- The queue is the bridge between the nightly orchestrator and the
-- Playwright worker that drives a real Chrome profile against
-- drive.google.com to capture Gemini's multimodal response.
-- Date: 2026-04-25
-- ============================================================

CREATE TABLE IF NOT EXISTS crm_guardian_summary_queue (
    id BIGSERIAL PRIMARY KEY,
    client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    -- work state
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'success', 'error', 'skipped', 'stale')),
    priority INT NOT NULL DEFAULT 100,
    -- lower number = higher priority. Pilot set can be pinned at 1.

    -- schema versioning — bumped only when L1ClientSummary shape changes
    schema_version TEXT NOT NULL DEFAULT 'v1.0',
    prompt_version TEXT NOT NULL DEFAULT 'L1_extraction_v1',

    -- input snapshot (frozen at enqueue time so reruns are reproducible)
    drive_folder_id TEXT,
    drive_folder_name TEXT,
    file_fingerprint TEXT,
    -- SHA256 over (file_id, modifiedTime) list sorted ascending.
    -- On rerun we skip if fingerprint matches the one in clients.ai_summary_file_hash.

    -- run bookkeeping
    attempts INT NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    last_error TEXT,
    next_retry_at TIMESTAMPTZ,

    -- capture metadata (populated by worker)
    raw_response_path TEXT,
    -- file on disk where the raw Gemini DOM dump is saved for audit.
    tokens_estimated INT,
    duration_ms INT,

    -- timing
    enqueued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- linkage to guardian audit trail
    run_id UUID,

    notes TEXT
);

-- One pending row per client (a rerun creates a new row once previous terminal)
CREATE UNIQUE INDEX IF NOT EXISTS ux_crm_guardian_queue_client_pending
    ON crm_guardian_summary_queue (client_id)
    WHERE status IN ('pending', 'running');

CREATE INDEX IF NOT EXISTS ix_crm_guardian_queue_status
    ON crm_guardian_summary_queue (status, priority, enqueued_at);

CREATE INDEX IF NOT EXISTS ix_crm_guardian_queue_client
    ON crm_guardian_summary_queue (client_id, completed_at DESC);

CREATE INDEX IF NOT EXISTS ix_crm_guardian_queue_retry
    ON crm_guardian_summary_queue (next_retry_at)
    WHERE status = 'error';

COMMENT ON TABLE crm_guardian_summary_queue IS
    'Work queue for Gemini Panel Side L1 extraction. Producer: nightly orchestrator. Consumer: Playwright worker (scripts/crm_guardian_gemini_worker.py).';

COMMENT ON COLUMN crm_guardian_summary_queue.file_fingerprint IS
    'SHA256 of sorted (file_id, modifiedTime) pairs inside the canonical folder. If unchanged since last success, worker skips.';

-- ============================================================
-- Register invariant I10b (summary_queue) in guardian state
-- ============================================================
INSERT INTO crm_guardian_state (invariant_id, enabled, dry_run, config)
VALUES ('I10b_summary_queue', false, true,
    jsonb_build_object(
        'description', 'Work queue orchestrator for I10 summary generation.',
        'stale_after_days', 30,
        'default_priority', 100,
        'max_retries', 3,
        'retry_backoff_minutes', 15
    ))
ON CONFLICT (invariant_id) DO NOTHING;

-- === ROLLBACK ===
DROP INDEX IF EXISTS ix_crm_guardian_queue_retry;
DROP INDEX IF EXISTS ix_crm_guardian_queue_client;
DROP INDEX IF EXISTS ix_crm_guardian_queue_status;
DROP INDEX IF EXISTS ux_crm_guardian_queue_client_pending;
DROP TABLE IF EXISTS crm_guardian_summary_queue;
DELETE FROM crm_guardian_state WHERE invariant_id = 'I10b_summary_queue';
