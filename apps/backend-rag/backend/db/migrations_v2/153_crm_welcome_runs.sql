-- 153_crm_welcome_runs.sql
--
-- Sprint 3 W2 — CRM cell consolidation: welcome flow event source
--
-- Reference: docs/sprint3/crm-cell-design.md § Q2c "New crm_welcome_completed channel"
-- Spec:      docs/sprint3/crm-cell-design.md § "crm_welcome_runs table spec"
--
-- WHAT THIS MIGRATION DOES:
--   1. Adds crm_welcome_runs table — audit row for each welcome flow attempt
--      (one (client_id, practice_id) pair per row).
--   2. Creates notify_crm_welcome_completed() trigger function emitting
--      crm_welcome_completed channel ONLY when success=true (partial-failure
--      attempts are persisted as audit rows but NOT broadcast downstream).
--   3. Persists to events_outbox BEFORE pg_notify (mig 144 + 146 outbox
--      pattern). _outbox_id injected for idempotent ack on replay.
--   4. AFTER INSERT OR UPDATE trigger with WHEN guard — fires once on the
--      false→true success transition (whether the row was created already
--      successful via direct INSERT, or was retried from partial failure
--      via ON CONFLICT DO UPDATE). The WHEN clause prevents duplicate
--      events when the cell adapter writes the same successful row twice.
--      Multi-LLM W2 review caught the original AFTER INSERT-only design
--      as silently dropping retry events; cf. SYNTHESIS B1.
--
-- The Python-side PG_CHANNEL_MAP in
-- apps/backend-rag/backend/services/events/event_bus.py must be updated
-- in the same PR to register crm_welcome_completed → crm.welcome_completed.
-- The migration runner picks up this SQL automatically via
-- run-sql-v2-migrations-post-deploy (cf. cicatrix SQL v2 deploy ordering).
--
-- Idempotency: CREATE TABLE IF NOT EXISTS + CREATE OR REPLACE FUNCTION +
-- DROP TRIGGER IF EXISTS guard against re-runs on partially-applied state.
--
-- Squawk: this migration creates a brand-new empty table — no lock contention
-- on existing rows. Trigger creation operates on a freshly-created empty
-- table; require-timeout-settings is suppressed because this is empty-table
-- DDL (same rationale as migration 144 events_outbox).

CREATE TABLE IF NOT EXISTS crm_welcome_runs (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    practice_id BIGINT REFERENCES practices(id) ON DELETE SET NULL,
    -- Drive folder created during welcome (NULL if Drive step skipped/failed)
    drive_folder_id TEXT,
    -- Channels actually delivered: subset of ['email', 'whatsapp', 'telegram']
    channels_sent TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Welcome flow has 4 sub-steps: practice + drive + WA + email.
    -- success=true ONLY when all 4 green; partial = false (and trigger
    -- does NOT emit; partial-failure path is documented in the W2 cell adapter).
    success BOOLEAN NOT NULL,
    -- Metadata for cross-step debugging (failed_step name, error msg, etc.)
    metadata JSONB DEFAULT '{}'::jsonb,
    -- One welcome run per (client, practice). Re-runs require explicit
    -- DELETE + INSERT or UPSERT in the cell adapter (out of trigger scope).
    UNIQUE (client_id, practice_id)
);

CREATE INDEX IF NOT EXISTS ix_crm_welcome_runs_client
    ON crm_welcome_runs (client_id);

CREATE INDEX IF NOT EXISTS ix_crm_welcome_runs_completed
    ON crm_welcome_runs (completed_at DESC) WHERE success = true;

CREATE OR REPLACE FUNCTION notify_crm_welcome_completed()
RETURNS TRIGGER AS $$
DECLARE
    payload    JSONB;
    outbox_id  BIGINT;
