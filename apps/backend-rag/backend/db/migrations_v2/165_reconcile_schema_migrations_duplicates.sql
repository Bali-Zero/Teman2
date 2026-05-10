-- Migration 165: reconcile duplicate rows in schema_migrations
--
-- Context:
--   During the migration-runner transition, `schema_migrations` accumulated
--   historical rows that reuse the same migration_number for unrelated old
--   migrations. `_schema_versions` is the release runner's current ledger and
--   has one canonical row per migration_number. `backend.db.schema_audit` now
--   fails when either tracking table contains duplicate numbers, so this
--   migration reconciles the canonical table without losing historical trace.
--
-- Safety:
--   - Only `schema_migrations` tracking rows are moved.
--   - The moved rows are copied into `schema_migrations_reconciliation_archive`
--     before deletion.
--   - The physical application tables are untouched.
--   - Re-running is a no-op after the first successful run.
--
-- Why these keepers:
--   The keeper names match the `_schema_versions` row for each duplicate
--   migration_number observed in prod/local on 2026-05-10. For migration 130,
--   the keeper also matches the currently tracked migrations_v2 file:
--   `130_crm_guardian_summary_queue.sql`.

SET lock_timeout = '5s';
SET statement_timeout = '60s';

CREATE TABLE IF NOT EXISTS schema_migrations_reconciliation_archive (
    archive_id SERIAL PRIMARY KEY,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archive_reason TEXT NOT NULL,
    source_id INTEGER,
    migration_name VARCHAR(255) NOT NULL,
    migration_number INTEGER,
    applied_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    checksum VARCHAR(64),
    description TEXT,
    execution_time_ms INTEGER,
    rollback_sql TEXT,
    applied_by VARCHAR(255),
    UNIQUE (archive_reason, migration_name)
);

WITH canonical_keep AS (
    SELECT *
    FROM (
        VALUES
            (2,   '002_portal_sync_tables'),
            (3,   '003_portal_performance_indexes'),
            (5,   '005_workflow_analytics'),
            (6,   '006_performance_indexes_advanced'),
            (7,   '007_omnichannel_workflow'),
            (8,   '008_generals_foundation'),
            (36,  '036_add_tax_id_to_clients'),
            (37,  '037_federation_messages'),
            (38,  '038_legal_instruments'),
            (39,  '039_workflow_jobs'),
            (40,  '040_documents_drive_integrity'),
            (41,  '041_workflow_jobs_context'),
            (42,  '042_clients_tax_ids'),
            (43,  '043_invoices_table'),
            (44,  '044_cleanup_practices_invoice_jsonb'),
            (130, '130_crm_guardian_summary_queue')
    ) AS keepers(migration_number, migration_name)
),
rows_to_archive AS (
    SELECT sm.*
    FROM schema_migrations sm
    JOIN canonical_keep ck USING (migration_number)
    WHERE sm.migration_name <> ck.migration_name
)
INSERT INTO schema_migrations_reconciliation_archive (
    archive_reason,
    source_id,
    migration_name,
    migration_number,
    applied_at,
    executed_at,
    checksum,
    description,
    execution_time_ms,
    rollback_sql,
    applied_by
)
SELECT
    '165_schema_migrations_duplicate_number_reconcile',
    id,
    migration_name,
    migration_number,
    applied_at,
    executed_at,
    checksum,
    description,
    execution_time_ms,
    rollback_sql,
    applied_by
FROM rows_to_archive
ON CONFLICT (archive_reason, migration_name) DO NOTHING;

WITH canonical_keep AS (
    SELECT *
    FROM (
        VALUES
            (2,   '002_portal_sync_tables'),
            (3,   '003_portal_performance_indexes'),
            (5,   '005_workflow_analytics'),
            (6,   '006_performance_indexes_advanced'),
            (7,   '007_omnichannel_workflow'),
            (8,   '008_generals_foundation'),
            (36,  '036_add_tax_id_to_clients'),
            (37,  '037_federation_messages'),
            (38,  '038_legal_instruments'),
            (39,  '039_workflow_jobs'),
            (40,  '040_documents_drive_integrity'),
            (41,  '041_workflow_jobs_context'),
            (42,  '042_clients_tax_ids'),
            (43,  '043_invoices_table'),
            (44,  '044_cleanup_practices_invoice_jsonb'),
            (130, '130_crm_guardian_summary_queue')
    ) AS keepers(migration_number, migration_name)
)
DELETE FROM schema_migrations sm
USING canonical_keep ck
WHERE sm.migration_number = ck.migration_number
  AND sm.migration_name <> ck.migration_name;

CREATE UNIQUE INDEX IF NOT EXISTS uq_schema_migrations_migration_number
    ON schema_migrations (migration_number)
    WHERE migration_number IS NOT NULL;

INSERT INTO _schema_versions (
    migration_name,
    migration_number,
    description,
    applied_by,
    checksum
)
VALUES (
    '165_reconcile_schema_migrations_duplicates',
    165,
    'Reconcile duplicate schema_migrations migration_number rows',
    'migration-165',
    'tracked-by-migration-165'
)
ON CONFLICT (migration_name) DO NOTHING;

-- === ROLLBACK ===
SET lock_timeout = '5s';
SET statement_timeout = '60s';

DROP INDEX IF EXISTS uq_schema_migrations_migration_number;

INSERT INTO schema_migrations (
    migration_name,
    migration_number,
    applied_at,
    executed_at,
    checksum,
    description,
    execution_time_ms,
    rollback_sql,
    applied_by
)
SELECT
    migration_name,
    migration_number,
    applied_at,
    executed_at,
    checksum,
    description,
    execution_time_ms,
    rollback_sql,
    applied_by
FROM schema_migrations_reconciliation_archive
WHERE archive_reason = '165_schema_migrations_duplicate_number_reconcile'
ON CONFLICT (migration_name) DO NOTHING;

DELETE FROM _schema_versions
WHERE migration_name = '165_reconcile_schema_migrations_duplicates';
