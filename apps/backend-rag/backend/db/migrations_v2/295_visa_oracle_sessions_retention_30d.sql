-- ============================================================================
-- 295_visa_oracle_sessions_retention_30d.sql
--
-- Number bound at write time (scar W40 — a reservation nobody re-checks
-- decays). Measured fresh this turn:
--   git ls-tree -r --name-only origin/main -- apps/backend-rag/backend/db/migrations_v2/
--     -> highest present is 280 (280_research_os_objects_truncate_guard.sql)
--   git ls-tree -r --name-only HEAD -- apps/backend-rag/backend/db/migrations_v2/
--     -> highest present is 282 (294_visa_oracle_consultant_requests_retention_policy.sql,
--        this branch's own two migrations — not yet on origin/main)
--   gh pr list --state open --limit 500 --json number,headRefName,files | grep migrations_v2
--     -> exactly one hit, unchanged from 282's own check: #4854 adds
--        281_garuda_voa_retention.sql on branch agent/air-m5/backend-rag/
--        garuda-l1-retention-0824. That collides with THIS branch's own 281,
--        not with 283 — not this migration's collision to fix. Nothing open
--        claims 282 or 283.
-- -> next available integer on every source checked: 283.
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
--     visa_oracle.py) never sets expires_at explicitly, so this is the
--     only place the 90-day value came from.
--   - Does NOT touch any EXISTING row's expires_at — no UPDATE statement
--     here. Retroactively shortening already-declared expiry dates on live
--     data is a production-data mutation, not a schema declaration; per
--     the ruling and per SWITCHBOARD-2-RETENTION.md, disposing of the
--     existing backlog is a separate, credentialed, operator act.
--   - Does NOT create a purge job, a policy table, or any enforcement of
--     the declared date (unlike migration 294's retention machinery for
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
-- collected a single test. 293 and 294 applied fine — they CREATE their own
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
