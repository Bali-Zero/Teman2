-- Migration 270: broker_jobs transport + wa_outbox.generation_route (BOT-V4 S2)
--
-- Flag-OFF build. Transport table for the ChatGPT-provider broker leg of the
-- WA outbox worker. Spec (panel-signed, 4 adversarial rounds):
-- research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md (#4333).
--
-- Design invariants this DDL enforces (spec section in parentheses):
-- - wa_outbox gains NO new status value (C11): the broker is reached through
--   this separate table; the outbox row never leaves its existing state
--   machine. The only wa_outbox change is one nullable additive column,
--   generation_route, written once at offer time (spec 2, retry budget).
-- - ONE codex leg per outbox row, ever (spec 2): uq_broker_jobs_serve_outbox
--   makes a second serve-mode job for the same row impossible AT THE DB,
--   not just in worker logic.
-- - The job row is a PII surface with a lifecycle, not plumbing (Codex NEW-1):
--   payload columns (package, evidence_inputs, result_text) are nullable so
--   every transition to a terminal state can NULL them atomically in the same
--   UPDATE. Terminal rows keep only ids, hashes, timestamps and typed outcome;
--   a retention sweep removes them after 7 days (worker-side, effect-verified).
-- - States (spec 2 named protocol, Codex r3-NEW-1): offered -> leased ->
--   completed_pending_consume -> consumed | expired | failed.
--   completed_pending_consume is NON-terminal: it holds result_text under the
--   fence until the single consumer (the worker's finalization) CASes it to
--   consumed. The reaper expires anything stale, with the same payload NULLing.
-- - mode 'shadow' (S3c) is declared now so the CHECK never needs an
--   in-place widening later; S2 only ever writes 'serve'. Shadow jobs carry
--   their own expires_at (Kimi N1); serve jobs are bounded by deadline_at.
--
-- wa_broker_gauge is the single-row admission/liveness gauge (spec 2.1,
-- Codex H12): every /claim poll upserts it (broker_last_seen_at +
-- queue_state); the worker offers only when the stored gauge predicts a
-- start within budget, and a stale broker_last_seen_at (> 2x poll interval)
-- reads as "broker absent" -> direct Gemini. The row is seeded lazily by
-- backend code (ON CONFLICT upsert on first /claim) — no DML in this
-- migration, deliberately. DB-atomicity of the offer-admission count is
-- taken via an advisory xact lock in the offering transaction (worker
-- code), not via this gauge.

BEGIN;

-- 1. Broker jobs: generation-subcontract transport (serve) + S3c shadow.
CREATE TABLE IF NOT EXISTS broker_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outbox_id BIGINT NOT NULL REFERENCES wa_outbox(id),
    thread_id BIGINT NOT NULL REFERENCES meta_inbox_threads(thread_id),
    mode TEXT NOT NULL DEFAULT 'serve'
        CHECK (mode IN ('serve', 'shadow')),
    state TEXT NOT NULL DEFAULT 'offered'
        CHECK (state IN ('offered', 'leased', 'completed_pending_consume',
                         'consumed', 'expired', 'failed')),

    -- PII payload (NULLed atomically on every transition to a terminal state)
    package JSONB,
    evidence_inputs JSONB,
    result_text TEXT,

    -- integrity + drift detection (frozen at offer time)
    package_hash TEXT NOT NULL,
    thread_epoch INT NOT NULL,

    -- serve-mode budget fence; shadow-mode rows use expires_at instead
    deadline_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,

    -- broker lease (set by /claim, checked by /complete)
    fence_token UUID,
    lease_expires_at TIMESTAMPTZ,

    -- /complete idempotency: same completion_key re-POST -> same 200 (spec 2)
    completion_key TEXT,

    -- observability at terminal (never client text)
    outcome TEXT,
    error_class TEXT,
    exec_ms INT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    leased_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    consumed_at TIMESTAMPTZ
);

-- ONE serve-mode codex leg per outbox row, enforced at the DB (spec 2).
CREATE UNIQUE INDEX IF NOT EXISTS uq_broker_jobs_serve_outbox
    ON broker_jobs (outbox_id)
    WHERE mode = 'serve';

-- Broker claim scan: oldest offered job first.
CREATE INDEX IF NOT EXISTS broker_jobs_offered_idx
    ON broker_jobs (created_at)
    WHERE state = 'offered';

-- Reaper scan: non-terminal rows by deadline.
CREATE INDEX IF NOT EXISTS broker_jobs_reaper_idx
    ON broker_jobs (deadline_at)
    WHERE state IN ('offered', 'leased', 'completed_pending_consume');

-- Retention sweep scan: terminal rows older than the 7d TTL.
CREATE INDEX IF NOT EXISTS broker_jobs_ttl_idx
    ON broker_jobs (created_at)
    WHERE state IN ('consumed', 'expired', 'failed');

-- 2. Single-row broker liveness/queue gauge (spec 2.1 admission). Seeded
-- lazily by backend code — see header note.
CREATE TABLE IF NOT EXISTS wa_broker_gauge (
    id SMALLINT PRIMARY KEY DEFAULT 1
        CHECK (id = 1),
    broker_last_seen_at TIMESTAMPTZ,
    in_flight INT NOT NULL DEFAULT 0,
    last_exec_ms INT,
    breaker_state TEXT NOT NULL DEFAULT 'closed'
        CHECK (breaker_state IN ('closed', 'open', 'half_open')),
    breaker_opened_at TIMESTAMPTZ,
    consecutive_failures INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Route marker on the serving row (spec 2 retry budget): set once, in the
-- same fenced transaction as the serve-job INSERT (worker code). NULL = this
-- row never spent its codex leg. Nullable + no default = pure additive, no
-- table rewrite, mixed-version deploys read-safe in both directions (spec 7).
ALTER TABLE wa_outbox ADD COLUMN IF NOT EXISTS generation_route TEXT;

COMMIT;

-- === ROLLBACK ===
-- Inline rollback per W42 lint requirement. To revert, run (manually, in a
-- transaction) the inverse of the DDL above, in reverse order: remove the
-- generation_route column from wa_outbox, then the wa_broker_gauge table,
-- then the broker_jobs table (its four indexes go with it). Statements
-- omitted verbatim because the guardrails hook blocks destructive SQL tokens
-- even in comments (same convention as migration 206). Additive-only forward
-- DDL: no data is rewritten, so the down-migration loses only broker
-- telemetry, never serving state.
