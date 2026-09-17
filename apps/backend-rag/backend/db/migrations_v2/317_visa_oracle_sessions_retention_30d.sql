-- ============================================================================
-- 317_visa_oracle_sessions_retention_30d.sql
--
-- ----------------------------------------------------------------------------
-- SUCCESSOR OF PR #6478 (2026-09-17, mandate SAETTA R2). #6478
-- (branch agent/air-m5/db/vo-sessions-retention-317, same filename, same
-- SQL body) is armed and frozen on GitHub but carries NO Gear-3 evidence
-- pack — its Harness floor is 3 (migration hot-zone) and an armed branch is
-- read-only per Builder Contract §1, so it can never grow the pack it is
-- missing. This is the fresh-from-origin/main follow-up the Contract
-- requires; #6478 is expected to be closed by the Dux once this successor
-- is ready, not merged alongside it. The SQL below is UNCHANGED from
-- #6478's version (already reviewed clean at that split-gate) — only this
-- provenance comment and the numbering re-check are new.
--
-- NUMBERING RE-CHECKED THIS TURN (successor turn, not a renumbering):
--   git ls-tree -r --name-only origin/main -- apps/backend-rag/backend/db/migrations_v2/
--     -> highest present is 318 (318_wa_outbox_inbound_binding_and_terminal_reasons.sql);
--        315 is also present (315_wa_outbox_fall_off_reason_support_judge_absent.sql);
--        316 and 317 are BOTH free — no file on origin/main claims either number.
--   gh pr list --state open --limit 500 --json number,headRefName,files | grep migrations_v2
--     -> #6478 (agent/air-m5/db/vo-sessions-retention-317) claims 317 with this
--        exact filename — the fossil this PR supersedes, not a competing author.
--     -> #6474 (agent/air-m5/db/vo-consultant-split) claims 315 and 316 with
--        DIFFERENT filenames (315_visa_oracle_consultant_requests.sql,
--        316_visa_oracle_consultant_requests_retention_policy.sql) — 315
--        collides with origin/main's own 315 under a different name, and 316
--        collides with nothing on main; neither is this migration's number
--        and neither is this migration's collision to fix.
--   backend/db/migration_manager.py::apply_all_pending computes `pending` by
--   set-membership in `_schema_versions` (migration_number not in
--   applied_numbers), never by comparison against the max applied number —
--   confirmed by reading `_apply_all_pending_locked` (migration_manager.py
--   L559-655) this turn. A database that has already applied 318 will still
--   pick up 317 as pending on its next `apply-all` and apply it out of
--   numeric order; nothing in the runner requires monotonic application, and
--   this migration's own SQL (CREATE TABLE IF NOT EXISTS / CREATE INDEX IF
--   NOT EXISTS / idempotent ALTER ... SET DEFAULT) has no ordering
--   dependency on 318's content (a disjoint table, wa_outbox). 317 is kept,
--   not renumbered.
-- ----------------------------------------------------------------------------
--
-- RENUMBERED 2026-09-14 (split from PR #5037, per the gate's own recommended
-- shape): drafted as 295 on the original, now-suspended PR — gated for 4
-- failed rounds on this repo's tripwire test, unrelated to this table
-- (Builder Contract §1 depth-1 cap on a fix-of-a-fix). Renumbered 295->317
-- alongside siblings 293->315 and 294->316 — see 315's own header for the
-- fresh measurement at that time. Everything below, including this file's
-- own now-doubly-stale bind-time provenance comment naming 282/283, is
-- otherwise UNCHANGED from the version the split-gate already reviewed as
-- clean.
-- ----------------------------------------------------------------------------
--
-- Owner ruling (Zero, 2026-08-25, docs/plans/2026-08-24-visa-oracle-live/
-- OWNER-RULINGS-2026-08-25.md §3, verbatim): "30 giorni (non i 90
-- dichiarati) — bastano per il visitatore che torna e per l'analisi
-- funnel, minimizzano la ritenzione dichiarata."
--
-- Migration 080 (apps/backend-rag/backend/migrations/migration_080a_
-- visa_oracle_sessions.py, the OLDER Python-based migration system —
-- already applied in production, its CREATE TABLE IF NOT EXISTS is a
-- historical record now, not re-run) declared:
--   expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days')
-- and its own docstring comment (line 15) additionally claimed
-- "90-day TTL, cleaned up by periodic job" — SWITCHBOARD-2-RETENTION.md
-- (2026-08-25) measured that no such job exists anywhere in the repo, on
-- any of the three paths it could live (application cron, launchd,
-- pg_cron): the column and its index exist, the purge that would act on
-- them does not. That absence is not this migration's to cure — Zero's
-- ruling asks only for the DECLARED number to become 30, and the
-- switchboard's own recommendation to arm a purge was explicitly deferred
-- pending Zero's answer, which came back as "stop collecting the free-text
-- field", not "build a purge job". This migration does exactly the one
-- thing asked: it changes what NEW rows declare.
--
-- Scope, stated so it cannot be over-read:
--   - Changes the DEFAULT for `expires_at` on every row inserted from now
--     on. `_persist_session_create` (apps/backend-rag/backend/app/routers/
--     visa_oracle.py:634-656) never sets expires_at explicitly in its
--     INSERT — confirmed by reading the router this turn: the statement
--     names only (session_id, quiz_answers, recommended_visas, ip_hash) —
--     so this migration alone is sufficient; the router needs no change.
--   - Does NOT touch any EXISTING row's expires_at — no UPDATE statement
--     here. Retroactively shortening already-declared expiry dates on live
--     data is a production-data mutation, not a schema declaration; per
--     the ruling and per SWITCHBOARD-2-RETENTION.md, disposing of the
--     existing backlog is a separate, credentialed, operator act. Existing
--     rows KEEP their already-declared 90-day expires_at.
--   - Does NOT create a purge job, a policy table, or any enforcement of
--     the declared date (unlike migration 316's retention machinery for
--     visa_oracle_consultant_requests) — none of that was asked for here,
--     and building it would be exactly the "purge on a field that might
--     not need to exist" the switchboard warned against for the sibling
--     `messages` question.
--   - Does NOT touch the `messages` column itself — the free-text funnel's
--     collection is stopped in application code
--     (visa_oracle.py::chat(), same commit), not by a schema change; the
--     column stays for whatever backlog already exists, per the same
--     "disposal is separate" boundary above.
-- ============================================================================

