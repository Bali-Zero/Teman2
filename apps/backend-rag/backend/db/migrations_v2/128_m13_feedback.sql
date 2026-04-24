-- ============================================================
-- 128_m13_feedback.sql
-- M13 Measurer feedback loop — store post metrics time series
-- and retrain decision log.
-- Date: 2026-04-22
-- Spec: docs/superpowers/specs/2026-04-22-bali-zero-social-sota-research-design.md
-- ============================================================

-- Bootstrap war_room_drafts + war_room_posts if CI schema missing (prod has via m112)
CREATE TABLE IF NOT EXISTS war_room_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic TEXT NOT NULL,
    tone_register TEXT,
    status TEXT NOT NULL DEFAULT 'briefed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS war_room_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id UUID NOT NULL,
    platform TEXT NOT NULL,
    post_external_id TEXT,
    post_url TEXT,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Post metrics history (6h granularity, append-only)
CREATE TABLE IF NOT EXISTS post_metrics_history (
    id BIGSERIAL PRIMARY KEY,
    post_id UUID NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    horizon_hours INT NOT NULL CHECK (horizon_hours IN (24, 72, 168)),
    metric_name TEXT NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('ig_graph', 'linkedin', 'tiktok', 'ga4', 'computed'))
);

CREATE INDEX IF NOT EXISTS ix_post_metrics_history_post_horizon
    ON post_metrics_history (post_id, horizon_hours, collected_at DESC);

-- Retrain log — append-only audit of every weights update
CREATE TABLE IF NOT EXISTS m13_retrain_log (
    id BIGSERIAL PRIMARY KEY,
    retrained_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('weekly', 'monthly', 'threshold_breach', 'manual')),
    delta_pct DOUBLE PRECISION,
    weights_before_json JSONB NOT NULL,
    weights_after_json JSONB NOT NULL,
    reason TEXT
);

-- === ROLLBACK ===
DROP TABLE IF EXISTS m13_retrain_log;
DROP INDEX IF EXISTS ix_post_metrics_history_post_horizon;
DROP TABLE IF EXISTS post_metrics_history;
-- keep war_room_drafts / war_room_posts (produced by m127 or m112)
