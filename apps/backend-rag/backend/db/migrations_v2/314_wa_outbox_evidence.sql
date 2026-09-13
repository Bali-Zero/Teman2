-- 314_wa_outbox_evidence.sql
--
-- B2.3a — the abstain record's SCHEMA, and nothing else (staff-room spec
-- research/operations/2026-09-11-bot-staff-room/README.md §0 D6 and
-- B2-engine.md §4 B2.3a). Before this, an abstain decision left no durable
-- trace on the outbox row that carried the reply: the sealed evidence label
-- and score are parsed in wa_codex_leg.py and consumed by wa_finalize, and
-- consumption clears the broker's copy (wa_broker.py), so nothing durable
-- says which generated reply went out under a true abstain label or with
-- which frozen score. Cycle 360 (B3) has to read that in SQL.
--
-- MEANING (D6, one meaning each, nothing inferred from reply text):
--   abstained_at   = the successful-send timestamp of a GENERATED reply
--                    whose frozen evidence label was true. It does NOT mean
--                    a refusal stub was delivered.
--   evidence_score = the same sealed package's frozen score.
-- Scripted and unscored routes keep both NULL. The final disposition is
-- recorded separately by B3.
--
-- WHY A SCHEMA-ONLY FILE: fly-deploy.yml runs the pre-deploy migration job
-- on the PREVIOUS image and applies new SQL again after the new image
-- starts. A writer shipped in the same PR would meet absent columns during
-- that window, so the carrier and the fenced worker write (B2.3b) open only
-- after this file is proven applied in production.
--
-- Nullable, no default, no backfill: on Postgres >= 11 an ADD COLUMN with
-- no default is a catalog change — no table rewrite, no row touched — and
-- the running image never reads either column, so a mixed-version deploy is
-- safe in both directions.
--
-- NUMBERING: measured on fresh origin/main 461a4a93ac with `git ls-tree`:
-- 313_garuda_practice_artifacts.sql is the last file. Open PRs carrying
-- migrations_v2 SQL at cut time: #5037 (293/294/295), #5526 (304), #5337
-- (304, a constraint on this table, no column of this file). A number is
-- reserved only by merging it (cicatrix W40).
--
-- LOCKS: ADD COLUMN still takes ACCESS EXCLUSIVE on wa_outbox, and a DDL
-- waiting for it queues every worker read and write behind itself. The
-- runner executes this file inside one transaction, so SET LOCAL bounds that
-- queue to at most 5 s for this migration (same form as 306); past it the
-- migration aborts atomically, 314 stays unrecorded and a rerun applies it.
--
-- FAIL FAST, NO IF NOT EXISTS: a same-named column that already exists, in
-- any shape (type, default, nullability, a leftover fast-default value, a
-- CHECK), is drift this migration must not adopt. Plain ADD COLUMN raises on
-- it, inside the transaction, so 314 is never recorded over it. No catalog
-- query is needed to decide that.
--
-- NAME RESOLUTION: the table is always `public.wa_outbox` (production
-- 2026-09-13: it exists only in public), and the two types are written as
-- the SQL keywords TIMESTAMP WITH TIME ZONE and NUMERIC, which the parser
-- binds to pg_catalog directly. Nothing in this file resolves through the
-- connection's search_path.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

ALTER TABLE public.wa_outbox ADD COLUMN abstained_at TIMESTAMP WITH TIME ZONE NULL;
ALTER TABLE public.wa_outbox ADD COLUMN evidence_score NUMERIC NULL;

-- === ROLLBACK ===
-- For isolated up/down/up validation. In production the routine rollback of
-- the abstain record is reverting B2.3b (the writer) while KEEPING these
-- nullable columns and the applied history; dropping them there is a
-- separately authorized destructive operation after dependent writers are
-- drained (B2-engine.md §3), never part of a routine rollback.
SET LOCAL lock_timeout = '5s';
ALTER TABLE public.wa_outbox DROP COLUMN IF EXISTS evidence_score;
ALTER TABLE public.wa_outbox DROP COLUMN IF EXISTS abstained_at;
