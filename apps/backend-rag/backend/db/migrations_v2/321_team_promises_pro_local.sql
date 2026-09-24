-- 321_team_promises_pro_local.sql
--
-- T3 promise gate, rebuilt PRO-LOCAL (owner ruling 2026-09-25: "attiva" —
-- rebuild T3-T7, data never leaves Pro, Symbiosis Law 2). Spec:
-- research (scratchpad) spec_T37_draft.md P1.
--
-- Two ledgers, two shapes it must fit at once:
--   - Pro: _schema_versions stops at 246 (2026-07-18) AND already holds a
--     slot-200 probe row (200_strip_rollback_probe, 2026-05-10) that
--     collides with the Fly-only 200_wa_copilot_infrastructure.sql, so
--     `team_promises` can never reach Pro by that number. This migration
--     is a NEW number (321) that depends on nothing after 246 — no FK to
--     any table a >246 migration created.
--   - Fly: merging apps/backend-rag/** deploys Fly and the release runs
--     `migrate apply-all` (fly.toml). Fly already carries
--     `team_promises` from 200_wa_copilot_infrastructure.sql (7 rows,
--     frozen since 2026-05-25) AND the `uix_team_promises_msg_type` index
--     via drift (no migration ever defined it there). Every statement
--     below is IF NOT EXISTS so this migration is a no-op on the table
--     shape on Fly — only the 4 new nullable columns land there.
--
-- Shape: CREATE TABLE mirrors mig-200's team_promises columns, minus the
-- two FKs mig-200 had (`conversation_id REFERENCES whatsapp_conversations`,
-- `client_id REFERENCES clients`) — neither target table's shape is safe
-- to assume from a migration that must not depend on anything after 246,
-- and Pro's own whatsapp_message_context.client_id (mig-177) carries no
-- FK to clients either, so this follows the same local convention. Four
-- columns are additive over mig-200's shape, needed because Pro cannot
-- use mig-200's sender_role/conversation_id (absent on Pro's
-- whatsapp_message_context — see spec finding #3): `thread_key` (the
-- md5 thread key computed in scripts/wa_team_promises.py, since Pro has
-- no whatsapp_conversations table to key off), `team_member_email` (the
-- notifier's per-member key, §P3), `extractor_version` (regex catalog
-- version, for a future re-extract audit), `resolution_kind` (P2's
-- media_sent / team_confirmed / client_ack split — column added now so
-- P2 does not need its own migration for one nullable field).

BEGIN;

CREATE TABLE IF NOT EXISTS team_promises (
    promise_id                BIGSERIAL PRIMARY KEY,
    message_id                BIGINT NOT NULL,
    conversation_id           BIGINT,
    client_id                 BIGINT,
    promise_text               TEXT NOT NULL,
    promise_type               TEXT,
    due_at                     TIMESTAMPTZ,
    resolved                   BOOLEAN NOT NULL DEFAULT false,
    resolved_at                TIMESTAMPTZ,
    resolved_by_message_id     BIGINT,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE team_promises
    ADD COLUMN IF NOT EXISTS thread_key TEXT;
ALTER TABLE team_promises
    ADD COLUMN IF NOT EXISTS team_member_email TEXT;
ALTER TABLE team_promises
    ADD COLUMN IF NOT EXISTS extractor_version TEXT;
ALTER TABLE team_promises
    ADD COLUMN IF NOT EXISTS resolution_kind TEXT;

-- Fly already has this index via drift (no migration ever created it there,
-- and Fly has 0 duplicate (message_id, promise_type) rows — spec finding
-- #2), so CREATE ... IF NOT EXISTS is safe there. On Pro it is the
-- ON CONFLICT target scripts/wa_team_promises.py relies on for idempotent
-- inserts.
CREATE UNIQUE INDEX IF NOT EXISTS uix_team_promises_msg_type
    ON team_promises (message_id, promise_type);

CREATE INDEX IF NOT EXISTS idx_team_promises_unresolved
    ON team_promises (resolved, due_at)
    WHERE resolved = false;

CREATE INDEX IF NOT EXISTS idx_team_promises_thread_key
    ON team_promises (thread_key)
    WHERE thread_key IS NOT NULL;

COMMIT;

-- === ROLLBACK ===
-- Fly already carries this table with 7 live rows from the 2026-05-25
-- pilot (mig-200) — dropping the table would destroy that history, not
-- just this migration's additions, so the rollback only reverses what
-- THIS migration can safely own: the four additive columns and the two
-- new indexes. `uix_team_promises_msg_type` is intentionally NOT dropped
-- — Fly depends on it via drift already (spec finding #2) and dropping
-- it here would remove a constraint Fly never got from a migration in
-- the first place. The table itself is never dropped by this rollback.

DROP INDEX IF EXISTS idx_team_promises_thread_key;
DROP INDEX IF EXISTS idx_team_promises_unresolved;
ALTER TABLE team_promises DROP COLUMN IF EXISTS resolution_kind;
ALTER TABLE team_promises DROP COLUMN IF EXISTS extractor_version;
ALTER TABLE team_promises DROP COLUMN IF EXISTS team_member_email;
ALTER TABLE team_promises DROP COLUMN IF EXISTS thread_key;
