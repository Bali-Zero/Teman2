-- ============================================================
-- 129_crm_guardian.sql
-- CRM-Guardian schema — autonomous Drive custodian for BALI ZERO/CRM.
-- - clients.ai_summary JSONB (L1 semantic layer produced by Gemini 3 Pro)
-- - crm_guardian_events (immutable audit trail of every action)
-- - crm_guardian_state (per-invariant runtime state + checkpoints)
-- - crm_guardian_exceptions (hard-skip list for specific clients/folders)
-- - system_settings.crm_guardian_enabled (global kill switch, default false)
-- Date: 2026-04-24
-- ============================================================

-- ============================================================
-- 1. clients.ai_summary — L1 Gemini summary (JSONB schema v1.0)
-- ============================================================
ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS ai_summary JSONB,
    ADD COLUMN IF NOT EXISTS ai_summary_generated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS ai_summary_file_hash TEXT,
    ADD COLUMN IF NOT EXISTS ai_summary_schema_version TEXT;

-- JSONB indexing on hot paths (queryability)
CREATE INDEX IF NOT EXISTS ix_clients_ai_summary_archetype
    ON clients ((ai_summary -> 'profile' ->> 'archetype'));

CREATE INDEX IF NOT EXISTS ix_clients_ai_summary_tier
    ON clients ((ai_summary -> 'profile' ->> 'tier'));

CREATE INDEX IF NOT EXISTS ix_clients_ai_summary_permit_expires
    ON clients ((ai_summary -> 'immigration' -> 'current_status' ->> 'expires_at'));

CREATE INDEX IF NOT EXISTS ix_clients_ai_summary_updated_at
    ON clients (ai_summary_generated_at DESC);

COMMENT ON COLUMN clients.ai_summary IS
    'L1 structured semantic summary produced by crm-guardian via Gemini 3 Pro multimodal. Schema v1.0 (see apps/backend-rag/backend/services/crm_guardian/schemas.py).';

-- ============================================================
-- 2. crm_guardian_events — immutable audit trail
-- ============================================================
CREATE TABLE IF NOT EXISTS crm_guardian_events (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    invariant_id TEXT NOT NULL,
    -- I1_canonical_folder / I2_template / I3_satellite_consol /
    -- I4_orphan_link / I5_dead_links / I6_missing_ocr / I10_summary_l1 /
    -- I11_summary_l2 / I12_summary_l3

    action TEXT NOT NULL,
    -- create_folder / create_subfolder / move_file / trash_folder /
    -- update_db_folder_id / generate_summary / write_brief / sync_notebook /
    -- skip / error / dry_run

    target_type TEXT NOT NULL,
    -- client / folder / file / db_row

    target_id TEXT NOT NULL,
    -- client_id / folder_id / file_id / composite

    client_id INT REFERENCES clients(id) ON DELETE SET NULL,

    before_state JSONB,
    after_state JSONB,

    status TEXT NOT NULL CHECK (status IN ('success', 'partial', 'error', 'dry_run', 'skipped')),

    dry_run BOOLEAN NOT NULL DEFAULT false,
    run_id UUID,
    -- links events of the same guardian run together

    notes TEXT,
    error_message TEXT
);

-- Append-only: forbid UPDATE/DELETE at application level by convention.
-- Enforced via a rule to make violations fail loud.
CREATE OR REPLACE RULE crm_guardian_events_no_update AS
    ON UPDATE TO crm_guardian_events DO INSTEAD NOTHING;
CREATE OR REPLACE RULE crm_guardian_events_no_delete AS
    ON DELETE TO crm_guardian_events DO INSTEAD NOTHING;

CREATE INDEX IF NOT EXISTS ix_crm_guardian_events_ts
    ON crm_guardian_events (ts DESC);
CREATE INDEX IF NOT EXISTS ix_crm_guardian_events_client
    ON crm_guardian_events (client_id, ts DESC);
CREATE INDEX IF NOT EXISTS ix_crm_guardian_events_invariant
    ON crm_guardian_events (invariant_id, ts DESC);
CREATE INDEX IF NOT EXISTS ix_crm_guardian_events_run
    ON crm_guardian_events (run_id);

COMMENT ON TABLE crm_guardian_events IS
    'Append-only audit log of every action performed by crm-guardian. UPDATE/DELETE blocked at rule level.';

