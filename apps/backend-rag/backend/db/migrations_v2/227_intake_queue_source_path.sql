-- Migration 227: intake_queue.source_path — WHERE the blob came from (entity signal).
--
-- Drive-intake wiring (smistamento CRM). The Dropbox→Drive copy job mirrors the
-- Dropbox folder structure under Drive/Dropbox-Intake/, and those folders are
-- named after clients/practices ("BUDI SANTOSO", "Jane Doe", ...). The transport
-- layer therefore KNOWS the likely subject of every blob — exactly like m225's
-- sender_phone knows who sent a WhatsApp document. Persisting the path relative
-- to the watched root ("<Client Name>/passport.jpg") lets FASE-4 routing
-- fuzzy-match the first segment against clients.full_name / companies.
-- company_name (a ~0.85 signal — folders are human-typed and can hold a whole
-- family's documents, so it ranks BELOW the phone signal and never auto-attaches
-- alone).
--
-- Pure additive nullable column. NULL stays valid for whatsapp/zoho sources.
--
-- On the Pro apply manually like 212-226:
--   psql postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev \
--     -f apps/backend-rag/backend/db/migrations_v2/227_intake_queue_source_path.sql
-- === FORWARD ===

ALTER TABLE intake_queue
    ADD COLUMN IF NOT EXISTS source_path TEXT;

COMMENT ON COLUMN intake_queue.source_path IS
    'Blob path relative to the watched Drive root (e.g. "<Client Name>/passport.jpg", migration 227). First segment is the folder-name entity signal for FASE-4 routing. NULL for sources without a folder (whatsapp/zoho).';

-- === ROLLBACK ===
-- ALTER TABLE intake_queue DROP COLUMN IF EXISTS source_path;
