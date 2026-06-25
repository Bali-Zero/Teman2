-- Migration 237: passwordless magic-link login tokens for the client portal (FASE 6).
--
-- A client requests a login link by email; we store a *hash* of a single-use,
-- short-lived token (never the raw token — defense-in-depth: a DB read does not
-- yield a usable login credential, cf. superscar #4 secret-in-the-clear). The
-- emailed link carries the raw token; verification re-hashes and matches.
--
-- Distinct from `client_invitations` (registration / PIN-set, 72h, plaintext
-- token): magic-link is for ALREADY-registered clients to log in without a PIN,
-- 15-minute TTL, single-use, hashed at rest.
--
-- Numbering: 236 is reserved by the FASE 5 PR (#1637, portal documents); this
-- lands on 237 to avoid a W40 collision once that merges.

-- === FORWARD ===
CREATE TABLE IF NOT EXISTS magic_link_tokens (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email       VARCHAR(255) NOT NULL,
    token_hash  CHAR(64)     NOT NULL,   -- sha256 hex of the raw token
    expires_at  TIMESTAMPTZ  NOT NULL,
    used_at     TIMESTAMPTZ,
    created_ip  VARCHAR(64),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Verification looks up by token_hash; uniqueness prevents replay/dupes.
CREATE UNIQUE INDEX IF NOT EXISTS idx_magic_link_token_hash
    ON magic_link_tokens (token_hash);

-- Rate-limit / cleanup queries scan by email + recency.
CREATE INDEX IF NOT EXISTS idx_magic_link_email_created
    ON magic_link_tokens (email, created_at DESC);

-- Sweep of expired/used tokens (a cron may clean rows where this is in the past).
CREATE INDEX IF NOT EXISTS idx_magic_link_expires
    ON magic_link_tokens (expires_at);

COMMENT ON TABLE magic_link_tokens IS
    'FASE 6 passwordless login: single-use, 15-min, sha256-hashed magic-link tokens for registered portal clients. Migration 237.';
COMMENT ON COLUMN magic_link_tokens.token_hash IS
    'sha256 hex of the raw emailed token — raw token never stored. Migration 237.';

-- === ROLLBACK ===
-- DROP INDEX IF EXISTS idx_magic_link_expires;
-- DROP INDEX IF EXISTS idx_magic_link_email_created;
-- DROP INDEX IF EXISTS idx_magic_link_token_hash;
-- DROP TABLE IF EXISTS magic_link_tokens;
