-- migration 197_wr2_carousel_runs
-- WR2 Autonomous Carousel Workflow — state machine table
-- Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md §3.1
-- Author: Claude Opus 4.7 (orchestrator session 2026-05-27)

CREATE TABLE IF NOT EXISTS wr2_carousel_runs (
    carousel_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic TEXT NOT NULL,
    topic_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'drafted',
        'brief_done',
        'storyboard_done',
        'layout_done',
        'critic_pass',
        'rendered',
        'awaiting_approval',
        'approved',
        'rejected',
        'published',
        'failed_cascade',
        'stale_abandoned'
    )),
    state_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id TEXT NOT NULL,
    cost_total_usd NUMERIC(10, 4) NOT NULL DEFAULT 0,
    retry_count INT NOT NULL DEFAULT 0,
    last_error TEXT,
    output_dir TEXT,
    publish_mode TEXT NOT NULL DEFAULT 'manual' CHECK (publish_mode IN ('manual', 'auto')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_wr2_carousel_topic_hash_active
    ON wr2_carousel_runs(topic_hash)
    WHERE state NOT IN ('published', 'rejected', 'failed_cascade', 'stale_abandoned');

CREATE INDEX IF NOT EXISTS idx_wr2_carousel_stale
    ON wr2_carousel_runs(state_updated_at)
    WHERE state IN (
        'drafted', 'brief_done', 'storyboard_done',
        'layout_done', 'critic_pass', 'rendered'
    );

CREATE INDEX IF NOT EXISTS idx_wr2_carousel_awaiting
    ON wr2_carousel_runs(state_updated_at)
    WHERE state = 'awaiting_approval';

CREATE INDEX IF NOT EXISTS idx_wr2_carousel_state_created
    ON wr2_carousel_runs(state, created_at DESC);

COMMENT ON TABLE wr2_carousel_runs IS
    'WR2 autonomous carousel workflow state machine. Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md';

COMMENT ON COLUMN wr2_carousel_runs.state IS
    'State machine: drafted → brief_done → storyboard_done → layout_done → critic_pass → rendered → awaiting_approval → approved/rejected → published. Terminal: failed_cascade, stale_abandoned';

COMMENT ON COLUMN wr2_carousel_runs.publish_mode IS
    'manual (Day 1 default, Telegram gate human-in-loop) or auto (path codato in standby, flag WR2_AUTO_PUBLISH_ENABLED=false Day 1)';

COMMENT ON COLUMN wr2_carousel_runs.topic_hash IS
    'sha256(topic) — used in unique index to prevent concurrent runs on same topic across non-terminal states';


-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_wr2_carousel_state_created;
DROP INDEX IF EXISTS idx_wr2_carousel_awaiting;
DROP INDEX IF EXISTS idx_wr2_carousel_stale;
DROP INDEX IF EXISTS idx_wr2_carousel_topic_hash_active;
DROP TABLE IF EXISTS wr2_carousel_runs;
