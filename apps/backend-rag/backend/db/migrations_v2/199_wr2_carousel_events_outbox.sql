-- migration 199_wr2_carousel_events_outbox
-- WR2 Carousel Events Outbox — pattern per strategos/learner consumers (DeepSeek STRONG REJECT mitigation)
-- Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md §7
-- Author: Claude Opus 4.7 (orchestrator session 2026-05-27)

CREATE TABLE IF NOT EXISTS wr2_carousel_events_outbox (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'carousel_published',
        'carousel_rejected',
        'carousel_failed',
        'topic_consumed'
    )),
    carousel_id UUID REFERENCES wr2_carousel_runs(carousel_id),
    payload JSONB NOT NULL,
    consumed_by JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    pruned_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_wr2_outbox_unconsumed
    ON wr2_carousel_events_outbox(created_at)
    WHERE pruned_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_wr2_outbox_event_type
    ON wr2_carousel_events_outbox(event_type, created_at DESC)
    WHERE pruned_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_wr2_outbox_carousel
    ON wr2_carousel_events_outbox(carousel_id);

COMMENT ON TABLE wr2_carousel_events_outbox IS
    'WR2 outbox pattern for Cluster C consumers (strategos, learner). Pattern chosen over direct PG NOTIFY per DeepSeek STRONG REJECT (mitigation cascading failures). Consumers poll table, write consumed_by jsonb array for idempotency.';

COMMENT ON COLUMN wr2_carousel_events_outbox.consumed_by IS
    'JSON array of consumer name strings (e.g. ["strategos","learner"]) that have processed this event. Consumers check membership before processing for idempotency.';

COMMENT ON COLUMN wr2_carousel_events_outbox.pruned_at IS
    'Soft-delete marker after retention period (30d default). Hard delete via separate housekeeping cron.';


-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_wr2_outbox_carousel;
DROP INDEX IF EXISTS idx_wr2_outbox_event_type;
DROP INDEX IF EXISTS idx_wr2_outbox_unconsumed;
DROP TABLE IF EXISTS wr2_carousel_events_outbox;
