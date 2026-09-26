-- 322_wa_outbox_served_by.sql
--
-- THE GAP (docs/zantara-loop-state.md, Iteration 2 "Measured, not fixed" +
-- "Next gap"): ~74% of client questions that reach retrieval get the fixed
-- `support_abstain` stub, but that rate is invisible in SQL. `abstained_at`
-- stays NULL for a `support_abstain` completion BY DESIGN (D6/B2.3b,
-- migration 314's own header: it means "a GENERATED reply whose frozen
-- evidence label was true", never "a refusal stub was delivered"), and
-- `wa_outbox_worker.py` only LOGS `leg.served_by`
-- (`logger.info("wa_outbox: %s served outbox=%s", ...)`) — nothing durable
-- on the row says which route served it. `CodexLegResult.served_by`
-- (`wa_codex_leg.py`) already carries the closed vocabulary this column
-- stores verbatim: `codex` (default), `support_abstain`,
-- `scripted_media_ack`, `scripted_greeting`, `scripted_human_handoff`,
-- `scripted_identity`.
--
-- NO CHECK CONSTRAINT, DELIBERATELY: the post-send bookkeeping UPDATE that
-- writes this column runs AFTER the irreversible Graph send (worker
-- comment above that UPDATE: "The Graph send has now IRREVERSIBLY
-- happened. Everything below is best-effort bookkeeping"). A CHECK would
-- make that UPDATE fail the day a new `served_by` value ships before this
-- column's vocabulary is widened — turning a bookkeeping miss into a
-- transaction abort on a message that was already delivered. Nullable, no
-- default: NULL means the row never carried a completion (failed
-- generation, or a route — human-send, non-generation — that never called
-- the codex leg), same meaning NULL already has for `evidence_score`.
--
-- LOCKS: ADD COLUMN with neither a type needing a rewrite nor a default is
-- a catalog-only change on Postgres >= 11 — no table rewrite, no row
-- touched (same rationale as migrations 314/318). `wa_outbox` is ~450 rows
-- in production; SET LOCAL bounds this the same as 314 out of caution, not
-- necessity.
--
-- IF NOT EXISTS: mirrors 318/321 (the two most recent ADD COLUMNs on this
-- table), not 314's fail-fast — a same-named column already present in the
-- right shape (TEXT, nullable, no default) is a no-op worth tolerating
-- here since nothing downstream depends on catching that drift loudly.
--
-- NUMBERING: `git ls-tree origin/main -- apps/backend-rag/backend/db/migrations_v2`
-- checked this turn — 321_portal_reply_and_email.sql is the last file;
-- `gh pr list --state open --json number,files` (this turn) shows no open
-- PR touching migrations_v2. 322 is free against both.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

ALTER TABLE public.wa_outbox ADD COLUMN IF NOT EXISTS served_by TEXT NULL;

COMMENT ON COLUMN public.wa_outbox.served_by IS
    'CodexLegResult.served_by verbatim (wa_codex_leg.py): codex (default), '
    'support_abstain, scripted_media_ack, scripted_greeting, '
    'scripted_human_handoff, scripted_identity. NULL = no completion (failed '
    'generation, or a route that never called the codex leg). No CHECK: '
    'written after the irreversible send, must never abort the bookkeeping '
    'UPDATE on an unrecognized value.';

-- === ROLLBACK ===
-- Additive and nullable: dropping it loses no other invariant, but the
-- routine rollback of the writer (revert the worker commit) can KEEP this
-- column, same as 314's abstain columns — the writer stops populating it,
-- the column just goes quiet. Drop it only as a separately authorized
-- cleanup once nothing reads it.
SET LOCAL lock_timeout = '5s';
ALTER TABLE public.wa_outbox DROP COLUMN IF EXISTS served_by;
