-- 155_asset_provenance_trigger.sql
--
-- Sprint 3 W2 — Mata-Garuda L4.5 cell: asset_provenance event emitter.
--
-- Reference: docs/sprint3/mata-garuda-cell-design.md § "Trigger emission"
-- Depends:   migration 154 (asset_provenance table)
-- Channel:   asset_provenance → mata_garuda.asset_provenance (registered
--            in PG_CHANNEL_MAP, see apps/backend-rag/backend/services/events/
--            event_bus.py).
--
-- WHAT THIS MIGRATION DOES:
--   1. Creates notify_asset_provenance() trigger function emitting
--      asset_provenance channel on INSERT/UPDATE.
--   2. event_type ∈ {provenance_recorded, provenance_updated} via TG_OP.
--   3. Persists to events_outbox BEFORE pg_notify (mig 144 + 146 outbox
--      pattern). _outbox_id injected into NOTIFY payload for idempotent
--      ack on replay.
--
-- The Python-side PG_CHANNEL_MAP already registers asset_provenance →
-- mata_garuda.asset_provenance (committed alongside migration 153).
--
-- Idempotency: CREATE OR REPLACE FUNCTION + DROP TRIGGER IF EXISTS guard
-- against re-runs on partially-applied state.
--
-- Squawk: this trigger creation operates on a freshly-created (mig 154)
-- empty table — no lock contention. require-timeout-settings is suppressed
-- for the same rationale used in migration 146 (trigger creation, not
-- a long-running DDL on data rows).

CREATE OR REPLACE FUNCTION notify_asset_provenance()
RETURNS TRIGGER AS $$
DECLARE
    payload      JSONB;
    event_type   TEXT;
    outbox_id    BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        event_type := 'provenance_recorded';
    ELSIF TG_OP = 'UPDATE' THEN
        event_type := 'provenance_updated';
    ELSE
        -- Defensive: trigger attached to an unexpected op — no-op.
        RETURN COALESCE(NEW, OLD);
    END IF;

    payload := jsonb_build_object(
        'provenance_id',             NEW.id,
        'asset_kind',                NEW.asset_kind,
        'asset_id',                  NEW.asset_id,
        'source',                    NEW.source,
        'reliability',               NEW.reliability,
        'credibility',               NEW.credibility,
        'owner',                     NEW.owner,
        'valid_until',               NEW.valid_until,
        'invalidation_event_topic',  NEW.invalidation_event_topic,
        'invalidation_mode',         NEW.invalidation_mode,
        'tlp',                       NEW.tlp,
        'event_type',                event_type,
        'occurred_at',               NEW.updated_at
    );

    -- Persist to durability layer BEFORE pg_notify (mig 144 pattern).
    -- Same user transaction: rollback erases both consistently.
    INSERT INTO events_outbox (channel, payload)
    VALUES ('asset_provenance', payload)
    RETURNING id INTO outbox_id;

    -- Attach _outbox_id to NOTIFY payload so consumers can ack idempotently
    -- on replay (mig 146 contract). NOTE: like all current channels, this
    -- emits at-least-once with auto-ack on dispatch (phase-2 outbox
    -- semantics). Consumers MUST be idempotent on _outbox_id. Phase-3
    -- per-handler ack is future work.
    PERFORM pg_notify(
        'asset_provenance',
        (payload || jsonb_build_object('_outbox_id', outbox_id))::text
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION notify_asset_provenance() IS
    'Sprint 3 W2 Mata-Garuda L4.5 asset_provenance event emitter. Emits '
    'asset_provenance channel on AFTER INSERT (provenance_recorded) and '
    'AFTER UPDATE (provenance_updated). Persists to events_outbox first '
    '(durability) then pg_notify (mig 146 outbox pattern). Payload includes '
    'admiralty 2-axis confidence (reliability/credibility), TLP, and the '
    '3-column invalidation policy.';

-- Drop existing triggers (idempotent re-run).
DROP TRIGGER IF EXISTS asset_provenance_notify ON asset_provenance;
DROP TRIGGER IF EXISTS asset_provenance_notify_insert ON asset_provenance;
DROP TRIGGER IF EXISTS asset_provenance_notify_update ON asset_provenance;

-- Two separate triggers — Postgres does NOT allow TG_OP in
-- CREATE TRIGGER WHEN clauses (only OLD/NEW columns are referenceable).
-- v2.6 fix (CI failed: column "tg_op" does not exist).
--
-- INSERT trigger: always fires (every new asset_provenance row becomes
-- a provenance_recorded event).
--
-- UPDATE trigger: fires only when the row truly changed (WHEN guard
-- using OLD.* IS DISTINCT FROM NEW.*) — prevents no-op emissions when
-- the cell adapter performs idempotent ON CONFLICT DO UPDATE that
-- writes the same values. Combined with mig 154's conditional BEFORE
-- UPDATE trigger that only bumps updated_at when the row truly
-- changes, the AFTER UPDATE trigger correctly skips no-op UPSERTs.
--
-- OLD.* IS DISTINCT FROM NEW.* uses Postgres NULL-safe comparison;
-- works correctly when columns transition NULL ↔ value (e.g.
-- valid_until set for the first time, invalidated_at populated
-- by sweeper).
CREATE TRIGGER asset_provenance_notify_insert
    AFTER INSERT ON asset_provenance
    FOR EACH ROW
    EXECUTE FUNCTION notify_asset_provenance();

CREATE TRIGGER asset_provenance_notify_update
    AFTER UPDATE ON asset_provenance
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION notify_asset_provenance();

-- === ROLLBACK ===
-- Reverts the triggers + function. Safe to run on any DB state because
-- all DROP statements use IF EXISTS. After rollback, asset_provenance
-- INSERT/UPDATE no longer emits the asset_provenance NOTIFY; the row
-- is still written but downstream consumers (WR2 invalidation reactor,
-- oracle citation guard, KG demotion cron) get no signal.
DROP TRIGGER IF EXISTS asset_provenance_notify_update ON asset_provenance;
DROP TRIGGER IF EXISTS asset_provenance_notify_insert ON asset_provenance;
DROP TRIGGER IF EXISTS asset_provenance_notify ON asset_provenance;
DROP FUNCTION IF EXISTS notify_asset_provenance();
