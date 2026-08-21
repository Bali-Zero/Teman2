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
--
-- squawk changing-column-type is suppressed on BOTH statements for that
-- same reason: the ACCESS EXCLUSIVE lock it warns about is on a table with
-- zero live traffic and zero other readers (censused above), and the type
-- change IS the point of the migration. Each ALTER is kept on ONE line
-- because squawk-cli 2.62.0 only honors the ignore comment for a
-- single-line statement (measured: the identical two-line form still
-- fires the rule).

-- squawk-ignore changing-column-type
ALTER TABLE broker_jobs ALTER COLUMN package TYPE TEXT USING package::text;

-- === ROLLBACK ===

-- squawk-ignore changing-column-type
ALTER TABLE broker_jobs ALTER COLUMN package TYPE JSONB USING package::jsonb;
