-- Migration 225: intake_queue.sender_phone — WHO SENT the document (entity signal).
--
-- Intake catalog v2. Today 64+/121 review_pending proposals are doc_type=unknown
-- and/or entity NO_MATCH because routing can only match on what OCR extracted
-- from the page. But the transport layer ALREADY knows who sent the blob:
-- wa-mirror records ``whatsapp_message_context.sender_phone`` and the live Meta
-- webhook carries ``messages[].from``. Persisting it on the queue row lets
-- FASE-4 routing exact-match against ``clients.phone_normalized`` (a
-- high-confidence ~0.90 signal — phones can be shared by spouse/agent, so it
-- ranks BELOW strong document identifiers and never auto-attaches alone).
--
-- Pure additive nullable column. No backfill here: the retroactive script
-- (scripts/intake_reprocess_backlog.py) re-enqueues historical rows with the
-- phone populated. NULL stays valid for drive/zoho/export sources (no sender).
--
-- On the Pro apply manually like 212-224:
--   psql postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev \
--     -f apps/backend-rag/backend/db/migrations_v2/225_intake_queue_sender_phone.sql
-- === FORWARD ===

ALTER TABLE intake_queue
    ADD COLUMN IF NOT EXISTS sender_phone TEXT;

COMMENT ON COLUMN intake_queue.sender_phone IS
    'Raw sender phone from the transport layer (wa-mirror sender_phone / Meta messages[].from). Normalized at match time against clients.phone_normalized (migration 225). NULL for sources without a sender (drive/zoho).';

-- === ROLLBACK ===
-- ALTER TABLE intake_queue DROP COLUMN IF EXISTS sender_phone;
