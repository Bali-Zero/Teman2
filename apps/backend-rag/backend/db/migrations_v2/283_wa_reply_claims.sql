-- Migration 283: wa_reply_claims
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
-- Renumbered 281 -> 282 -> 283 (second adversarial-review finding, W40
-- collision class -- the FIRST rename to 282 was itself a collision that
-- was not caught by re-checking only main + the one other PR the first
-- reviewer named). At rename time (2026-08-25), queried the FULL open-PR
-- set, not just main: `gh pr list --state open --limit 300 --json
-- number,files -q '.[] | .number as $n | .files[]?.path | select(test(
-- "migrations_v2/[0-9]+_")) | "\($n): \(.)"'` returned PR #4879
-- (garuda_orders, open) ALSO claiming 282 -- the exact silent-collision
-- shape this rename exists to prevent, since CI's own migration-number
-- lint only compares main + the current PR, never two open PRs against
-- each other. `git ls-tree origin/main -- .../migrations_v2/` (cross-
-- checked against the GitHub Contents API directly, not just a local
-- fetch) confirms the highest number actually present on main is still
-- 280 (280_research_os_objects_truncate_guard.sql).
--
-- Anomaly noted, NOT resolved here (out of scope, flagged for the
-- record): PR #4854 is reported MERGED by the GitHub API and its commit
-- message claims migration 281 (281_garuda_voa_retention.sql), but that
-- file is absent from origin/main's current tip, and #4854's merge commit
-- (09bb478323845a9e80a90afdaf877efff4018874) is NOT an ancestor of
-- origin/main -- verified via `git merge-base --is-ancestor`. Whatever the
-- cause, 281 is therefore NOT used as this PR's number: 283 keeps a
-- two-integer margin from every number confirmed live (280 on main, 282
-- claimed by open PR #4879), so a future resolution of the #4854/281
-- anomaly (whichever direction it goes) cannot collide with this file.
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
