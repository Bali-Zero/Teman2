-- ============================================================
-- 112_rag_traces.sql
-- Persistent RAG trace ledger for stage timing + cost correlation.
-- Date: 2026-04-18
-- Spec: docs/plans/b2b3-briefing.md — PARTE 2 (B3)
--
-- One row per end-to-end RAG query. Nested stages (retrieval, rerank,
-- reasoning, graphrag.*) live in the ``root_span`` JSONB column so
-- percentile queries read a single row per trace; stats_aggregator uses
-- ``jsonb_path_query`` to unnest when needed.
--
-- Separation of concerns: llm_cost_recorder (branch feat/llm-cost-tracking-v1)
-- is the immutable financial ledger; rag_traces is the debugging / perf
-- ledger and MAY be truncated on schedule without regulatory impact.
-- ============================================================

CREATE TABLE IF NOT EXISTS rag_traces (
    trace_id           UUID PRIMARY KEY,
    root_span          JSONB NOT NULL,
    total_duration_ms  INTEGER NOT NULL,
    total_cost_usd     NUMERIC(12, 6) NOT NULL DEFAULT 0,
    total_tokens_in    INTEGER NOT NULL DEFAULT 0,
    total_tokens_out   INTEGER NOT NULL DEFAULT 0,
    domain             TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Percentile / window queries scan by time; index on created_at is
-- the primary access path from stats_aggregator.
CREATE INDEX IF NOT EXISTS ix_rag_traces_created_at
    ON rag_traces (created_at DESC);

-- Secondary filter by domain is common ("top domains by cost").
CREATE INDEX IF NOT EXISTS ix_rag_traces_domain_created
    ON rag_traces (domain, created_at DESC)
    WHERE domain IS NOT NULL;

-- GIN index on root_span enables jsonb_path_query for stage drill-down
-- without scanning the full table.
CREATE INDEX IF NOT EXISTS ix_rag_traces_root_span_gin
    ON rag_traces USING GIN (root_span jsonb_path_ops);

-- === ROLLBACK ===
DROP INDEX IF EXISTS ix_rag_traces_root_span_gin;
DROP INDEX IF EXISTS ix_rag_traces_domain_created;
DROP INDEX IF EXISTS ix_rag_traces_created_at;
DROP TABLE IF EXISTS rag_traces;
