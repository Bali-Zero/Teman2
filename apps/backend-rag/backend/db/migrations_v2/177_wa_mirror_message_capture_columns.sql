-- migration 177_wa_mirror_message_capture_columns
-- Complete wa-mirror message capture fields.
--
-- Migration 173 added the team-session scaffold and legacy source markers.
-- The bridge now stores every one-to-one message, including prospects with
-- client_id=NULL, plus media/OCR metadata and the raw Baileys payload.

ALTER TABLE whatsapp_team_sessions
    ADD COLUMN IF NOT EXISTS team_member_phone VARCHAR(32);

ALTER TABLE whatsapp_team_sessions
    ADD COLUMN IF NOT EXISTS team_member_name VARCHAR(255);

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS client_id BIGINT;

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS practice_id BIGINT;

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS team_member_phone VARCHAR(32);

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS counterpart_phone VARCHAR(32);

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS body TEXT;

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS media_type VARCHAR(24);

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS media_mime TEXT;

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS media_url TEXT;

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS media_stored_path TEXT;

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS raw_baileys_event JSONB;

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS baileys_message_id TEXT;

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS ocr_result JSONB;

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS uq_wmc_baileys_message_id
    ON whatsapp_message_context (baileys_message_id)
    WHERE baileys_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_wmc_client_practice_date
    ON whatsapp_message_context (client_id, practice_id, message_date DESC)
    WHERE client_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_wmc_counterpart_date
    ON whatsapp_message_context (counterpart_phone, message_date DESC)
    WHERE counterpart_phone IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_team_sessions_active_phone
    ON whatsapp_team_sessions (team_member_phone)
    WHERE team_member_phone IS NOT NULL
      AND status IN ('pending', 'connected');

COMMENT ON COLUMN whatsapp_message_context.client_id IS
    'Nullable CRM client id matched from counterpart_phone. NULL means prospect/lead.';

COMMENT ON COLUMN whatsapp_message_context.practice_id IS
    'Nullable best-match open practice id for the matched client.';

COMMENT ON COLUMN whatsapp_message_context.team_member_phone IS
    'Canonical E.164 Bali Zero team account captured by wa-mirror.';

COMMENT ON COLUMN whatsapp_message_context.counterpart_phone IS
    'Canonical E.164 phone of the other party in the one-to-one WhatsApp chat.';

COMMENT ON COLUMN whatsapp_message_context.body IS
    'Full text/caption body captured from Baileys. Empty string for media-only messages.';

COMMENT ON COLUMN whatsapp_message_context.raw_baileys_event IS
    'Full JSON-safe Baileys message payload for audit and replay diagnostics.';

COMMENT ON COLUMN whatsapp_message_context.baileys_message_id IS
    'Baileys message id used as the reconnect-safe deduplication key.';

COMMENT ON COLUMN whatsapp_message_context.ocr_result IS
    'Best-effort structured OCR result for supported downloaded media.';

-- === ROLLBACK ===
DROP INDEX IF EXISTS uq_whatsapp_team_sessions_active_phone;
DROP INDEX IF EXISTS idx_wmc_counterpart_date;
DROP INDEX IF EXISTS idx_wmc_client_practice_date;
DROP INDEX IF EXISTS uq_wmc_baileys_message_id;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS updated_at;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS ocr_result;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS baileys_message_id;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS raw_baileys_event;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS media_stored_path;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS media_url;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS media_mime;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS media_type;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS body;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS counterpart_phone;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS team_member_phone;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS practice_id;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS client_id;
ALTER TABLE whatsapp_team_sessions DROP COLUMN IF EXISTS team_member_name;
ALTER TABLE whatsapp_team_sessions DROP COLUMN IF EXISTS team_member_phone;
