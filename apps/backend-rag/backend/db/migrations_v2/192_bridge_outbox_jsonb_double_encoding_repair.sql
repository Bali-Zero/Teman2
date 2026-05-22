-- migration 192_bridge_outbox_jsonb_double_encoding_repair
-- Data-only repair for the jsonb double-encoding regression in bridge_outbox
-- discovered 2026-05-21 during NB automations audit
-- (research/operations/2026-05-21-nb-automations-audit.md).
--
-- Same root cause as migration 174 (intel_lake) — the asyncpg pool registers
-- a jsonb codec with `encoder=json.dumps` in service_initializer.py's
-- init_db_connection, and `apps/backend-rag/backend/services/bridge/outbox.py
-- :insert_outbox_event` ALSO called `json.dumps(payload)` before passing it
-- to `$2::jsonb`. Result: payload serialized twice, stored as jsonb *string*
-- scalar (e.g. `"{\"client_id\":\"...\"}"`) instead of a jsonb *object*.
--
-- Downstream `mata_garuda.bridge.nerve.pull_once` decoded the column,
-- received a `str` instead of a `dict`, crashed on `**payload` with
-- `TypeError: 'str' object is not a mapping`, and refused to advance the
-- cursor (all-or-nothing semantics — see nerve.py:179-190). This left the
-- Fly→Pro NLM feed stuck since 2026-05-06 (~15 days), 5 NB-INTEL notebooks
-- not receiving new sources, 64K+ daily error lines, ~47MB error log/day.
--
-- The code fix (same PR): `outbox.py:insert_outbox_event` now passes the
-- raw dict; `outbox.py:fetch_outbox_events` defensively unwraps `str`
-- payloads via `json.loads` so the consumer always sees a dict regardless
-- of which side gets repaired first during rolling deploy.
--
-- This migration repairs already-written rows. Each broken value is a valid
-- JSON document, so `col #>> '{}'` extracts the inner text and `::jsonb`
-- re-parses it into the correct object form.
--
-- Idempotent: the `WHERE` guard restricts to `jsonb_typeof = 'string'`
-- AND inner re-parse is `object`, so re-runs are no-ops on already-repaired
-- rows (which are `object`, not `string`).
--
-- Rolling-deploy race: bridge_outbox writes are produced by EventBus
-- handlers in `services/events/handlers/_core.py` and by
-- `services/bridge/low_confidence_emitter.py`. During the 1-3 minute
-- rollout window, old-code instances may still write new double-encoded
-- rows. A second manual run after full rollout is safe.

-- Defensive guard: `bridge_outbox` is created by legacy migration 107
-- (`apps/backend-rag/backend/migrations/migration_107_bridge_outbox.py`)
-- which lives in the legacy .py system and is NOT auto-discovered by the
-- v2 runner (`migration_manager.py:discover_migrations` globs only
-- `migrations_v2/*.sql`). Mig 107 was applied manually on prod pre-
-- 2026-04-18 (table exists in production), but fresh CI Postgres does
-- NOT have it. Without this guard, `UPDATE bridge_outbox …` aborts the
-- entire migration run with `relation "bridge_outbox" does not exist`
-- and the suite stops at mig 192 forever. The IF NOT EXISTS check makes
-- this migration a no-op when the table is absent — repair will run
-- when (if) mig 107 is promoted to v2 (separate ticket).
DO $$
DECLARE
    n_repaired bigint;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'bridge_outbox'
    ) THEN
        RAISE NOTICE 'm192 jsonb repair: bridge_outbox absent — skipping (legacy mig 107 not yet promoted to v2)';
        RETURN;
    END IF;

    UPDATE bridge_outbox
       SET payload = (payload #>> '{}')::jsonb
     WHERE jsonb_typeof(payload) = 'string'
       AND jsonb_typeof((payload #>> '{}')::jsonb) = 'object';
    GET DIAGNOSTICS n_repaired = ROW_COUNT;

    RAISE NOTICE 'm192 jsonb repair: bridge_outbox.payload repaired=%',
        n_repaired;
END $$;

-- === ROLLBACK ===
-- No-op: this migration only repairs malformed data into its correct
-- shape. Re-introducing the double-encoded form would re-create the bug,
-- so rollback intentionally does nothing.
SELECT 1;
