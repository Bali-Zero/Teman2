-- migration 203_wr2_orchestrator_metrics
-- WR2 Orchestrator Metrics — per-step observability (Law 7 numbers first)
-- Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md §5
-- NOTE: spec mentioned "migration 200" but 200/201/202 already used (wa_copilot + crm_guardian). Bumped to 203.
-- Author: Claude Opus 4.7 (orchestrator session 2026-05-27)

CREATE TABLE IF NOT EXISTS wr2_orchestrator_metrics (
    id BIGSERIAL PRIMARY KEY,
    carousel_id UUID NOT NULL REFERENCES wr2_carousel_runs(carousel_id),
    step_name TEXT NOT NULL CHECK (step_name IN (
        'brief_interpreter',
        'storyboarder',
        'image_prompt_author',
        'layout_composer',
        'critic',
        'playwright_render',
        'telegram_gate',
        'ig_publisher'
    )),
    step_index INT NOT NULL,
    model TEXT,
    tier INT NOT NULL DEFAULT 1 CHECK (tier IN (1, 2, 3, 4)),
    latency_ms BIGINT,
    tokens_in INT,
    tokens_out INT,
    cost_usd_figurative NUMERIC(10, 6) NOT NULL DEFAULT 0,
    retry_count INT NOT NULL DEFAULT 0,
    success BOOLEAN NOT NULL,
    error_class TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wr2_metrics_carousel
    ON wr2_orchestrator_metrics(carousel_id, step_index);

CREATE INDEX IF NOT EXISTS idx_wr2_metrics_step_created
    ON wr2_orchestrator_metrics(step_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wr2_metrics_tier_created
    ON wr2_orchestrator_metrics(tier, created_at DESC)
    WHERE tier > 1;

CREATE INDEX IF NOT EXISTS idx_wr2_metrics_errors
    ON wr2_orchestrator_metrics(error_class, created_at DESC)
    WHERE success = false;

COMMENT ON TABLE wr2_orchestrator_metrics IS
    'WR2 per-step observability. Cost USD is figurative for AUDIT (detect runaway), NOT real spend — Claude OAuth MAX quota is flat. Real throttle metric in spec §11.';

COMMENT ON COLUMN wr2_orchestrator_metrics.tier IS
    '1=Claude OAuth MAX (default), 2=Gemini agy fallback, 3=DeepSeek V4 Pro, 4=Ollama local. Tier >1 indicates cascade kicked in (usage_5h > 90% or quota_exhausted).';

COMMENT ON COLUMN wr2_orchestrator_metrics.cost_usd_figurative IS
    'Figurative cost per Anthropic 2026 pricing (input $15/Mtok opus, cache_read $1.50/Mtok). Used for audit thresholds (>$5/run WARNING). NOT actual spend (OAuth MAX flat quota).';


-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_wr2_metrics_errors;
DROP INDEX IF EXISTS idx_wr2_metrics_tier_created;
DROP INDEX IF EXISTS idx_wr2_metrics_step_created;
DROP INDEX IF EXISTS idx_wr2_metrics_carousel;
DROP TABLE IF EXISTS wr2_orchestrator_metrics;
