-- 184_reconcile_182_tracking_divergence.sql
--
-- Production had migration_number 182 recorded in the canonical
-- schema_migrations table as 182_companies_tax_dept_folder, but missing from
-- the legacy _schema_versions table used by the release runner. That makes
-- backend.db.schema_audit fail with tracking_divergence_canonical_only after
-- otherwise-successful deploy migrations.
--
-- This migration reconciles only the tracking ledger. It does not change any
-- application tables.

SET lock_timeout = '5s';
SET statement_timeout = '30s';

INSERT INTO _schema_versions (
    migration_name,
    migration_number,
    executed_at,
    checksum,
    description,
    execution_time_ms,
    rollback_sql,
    applied_by
)
SELECT
    sm.migration_name,
    sm.migration_number,
    COALESCE(sm.executed_at, NOW()),
    sm.checksum,
    COALESCE(
        sm.description,
        'Backfilled from schema_migrations by 184_reconcile_182_tracking_divergence'
    ),
    sm.execution_time_ms,
    sm.rollback_sql,
    'migration-184-ledger-reconcile'
FROM schema_migrations sm
WHERE sm.migration_number = 182
  AND NOT EXISTS (
      SELECT 1
      FROM _schema_versions sv
      WHERE sv.migration_number = 182
  )
ON CONFLICT (migration_name) DO NOTHING;

-- === ROLLBACK ===
-- Intentionally no-op. Removing the backfilled 182 tracking row would recreate
-- the production schema_audit failure that this migration fixes.
