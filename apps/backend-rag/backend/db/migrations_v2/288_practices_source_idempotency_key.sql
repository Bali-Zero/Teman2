-- ============================================================================
-- 288 — give `practices` the idempotency authority the L7 CRM handoff needs
--
-- `services/garuda_ops/ports.py::CrmWriter` states the contract in its own
-- docstring, and it is not advisory:
--
--     "CrmHandoffService calls find_practice_by_source_idempotency_key then
--      create_client_and_practice as two separate awaits — this is
--      check-then-act, not atomic. [...] A real Postgres implementation MUST
--      enforce this at the database, e.g. a UNIQUE constraint on the
--      idempotency key digest plus INSERT ... ON CONFLICT DO NOTHING
--      RETURNING id, so the DB — not this two-step dance — is the single
--      idempotency authority."
--
-- Measured before writing this file: `practices` has NO unique constraint of
-- any kind and no idempotency column, so today the only implementations of
-- that port are in-memory test fakes, and an adapter written against the
-- table as it stands would reproduce the exact race the port warns about
-- while passing every existing single-threaded test. This migration supplies
-- the missing authority; the adapter that uses it lands in the same PR.
--
-- WHY NULLABLE, AND WHY A PARTIAL INDEX. Every practice row that already
-- exists was created by a human through the CRM, not by a GARUDA order, and
-- has no source event to key on. A NOT NULL column would need a backfilled
-- sentinel, and a sentinel repeated across rows is exactly what a UNIQUE
-- index forbids — so the column is nullable and the index is partial. In
-- Postgres a plain UNIQUE index already treats NULLs as distinct, so the
-- `WHERE ... IS NOT NULL` clause does not change WHICH rows can collide; it
-- keeps the index off the permanently-NULL human-created majority, and it
-- states the intent for the next reader instead of leaving it as folklore.
--
-- WHY NOT `CONCURRENTLY`. `db/migration_base.py:511` runs every migration
-- inside `async with conn.transaction()`, and `CREATE INDEX CONCURRENTLY`
-- cannot run inside a transaction block — the same constraint migration 279
-- already records for itself. This index is therefore created plainly and
-- holds a write lock on `practices` for its duration.
-- ============================================================================

ALTER TABLE public.practices
    ADD COLUMN IF NOT EXISTS source_idempotency_key TEXT;

COMMENT ON COLUMN public.practices.source_idempotency_key IS
    'GARUDA L7 handoff only: the committed payment.paid journal event identity '
    '(events.yaml x-idempotency-source for PracticeReceived) that produced this '
    'practice. NULL for every practice created by a human through the CRM. '
    'The partial unique index below is what makes the CRM write idempotent — '
    'see services/garuda_ops/ports.py::CrmWriter.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_practices_source_idempotency_key
    ON public.practices (source_idempotency_key)
    WHERE source_idempotency_key IS NOT NULL;

-- === ROLLBACK ===
-- DROP INDEX IF EXISTS public.uq_practices_source_idempotency_key;
-- ALTER TABLE public.practices DROP COLUMN IF EXISTS source_idempotency_key;
