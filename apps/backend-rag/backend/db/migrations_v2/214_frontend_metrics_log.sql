-- ============================================================
-- 214_frontend_metrics_log.sql
-- Ingestion sink for frontend (browser) metrics.
-- Date: 2026-06-05
--
-- The Next.js frontend (apps/mouth/src/lib/metrics.ts) collected metrics
-- in memory but flush() was a 404 no-op because POST /api/metrics/frontend
-- never existed. This table is the durable sink the new router writes to.
-- Best-effort observability: rows are append-only, no PII.
-- ============================================================

CREATE TABLE IF NOT EXISTS frontend_metrics (
    id              BIGSERIAL PRIMARY KEY,
    ts_utc          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metric_name     TEXT NOT NULL,
    metric_value    DOUBLE PRECISION,
    labels          JSONB,
    client_session  TEXT
);

-- Time-window scans (recent metrics dashboards)
CREATE INDEX IF NOT EXISTS ix_frontend_metrics_ts
    ON frontend_metrics (ts_utc DESC);

-- Per-metric aggregation over time
CREATE INDEX IF NOT EXISTS ix_frontend_metrics_name_ts
    ON frontend_metrics (metric_name, ts_utc DESC);

COMMENT ON TABLE frontend_metrics IS 'Browser-side metrics ingested via POST /api/metrics/frontend (apps/mouth metrics.ts flush). Append-only, no PII, best-effort.';

-- === ROLLBACK ===
-- DROP INDEX IF EXISTS ix_frontend_metrics_name_ts;
-- DROP INDEX IF EXISTS ix_frontend_metrics_ts;
-- DROP TABLE IF EXISTS frontend_metrics;
