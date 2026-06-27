-- Migration 240: intake_queue.source_context — PII-safe transport provenance.
--
-- `stage_output` belongs to the OCR/classify/extract/validate/route pipeline and
-- is deliberately reset when a document is reprocessed. Transport provenance is
-- different: a WA mirror file must keep whether it came from a direct chat or a
-- group chat, and which identity policy was applied, across reprocesses.
--
-- This column is intentionally JSONB, but the contract is conservative:
--   - no raw phone numbers beyond existing intake_queue.sender_phone;
--   - no raw group JID;
--   - no raw group subject, because subjects can contain client/team names;
--   - hashes/booleans/policy labels only.
--
-- On the Pro apply manually like 212-239:
--   psql postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev \
--     -f apps/backend-rag/backend/db/migrations_v2/240_intake_queue_source_context.sql
-- === FORWARD ===

ALTER TABLE intake_queue
    ADD COLUMN IF NOT EXISTS source_context JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN intake_queue.source_context IS
    'PII-safe source provenance and routing policy context (migration 240), e.g. WA mirror direct/group scope. No raw group JID/subject/extra phone data.';

CREATE INDEX IF NOT EXISTS idx_iq_source_context_chat_type
    ON intake_queue ((source_context->>'chat_type'))
    WHERE source_context <> '{}'::jsonb;

-- === ROLLBACK ===
-- DROP INDEX IF EXISTS idx_iq_source_context_chat_type;
-- ALTER TABLE intake_queue DROP COLUMN IF EXISTS source_context;
