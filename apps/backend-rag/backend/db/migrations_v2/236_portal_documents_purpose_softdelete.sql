-- Migration 236: portal documents — purpose statement + soft-delete with recovery.
--
-- FASE 5 (trust UX, two low-risk levers from the my.balizero.com client-ready
-- blueprint research/operations/2026-06-21-my-balizero-portal-client-ready-design.md):
--
--   * document_purpose (TEXT, client-facing "why we hold this document"): distinct
--     from the existing `notes` column, which is internal team scratch. Surfaced to
--     the client in the vault so they understand what each file is FOR — a GDPR-style
--     purpose statement that builds trust. NULL = no purpose stated (legacy rows).
--
--   * Soft-delete with recovery (deleted_at + deleted_by): a client delete becomes a
--     recoverable trash, NOT a hard DELETE. Distinct from the existing `is_archived`
--     flag (archive = team lifecycle; delete = client intent to remove). The vault
--     list query filters `deleted_at IS NULL`; a restore endpoint clears it. Rows are
--     never physically removed here — recovery stays possible until a separate purge
--     policy (out of scope) reaps them.
--
-- Pure additive: three nullable columns, no constraint change, no row rewrite — every
-- existing row keeps deleted_at=NULL (visible) and document_purpose=NULL.
--
-- On the Pro apply manually like 212-235:
--   psql postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev \
--     -f apps/backend-rag/backend/db/migrations_v2/236_portal_documents_purpose_softdelete.sql

-- === FORWARD ===

ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_purpose TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS deleted_by VARCHAR(255);

-- Partial index: the vault list query is always `WHERE client_id = $1 AND
-- deleted_at IS NULL`, so index the live rows per client. Partial keeps it small
-- (trash rows excluded) and serves the hot path.
CREATE INDEX IF NOT EXISTS idx_documents_client_live
    ON documents (client_id)
    WHERE deleted_at IS NULL;

COMMENT ON COLUMN documents.document_purpose IS
    'Client-facing purpose statement ("why we hold this document"). Distinct from notes (internal). FASE 5 trust UX, migration 236.';
COMMENT ON COLUMN documents.deleted_at IS
    'Soft-delete timestamp. NULL = live. Set by a client delete; cleared by restore. Distinct from is_archived (team lifecycle). FASE 5, migration 236.';
COMMENT ON COLUMN documents.deleted_by IS
    'Who soft-deleted (client email or impersonating superuser). Audit for the trash/recovery flow. FASE 5, migration 236.';

-- === ROLLBACK ===
-- (Safe: additive columns, no data depends on them outside FASE 5 code paths.)
-- DROP INDEX IF EXISTS idx_documents_client_live;
-- ALTER TABLE documents DROP COLUMN IF EXISTS deleted_by;
-- ALTER TABLE documents DROP COLUMN IF EXISTS deleted_at;
-- ALTER TABLE documents DROP COLUMN IF EXISTS document_purpose;
