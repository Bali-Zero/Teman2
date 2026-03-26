-- Migration 041: Workflow Jobs Context
-- Add client_id, practice_id, initiated_by, context_label to workflow_jobs.
-- These columns make job logs useful for support triage and audit.

ALTER TABLE workflow_jobs
    ADD COLUMN IF NOT EXISTS client_id     INTEGER     REFERENCES clients(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS practice_id   INTEGER     REFERENCES practices(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS initiated_by  TEXT,       -- team member email or 'system'
    ADD COLUMN IF NOT EXISTS context_label TEXT;       -- human-readable label, e.g. "intel.review #12"

-- Index for per-client job history
CREATE INDEX IF NOT EXISTS idx_workflow_jobs_client
    ON workflow_jobs (client_id)
    WHERE client_id IS NOT NULL;

-- Index for per-practice job history
CREATE INDEX IF NOT EXISTS idx_workflow_jobs_practice
    ON workflow_jobs (practice_id)
    WHERE practice_id IS NOT NULL;
