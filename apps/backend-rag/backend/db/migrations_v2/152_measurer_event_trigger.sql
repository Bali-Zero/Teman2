-- 152_measurer_event_trigger.sql
--
-- Sprint 2 — Measurer Event-driven compliance (Symbiosis Law 4)
--
-- Reference: docs/audits/sprint0/wr2-ipc-mechanism.md § "Violation 1 — measurer
--            writes to DB but no trigger fires"
-- Spec:      docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md
--            § Sprint 2 — WR2 mapping + event contracts
--
-- TRAUMA addressed:
--   `backend.services.measurer.scheduler_cli` INSERTs into post_metrics_history
--   and m13_retrain_log (mig 128) but NO trigger fires after the write. The
--   downstream Measurer dashboards/M14 learner currently poll. This is the
--   only WR2 cognitive organelle that violates Law 3 (Event-driven) per the
--   Sprint 0 Track B2 audit.
--
-- WHAT THIS MIGRATION DOES:
--   1. Adds `measurer_event` to the durability layer (events_outbox + pg_notify)
--      following the migration 146 pattern (write to outbox THEN fire NOTIFY,
--      both inside the same user transaction).
--   2. Creates `notify_measurer_event()` trigger function dispatching on
--      TG_TABLE_NAME for post_metrics_history (event_type=metric_recorded)
--      and m13_retrain_log (event_type=retrain_executed).
--   3. Attaches AFTER INSERT triggers to both tables.
--
-- The Python-side `PG_CHANNEL_MAP` in
-- `apps/backend-rag/backend/services/events/event_bus.py` must be updated
-- in the same PR to register `measurer_event → measurer.event`. The
-- migration runner picks up this SQL automatically via
-- `run-sql-v2-migrations-post-deploy` (cf. cicatrix SQL v2 deploy ordering).
--
-- Idempotency: CREATE OR REPLACE FUNCTION + DROP TRIGGER IF EXISTS guard
-- against re-runs on a partially-applied state.
--
-- Squawk: this trigger creation operates on production tables (post_metrics_history
-- and m13_retrain_log) that already contain rows. The trigger is AFTER INSERT only
-- (no UPDATE/DELETE rewrite), so existing rows are NOT touched and lock acquisition
-- is brief. require-timeout-settings is suppressed for the same rationale used in
-- migration 146 (trigger creation, not a long-running DDL on data rows).

CREATE OR REPLACE FUNCTION notify_measurer_event()
RETURNS TRIGGER AS $$
DECLARE
    payload      JSONB;
    event_type   TEXT;
    outbox_id    BIGINT;
BEGIN
    IF TG_TABLE_NAME = 'post_metrics_history' THEN
        event_type := 'metric_recorded';
        payload := jsonb_build_object(
            'metric_id',      NEW.id,
            'post_id',        NEW.post_id,
            'horizon_hours',  NEW.horizon_hours,
            'metric_name',    NEW.metric_name,
            'metric_value',   NEW.metric_value,
            'source',         NEW.source,
            'event_type',     event_type,
            'occurred_at',    NEW.collected_at
        );
    ELSIF TG_TABLE_NAME = 'm13_retrain_log' THEN
        event_type := 'retrain_executed';
        payload := jsonb_build_object(
            'retrain_id',     NEW.id,
            'trigger_type',   NEW.trigger_type,
            'delta_pct',      NEW.delta_pct,
            'event_type',     event_type,
            'occurred_at',    NEW.retrained_at
        );
    ELSE
        -- Defensive: trigger attached to an unexpected table — no-op.
        RETURN NEW;
    END IF;

    -- Persist to durability layer BEFORE pg_notify (mig 144 pattern).
    -- Same user transaction: rollback erases both consistently.
    INSERT INTO events_outbox (channel, payload)
    VALUES ('measurer_event', payload)
    RETURNING id INTO outbox_id;

    -- Attach _outbox_id to NOTIFY payload so consumers can ack idempotently
    -- on replay (mig 146 contract).
    PERFORM pg_notify(
        'measurer_event',
        (payload || jsonb_build_object('_outbox_id', outbox_id))::text
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION notify_measurer_event() IS
    'Sprint 2 Measurer event-driven compliance. Emits measurer_event channel '
    'on AFTER INSERT into post_metrics_history (metric_recorded) and '
    'm13_retrain_log (retrain_executed). Persists to events_outbox first '
    '(durability) then pg_notify (mig 146 outbox pattern).';

-- Drop existing triggers (idempotent re-run of this migration).
DROP TRIGGER IF EXISTS post_metrics_history_notify_measurer ON post_metrics_history;
DROP TRIGGER IF EXISTS m13_retrain_log_notify_measurer ON m13_retrain_log;

-- Attach triggers — AFTER INSERT only (no UPDATE/DELETE — m13 tables are
-- append-only by design, see mig 128 schema comments).
CREATE TRIGGER post_metrics_history_notify_measurer
    AFTER INSERT ON post_metrics_history
    FOR EACH ROW
    EXECUTE FUNCTION notify_measurer_event();

CREATE TRIGGER m13_retrain_log_notify_measurer
    AFTER INSERT ON m13_retrain_log
    FOR EACH ROW
    EXECUTE FUNCTION notify_measurer_event();

-- === ROLLBACK ===
-- Reverts the trigger + function. Safe to run on any DB state because both
-- DROP statements use IF EXISTS — no error if the migration was never
-- applied. After rollback, post_metrics_history and m13_retrain_log INSERTs
-- no longer emit measurer_event NOTIFY; downstream consumers (M14 learner,
-- dashboards) fall back to the pre-Sprint-2 polling behaviour.
DROP TRIGGER IF EXISTS post_metrics_history_notify_measurer ON post_metrics_history;
DROP TRIGGER IF EXISTS m13_retrain_log_notify_measurer ON m13_retrain_log;
DROP FUNCTION IF EXISTS notify_measurer_event();
