-- ============================================================
-- 119_llm_cost_recommendations.sql
-- CostAdvisor output table — weekly cheaper-model suggestions.
-- Date: 2026-04-20
--
-- One row per (endpoint, current_model, proposed_model) triple produced
-- by the weekly CostAdvisor agent (see
-- backend/services/observability/cost_advisor.py). Status flow:
--   pending → reviewed → applied | rejected
-- 7-day dedup window is enforced at the Python layer
-- (CostAdvisor.persist_recommendations, WHERE NOT EXISTS).
--
-- Note: 118 was taken by 118_clients_referrer_url (SEO cell). This
-- migration uses 119 to avoid collision. The Python peer at
-- backend/migrations/migration_119_cost_recommendations.py is
-- effectively dead because the Fly runner only scans migrations_v2/;
-- this SQL file is the canonical source.
-- ============================================================

CREATE TABLE IF NOT EXISTS llm_cost_recommendations (
    id                           BIGSERIAL PRIMARY KEY,
    ts_utc                       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    endpoint                     VARCHAR(128) NOT NULL,
    current_model                VARCHAR(128) NOT NULL,
    proposed_model               VARCHAR(128) NOT NULL,
    estimated_monthly_saving_usd NUMERIC(12, 6) NOT NULL,
    quality_tradeoff             TEXT NOT NULL,
    confidence                   VARCHAR(16) NOT NULL
        CHECK (confidence IN ('low','medium','high')),
    spike_flag                   BOOLEAN NOT NULL DEFAULT FALSE,
    status                       VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','reviewed','applied','rejected')),
    reviewed_at                  TIMESTAMP WITH TIME ZONE,
    reviewed_by                  VARCHAR(128),
    notes                        TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_cost_reco_status_ts
    ON llm_cost_recommendations (status, ts_utc DESC);

CREATE INDEX IF NOT EXISTS idx_llm_cost_reco_endpoint
    ON llm_cost_recommendations (endpoint, ts_utc DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_llm_cost_reco_endpoint;
DROP INDEX IF EXISTS idx_llm_cost_reco_status_ts;
DROP TABLE IF EXISTS llm_cost_recommendations CASCADE;
