-- Migration 270: distinguish a successfully sent bot abstention from a normal
-- bot reply without changing wa_outbox's shared terminal status contract.
-- Nullable and additive: existing rows/readers need no backfill or changes.

ALTER TABLE wa_outbox
    ADD COLUMN IF NOT EXISTS abstained_at TIMESTAMPTZ;

-- === ROLLBACK ===
ALTER TABLE wa_outbox DROP COLUMN IF EXISTS abstained_at;
