-- migration 173_wa_mirror_team_sessions
-- Bali Zero team WhatsApp mirror (wa-mirror) — additive infrastructure.
-- The existing Meta Cloud API handler at apps/backend-rag/backend/channels/whatsapp/
-- writes to whatsapp_contacts + whatsapp_message_context (legacy export, 14.847
-- rows). The new wa-mirror Baileys daemon (apps/wa-mirror/) connects each team
-- member's personal WhatsApp number as a "Linked Device" and writes mirror
-- rows to the SAME tables with a new team_member_email column to discriminate
-- source. Adds whatsapp_team_sessions to track each team member's bridge
-- lifecycle (connect / heartbeat / disconnect).
--
-- Privacy contract: see apps/wa-mirror/docs/PRIVACY_CONTRACT_TEAM.md.
-- Server-side filter only writes rows where the counterpart phone is in the
-- clients table; non-client messages are dropped before INSERT.
--
-- Squawk: ADD COLUMN with no DEFAULT on non-empty table (whatsapp_message_context
-- has 14.847 rows) is a fast operation in PG 11+ (catalog-only metadata change).
-- Repo-wide excludes prefer-robust-stmts + constraint-missing-not-valid already
-- in .github/workflows/migration-lint.yml.

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS team_member_email VARCHAR(255);

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS source VARCHAR(32) NOT NULL DEFAULT 'meta_cloud_api';

ALTER TABLE whatsapp_message_context
    ADD COLUMN IF NOT EXISTS bridge_session_id INTEGER;

CREATE TABLE IF NOT EXISTS whatsapp_team_sessions (
    id                  SERIAL PRIMARY KEY,
    team_member_email   VARCHAR(255) NOT NULL,
    phone_normalized    VARCHAR(50) NOT NULL,
    session_label       VARCHAR(128) NOT NULL,
    auth_state_path     TEXT NOT NULL,
    status              VARCHAR(32) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'connected', 'disconnected', 'expired', 'revoked')),
    connected_at        TIMESTAMPTZ,
    last_seen_at        TIMESTAMPTZ,
    disconnected_at     TIMESTAMPTZ,
    disconnect_reason   VARCHAR(64),
    messages_logged     BIGINT NOT NULL DEFAULT 0,
    messages_filtered   BIGINT NOT NULL DEFAULT 0,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_whatsapp_team_sessions_active
        UNIQUE (team_member_email, status)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_team_sessions_status
    ON whatsapp_team_sessions (status, last_seen_at DESC)
    WHERE status = 'connected';

CREATE INDEX IF NOT EXISTS idx_whatsapp_team_sessions_email
    ON whatsapp_team_sessions (team_member_email);

CREATE INDEX IF NOT EXISTS idx_whatsapp_message_context_team
    ON whatsapp_message_context (team_member_email, message_date DESC)
    WHERE team_member_email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_whatsapp_message_context_source
    ON whatsapp_message_context (source, message_date DESC);

ALTER TABLE whatsapp_message_context
    ADD CONSTRAINT fk_wmc_bridge_session
        FOREIGN KEY (bridge_session_id)
        REFERENCES whatsapp_team_sessions(id)
        ON DELETE SET NULL;

COMMENT ON COLUMN whatsapp_message_context.team_member_email IS
    'Email of the Bali Zero team member whose linked-device bridge captured '
    'this message. NULL for messages from the legacy Meta Cloud API path '
    '(source = meta_cloud_api).';

COMMENT ON COLUMN whatsapp_message_context.source IS
    'Where this row came from. "meta_cloud_api" = official Bali Zero number '
    'via Meta Cloud API. "wa_mirror" = team-member personal number via the '
    'Baileys bridge (apps/wa-mirror/).';

COMMENT ON COLUMN whatsapp_message_context.bridge_session_id IS
    'When source="wa_mirror", FK to whatsapp_team_sessions row. Lets us '
    'attribute every message to the specific bridge connect cycle.';

COMMENT ON TABLE whatsapp_team_sessions IS
    'Each row = one team member''s connect cycle to the wa-mirror Baileys '
    'bridge. A team member can have one active row (status=connected) at a '
    'time. The DEFERRABLE unique constraint allows transient overlap during '
    'reconnect retries.';

COMMENT ON COLUMN whatsapp_team_sessions.session_label IS
    'Human-readable label that appears in WhatsApp Settings → Linked Devices '
    'on the team member''s phone (e.g. "Bali Zero WA-Mirror"). Stable across '
    'reconnects to avoid spurious device-list churn.';

COMMENT ON COLUMN whatsapp_team_sessions.auth_state_path IS
    'Filesystem path on Mini-Pro2 where Baileys persists the multi-device '
    'auth state for this session. Format: ~/.wa-mirror/sessions/<email>/.';

COMMENT ON COLUMN whatsapp_team_sessions.messages_filtered IS
    'Count of inbound/outbound messages dropped because the counterpart phone '
    'was NOT in the clients table. Metric only — message content is never '
    'persisted for these.';

-- === ROLLBACK ===
ALTER TABLE whatsapp_message_context DROP CONSTRAINT IF EXISTS fk_wmc_bridge_session;
DROP INDEX IF EXISTS idx_whatsapp_message_context_source;
DROP INDEX IF EXISTS idx_whatsapp_message_context_team;
DROP INDEX IF EXISTS idx_whatsapp_team_sessions_email;
DROP INDEX IF EXISTS idx_whatsapp_team_sessions_status;
DROP TABLE IF EXISTS whatsapp_team_sessions;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS bridge_session_id;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS source;
ALTER TABLE whatsapp_message_context DROP COLUMN IF EXISTS team_member_email;