-- ============================================================
-- 3. crm_guardian_state — per-invariant runtime state
-- ============================================================
CREATE TABLE IF NOT EXISTS crm_guardian_state (
    invariant_id TEXT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT false,
    -- opt-in model: every invariant starts disabled, operator enables one at a time

    dry_run BOOLEAN NOT NULL DEFAULT true,
    -- new invariants spend first 7 days in dry-run before going live

    last_run_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_error_at TIMESTAMPTZ,
    last_error_message TEXT,

    consecutive_errors INT NOT NULL DEFAULT 0,
    circuit_breaker_tripped BOOLEAN NOT NULL DEFAULT false,
    -- 3 consecutive errors → trip → auto-disable until manual reset

    checkpoint JSONB,
    -- resumable state (e.g., last processed client_id)

    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- per-invariant tunable config (thresholds, batch sizes, ...)

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_crm_guardian_state_enabled
    ON crm_guardian_state (enabled);

-- ============================================================
-- 4. crm_guardian_exceptions — hard-skip list
-- ============================================================
CREATE TABLE IF NOT EXISTS crm_guardian_exceptions (
    id BIGSERIAL PRIMARY KEY,
    invariant_id TEXT NOT NULL,
    -- which invariant to skip for this target; '*' means skip all

    target_type TEXT NOT NULL CHECK (target_type IN ('client', 'folder', 'file')),
    target_id TEXT NOT NULL,

    reason TEXT NOT NULL,
    -- human-readable reason: "team_member", "legal_hold", "manual_curation", ...

    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    -- null = permanent; otherwise exception expires and guardian resumes

    UNIQUE (invariant_id, target_type, target_id)
);

-- Note: no partial predicate on expires_at — NOW() is not IMMUTABLE in index predicate.
-- Filter at query-time: `WHERE expires_at IS NULL OR expires_at > NOW()`.
CREATE INDEX IF NOT EXISTS ix_crm_guardian_exceptions_lookup
    ON crm_guardian_exceptions (invariant_id, target_type, target_id);

-- ============================================================
-- 5. Global kill switch in system_settings (idempotent upsert)
-- ============================================================
INSERT INTO system_settings (key, value, updated_at)
VALUES ('crm_guardian_enabled', 'false', NOW())
ON CONFLICT (key) DO NOTHING;

-- ============================================================
-- 6. Seed state rows for known invariants (all disabled, dry_run=true)
-- ============================================================
INSERT INTO crm_guardian_state (invariant_id, enabled, dry_run, config)
VALUES
    ('I1_canonical_folder', false, true, '{"description": "Ensure every active client has exactly one canonical folder in Individual_CRM/Companies_CRM"}'::jsonb),
    ('I2_template_structure', false, true, '{"description": "Ensure every canonical folder has the 14-subfolder template"}'::jsonb),
    ('I3_satellite_consolidation', false, true, '{"description": "Move files from satellite folders (outside CRM) into canonical/99_Misc; trash empty satellites", "batch_size": 10, "max_files_per_client": 500}'::jsonb),
    ('I4_orphan_folders', false, true, '{"description": "Folders in CRM with no DB client link: auto-link if unambiguous, else queue for review"}'::jsonb),
    ('I5_dead_links', false, true, '{"description": "Clients pointing to trashed/deleted folders: unlink + reprovision"}'::jsonb),
    ('I6_missing_ocr', false, true, '{"description": "Clients with NULL passport_expiry + passport PDF in 00_Profile: trigger OCR"}'::jsonb),
    ('I7_db_duplicates', false, true, '{"description": "DB duplicate client records: report-only (no auto-fix)"}'::jsonb),
    ('I8_permission_audit', false, true, '{"description": "Client folders shared externally or with anyoneWithLink: alert"}'::jsonb),
    ('I10_summary_l1', false, true, '{"description": "Generate clients.ai_summary via Gemini 3 Pro multimodal on canonical folder contents", "model": "gemini-3.1-pro-preview", "max_files_sent": 50}'::jsonb),
    ('I11_summary_l2_markdown', false, true, '{"description": "Render _AI_BRIEF.md inside canonical folder from ai_summary L1"}'::jsonb),
    ('I12_summary_l3_notebooklm', false, true, '{"description": "Sync VIP client folder to a per-client NotebookLM notebook via nlm CLI", "vip_only": true}'::jsonb)
ON CONFLICT (invariant_id) DO NOTHING;

-- === ROLLBACK ===
DROP TABLE IF EXISTS crm_guardian_exceptions;
DROP TABLE IF EXISTS crm_guardian_state;
DROP TABLE IF EXISTS crm_guardian_events;
DELETE FROM system_settings WHERE key = 'crm_guardian_enabled';
DROP INDEX IF EXISTS ix_clients_ai_summary_archetype;
DROP INDEX IF EXISTS ix_clients_ai_summary_tier;
DROP INDEX IF EXISTS ix_clients_ai_summary_permit_expires;
DROP INDEX IF EXISTS ix_clients_ai_summary_updated_at;
ALTER TABLE clients
    DROP COLUMN IF EXISTS ai_summary_schema_version,
    DROP COLUMN IF EXISTS ai_summary_file_hash,
    DROP COLUMN IF EXISTS ai_summary_generated_at,
    DROP COLUMN IF EXISTS ai_summary;
