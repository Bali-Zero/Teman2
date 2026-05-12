-- Migration 168: Intel Lake schema (Wave 1 of unified intel pipeline)
--
-- Purpose: single source of truth for intel/news/sources from 12+ producers.
-- Wave 1 producer: intel_radar (existing PG `intel_radar_findings` from mig 139).
-- Design doc: research/symbiosis/2026-05-12-intel-lake-design.md
-- Wave 1 plan: research/symbiosis/2026-05-12-intel-lake-wave1-plan.md
--
-- Schema:
--   intel_items        — canonical, one row per canonical_url
--   intel_observations — append-only, one row per producer-hit
--   intel_lake_audit_log — endpoint auth audit trail
--
-- Outbox: trigger emits `intel_lake_event` channel via events_outbox pattern
-- (migration 146). Consumer must register channel in PG_CHANNEL_MAP in
-- backend/services/events/__init__.py.

BEGIN;

-- ─── intel_items ───────────────────────────────────────────────────────────

-- squawk-ignore: require-concurrent-index-creation -- new empty table, no traffic to block
-- squawk-ignore: require-timeout-settings -- migration runner sets statement_timeout globally
CREATE TABLE IF NOT EXISTS intel_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_url   TEXT UNIQUE NOT NULL,
    content_hash    TEXT NOT NULL,
    title           TEXT NOT NULL,
    summary         TEXT,
    source_domain   TEXT NOT NULL,
    language        TEXT,
    jurisdiction    TEXT,
    topic_tags      TEXT[] NOT NULL DEFAULT '{}',
    routing_status  TEXT NOT NULL DEFAULT 'unrouted'
        CHECK (routing_status IN ('unrouted','blog','wr2','nb-intel','archive','skip','needs_review')),
    routing_targets JSONB NOT NULL DEFAULT '{}',
    confidence_score REAL CHECK (confidence_score IS NULL OR (0 <= confidence_score AND confidence_score <= 1)),
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    raw_payload     JSONB NOT NULL DEFAULT '{}'
);

-- squawk-ignore: require-concurrent-index-creation -- new table
CREATE INDEX IF NOT EXISTS idx_intel_items_unrouted
    ON intel_items(first_seen_at DESC) WHERE routing_status = 'unrouted';
-- squawk-ignore: require-concurrent-index-creation -- new table
CREATE INDEX IF NOT EXISTS idx_intel_items_routed_recent
    ON intel_items(last_seen_at DESC) WHERE routing_status IN ('blog','wr2','nb-intel');
-- squawk-ignore: require-concurrent-index-creation -- new table
CREATE INDEX IF NOT EXISTS idx_intel_items_tags
    ON intel_items USING GIN(topic_tags);
-- squawk-ignore: require-concurrent-index-creation -- new table
CREATE INDEX IF NOT EXISTS idx_intel_items_content_hash
    ON intel_items(content_hash);

COMMENT ON TABLE intel_items IS
'Intel Lake canonical items (Wave 1, 2026-05-12). Single source of truth across 12+ producers.';
COMMENT ON COLUMN intel_items.routing_status IS
'unrouted=awaiting router; blog/wr2/nb-intel=routed; archive=cold; skip=not relevant; needs_review=LLM tier-2 queue';
COMMENT ON COLUMN intel_items.routing_targets IS
'JSONB {nb_uuids:[], blog_slug:"", wr2_draft_id:"", telegram_chat:""}. Populated by router after Tier 1 rules or Tier 2 LLM.';

-- ─── intel_observations ────────────────────────────────────────────────────

-- squawk-ignore: require-concurrent-index-creation -- new empty table
-- squawk-ignore: require-timeout-settings -- migration runner sets statement_timeout
CREATE TABLE IF NOT EXISTS intel_observations (
    id              BIGSERIAL PRIMARY KEY,
    item_id         UUID NOT NULL REFERENCES intel_items(id) ON DELETE CASCADE,
    producer_name   TEXT NOT NULL,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload     JSONB NOT NULL DEFAULT '{}',
    score           REAL
);

