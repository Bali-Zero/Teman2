-- migration 175_analytics_jsonb_double_encoding_repair
-- Data-only repair for the jsonb double-encoding regression in the
-- analytics repositories (2026-05-14). Companion to migration 174, which
-- fixed the same pattern in the Intel Lake tables.
--
-- Root cause: the app/runtime asyncpg pool registers a jsonb codec with
-- `encoder=json.dumps` (backend/app/core/database.py +
-- service_initializer.py). Two analytics repositories also called
-- `json.dumps(...)` on the value before binding it:
--   - workflow_analytics_repository.py:47 → workflow_analytics.steps_json
--   - query_analytics_repository.py:54    → query_analytics.metadata
-- The value was serialized twice and stored as a jsonb *string* scalar
-- instead of a jsonb array/object. Any `steps_json -> ...` path query or
-- `metadata ? 'user_email'` operator silently returns nothing.
--
-- The code fix ships in the same PR. This migration repairs the rows
-- already written with the broken path.
--
-- Empirical scope verified on Fly PG 2026-05-14:
--   workflow_analytics.steps_json = string : 3470 rows (inner type: array)
--   query_analytics.metadata      = string : 6055 rows (inner type: object)
-- = 9525 rows. Note steps_json inner type is `array`, not `object`, so the
-- guard below accepts BOTH `object` and `array` (every valid container
-- jsonb type).
--
-- ABORT-SAFETY: `(col #>> '{}')::jsonb` raises on a non-JSON inner string,
-- and an unhandled raise inside a DO block rolls back EVERY repair in the
-- block. To stay abort-safe across all 9525 rows the WHERE clause uses a
-- cheap regex pre-filter (`~ '^\s*[\[{]'`) so the `::jsonb` cast is only
-- ever evaluated on inner text that starts with `[` or `{` — i.e. a
-- container. Anything else (deeper-encoded scalar, `"null"`, a stray
-- non-JSON string) is skipped, not cast, so the migration cannot abort.
-- Empirically 0 rows fail the pre-filter today (verified 2026-05-14) — the
-- pre-filter is defense-in-depth against a corrupt row we have not seen.
--
-- Idempotent: the `jsonb_typeof(col) = 'string'` guard means a second run
-- is a no-op (already-repaired rows are object/array, not string). The
-- `to_regclass` guards (see DO block) additionally make it a clean no-op
-- on databases where the legacy analytics tables were never created
-- (e.g. the CI test DB, which only applies migrations_v2/).
--
-- Rolling-deploy race: old-code instances may write new double-encoded
-- rows during the 1-3 minute window between this migration and full code
-- rollout. The RAISE NOTICE below reports the count; a second manual run
-- after full rollout is safe (idempotent). Given ~9.5k rows the window's
-- contribution is negligible.

-- TABLE-EXISTENCE GUARD: `workflow_analytics` / `query_analytics` are
-- created by a LEGACY migration (`005_workflow_analytics`, tracked in
-- `_schema_versions`), NOT by the `migrations_v2/` runner. The CI test DB
-- (`nuzantara_test`) only applies `migrations_v2/`, so these tables are
-- absent there — a bare UPDATE would raise `relation does not exist` and
-- fail the migration. This is a data-only repair: if the table is not
-- present there is simply nothing to repair, so each block is gated on
-- `to_regclass(...)` and is a clean no-op when the table is missing.
DO $$
DECLARE
    n_steps    bigint;
    n_metadata bigint;
BEGIN
    IF to_regclass('public.workflow_analytics') IS NOT NULL THEN
        UPDATE workflow_analytics
           SET steps_json = (steps_json #>> '{}')::jsonb
         WHERE jsonb_typeof(steps_json) = 'string'
           AND (steps_json #>> '{}') ~ '^\s*[\[{]'
           AND jsonb_typeof((steps_json #>> '{}')::jsonb) IN ('object', 'array');
        GET DIAGNOSTICS n_steps = ROW_COUNT;
    ELSE
        n_steps := -1;  -- sentinel: table absent (CI test DB)
    END IF;

    IF to_regclass('public.query_analytics') IS NOT NULL THEN
        UPDATE query_analytics
           SET metadata = (metadata #>> '{}')::jsonb
         WHERE jsonb_typeof(metadata) = 'string'
           AND (metadata #>> '{}') ~ '^\s*[\[{]'
           AND jsonb_typeof((metadata #>> '{}')::jsonb) IN ('object', 'array');
        GET DIAGNOSTICS n_metadata = ROW_COUNT;
    ELSE
        n_metadata := -1;  -- sentinel: table absent (CI test DB)
    END IF;

    RAISE NOTICE 'm175 analytics jsonb repair: workflow_analytics.steps_json=% query_analytics.metadata=% (-1 = table absent, no-op)',
        n_steps, n_metadata;
END $$;

-- === ROLLBACK ===
-- No-op: this migration only repairs malformed data into its correct
-- shape. Re-introducing the double-encoded form would re-create the bug,
-- so rollback intentionally does nothing.
SELECT 1;
