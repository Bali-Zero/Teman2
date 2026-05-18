-- 184_reconcile_ghost_182_schema_versions.sql
--
-- Reconcile cross-table divergence introduced by ghost migration 182.
--
-- TIMELINE:
--   * PR #722 (DRAFT, feat/wr3-room-genesis, 2026-05-17 21:18) authored a
--     `182_wr3_eventbus_channels.sql` migration. Someone applied it manually
--     on Fly Postgres for testing, registering migration_number=182 in
--     `schema_migrations` BUT NOT in `_schema_versions`. The DRAFT was
--     never merged.
--   * PR #735 (mergeato 2026-05-18 01:37) carved out the same migration
--     under the same number `182_wr3_eventbus_channels.sql`. Release
--     command on Fly tried to INSERT migration_number=182 → UniqueViolation
--     against schema_migrations (mig 165 uq_schema_migrations_migration_number).
--   * PR #741 (mergeato 2026-05-18 02:18) renamed the file 182→183 to
--     avoid the apply-time conflict. Mig 183 applied successfully (27ms).
--   * Post-deploy schema_audit STILL FAILS with
--     `tracking_divergence_canonical_only: {"only_in_canonical": [182]}`
--     because the ghost row in schema_migrations remains, and
--     _schema_versions never received a row for 182.
--
-- FIX STRATEGY:
--   Insert a TOMBSTONE row in `_schema_versions` for migration_number=182
--   so schema_audit sees both tables in sync. Do NOT touch schema_migrations
--   (the ghost row is harmless once the divergence is reconciled — both
--   tables agree that 182 is "applied"). Idempotent via ON CONFLICT.
--
--   Why migration_name = '182_ghost_pre_renumber_to_183'? Because
--   _schema_versions.migration_name has UNIQUE constraint. The name is
--   self-documenting and prevents accidental collision with the (never
--   used) name '182_wr3_eventbus_channels' from PR #722. The actual WR3
--   eventbus channel migration lives at migration_number=183 (file
--   183_wr3_eventbus_channels.sql) via PR #741.
--
-- AUTONOMOUS_OPS rule compliance: this is a NEW migration applied via
-- the runner (the canonical path), NOT a manual `fly ssh console` DDL/DML
-- write to either tracking table. The rule "do not write to either table
-- directly outside the runner" is honored.
--
-- Squawk lint: INSERT statement with ON CONFLICT DO NOTHING is safe. No
-- DDL in forward path.

INSERT INTO _schema_versions
    (migration_name, migration_number, checksum, description, execution_time_ms, rollback_sql, applied_by)
VALUES
    (
        '182_ghost_pre_renumber_to_183',
        182,
        'GHOST_TOMBSTONE_NO_DDL_APPLIED',
        'Tombstone row to reconcile schema_migrations ghost migration 182. See migration 184 header for full context.',
        0,
        '-- ROLLBACK by mig 184 itself: DELETE FROM _schema_versions WHERE migration_name = ''182_ghost_pre_renumber_to_183''',
        'mig_184_reconcile'
    )
ON CONFLICT (migration_name) DO NOTHING;

-- === ROLLBACK ===
-- Tombstone removal: if mig 184 is rolled back, schema_audit will resume
-- flagging divergence_canonical_only:[182] until the schema_migrations
-- ghost is cleaned up by an out-of-band operation.
DELETE FROM _schema_versions WHERE migration_name = '182_ghost_pre_renumber_to_183';
