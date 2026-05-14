-- migration 174_intel_lake_jsonb_double_encoding_repair
-- Data-only repair for the jsonb double-encoding regression (2026-05-14).
--
-- Root cause: the asyncpg pool registers a jsonb codec with
-- `encoder=json.dumps` (backend/app/core/database.py + service_initializer.py).
-- Two Intel Lake call sites also called `json.dumps(...)` on the value before
-- binding it:
--   - intel_lake_router.py:158  → routing_targets
--   - intel_lake_service.py:184,205 → raw_payload (intel_items + intel_observations)
-- The value was serialized twice and stored as a jsonb *string* scalar
-- (e.g. `"{}"`) instead of a jsonb *object* (`{}`). The Pro-local router
-- and nb-pusher then read `jsonb_typeof = 'string'` and could not extract
-- `nb_uuids`, so every affected item fell through to `needs_review`.
--
-- The code fix ships in the same PR. This migration repairs the rows
-- already written with the broken path. Each broken value is itself a
-- valid JSON document, so `col #>> '{}'` extracts the inner text and
-- `::jsonb` re-parses it into the correct object form.
--
-- Empirical scope verified on Fly PG 2026-05-14 — every string-typed value
-- in all three columns has `jsonb_typeof((col #>> '{}')::jsonb) = 'object'`,
-- i.e. exactly one extra encoding layer (no triple-encoding, no jsonb-null
-- scalars). The `WHERE` guard below additionally restricts to values whose
-- inner text re-parses as an `object`, so any future deeper-encoded or
-- non-object string scalar is skipped rather than aborting the migration.
--
-- Idempotent: the guard means a second run is a no-op (already-repaired
-- rows are `object`, not `string`).
--
-- Rolling-deploy race: the migration runner executes this before all Fly
-- instances have the fixed code. Old-code instances still serving
-- `intel_lake.event` / `observations` writes during the 1-3 minute rollout
-- window can write NEW double-encoded rows after this migration has run.
-- The migration is not re-run automatically — a second manual run after
-- full rollout is safe (idempotent). For a ~20-30 row corpus this is
-- acceptable; the RAISE NOTICE below lets the operator see the final count.

DO $$
DECLARE
    n_routing  bigint;
    n_items    bigint;
    n_obs      bigint;
BEGIN
    UPDATE intel_items
       SET routing_targets = (routing_targets #>> '{}')::jsonb
     WHERE jsonb_typeof(routing_targets) = 'string'
       AND jsonb_typeof((routing_targets #>> '{}')::jsonb) = 'object';
    GET DIAGNOSTICS n_routing = ROW_COUNT;

    UPDATE intel_items
       SET raw_payload = (raw_payload #>> '{}')::jsonb
     WHERE jsonb_typeof(raw_payload) = 'string'
       AND jsonb_typeof((raw_payload #>> '{}')::jsonb) = 'object';
    GET DIAGNOSTICS n_items = ROW_COUNT;

    UPDATE intel_observations
       SET raw_payload = (raw_payload #>> '{}')::jsonb
     WHERE jsonb_typeof(raw_payload) = 'string'
       AND jsonb_typeof((raw_payload #>> '{}')::jsonb) = 'object';
    GET DIAGNOSTICS n_obs = ROW_COUNT;

    RAISE NOTICE 'm174 jsonb repair: intel_items.routing_targets=% intel_items.raw_payload=% intel_observations.raw_payload=%',
        n_routing, n_items, n_obs;
END $$;

-- === ROLLBACK ===
-- No-op: this migration only repairs malformed data into its correct
-- shape. Re-introducing the double-encoded form would re-create the bug,
-- so rollback intentionally does nothing.
SELECT 1;
