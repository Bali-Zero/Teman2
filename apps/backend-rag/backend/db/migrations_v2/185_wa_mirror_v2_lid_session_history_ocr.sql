-- migration 185_wa_mirror_v2_lid_session_history_ocr
-- wa-mirror v2 architecture: LID resolution map, session-flap audit trail,
-- OCR worker queue, and FTS-ready trigram index for the intelligence layer.
--
-- Purely additive. All ALTER TABLE statements use ADD COLUMN IF NOT EXISTS;
-- all CREATE statements use IF NOT EXISTS. Safe to re-apply.
--
-- Context (verified 2026-05-19 against production `nuzantara_rag`):
-- - whatsapp_message_context: 15,209 rows, 0% client_id match because
--   counterpart_phone was synthesised wrong for @lid identifiers (WhatsApp
--   privacy-shielded contacts, rolled out late 2024).
-- - whatsapp_team_sessions: 4,545 rows of which 4,538 status='revoked' from
--   the reconnect-flap loop (Sahira alone has 1,116 rows). UPSERT on a
--   single state row was needed but lost the audit trail; the new
--   whatsapp_session_history table is the append-only ledger, current state
--   reads via the whatsapp_current_sessions view.
-- - OCR: 66 media files downloaded, 0 processed. Worker queue lives in
--   whatsapp_message_context.ocr_status (pending / done / error).
-- - FTS: GIN trgm index on message_text enables the daily-digest cron to
--   surface KITAS / E33G / PT PMA mentions without a vector DB.
--
-- Squawk: ADD COLUMN with no DEFAULT on non-empty table is fast in PG 11+
-- (catalog-only metadata change). pg_trgm extension is shipped with PG 14+
-- on Fly.io's nuzantara-postgres v0.1.0.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ───────────────────────────────────────────────────────────────────────
-- 1. whatsapp_lid_phone_map — LID resolution, per (team_member, LID) pair.
--    LID is NOT globally unique: WhatsApp assigns a different LID to the
--    same counterpart per linked-device pairing. Composite PK enforces.
-- ───────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS whatsapp_lid_phone_map (
    team_member_phone   VARCHAR(32) NOT NULL,
    lid                 VARCHAR(64) NOT NULL,
    jid_phone           VARCHAR(32),                -- canonical E.164 once resolved; NULL while unresolved
    pushname            TEXT,                       -- counterpart's display name as broadcast by WhatsApp
    source              VARCHAR(32) NOT NULL DEFAULT 'contacts_upsert',
                                                    -- 'contacts_upsert' | 'manual' | 'message_signal' | 'on_whatsapp_query'
    first_seen          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen           TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ,                -- when jid_phone first became non-NULL
    PRIMARY KEY (team_member_phone, lid)
);

CREATE INDEX IF NOT EXISTS idx_lid_map_jid_phone
    ON whatsapp_lid_phone_map (jid_phone)
    WHERE jid_phone IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_lid_map_unresolved
    ON whatsapp_lid_phone_map (last_seen DESC)
    WHERE jid_phone IS NULL;

