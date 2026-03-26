-- Migration 039: workflow_jobs table for resumable MCP workflow chains
-- Pattern: SKIP LOCKED + visibility_at timeout (no Redis/Celery needed)
-- Designed for Fly.io auto_stop: jobs survive machine death via visibility timeout

CREATE TABLE IF NOT EXISTS workflow_jobs (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    chain_id     TEXT        NOT NULL,
    thread_id    TEXT,                                            -- LangGraph thread_id for resume
    status       TEXT        NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'in_progress', 'done', 'failed')),
    payload      JSONB       DEFAULT '{}',
    visible_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),              -- heartbeat/visibility timeout
    retry_count  INT         NOT NULL DEFAULT 0,
    max_retries  INT         NOT NULL DEFAULT 3,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_msg    TEXT
);

-- Index for the dequeue query: status=pending AND visible_at <= NOW()
CREATE INDEX IF NOT EXISTS idx_workflow_jobs_dequeue
    ON workflow_jobs (status, visible_at)
    WHERE status IN ('pending', 'in_progress');

-- Index for thread_id lookups (LangGraph resume)
CREATE INDEX IF NOT EXISTS idx_workflow_jobs_thread_id
    ON workflow_jobs (thread_id)
    WHERE thread_id IS NOT NULL;

-- auto-update updated_at
CREATE OR REPLACE FUNCTION workflow_jobs_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS workflow_jobs_updated_at ON workflow_jobs;
CREATE TRIGGER workflow_jobs_updated_at
    BEFORE UPDATE ON workflow_jobs
    FOR EACH ROW EXECUTE FUNCTION workflow_jobs_set_updated_at();