BEGIN
    -- Function body is the unconditional emit; the trigger declaration
    -- WHEN clause guards on (NEW.success=true AND
    -- (TG_OP='INSERT' OR OLD.success IS DISTINCT FROM NEW.success)) so
    -- this code only runs on the false→true success transition.
    payload := jsonb_build_object(
        'client_id',       NEW.client_id,
        'practice_id',     NEW.practice_id,
        'drive_folder_id', NEW.drive_folder_id,
        'channels_sent',   NEW.channels_sent,
        'event_type',      'welcome_completed',
        'occurred_at',     NEW.completed_at
    );

    -- Persist to durability layer BEFORE pg_notify (mig 144 pattern).
    -- Same user transaction: rollback erases both consistently.
    INSERT INTO events_outbox (channel, payload)
    VALUES ('crm_welcome_completed', payload)
    RETURNING id INTO outbox_id;

    -- Attach _outbox_id to NOTIFY payload so consumers can ack
    -- idempotently on replay (mig 146 contract).
    PERFORM pg_notify(
        'crm_welcome_completed',
        (payload || jsonb_build_object('_outbox_id', outbox_id))::text
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION notify_crm_welcome_completed() IS
    'Sprint 3 W2 CRM-cell welcome flow event emitter. Emits '
    'crm_welcome_completed channel on AFTER INSERT OR UPDATE into '
    'crm_welcome_runs whose WHEN clause matches the false→true success '
    'transition (covers fresh INSERT(success=true) AND retry UPSERT '
    'where OLD.success=false changes to NEW.success=true). '
    'Partial-failure rows are persisted for audit but do NOT fire '
    'downstream observers. Persists to events_outbox first (durability) '
    'then pg_notify (mig 146 outbox pattern). Function body is '
    'unconditional emit; the WHEN guard on the trigger declaration '
    'enforces the success-transition policy.';

-- Drop existing triggers (idempotent re-run).
DROP TRIGGER IF EXISTS crm_welcome_runs_notify ON crm_welcome_runs;
DROP TRIGGER IF EXISTS crm_welcome_runs_notify_insert ON crm_welcome_runs;
DROP TRIGGER IF EXISTS crm_welcome_runs_notify_update ON crm_welcome_runs;

-- Two separate triggers — Postgres does NOT allow TG_OP in CREATE TRIGGER
-- WHEN clauses (only OLD/NEW columns are referenceable per the docs:
-- "the WHEN condition can refer to columns of the old and/or new row").
-- Splitting INSERT and UPDATE handles the same matrix as a unified
-- "AFTER INSERT OR UPDATE WHEN (TG_OP=... OR ...)" without the syntax
-- violation. v2.6 fix (CI failed: column "tg_op" does not exist).
--
-- Cases the two triggers cover:
--   * INSERT(success=true)        → INSERT trigger fires (WHEN NEW.success=true)
--   * INSERT(success=false)       → DOES NOT fire (WHEN gates it)
--   * UPDATE: false→true (retry)  → UPDATE trigger fires (success transitioned)
--   * UPDATE: true→true (no-op)   → DOES NOT fire (OLD.success = NEW.success)
--   * UPDATE: true→false          → DOES NOT fire (NEW.success=false gates it)
CREATE TRIGGER crm_welcome_runs_notify_insert
    AFTER INSERT ON crm_welcome_runs
    FOR EACH ROW
    WHEN (NEW.success = true)
    EXECUTE FUNCTION notify_crm_welcome_completed();

CREATE TRIGGER crm_welcome_runs_notify_update
    AFTER UPDATE ON crm_welcome_runs
    FOR EACH ROW
    WHEN (NEW.success = true
          AND OLD.success IS DISTINCT FROM NEW.success)
    EXECUTE FUNCTION notify_crm_welcome_completed();

-- === ROLLBACK ===
-- Reverts the triggers + function + indexes + table. Safe to run on any
-- DB state because all DROP statements use IF EXISTS — no error if the
-- migration was never applied. After rollback, crm_welcome_runs is gone;
-- downstream observers (analytics, retention loop) lose the welcome
-- completion signal and fall back to the pre-Sprint-3 polling behaviour.
DROP TRIGGER IF EXISTS crm_welcome_runs_notify_update ON crm_welcome_runs;
DROP TRIGGER IF EXISTS crm_welcome_runs_notify_insert ON crm_welcome_runs;
DROP TRIGGER IF EXISTS crm_welcome_runs_notify ON crm_welcome_runs;
DROP FUNCTION IF EXISTS notify_crm_welcome_completed();
DROP INDEX IF EXISTS ix_crm_welcome_runs_completed;
DROP INDEX IF EXISTS ix_crm_welcome_runs_client;
DROP TABLE IF EXISTS crm_welcome_runs;
