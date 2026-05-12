-- Migration 169: CRM Workspace AI snapshots
--
-- Stores human-reviewed facts produced from Workspace-native AI workflows
-- such as NotebookLM/Gemini over Google Drive evidence. Draft rows are intake
-- only; product surfaces must read approved rows.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS crm_workspace_ai_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id BIGINT REFERENCES companies(id) ON DELETE SET NULL,
    client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL,
    company_name TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (provider IN ('notebooklm', 'gemini', 'manual')),
    notebook_id TEXT,
    note_id TEXT,
    source_file_ids TEXT[] NOT NULL DEFAULT '{}',
    facts JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected')),
    created_by TEXT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        status <> 'approved'
        OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_crm_workspace_ai_snapshots_company_status
    ON crm_workspace_ai_snapshots (company_id, status, approved_at DESC);

CREATE INDEX IF NOT EXISTS idx_crm_workspace_ai_snapshots_client_status
    ON crm_workspace_ai_snapshots (client_id, status, approved_at DESC);

CREATE INDEX IF NOT EXISTS idx_crm_workspace_ai_snapshots_facts
    ON crm_workspace_ai_snapshots USING GIN (facts);

-- === ROLLBACK ===

DROP INDEX IF EXISTS idx_crm_workspace_ai_snapshots_facts;
DROP INDEX IF EXISTS idx_crm_workspace_ai_snapshots_client_status;
DROP INDEX IF EXISTS idx_crm_workspace_ai_snapshots_company_status;
DROP TABLE IF EXISTS crm_workspace_ai_snapshots;
