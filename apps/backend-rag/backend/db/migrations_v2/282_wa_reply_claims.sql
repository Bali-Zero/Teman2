-- Migration 282: wa_reply_claims
-- (2026-08-25 double-reply race: PR #4878 closed the routing gap that let a
-- second webhook subscription reach the legacy inline path, but the
-- cross-path dedup it added at the top of `process_whatsapp_message` is a
-- plain SELECT against `meta_inbox_messages` -- read-only, best-effort. The
-- meta-inbox pipeline (`_handle_meta_inbox_message`, wa_outbox_worker) and
-- the legacy path (`process_whatsapp_message`, whatsapp_chat.py) are two
-- concurrent BackgroundTasks; a live probe at 04:03-04:04Z on 2026-08-25
-- reproduced two replies to one inbound message (an English abstain from
-- one path, an Italian greeting from the other) because the legacy SELECT
-- can run before the meta-inbox pipeline's own write commits -- classic
-- TOCTOU, cicatrix family #5's shape applied to two application-level
-- paths instead of two worktrees.)
--
-- Renumbered 281 -> 282 (adversarial-review finding, W40 collision class):
-- PR #4854 already claims 281_garuda_voa_retention.sql on its own open
-- branch, and on origin/main the highest present number is 280
-- (280_research_os_objects_truncate_guard.sql) -- re-measured at rename
-- time via `git ls-tree origin/main -- .../migrations_v2/`. 282 is the
-- next free integer once #4854's claim on 281 is respected.
--
-- Purpose
-- -------
-- A dedicated claim table, independent of `meta_inbox_messages`'s schema
-- (whose `thread_id` column is `NOT NULL REFERENCES meta_inbox_threads` --
-- the legacy path has no thread concept and must not be forced to invent
-- one just to win a race). Both paths perform the SAME atomic UPSERT keyed
-- on the Meta `wamid`, before generating or sending a reply, written here
-- in prose rather than verbatim (the guardrails hook blocks destructive-
-- looking SQL tokens even inside comments -- same convention as migration
-- 206's header): a write that sets a row's own primary key back to itself
-- on conflict, so a conflicting attempt still gets a row back via
-- RETURNING. That is deliberate, not decorative: the "do nothing on
-- conflict" form returns no row at all on conflict, which cannot
-- distinguish "someone else already claimed it" from "I already claimed it
-- on a legitimate retry of my own path" -- the two cases need different
-- handling (retry-safely proceed in the second, never in the first). The
-- returned `claimed_by` on a conflict is the FIRST claimant's value
-- (untouched by the no-op update), so the caller compares it against its
-- own path name: equal = this call either just won the claim or is a safe
-- same-path retry (each path's own downstream dedup already makes
-- re-processing idempotent); different = the OTHER path already claimed
-- this wamid -- log and discard.
--
-- Retention (declared, NOT implemented here -- one-concern rule)
-- ----------------------------------------------------------------
-- This table grows by one row per inbound WhatsApp message, forever --
-- there is no TTL, no cleanup job, and no expiry column in this migration.
-- A future migration/cron should add either a `claimed_at`-based retention
-- sweep (the column already exists for this purpose) or a partitioning
-- scheme once volume warrants it. Out of scope for this PR, which only
-- cures the double-reply race; flagging it explicitly so it does not read
-- as an oversight.
--
-- Additive only
-- --------------
-- New table only. Does not ALTER, or otherwise touch any existing table,
-- column, constraint, index, or trigger.
--
-- Rollback marker convention
-- ----------------------------
-- Per `backend/db/migration_base.py:29`, the `-- === ROLLBACK ===` marker
-- below is mandatory for migrations numbered > 111 and the runner's
-- `split_migration_sql()` executes ONLY the forward portion above the
-- marker via `ROLLBACK_MARKER_RE`, anchored to a whole line
-- (`^\s*--\s*===\s*ROLLBACK\s*===\s*$`, MULTILINE). This file keeps the
-- literal marker on exactly one line, used only as the real delimiter.

BEGIN;

CREATE TABLE IF NOT EXISTS wa_reply_claims (
    wamid TEXT PRIMARY KEY,
    claimed_by TEXT NOT NULL CHECK (claimed_by IN ('meta_inbox', 'legacy')),
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;

-- === ROLLBACK ===

DROP TABLE IF EXISTS wa_reply_claims;