-- ───────────────────────────────────────────────────────────────────────
-- 2. whatsapp_session_history — append-only flap ledger.
--    The pre-v2 design UPSERTed whatsapp_team_sessions on every state
--    change, losing the flap history. Sahira's 1,116 'revoked' rows were
--    an accidental ledger; we now make it intentional.
-- ───────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS whatsapp_session_history (
    id                     BIGSERIAL PRIMARY KEY,
    team_member_email      VARCHAR(255) NOT NULL,
    team_member_phone      VARCHAR(32),
    team_member_name       VARCHAR(255),
    session_label          VARCHAR(255),
    transition             VARCHAR(32) NOT NULL,
                                                    -- 'opened' | 'connected' | 'disconnected' | 'revoked' | 'heartbeat'
    reason                 TEXT,                    -- disconnect reason code (loggedOut / connectionLost / restartRequired / …)
    messages_logged_delta  INTEGER NOT NULL DEFAULT 0,
    messages_filtered_delta INTEGER NOT NULL DEFAULT 0,
    metadata               JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_session_history_team_recent
    ON whatsapp_session_history (team_member_phone, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_session_history_transition_recent
    ON whatsapp_session_history (transition, occurred_at DESC);

-- Current state projection: latest row per team_member_phone wins.
CREATE OR REPLACE VIEW whatsapp_current_sessions AS
SELECT DISTINCT ON (team_member_phone)
       team_member_phone,
       team_member_email,
       team_member_name,
       session_label,
       transition       AS current_status,
       reason           AS last_reason,
       occurred_at      AS last_seen_at,
       metadata
  FROM whatsapp_session_history
 WHERE team_member_phone IS NOT NULL
 ORDER BY team_member_phone, occurred_at DESC;

-- ───────────────────────────────────────────────────────────────────────
-- 3. whatsapp_message_context additive columns
-- ───────────────────────────────────────────────────────────────────────

-- LID storage: separate from counterpart_phone so the message row stays
-- intact when only the LID is known. The Python consumer joins against
-- whatsapp_lid_phone_map to attribute messages once the LID is resolved.
ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS counterpart_lid VARCHAR(64);

-- OCR worker queue. Worker SELECTs … WHERE ocr_status='pending' AND
-- media_stored_path IS NOT NULL FOR UPDATE SKIP LOCKED.
ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS ocr_status VARCHAR(16) NOT NULL DEFAULT 'pending';

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS ocr_engine VARCHAR(32);
    -- 'tesseract' | 'qwen2.5vl' | 'manual' once worker processes a row

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS ocr_completed_at TIMESTAMPTZ;

-- Flag for the storico repair script (step 4): rows with corrupted
-- counterpart_phone (LENGTH >= 15) get counterpart_phone=NULL +
-- counterpart_lid populated + needs_lid_resolve=true so the consumer
-- knows the LID resolver should re-attempt attribution.
ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS needs_lid_resolve BOOLEAN NOT NULL DEFAULT false;

-- ───────────────────────────────────────────────────────────────────────
-- 4. Indexes
-- ───────────────────────────────────────────────────────────────────────

-- OCR worker queue scan (small index: only pending rows with media)
CREATE INDEX IF NOT EXISTS idx_wmc_ocr_pending
    ON whatsapp_message_context (id)
    WHERE ocr_status = 'pending' AND media_stored_path IS NOT NULL;

-- LID resolver scan
CREATE INDEX IF NOT EXISTS idx_wmc_lid_unresolved
    ON whatsapp_message_context (counterpart_lid, team_member_phone)
    WHERE counterpart_lid IS NOT NULL AND client_id IS NULL;

-- FTS trigram index for cross-conversation search (KITAS, E33G, PT PMA…)
-- pg_trgm GIN allows ILIKE '%kitas%' to use the index instead of seq scan.
-- Scoped to message_text (already populated) and limited by a partial
-- predicate to avoid indexing the 14,860 NULL/empty rows.
CREATE INDEX IF NOT EXISTS idx_wmc_message_text_trgm
    ON whatsapp_message_context USING GIN (message_text gin_trgm_ops)
    WHERE message_text IS NOT NULL AND LENGTH(message_text) > 0;

-- === ROLLBACK ===
DROP INDEX IF EXISTS idx_wmc_message_text_trgm;
DROP INDEX IF EXISTS idx_wmc_lid_unresolved;
DROP INDEX IF EXISTS idx_wmc_ocr_pending;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS needs_lid_resolve;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS ocr_completed_at;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS ocr_engine;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS ocr_status;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS counterpart_lid;
DROP VIEW IF EXISTS whatsapp_current_sessions;
DROP INDEX IF EXISTS idx_session_history_transition_recent;
DROP INDEX IF EXISTS idx_session_history_team_recent;
DROP TABLE IF EXISTS whatsapp_session_history;
DROP INDEX IF EXISTS idx_lid_map_unresolved;
DROP INDEX IF EXISTS idx_lid_map_jid_phone;
DROP TABLE IF EXISTS whatsapp_lid_phone_map;
