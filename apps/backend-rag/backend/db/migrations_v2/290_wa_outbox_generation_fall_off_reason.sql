-- 290_wa_outbox_generation_fall_off_reason.sql
--
-- THE DEFECT (2026-08-27, measured live): wa_outbox row 346 was answered,
-- but not by the codex broker leg — generation_route stayed NULL and no
-- broker_jobs row was ever created, so the fall-off happened at one of the
-- codex leg's PRE-OFFER route-decision conditions (wa_codex_leg.py's own
-- docstring: autoreply flag, provider switch, 24h-window margin, or the
-- context-package build). WHICH one refused is unrecoverable after the
-- fact: it exists only in a Fly log line, and that log's retained window
-- was ~1 minute. `llm_cost_events` cannot substitute — it only sees calls
-- that reached a generator. This makes the fall-off reason durable, per
-- row, surviving the row the way its other columns do.
--
-- Deliberately a SEPARATE column from generation_route, not a repurposing
-- of it (CLAUDE.md/bot-corner constraint): generation_route is a CAS fence
-- half — set ONCE, at offer time, under `AND generation_route IS NULL`,
-- and read back by offer_job's own second-offer guard (270/296) to decide
-- ALREADY_SPENT. Recording a fall-off reason on EVERY non-served attempt,
-- including all four pre-offer conditions, would either corrupt that fence
-- (if written through the same column) or force the fence's CAS to ignore
-- a value it currently trusts as "untouched". A second, independent column
-- carries no such risk: it is written best-effort, from a fresh connection,
-- and nothing else on the offer path reads it.
--
-- generation_fall_off_reason is a bounded, non-PII enum: log lines and this
-- column carry outbox ids, thread ids and short codes only (wa_codex_leg's
-- own PII-discipline paragraph) — never query text, customer history, or
-- phone numbers. The raw strings wa_codex_leg.CodexLegResult.reason/.fail
-- already produce (e.g. "offer_uncertain:TimeoutError",
-- "wait:FAILED:upstream_5xx") are themselves built only from fixed
-- literals, typed exception class names and typed enum values — never from
-- message content — but they are still open-ended text (an exception class
-- name is not drawn from a closed set the DB can enumerate). The backend
-- normalizes each one to one of the 20 category codes below
-- (wa_codex_leg._normalize_fall_off_reason, mirrored in the CHECK) before
-- writing, so the column itself can never carry anything wider than this
-- fixed vocabulary regardless of what a future exception type is named.
--
-- Nullable, no default, no backfill: mixed-version deploys read-safe in
-- both directions, no table rewrite (spec 7 precedent, migration 270).
-- generation_fall_off_at is the write time of the LAST recorded fall-off
-- on this row — it is not cleared on a later successful attempt, so a row
-- that fell off once and then succeeded still shows what happened; that is
-- the point (constraint 2 of the mandate: pre-offer fall-offs, the exact
-- shape of row 346, must be recoverable too, not only offer refusals).

ALTER TABLE wa_outbox ADD COLUMN IF NOT EXISTS generation_fall_off_reason TEXT;
ALTER TABLE wa_outbox ADD COLUMN IF NOT EXISTS generation_fall_off_at TIMESTAMPTZ;

ALTER TABLE wa_outbox
    DROP CONSTRAINT IF EXISTS wa_outbox_generation_fall_off_reason_check;
ALTER TABLE wa_outbox
    ADD CONSTRAINT wa_outbox_generation_fall_off_reason_check
    CHECK (generation_fall_off_reason IS NULL OR generation_fall_off_reason IN (
        'provider_not_codex',
        'standing_autoreply_disabled',
        'standing_no_customer_message',
        'window_margin',
        'package_build_error',
        'package_unbuildable',
        'build_contract_break',
        'offer_acquire_error',
        'offer_uncertain',
        'offer_refused',
        'offer_contract_break',
        'wait_error',
        'wait_failed',
        'stand_down_drift',
        'stand_down_fence_lost',
        'post_completion_error',
        'consume_lost',
        'finalize_defect',
        'internal_error',
        'unknown'
    ));

-- === ROLLBACK ===

ALTER TABLE wa_outbox
    DROP CONSTRAINT IF EXISTS wa_outbox_generation_fall_off_reason_check;
ALTER TABLE wa_outbox DROP COLUMN IF EXISTS generation_fall_off_reason;
ALTER TABLE wa_outbox DROP COLUMN IF EXISTS generation_fall_off_at;
