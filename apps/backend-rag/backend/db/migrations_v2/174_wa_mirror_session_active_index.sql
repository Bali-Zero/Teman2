-- migration 174_wa_mirror_session_active_index
-- Fix the whatsapp_team_sessions uniqueness model.
--
-- Migration 173 created:
--   CONSTRAINT uq_whatsapp_team_sessions_active
--     UNIQUE (team_member_email, status) DEFERRABLE INITIALLY DEFERRED
--
-- Intent was "one ACTIVE session row per team member". But UNIQUE on the
-- full (email, status) pair ALSO forbids a team member from having two rows
-- in a *terminal* state — e.g. two 'disconnected' rows across two connect
-- cycles. That is legitimate history, not a conflict. In practice the
-- Baileys reconnect loop hit this constantly: the post-pairing
-- restartRequired close tried to mark a fresh row 'disconnected' while a
-- prior failed-onboarding row was already 'disconnected' →
-- "duplicate key value violates unique constraint".
--
-- Fix: drop the full-pair constraint, replace with a PARTIAL UNIQUE INDEX
-- that only covers the two ACTIVE states ('pending', 'connected'). A team
-- member can have at most one active row; unlimited terminal-state rows.
--
-- Squawk: repo-wide excludes prefer-robust-stmts + constraint-missing-not-valid
-- + require-concurrent-index-creation already in migration-lint.yml. The
-- table is brand-new (created in 173, effectively empty in prod), so the
-- non-concurrent index build and the constraint drop take no meaningful lock.

-- Defensive: 173 may not have run yet on a fully fresh DB exercised by the
-- SQL v2 test runner in isolation. CREATE TABLE IF NOT EXISTS mirrors the
-- 173 shape so 174 can apply standalone. No-op on prod.
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
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Drop the over-broad constraint from 173 (IF EXISTS: it may be absent on a
-- fresh DB where the CREATE TABLE above just built the table without it).
ALTER TABLE whatsapp_team_sessions
    DROP CONSTRAINT IF EXISTS uq_whatsapp_team_sessions_active;

-- One active row per team member. Terminal states are unconstrained.
CREATE UNIQUE INDEX IF NOT EXISTS uq_whatsapp_team_sessions_active_member
    ON whatsapp_team_sessions (team_member_email)
    WHERE status IN ('pending', 'connected');

COMMENT ON INDEX uq_whatsapp_team_sessions_active_member IS
    'At most one ACTIVE (pending|connected) wa-mirror session row per team '
    'member. Terminal rows (disconnected|expired|revoked) are unconstrained '
    'history — replaces the 173 full-pair UNIQUE that wrongly blocked them.';

-- === ROLLBACK ===
DROP INDEX IF EXISTS uq_whatsapp_team_sessions_active_member;
ALTER TABLE whatsapp_team_sessions
    ADD CONSTRAINT uq_whatsapp_team_sessions_active
        UNIQUE (team_member_email, status)
        DEFERRABLE INITIALLY DEFERRED;