SET lock_timeout = '5s';
SET statement_timeout = '60s';

-- ----------------------------------------------------------------------------
-- PROVENANCE GUARD — why an ALTER migration begins with a CREATE.
--
-- `visa_oracle_sessions` predates migrations_v2. It is created by the LEGACY
-- Python migration system (backend/migrations/migration_080a_visa_oracle_
-- sessions.py), and `migration_base.py:66` says plainly that the automated
-- loader "only reads db/migrations_v2/*.sql" — so nothing in CI ever runs
-- 080a. The table is also not a SQLModel `table=True` class, so it is missed
-- by scripts/ci_bootstrap_schema.py, the CI-only sweep that exists precisely
-- to cover tables predating migrations_v2. Net effect: the table exists in
-- production and has NEVER existed on a fresh CI database, and this file is
-- the first migrations_v2 member to touch it.
--
-- Measured, not assumed: the bare ALTER below failed identically in all three
-- CI backend shards with `relation "public.visa_oracle_sessions" does not
-- exist`, during `python -m backend.db.migrate apply-all`, before pytest
-- collected a single test. 315 and 316 applied fine — they CREATE their own
-- tables; only this one assumed a table into existence.
--
-- The cure is to stop assuming: migrations_v2 now owns the table's existence.
-- On production every statement below is a no-op (the table and both indexes
-- are already there); on a fresh database they build it. The column list,
-- types, nullability and defaults are transcribed from the LIVE production
-- catalog (information_schema.columns), not from the legacy file, so a fresh
-- database converges on what production actually has.
--
-- THE INDEX NAMES ARE PRODUCTION'S, NOT THE LEGACY FILE'S, AND THE DIFFERENCE
-- IS LOAD-BEARING. 080a names them `idx_visa_oracle_sessions_{session_id,
-- created_at}`; production actually carries `idx_vo_sessions_session_id` and
-- `idx_vo_sessions_created_at` (read out of pg_indexes). Using the legacy
-- names here would find no existing index on production, so IF NOT EXISTS
-- would not protect anything — it would BUILD A SECOND, DUPLICATE INDEX on a
-- live table. Using production's names makes it the intended no-op.
--
-- LOCKS: on production, CREATE TABLE IF NOT EXISTS and both CREATE INDEX IF
-- NOT EXISTS calls are no-ops (table and indexes already exist) — no lock of
-- consequence. The one statement with a real effect, ALTER COLUMN ... SET
-- DEFAULT, is a catalog-only change (it does not rewrite existing rows or
-- take an ACCESS EXCLUSIVE table rewrite lock); it takes a brief ACCESS
-- EXCLUSIVE lock only for the DDL statement itself, matching every other
-- SET DEFAULT change already in this directory. On a genuinely fresh
-- database the CREATE TABLE/INDEX statements run for real, against a table
-- with zero rows.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.visa_oracle_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          VARCHAR(64) NOT NULL,
    quiz_answers        JSONB DEFAULT '{}'::jsonb,
    recommended_visas   JSONB DEFAULT '[]'::jsonb,
    messages            JSONB DEFAULT '[]'::jsonb,
    language_detected   VARCHAR(10),
    handoff_triggered   BOOLEAN DEFAULT FALSE,
    ip_hash             VARCHAR(64),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at          TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days')
);

CREATE INDEX IF NOT EXISTS idx_vo_sessions_session_id
    ON public.visa_oracle_sessions (session_id);

CREATE INDEX IF NOT EXISTS idx_vo_sessions_created_at
    ON public.visa_oracle_sessions (created_at DESC);

-- The declaration this migration actually exists for. It runs identically on
-- both paths: on production against the table that was already there, on a
-- fresh database against the one just created above with the 90-day default.
ALTER TABLE public.visa_oracle_sessions
    ALTER COLUMN expires_at SET DEFAULT (NOW() + INTERVAL '30 days');

-- === ROLLBACK ===
SET lock_timeout = '5s';
SET statement_timeout = '60s';

ALTER TABLE public.visa_oracle_sessions
    ALTER COLUMN expires_at SET DEFAULT (NOW() + INTERVAL '90 days');
