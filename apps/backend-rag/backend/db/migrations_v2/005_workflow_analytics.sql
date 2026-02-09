-- Migration 005: Workflow Analytics Table
-- Tracks LangGraph workflow generation and user feedback:
--   - Which workflows were generated for which queries?
--   - Did the user follow the suggested workflow?
--   - What feedback score did the workflow receive?
--   - Which workflow types are most useful?

CREATE TABLE IF NOT EXISTS workflow_analytics (
    id BIGSERIAL PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    query TEXT NOT NULL,
    user_email TEXT,
    workflow_type TEXT,
    workflow_name TEXT,
    steps_count INTEGER DEFAULT 0,
    steps_json JSONB,
    source TEXT DEFAULT 'kg_langgraph',
    confidence FLOAT DEFAULT 0.0,
    followed BOOLEAN NOT NULL DEFAULT FALSE,
    feedback_score FLOAT,
    feedback_comment TEXT,
    execution_time_ms INTEGER,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Primary lookup by workflow_id
CREATE INDEX IF NOT EXISTS idx_workflow_analytics_id
    ON workflow_analytics(workflow_id);

-- Dashboard: time-series queries
CREATE INDEX IF NOT EXISTS idx_workflow_analytics_timestamp
    ON workflow_analytics(timestamp DESC);

-- Filter by user
CREATE INDEX IF NOT EXISTS idx_workflow_analytics_user
    ON workflow_analytics(user_email)
    WHERE user_email IS NOT NULL;

-- Filter workflows with feedback (partial index)
CREATE INDEX IF NOT EXISTS idx_workflow_analytics_feedback
    ON workflow_analytics(feedback_score)
    WHERE feedback_score IS NOT NULL;

-- Filter by workflow type for aggregation
CREATE INDEX IF NOT EXISTS idx_workflow_analytics_type
    ON workflow_analytics(workflow_type)
    WHERE workflow_type IS NOT NULL;
