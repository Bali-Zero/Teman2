-- 217_intake_commit_audit.sql — FASE 5B/5C CRM-writer audit + idempotency (DDL, no data)
-- Adds the two persistence primitives the document-intake CRM writer needs:
--   1. intake_commit_audit            — forensic trace of EVERY commit attempt
--                                        (committed / dry_run / failed / rolled_back).
--   2. documents.intake_idempotency_key + intake_proposal_id
--                                      — intake-instance idempotency key (P0#1) so a
--                                        re-commit of the SAME proposal is a no-op and
--                                        the same physical blob attached to TWO different
--                                        clients does NOT collide.
--
-- Panel 4-LLM P0 incorporated (06-fase5-hitl-writer-design 8):
--   * P0#1 idempotency_key is INTAKE-INSTANCE based, NOT content based. The UNIQUE
--     constraint is on (client_id, intake_idempotency_key) — NEVER global on content.
--   * P0#9 / 6b dry-run: the writer in 5B logs a row here with dry_run=true and writes
--     NOTHING to documents/practices, and never advances proposal/queue to a terminal state.
--
-- READ-ONLY w.r.t. the CRM in 5B: the new \`documents\` columns are only WRITTEN by the
-- real (5C) commit path, gated by INTAKE_WRITER_ENABLED (default OFF).
-- DDL-vs-DATA boundary (Law 2 / UU-PDP): this migration is SCHEMA ONLY — an empty
-- `intake_commit_audit` table + two nullable `documents` columns. The numbered-migration
-- runner (migration_manager.discover_migrations) applies every migrations_v2/*.sql by
-- number on EVERY DB it runs against (local AND Fly), so this schema IS present on Fly —
-- a `-- comment` cannot gate the runner. That is fine: zero PII is written by the schema.
-- What is PII-local-only is the DATA: the 5C writer (gated by INTAKE_WRITER_ENABLED,
-- default OFF) must only ever write rows here against nuzantara_dev @127.0.0.1, never Fly.
-- (Earlier header said "MAI applicare su Fly" — that was wrong about the DDL; corrected
--  2026-06-06 after empirical verify that 217 is in _schema_versions on Fly, table empty.)
-- === FORWARD ===

-- A. Idempotency + provenance columns on documents (nullable: legacy rows untouched).
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS intake_idempotency_key TEXT,
    ADD COLUMN IF NOT EXISTS intake_proposal_id     BIGINT;

-- P0#1: UNIQUE per-(client, key), NEVER global on content. NULL key (legacy) is exempt.
CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_intake_key
    ON documents (client_id, intake_idempotency_key)
    WHERE intake_idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_documents_intake_proposal
    ON documents (intake_proposal_id)
    WHERE intake_proposal_id IS NOT NULL;

COMMENT ON COLUMN documents.intake_idempotency_key IS
    'Intake-instance idempotency key (P0#1): sha256(source|source_ref|blob_hash|doc_index|pipeline_version). UNIQUE per (client_id, key) — NEVER global on content. Re-commit = no-op.';
COMMENT ON COLUMN documents.intake_proposal_id IS
    'document_routing_proposal.id that produced this attachment (forensic link to the HITL decision).';

-- B. Commit audit (append-only forensic trace) — 6d.
CREATE TABLE IF NOT EXISTS intake_commit_audit (
    id              BIGSERIAL PRIMARY KEY,
    proposal_id     BIGINT      NOT NULL REFERENCES document_routing_proposal(id) ON DELETE CASCADE,
    queue_id        BIGINT      REFERENCES intake_queue(id) ON DELETE SET NULL,
    client_id       BIGINT,
    doc_id          BIGINT,
    practice_id     BIGINT,
    decision        VARCHAR(20),
    committed_by    TEXT        NOT NULL,
    dry_run         BOOLEAN     NOT NULL DEFAULT true,
    outcome         VARCHAR(16) NOT NULL,
    idempotency_key TEXT,
    plan            JSONB       NOT NULL DEFAULT '{}'::jsonb,
    error           TEXT,
    committed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_ica_outcome CHECK (outcome IN ('committed','dry_run','blocked','failed','rolled_back')),
    CONSTRAINT chk_ica_decision CHECK (decision IS NULL OR decision IN ('AUTO_ATTACH','LINK_CANDIDATE','AMBIGUOUS','NO_MATCH'))
);
CREATE INDEX IF NOT EXISTS idx_ica_proposal  ON intake_commit_audit (proposal_id, committed_at);
CREATE INDEX IF NOT EXISTS idx_ica_outcome   ON intake_commit_audit (outcome, committed_at);
CREATE INDEX IF NOT EXISTS idx_ica_client    ON intake_commit_audit (client_id) WHERE client_id IS NOT NULL;

COMMENT ON TABLE intake_commit_audit IS
    'Forensic trace of every document-intake CRM commit ATTEMPT. In FASE 5B (INTAKE_WRITER_ENABLED=OFF) the ONLY effect of an approve is one dry_run row here. PII local-only (Law 2).';

-- === ROLLBACK ===
-- DROP TABLE IF EXISTS intake_commit_audit CASCADE;
-- DROP INDEX IF EXISTS idx_documents_intake_proposal;
-- DROP INDEX IF EXISTS uq_documents_intake_key;
-- ALTER TABLE documents DROP COLUMN IF EXISTS intake_proposal_id, DROP COLUMN IF EXISTS intake_idempotency_key;
