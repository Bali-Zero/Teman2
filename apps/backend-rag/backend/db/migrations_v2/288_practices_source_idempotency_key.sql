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
-- Measured before writing this file — and stated narrowly, because the first
-- draft of this comment said `practices` had "NO unique constraint of any
-- kind" and that is FALSE. It has two: `practices_pkey` (the integer
-- surrogate PK) and `ix_practices_uuid` (a generated UUID). What it has none
-- of is a unique constraint on any key the CALLER supplies: both existing
-- ones are produced BY the insert, so neither can arbitrate an ON CONFLICT
-- against an identity the caller already knows. That is the gap, and it is
-- enough of a gap — today the only implementations of the port are in-memory
-- test fakes, and an adapter written against the table as it stands would
-- reproduce the exact race the port warns about while passing every existing
-- single-threaded test. This migration supplies the missing authority; the
-- adapter that uses it lands in the same PR.
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
-- already records for itself.
--
-- WHAT THAT ACTUALLY LOCKS — stated precisely, because an earlier draft of
-- this comment said "a write lock ... for its duration" and that was wrong on
-- BOTH counts. `ALTER TABLE ... ADD COLUMN` takes ACCESS EXCLUSIVE, which
-- blocks SELECTs too, not merely writes; and Postgres holds a lock to the END
-- OF THE TRANSACTION, so because the runner wraps this whole file in one
-- transaction the ACCESS EXCLUSIVE taken by the ALTER is still held through
-- the COMMENT and through the index build. For the duration of this migration
-- `practices` is UNREADABLE, not just unwritable.
--
-- Why that is acceptable HERE, and why this is not a general licence: the
-- column is created empty in the same transaction, so at index-build time
-- every row has `source_idempotency_key IS NULL` and the partial predicate
-- matches ZERO rows. The build is a scan with nothing to insert, not a sort
-- proportional to the live table. The exposure is short — but it is a read
-- outage, so run this against a busy `practices` in a low-traffic window
-- rather than assuming the CRM and the portal can read through it.
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
