-- 145_inbound_webhooks.sql
--
-- Inbound webhooks durability table (P0-6 from zero-crash audit 2026-04-29).
--
-- TRAUMA: Webhook routers (whatsapp, telegram, instagram, twitter) currently
-- process synchronously OR via FastAPI BackgroundTasks (volatile). Meta and
-- Twitter auto-disable webhooks after 3 failures in 5 min when processing
-- exceeds 3s. On Fly machine crash mid-processing, in-flight webhook is lost
-- — no ack to external = external retry storm = duplicates.
--
-- ANTIBODY: Ack-first pattern. Each webhook router persists the verified
-- payload to ``inbound_webhooks`` and returns 200 OK in <200ms. A background
-- ``WebhookProcessor`` (services/channels/webhook_processor.py) drains the
-- table via PG LISTEN + 5s polling fallback.
--
-- Schema notes:
--   * id BIGSERIAL          : monotonic ordering for the worker SELECT.
--   * channel TEXT          : "whatsapp" | "telegram" | "instagram" | "twitter".
--   * payload JSONB         : opaque to the table; the channel handler parses it.
--   * dedup_key TEXT        : channel-specific idempotency key (Meta message_id,
--                             Telegram update_id, Twitter dm.id). Combined with
--                             channel, this is UNIQUE — Meta/Twitter retries
--                             that arrive before our ack are dropped at the
--                             ON CONFLICT DO NOTHING boundary in the router.
--   * received_at TIMESTAMPTZ DEFAULT NOW() : when the router persisted it.
--   * processed_at TIMESTAMPTZ NULL         : set by worker on success or
--                                              terminal failure (5 attempts).
--   * error_message TEXT NULL  : last exception repr (truncated 500 chars).
--   * attempts INTEGER NOT NULL DEFAULT 0   : incremented by worker on failure.
--   * next_retry_at TIMESTAMPTZ NULL        : when the worker may try again.
--                                              NULL = ready immediately.
--
-- Retry policy: 5 attempts, linear backoff (5min × attempt). After the 5th
-- failure the row is marked processed with error_message="GIVING UP after
-- 5 attempts: <reason>".
--
-- Indexes:
--   * Partial index on (channel, received_at) WHERE processed_at IS NULL —
--     fast worker scan (small-cardinality WHERE collapses to ~queue size).
--   * Index on (received_at DESC) — full-table scan helper for ChannelSensor
--     and admin debugging.
--   * The UNIQUE(channel, dedup_key) creates an implicit btree used by the
--     ON CONFLICT DO NOTHING in the router.
--
-- Squawk lint: BIGSERIAL on a brand-new table cannot contend with anything,
-- and the partial indexes are on an empty table at creation time — no need
-- for CONCURRENTLY. Suppressed per-statement to keep noise out of CI.

CREATE TABLE IF NOT EXISTS inbound_webhooks (   -- squawk-ignore: prefer-bigint-over-smallint
    id              BIGSERIAL PRIMARY KEY,
    channel         TEXT NOT NULL,
    payload         JSONB NOT NULL,
    dedup_key       TEXT NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ,
    error_message   TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0,
    next_retry_at   TIMESTAMPTZ,
    UNIQUE (channel, dedup_key)
);

-- squawk-ignore: require-concurrent-index-creation
CREATE INDEX IF NOT EXISTS idx_inbound_webhooks_pending
    ON inbound_webhooks (channel, received_at)
    WHERE processed_at IS NULL;

-- squawk-ignore: require-concurrent-index-creation
CREATE INDEX IF NOT EXISTS idx_inbound_webhooks_received
    ON inbound_webhooks (received_at DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_inbound_webhooks_received;
DROP INDEX IF EXISTS idx_inbound_webhooks_pending;
DROP TABLE IF EXISTS inbound_webhooks;
