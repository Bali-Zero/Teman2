-- Migration 141: audit canary for P0-4 verification (zero-crash audit 2026-04-29).
--
-- Purpose: prove that the new run-sql-v2-migrations-post-deploy job actually
-- applies new SQL files against the FRESHLY-DEPLOYED image. The pre-deploy
-- run-migrations job runs against the OLD image and will NOT see this file
-- (cicatrix STRUCTURAL 2026-04-26). Only the post-deploy job, on the fresh
-- container, will pick up 141 — that's the test.
--
-- Telegram alert with applied_count >= 1 = fix verified working in prod.
--
-- A follow-up PR (chore/cleanup-p04-canary) will git-rm this file once the
-- alert has fired. The forward DDL is harmless: a single-column placeholder
-- table that is dropped immediately by the rollback section if anything
-- needs to be unwound.
--
-- DO NOT BACKPORT this convention to real migrations. Canaries belong in
-- migrations_v2/ only because the runner is the system under test.

CREATE TABLE IF NOT EXISTS p04_canary_20260429 (
    id BIGSERIAL PRIMARY KEY,
    note TEXT NOT NULL DEFAULT 'P0-4 verification 2026-04-29 — cicatrix STRUCTURAL 2026-04-26 resolved'
);

-- === ROLLBACK ===

DROP TABLE IF EXISTS p04_canary_20260429;