-- squawk-ignore: require-concurrent-index-creation -- new table
CREATE INDEX IF NOT EXISTS idx_intel_obs_item ON intel_observations(item_id);
-- squawk-ignore: require-concurrent-index-creation -- new table
CREATE INDEX IF NOT EXISTS idx_intel_obs_producer_recent
    ON intel_observations(producer_name, observed_at DESC);

COMMENT ON TABLE intel_observations IS
'Append-only producer-hit log. 4 producers see same URL → 1 intel_items + 4 intel_observations rows. Trust signal = COUNT(observations) per item.';

-- ─── intel_lake_audit_log ──────────────────────────────────────────────────

-- squawk-ignore: require-concurrent-index-creation -- new empty table
-- squawk-ignore: require-timeout-settings -- migration runner sets statement_timeout
CREATE TABLE IF NOT EXISTS intel_lake_audit_log (
    id           BIGSERIAL PRIMARY KEY,
    producer_name TEXT NOT NULL,
    client_ip    TEXT,
    request_path TEXT NOT NULL,
    status_code  INTEGER NOT NULL,
    payload_size INTEGER,
    error_message TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- squawk-ignore: require-concurrent-index-creation -- new table
CREATE INDEX IF NOT EXISTS idx_audit_recent ON intel_lake_audit_log(created_at DESC);
-- squawk-ignore: require-concurrent-index-creation -- new table
CREATE INDEX IF NOT EXISTS idx_audit_failed ON intel_lake_audit_log(producer_name, created_at DESC)
    WHERE status_code >= 400;

COMMENT ON TABLE intel_lake_audit_log IS
'Endpoint auth audit. Tracks every POST /api/intel/lake/observations with producer, IP, status.';

-- ─── Outbox trigger (reuses migration 146 pattern) ─────────────────────────

CREATE OR REPLACE FUNCTION notify_intel_lake_event()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    outbox_id BIGINT;
    payload JSONB;
BEGIN
    -- Only emit on INSERT (new item). Updates (last_seen_at refresh) don't fire.
    IF (TG_OP = 'INSERT') THEN
        payload := jsonb_build_object(
            'item_id', NEW.id,
            'canonical_url', NEW.canonical_url,
            'source_domain', NEW.source_domain,
            'topic_tags', NEW.topic_tags,
            'routing_status', NEW.routing_status,
            'first_seen_at', NEW.first_seen_at
        );

        INSERT INTO events_outbox (channel, payload)
        VALUES ('intel_lake_event', payload)
        RETURNING id INTO outbox_id;

        PERFORM pg_notify(
            'intel_lake_event',
            (payload || jsonb_build_object('_outbox_id', outbox_id))::text
        );
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_notify_intel_lake_event ON intel_items;
CREATE TRIGGER trg_notify_intel_lake_event
    AFTER INSERT ON intel_items
    FOR EACH ROW
    EXECUTE FUNCTION notify_intel_lake_event();

COMMENT ON FUNCTION notify_intel_lake_event IS
'Wave 1 (mig 168): emits intel_lake_event channel via events_outbox pattern (mig 146). Only on INSERT. Listener must be registered in PG_CHANNEL_MAP.';

COMMIT;

-- === ROLLBACK ===
-- Reverses migration 168. Drops trigger first, then function, then tables in
-- FK-correct order. intel_items references nothing; intel_observations FK to
-- intel_items; intel_lake_audit_log standalone.

BEGIN;
DROP TRIGGER IF EXISTS trg_notify_intel_lake_event ON intel_items;
DROP FUNCTION IF EXISTS notify_intel_lake_event();
DROP TABLE IF EXISTS intel_observations;
DROP TABLE IF EXISTS intel_lake_audit_log;
DROP TABLE IF EXISTS intel_items;
COMMIT;
