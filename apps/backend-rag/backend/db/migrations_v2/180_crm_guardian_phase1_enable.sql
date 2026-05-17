-- ============================================================
-- 180_crm_guardian_phase1_enable.sql
-- CRM-Guardian Phase 1 activation — flip enabled=true on I10 + I10b
-- in dry_run=true mode (sicurezza: nessun write su clients.ai_summary
-- finché il pilot 5 VIP non passa il sign-off Antonello).
--
-- Phase 1 scope: cross-folder L1 summary (client root + linked companies
-- via client_company_links). Schema L1 v2.0, prompt L1_extraction_v2.
-- Decision memo: docs/superpowers/plans/2026-05-16-crm-guardian-activation-phase1.md
-- Depends on: 129_crm_guardian.sql (clients.ai_summary, crm_guardian_state)
--             130_crm_guardian_summary_queue.sql (queue table)
-- Date: 2026-05-16
-- ============================================================

-- Guard against ordering hazards: 129+130 MUST be applied first.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'crm_guardian_state'
    ) THEN
        RAISE EXCEPTION 'crm_guardian_state table not found — apply migrations 129+130 first';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'crm_guardian_summary_queue'
    ) THEN
        RAISE EXCEPTION 'crm_guardian_summary_queue table not found — apply migration 130 first';
    END IF;
END $$;

-- I10_summary_l1 — enable in dry_run mode + bump prompt_version + add Phase 1 config
UPDATE crm_guardian_state
SET enabled = true,
    dry_run = true,
    config = config || jsonb_build_object(
        'phase', 'phase1_activation_2026_05_16',
        'schema_version', 'v2.0',
        'prompt_version', 'L1_extraction_v2',
        'cross_folder_enabled', true,
        'tax_records_aggressive_refresh', true,
        'narrative_languages', jsonb_build_array('en'),
        'max_files_sent', 50,
        'concurrency_max', 3,
        'throttle_seconds_between_jobs', 30,
        'manual_review_confidence_threshold', 0.6
    ),
    updated_at = NOW()
WHERE invariant_id = 'I10_summary_l1';

-- I10b_summary_queue — enable in dry_run mode + add Phase 1 retry/priority config
UPDATE crm_guardian_state
SET enabled = true,
    dry_run = true,
    config = config || jsonb_build_object(
        'phase', 'phase1_activation_2026_05_16',
        'priority_vip', 1,
        'priority_standard', 50,
        'priority_archive', 100,
        'stale_after_days', 30,
        'max_retries', 3,
        'retry_backoff_minutes', 15,
        'orphan_running_timeout_minutes', 15
    ),
    updated_at = NOW()
WHERE invariant_id = 'I10b_summary_queue';

-- Update default schema_version + prompt_version on queue rows enqueued from now on.
-- Existing queue rows with status='pending' keep their v1 metadata; worker handles both.
ALTER TABLE crm_guardian_summary_queue
    ALTER COLUMN schema_version SET DEFAULT 'v2.0';

ALTER TABLE crm_guardian_summary_queue
    ALTER COLUMN prompt_version SET DEFAULT 'L1_extraction_v2';

-- Sanity: log activation to crm_guardian_events for audit trail.
-- NULL client_id is allowed (FK ON DELETE SET NULL); target_type='system'
-- to denote a global state change rather than a per-client action.
INSERT INTO crm_guardian_events (
    invariant_id, action, target_type, target_id, client_id,
    before_state, after_state, status, dry_run
)
VALUES (
    'I10_summary_l1',
    'enable_phase1',
    'system',
    'crm_guardian_state',
    NULL,
    jsonb_build_object('enabled', false),
    jsonb_build_object(
        'enabled', true,
        'dry_run', true,
        'migration', '180_crm_guardian_phase1_enable',
        'schema_version', 'v2.0',
        'prompt_version', 'L1_extraction_v2',
        'note', 'Phase 1 cross-folder activation. dry_run=true until pilot 5 VIP sign-off.'
    ),
    'dry_run',
    true
);

INSERT INTO crm_guardian_events (
    invariant_id, action, target_type, target_id, client_id,
    before_state, after_state, status, dry_run
)
VALUES (
    'I10b_summary_queue',
    'enable_phase1',
    'system',
    'crm_guardian_state',
    NULL,
    jsonb_build_object('enabled', false),
    jsonb_build_object(
        'enabled', true,
        'dry_run', true,
        'migration', '180_crm_guardian_phase1_enable',
        'concurrency_max', 3,
        'throttle_seconds_between_jobs', 30,
        'note', 'Phase 1 work queue activation. Worker LaunchAgent deployment Day 7.'
    ),
    'dry_run',
    true
);

-- === ROLLBACK ===
-- Revert column defaults to v1 (the values from migration 130).
ALTER TABLE crm_guardian_summary_queue
    ALTER COLUMN schema_version SET DEFAULT 'v1.0';

ALTER TABLE crm_guardian_summary_queue
    ALTER COLUMN prompt_version SET DEFAULT 'L1_extraction_v1';

-- Disable invariants. Keep config in place for forensic inspection;
-- only the enabled flag flips. Re-running the forward migration re-enables.
UPDATE crm_guardian_state
SET enabled = false,
    updated_at = NOW()
WHERE invariant_id IN ('I10_summary_l1', 'I10b_summary_queue');

-- Mark rollback in audit trail.
INSERT INTO crm_guardian_events (
    invariant_id, action, target_type, target_id, client_id,
    before_state, after_state, status, dry_run
)
VALUES (
    'I10_summary_l1',
    'disable_phase1',
    'system',
    'crm_guardian_state',
    NULL,
    jsonb_build_object('enabled', true),
    jsonb_build_object('enabled', false, 'migration', '180_crm_guardian_phase1_enable', 'rolled_back', true),
    'success',
    false
);
