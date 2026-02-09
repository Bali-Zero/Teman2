-- Migration 004: Query Analytics – Extend existing table for dashboard
--
-- The query_analytics table already exists in production with columns:
--   id, user_id, query_hash, query_text, response_text, language_preference,
--   model_used, response_time_ms, document_count, user_satisfaction,
--   session_id, metadata, created_at
--
-- This migration adds the columns needed by the analytics dashboard:
--   collections_queried, chunks_retrieved_count, response_generated,
--   execution_time_ms, token_usage_total, cost_usd, user_feedback,
--   feedback_comment, error_message
--
-- Existing data is preserved. Old columns remain for backward compatibility.

-- New columns for dashboard analytics
ALTER TABLE query_analytics ADD COLUMN IF NOT EXISTS collections_queried TEXT[] DEFAULT '{}';
ALTER TABLE query_analytics ADD COLUMN IF NOT EXISTS chunks_retrieved_count INTEGER DEFAULT 0;
ALTER TABLE query_analytics ADD COLUMN IF NOT EXISTS response_generated BOOLEAN DEFAULT FALSE;
ALTER TABLE query_analytics ADD COLUMN IF NOT EXISTS execution_time_ms INTEGER;
ALTER TABLE query_analytics ADD COLUMN IF NOT EXISTS token_usage_total INTEGER DEFAULT 0;
ALTER TABLE query_analytics ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10, 6) DEFAULT 0;
ALTER TABLE query_analytics ADD COLUMN IF NOT EXISTS user_feedback VARCHAR(20);
ALTER TABLE query_analytics ADD COLUMN IF NOT EXISTS feedback_comment TEXT;
ALTER TABLE query_analytics ADD COLUMN IF NOT EXISTS error_message TEXT;

-- Backfill: map existing document_count → chunks_retrieved_count for old rows
UPDATE query_analytics
SET chunks_retrieved_count = COALESCE(document_count, 0)
WHERE chunks_retrieved_count = 0 AND document_count IS NOT NULL AND document_count > 0;

-- Backfill: map existing response_time_ms → execution_time_ms for old rows
UPDATE query_analytics
SET execution_time_ms = response_time_ms
WHERE execution_time_ms IS NULL AND response_time_ms IS NOT NULL;

-- Backfill: mark old rows with documents as response_generated = true
UPDATE query_analytics
SET response_generated = TRUE
WHERE response_generated = FALSE AND document_count IS NOT NULL AND document_count > 0;

-- Indexes for dashboard queries
CREATE INDEX IF NOT EXISTS idx_query_analytics_created_at
    ON query_analytics (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_query_analytics_user_id
    ON query_analytics (user_id);

CREATE INDEX IF NOT EXISTS idx_query_analytics_session_id
    ON query_analytics (session_id);

CREATE INDEX IF NOT EXISTS idx_query_analytics_chunks_zero
    ON query_analytics (chunks_retrieved_count)
    WHERE chunks_retrieved_count = 0;

CREATE INDEX IF NOT EXISTS idx_query_analytics_feedback
    ON query_analytics (user_feedback)
    WHERE user_feedback IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_query_analytics_collections
    ON query_analytics USING GIN (collections_queried);
