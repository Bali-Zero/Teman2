-- Migration 242: conversation_messages.metadata — string-scalar → object backfill.
--
-- Root cause (2026-07-13, live-probe finding): the app pools register a jsonb
-- type codec whose encoder is json.dumps (backend/app/core/database.py:30,
-- service_initializer.py:507). Every writer of conversation_messages passed an
-- ALREADY-serialized json.dumps(...) string, so the codec dumped it a second
-- time and the value landed as a jsonb STRING SCALAR, not an object. All 418
-- historical rows (322 instagram inbound, 19 outbound, 77 whatsapp) are
-- string-typed: `metadata->>'session_id'` returns NULL on every one of them,
-- which blinds the session-context reader (conversation/engine.py:279) and any
-- other SQL-side consumer.
--
-- The writers are fixed in the same PR ($N::text::jsonb — param typed text,
-- server parses to object; proven empirically against the registered codec).
-- This migration repairs the existing rows. Idempotent: converted rows are
-- typeof 'object' and no longer match the WHERE.
--
-- The guard on left(...) keeps the cast from ever seeing a non-JSON string;
-- rows written by the known writers are all json.dumps output, so in practice
-- every string row converts.
--
-- On the Pro apply manually like 212-241:
--   psql postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev \
--     -f apps/backend-rag/backend/db/migrations_v2/242_conversation_messages_metadata_object_backfill.sql
-- === FORWARD ===

UPDATE conversation_messages
SET metadata = (metadata #>> '{}')::jsonb
WHERE jsonb_typeof(metadata) = 'string'
  AND left(ltrim(metadata #>> '{}'), 1) IN ('{', '[');

-- === ROLLBACK ===
-- Intentionally none: re-double-encoding object rows back into string scalars
-- would re-blind every jsonb-path reader. Forward-only data repair.
