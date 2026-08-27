-- 296_wa_broker_jobs_live_only_unique.sql
-- BOT-V4 S2 — retry budget for the codex leg (gradino 2/5 of the Gemini
-- retirement plan). research/operations/2026-08-19-bot-chatgpt-provider-
-- broker-spec.md still describes "ONE codex leg per outbox row, ever"
-- (migration 270's header, uq_broker_jobs_serve_outbox). That invariant is
-- what turned every RECOVERABLE codex failure into a silent Gemini
-- fall-off (offer_job's second offer read generation_route IS NOT NULL and
-- returned ALREADY_SPENT with no job_id — not even a way to reattach a
-- still-running job). With Gemini scheduled for permanent removal from
-- this channel, that same fall-off would become a mute customer instead.
--
-- New invariant, same spirit, narrower scope: ONE codex leg IN FLIGHT per
-- outbox row at a time, up to wa_outbox's own MAX_ATTEMPTS (5) legs total
-- over the row's life — wa_codex_leg.py's offer_job now offers a NEW leg
-- once the PRIOR one for the same outbox_id is terminal (consumed/expired/
-- failed), and reattaches (rather than re-offering) to one still alive.
--
-- Why a new broker_jobs ROW per leg, not an in-place reset of the one row
-- (the no-migration option): the wider option was reusing an existing
-- row column, e.g. wa_outbox.attempts, as the budget counter — but that
-- counter is written by the OUTER retry ladder only when a claim's
-- generation genuinely raises, and a worker crash between a durable offer
-- and that raise (stale-claim reclaim, see wa_outbox_worker.py's
-- claim_expires_at sweep) resets wa_outbox.status to 'pending' WITHOUT
-- ever touching attempts — so attempts cannot durably bound how many
-- codex legs a row has actually spent across a crash/reclaim cycle. A new
-- broker_jobs row is written durably by the SAME INSERT that creates the
-- leg, so counting rows for an outbox_id survives that crash by
-- construction. It also keeps each attempt's own error_class/outcome/
-- exec_ms — an in-place reset would have to null and overwrite that
-- history on every retry, destroying the audit trail this table exists to
-- carry (migration 270's header, "PII surface with a lifecycle").
--
-- The DDL: uq_broker_jobs_serve_outbox was NEVER scoped to "one live job"
-- — it was outbox_id-unique across ALL states, forever (migration 270's
-- own header: "the durable wa_outbox.generation_route marker ... is what
-- makes the invariant HISTORICAL"). That is exactly the invariant this
-- migration retires. Replaced with a partial index scoped to the LIVE
-- states only (offered/leased/completed_pending_consume) — still exactly
-- one in-flight serve job per outbox row (the property offer_job's
-- MAX_DEPTH=1 global admission cap and the advisory xact lock already
-- assume), but a second, third, ... row is now permitted once the prior
-- one is terminal. The application-level cap on TOTAL rows per outbox_id
-- (mirroring wa_outbox_worker.MAX_ATTEMPTS) lives in offer_job, not here —
-- the DB only ever enforced "one live", never "N total".
--
-- The table ships (still) near-empty: WA_GENERATION_PROVIDER stays unset
-- in every environment until gradino 5 flips it, so this DROP+CREATE INDEX
-- takes its ACCESS EXCLUSIVE lock on a table with no meaningful traffic
-- (same premise migrations 272/274 documented for this table).

DROP INDEX IF EXISTS uq_broker_jobs_serve_outbox;

CREATE UNIQUE INDEX IF NOT EXISTS uq_broker_jobs_serve_outbox_live
    ON broker_jobs (outbox_id)
    WHERE mode = 'serve'
      AND state IN ('offered', 'leased', 'completed_pending_consume');

-- === ROLLBACK ===
--
-- NOT ALWAYS REVERSIBLE (documented, not fixed — Kimi K3 cross-family
-- review round 2): once this migration has been live long enough for a
-- single outbox_id to accumulate MORE THAN ONE broker_jobs row (mode=
-- 'serve') — the entire point of this change — the CREATE UNIQUE INDEX
-- below fails outright with a duplicate-key error, because a row set
-- unique on bare outbox_id can no longer be built over data that already
-- violates it. There is no forward-compatible down-migration for that
-- state: reverting the SCHEMA requires first reverting the DATA (deleting
-- every non-latest broker_jobs row per outbox_id, which throws away the
-- audit trail the multi-row design exists to keep) or accepting the
-- rollback cannot run until the offending rows have aged out via the
-- normal 7-day retention sweep. A rollback that fails loudly here is the
-- INTENDED behavior — silently succeeding on an index that doesn't
-- actually hold the caller's assumed invariant would be worse.

DROP INDEX IF EXISTS uq_broker_jobs_serve_outbox_live;

CREATE UNIQUE INDEX IF NOT EXISTS uq_broker_jobs_serve_outbox
    ON broker_jobs (outbox_id)
    WHERE mode = 'serve';
