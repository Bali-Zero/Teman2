-- Migration 281: team_bot_ingress_leader
-- (I DUE BOT, lane B5 -- MANDATE.md F9, the Mini<->Pro failover control record)
--
-- INTEGER BOUND PROVISIONALLY. This repo's own convention
-- (LEGACY_PROMOTION_README.md / migration 279's header) is: reserve a
-- SYMBOLIC name, bind the integer FRESH at the committing session's
-- integration time, never copy a number from a prompt or an earlier
-- branch. This mandate is explicitly LOCAL-FIRST (MANDATE.md preamble:
-- "no per-commit PR ceremony ... nightly push of the integration branch,
-- final landing as a short PR train") and several duebot lanes may be
-- adding migrations concurrently on their own worktrees against the SAME
-- `feature/due-bot` base. 281 is the correct next integer against
-- `feature/due-bot`@10af71ed7 (the commit this worktree was reset to --
-- `ls backend/db/migrations_v2/*.sql | sed -E 's#.*/([0-9]+)_.*#\1#' |
-- sort -n | tail -1` -> 280) at the time this file was written. Whoever
-- lands the final PR train MUST re-run that measurement against the then-
-- current integration branch tip and renumber this file if another lane's
-- migration has since claimed 281 -- this is expected, not an error.
--
-- Purpose
-- -------
-- The Single-Source-of-Truth control record for F9's leader-epoch CAS
-- (superscar family #10, "active-active split-brain" -- antidote: "SSOT
-- nel DB ... graceful exit se node != hostname", never a per-Mac belief
-- or a lockfile). Backs `ingress_leader.IngressLeaderStore` (already
-- committed, `apps/backend-rag/backend/services/team_bot_ingress/
-- ingress_leader.py`) for `ingress_state_repo.py`'s Postgres
-- implementation.
--
-- Deliberately lives in the SAME Postgres the CRM mutation endpoints
-- already run against -- not local SQLite on Mini/Pro. A per-Mac file
-- cannot be checked in-process by a CRM endpoint running on the shared
-- backend without an extra network hop THROUGH one of the two Macs,
-- which reopens exactly the split-brain gap this table exists to close.
-- Reachable from both Mini and Pro over the same outbound-only HTTPS
-- path the existing wa_codex_daemon / wa_outbox_worker already use.
--
-- Single-tenant: one WABA to arbitrate today, so one row keyed by a
-- literal `record_id` (`ingress_leader.DEFAULT_RECORD_ID` =
-- "team_wa_default"). A second WABA would get a second row, never a
-- second table.
--
-- Bootstrap lease is deliberately SHORT (60s), not far-future. An
-- ingress process that has not yet started its heartbeat should not
-- look authorized indefinitely -- the real Mini heartbeat (once B3 wires
-- it) must call `renew()` promptly after startup, exactly as a fresh
-- deploy with no live heartbeat should read as unauthorized rather than
-- silently valid. `callback_uri_sha256` bootstraps to 64 zero-chars -- a
-- SENTINEL, explicitly not a valid sha256 of anything, meaning "no
-- callback configured yet". The CHECK constraint below still requires
-- 64 lowercase-hex chars so this sentinel is well-formed, not a special
-- case the column type has to tolerate.
--
-- Everything that reads this table stays dark until
-- TEAM_BOT_FAILOVER_AUTO_ENABLED flips (see
-- docs/plans/2026-08-25-due-bot-live/ops/KILL-SWITCHES.md, owned by
-- lane B7 -- not yet landed on feature/due-bot at the time of this
-- migration, hence no FK/dependency on anything B7 owns here).
--
-- Rollback marker convention: mandatory for migrations > 111 per
-- backend/db/migration_base.py:29. This file's ONE literal
-- `-- === ROLLBACK ===` line is the real delimiter (see 279's own
-- header for the naive-split trap this note exists to avoid repeating).

CREATE TABLE IF NOT EXISTS public.team_bot_ingress_leader (
    record_id            text        PRIMARY KEY,
    active_node_id       text        NOT NULL,
    leader_epoch         bigint      NOT NULL DEFAULT 1,
    lease_expires_at     timestamptz NOT NULL,
    callback_uri_sha256  text        NOT NULL,
    changed_at           timestamptz NOT NULL DEFAULT now(),
    created_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT team_bot_ingress_leader_epoch_positive
        CHECK (leader_epoch > 0),
    CONSTRAINT team_bot_ingress_leader_callback_sha256_shape
        CHECK (callback_uri_sha256 ~ '^[0-9a-f]{64}$')
);

COMMENT ON TABLE public.team_bot_ingress_leader IS
    'F9 leader-epoch CAS control record (superscar #10 antidote). '
    'One row per WABA. Written ONLY via compare-and-swap '
    '(UPDATE ... WHERE leader_epoch = $expected) -- never a bare UPDATE. '
    'Non-PII: every column is an infrastructure identifier.';

INSERT INTO public.team_bot_ingress_leader (
    record_id, active_node_id, leader_epoch, lease_expires_at,
    callback_uri_sha256, changed_at
)
VALUES (
    'team_wa_default',
    'mini-pro2',
    1,
    now() + interval '60 seconds',
    repeat('0', 64),
    now()
)
ON CONFLICT (record_id) DO NOTHING;

-- === ROLLBACK ===

DROP TABLE IF EXISTS public.team_bot_ingress_leader;
