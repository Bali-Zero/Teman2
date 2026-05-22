-- 193_reconcile_107_bridge_outbox_tracking.sql
-- Backfill `schema_migrations` for legacy migration 107 when it was applied
-- manually on production and recorded only in `_schema_versions`.
--
-- WHY THIS EXISTS (Codex panelist finding 2026-05-23):
-- `MigrationManager.apply_all_pending()` computes pending migrations from
-- `_schema_versions.migration_number`, not from `schema_migrations`. On prod
-- with legacy `_schema_versions(107)` already present, the companion
-- `107_bridge_outbox.sql` is SKIPPED by number and never logs a row into
-- `schema_migrations`. `schema_audit.py` treats tracker divergence as an error.
-- This file repairs the divergence in a separate migration number that the
-- runner WILL execute (193 is fresh on both prod and fresh-CI).
--
-- SAFE TIMEOUTS: small `lock_timeout` and `statement_timeout` because this is
-- a metadata-only INSERT — should complete in milliseconds.

SET lock_timeout = '5s';
SET statement_timeout = '30s';

INSERT INTO schema_migrations (
    migration_name,
    migration_number,
    executed_at,
    checksum,
    description,
    execution_time_ms,
    rollback_sql
)
SELECT
    '107_bridge_outbox',
    107,
    COALESCE(sv.executed_at, NOW()),
    COALESCE(NULLIF(sv.checksum, ''), 'legacy-107-bridge-outbox'),
    'Backfilled from _schema_versions by 193_reconcile_107_bridge_outbox_tracking',
    COALESCE(sv.execution_time_ms, 0),
    NULL
FROM _schema_versions sv
WHERE sv.migration_number = 107
  AND NOT EXISTS (
      SELECT 1 FROM schema_migrations sm WHERE sm.migration_number = 107
  )
ON CONFLICT (migration_name) DO NOTHING;

-- === ROLLBACK ===
-- No-op. Removing this ledger row would recreate the schema_audit tracker
-- divergence this migration was written to repair.
SELECT 1;
