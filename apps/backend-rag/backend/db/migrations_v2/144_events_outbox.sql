-- 144_events_outbox.sql
--
-- Outbox pattern foundation for the EventBus replay-on-reconnect mechanism.
-- See: docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-2_eventbus_outbox_pattern.md
-- Cicatrix scar: "EventBus is PG LISTEN/NOTIFY but Symbiosis docs say Redis Streams (2026-04-29)"
--
-- PHASE 1 (this migration + helper + EventBus reconnect hook):
--   * Adds the durable record of every EventBus publication.
--   * Existing pg_notify callsites are NOT refactored. They keep working.
--   * Only the new replay-on-reconnect path uses the table for now.
--
-- PHASE 2 (separate PR):
--   * Refactor existing emit_pg() callers to publish through outbox.publish().
--   * Update DB trigger functions in migrations 112/113/114 to write to outbox.
--   * Per-handler acknowledgment so a crashing handler does not lose events.
--   * Pruning cron (LaunchAgent on Pro) calls prune_consumed daily.
--
-- Schema notes:
--   * id BIGSERIAL  : monotonic ordering for replay_unconsumed.
--   * channel TEXT  : same string passed to pg_notify($channel, ...).
--   * payload JSONB : opaque to the helper; consumers parse it.
--   * created_at    : default NOW() so callers don't need to set it.
--   * consumed_at   : NULL = unconsumed; NOT NULL = consumed (idempotent ack).
--   * consumer_id   : optional diagnostic; identifies the handler that acked.
--
-- Indexes:
--   * Partial index on (created_at) WHERE consumed_at IS NULL — fast replay.
--   * Partial index on (consumed_at) WHERE consumed_at IS NOT NULL — fast prune.

CREATE TABLE IF NOT EXISTS events_outbox (
    id           BIGSERIAL PRIMARY KEY,
    channel      TEXT NOT NULL,
    payload      JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consumed_at  TIMESTAMPTZ,
    consumer_id  TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_outbox_unconsumed
    ON events_outbox (created_at ASC)
    WHERE consumed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_events_outbox_consumed_age
    ON events_outbox (consumed_at)
    WHERE consumed_at IS NOT NULL;

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_events_outbox_consumed_age;
DROP INDEX IF EXISTS idx_events_outbox_unconsumed;
DROP TABLE IF EXISTS events_outbox;
