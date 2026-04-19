-- ============================================================
-- 117_llm_cost_events.sql
-- Indestructible cost ledger for every LLM call (triple-write sink).
-- Date: 2026-04-20
--
-- Every LLM call in the system (backend + Pro/Air cron agents) appends
-- one row here. Used for:
--   - Per-endpoint cost attribution (which feature is burning budget).
--   - Per-model / per-provider rollups.
--   - Alerting when hourly spend crosses a threshold.
--   - Reconciliation with provider invoices.
--
-- Persistence strategy (defense in depth) — see
-- backend/services/observability/llm_cost_recorder.py:
--   1. Prometheus counters (real-time dashboards).
--   2. This Postgres table (audit + aggregations).
--   3. Append-only JSONL on the /data volume (last-resort).
--
-- NOTE: a Python version of this migration exists at
-- backend/migrations/migration_117_llm_cost_events.py but the Fly
-- migration runner (backend/db/migrate.py) only scans this directory,
-- so the Python file is effectively dead. This SQL file is the
-- canonical source — see the hotfix PR (fix/llm-cost-migrations-sql-v2).
-- ============================================================

CREATE TABLE IF NOT EXISTS llm_cost_events (
    id               BIGSERIAL PRIMARY KEY,
    ts_utc           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    provider         VARCHAR(32) NOT NULL,
    model            VARCHAR(128) NOT NULL,
    input_tokens     INT NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens    INT NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    cache_hit_tokens INT NOT NULL DEFAULT 0 CHECK (cache_hit_tokens >= 0),
    cost_usd         NUMERIC(12, 6) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
    endpoint         VARCHAR(128),
    request_id       VARCHAR(64),
    success          BOOLEAN NOT NULL,
    error_class      VARCHAR(64),
    latency_ms       INT NOT NULL DEFAULT 0 CHECK (latency_ms >= 0)
);

CREATE INDEX IF NOT EXISTS idx_llm_cost_ts
    ON llm_cost_events (ts_utc DESC);

CREATE INDEX IF NOT EXISTS idx_llm_cost_endpoint_ts
    ON llm_cost_events (endpoint, ts_utc DESC)
    WHERE endpoint IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_llm_cost_model_ts
    ON llm_cost_events (model, ts_utc DESC);

CREATE INDEX IF NOT EXISTS idx_llm_cost_provider_ts
    ON llm_cost_events (provider, ts_utc DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_llm_cost_provider_ts;
DROP INDEX IF EXISTS idx_llm_cost_model_ts;
DROP INDEX IF EXISTS idx_llm_cost_endpoint_ts;
DROP INDEX IF EXISTS idx_llm_cost_ts;
DROP TABLE IF EXISTS llm_cost_events;
