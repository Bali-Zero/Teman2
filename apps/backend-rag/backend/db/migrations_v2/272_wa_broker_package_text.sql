-- 272_wa_broker_package_text.sql
-- BOT-V4 S2 PR-2 (Codex re-verdict r4): the package is a SEALED ENVELOPE —
-- the broker verifies its bytes against package_hash (computed once, in
-- wa_package_builder, over the canonical serialization). Storing it as
-- JSONB destroyed byte fidelity by construction: Postgres normalizes key
-- order and whitespace on ingest, so the package::text handed back at
-- /claim could differ byte-for-byte from what was hashed —
-- '{"history": [], "chunks": []}' comes back '{"chunks": [], "history": []}'
-- (measured on PG 15) — and every hash verification would reject a valid
-- package. Nothing anywhere queries INSIDE package (censused 2026-08-19:
-- zero `->`/`?`/`@>`/jsonb_* consumers, zero indexes), so jsonb bought
-- nothing and cost the one property the column exists to carry.
-- evidence_inputs keeps jsonb: it has no byte-hash contract.
-- The table ships dark (flag-OFF lane, no broker daemon yet): the rewrite
-- ALTER takes is on an empty-or-tiny table.

ALTER TABLE broker_jobs
    ALTER COLUMN package TYPE TEXT USING package::text;

-- === ROLLBACK ===

ALTER TABLE broker_jobs
    ALTER COLUMN package TYPE JSONB USING package::jsonb;
