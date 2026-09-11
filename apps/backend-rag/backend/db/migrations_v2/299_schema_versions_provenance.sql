-- 299_schema_versions_provenance.sql
--
-- WHY 299 AND NOT 298. The L12 lane spec names `298` as "the verified next
-- free number". It was, when the spec was written. `298_garuda_payment_inbox_
-- quarantine_reason.sql` landed since. Measured on disk 2026-08-31 rather than
-- read from the spec, because a stale number is how two migrations collide
-- (W40) and the runner's `_assert_unique_migration_numbers` fails the whole
-- deploy before applying ANY migration -- including migrations that have
-- nothing to do with the collision.
--
-- THE DEFECT. `_schema_versions` records WHAT was applied and WHEN. It does
-- not record WHO applied it, THROUGH WHAT, or WITH WHICH RUNNER, and nothing
-- ever re-verifies the `checksum` it stores.
--
-- Why each of those is not bookkeeping:
--
--   * WHO. Migrations execute as the runtime role, and this repository has a
--     live scar about exactly that (W130, 2026-08-26): a migration wrote DDL
--     against a table the runtime role no longer owned, the release command
--     aborted, and production sat un-deployed. Two migrations were then
--     applied under a TEMPORARY `GRANT visa_ledger_owner TO backend_rag_v2`
--     that was revoked afterwards. Nothing in the schema records that those
--     two rows were applied under a different effective identity than every
--     other row -- the knowledge lives in a test-file docstring. `applied_as`
--     puts it in the table, and takes it from PostgreSQL's own `current_user`
--     rather than from anything the caller claims.
--
--   * THROUGH WHAT. `apply-all` is invoked from the Fly `release_command`, by
--     hand over `fly ssh console`, and from CI. Those three have different
--     blast radii and different people behind them, and today they are
--     indistinguishable after the fact.
--
--   * THE CHECKSUM NOBODY READS. `migration_base.py::_log_migration` computes
--     `sha256(sql)` and stores it. Grep the tree: nothing ever compares it
--     back. A stored proof that is never verified is the same family as a
--     cron that exits 0 without doing its work -- it reassures without
--     checking. The verification lands in `schema_audit.py` in this PR; this
--     migration only makes the provenance columns exist to compare against.
--
-- WHAT THIS MIGRATION DELIBERATELY DOES NOT DO.
--
--   * It does not touch a single object owned by `visa_ledger_owner`,
--     `zantara_rag_user`, `postgres` or `repmgr`. `_schema_versions` is not in
--     `NON_APP_OWNED_TABLES` (the snapshot in
--     `test_post_d1_migrations_guard_ledger_owned_ddl.py`), so the runtime
--     role can ALTER it. That snapshot is a FLOOR, not a live query -- its own
--     comment says so -- which is why the audit added in this PR preflights
--     ownership at APPLY time instead of trusting the list.
--
--   * It does not backfill. Legacy rows keep `applied_as = NULL`, and that
--     NULL is honest: nobody recorded who applied them, and inventing a value
--     now would manufacture provenance, which is worse than admitting there is
--     none. The audit therefore treats NULL as "legacy", never as "system".
--
--   * It does not add a NOT NULL or a DEFAULT. A DEFAULT would silently make
--     every future row claim an identity the runner never measured.
--
-- The `applied_via` CHECK is deliberately narrow. An unconstrained text column
-- would drift into free-form prose within a year and stop being queryable,
-- which is how a provenance field becomes decoration.

ALTER TABLE _schema_versions
    ADD COLUMN IF NOT EXISTS applied_as TEXT;

ALTER TABLE _schema_versions
    ADD COLUMN IF NOT EXISTS applied_via TEXT;

ALTER TABLE _schema_versions
    ADD COLUMN IF NOT EXISTS runner_version TEXT;

DO $$
BEGIN
    -- `conname` is NOT globally unique in PostgreSQL -- it is unique per
    -- table. A constraint of this name on ANY other table would make this
    -- guard skip the ADD and leave `_schema_versions` unconstrained, silently.
    -- Scoped to conrelid after a blind refuter pointed it out (2026-08-31).
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'schema_versions_applied_via_check'
          AND conrelid = 'public._schema_versions'::regclass
    ) THEN
        ALTER TABLE _schema_versions
            ADD CONSTRAINT schema_versions_applied_via_check
            CHECK (applied_via IS NULL
                   OR applied_via IN ('release_command', 'manual', 'ci'));
    END IF;
END
$$;

COMMENT ON COLUMN _schema_versions.applied_as IS
    'PostgreSQL current_user at apply time. NULL means legacy (pre-299): nobody '
    'recorded it, and that is not the same as "system". Never taken from an '
    'environment variable a caller could set.';

COMMENT ON COLUMN _schema_versions.applied_via IS
    'How apply-all was invoked: release_command | manual | ci. NULL means legacy.';

COMMENT ON COLUMN _schema_versions.runner_version IS
    'Non-secret identifier of the runner that applied the row. NULL means legacy.';

-- === ROLLBACK ===

-- DELIBERATELY unconditional, and the reason is worth stating because the
-- asymmetry is real: `ADD COLUMN IF NOT EXISTS` is a no-op if a column of that
-- name already existed, so a strict inverse would have to know whether IT
-- created the column. PostgreSQL does not record that. A blind refuter flagged
-- the asymmetry (2026-08-31) and it is accepted rather than papered over:
-- these three names are introduced by THIS migration and appear nowhere else
-- in migrations_v2/ (grep-verified), so on any database this repository can
-- produce, dropping them is the exact inverse. On a database where somebody
-- added a column with one of these names OUT OF BAND, the rollback would take
-- it -- which is a real, narrow, documented limit, not an unknown one.
ALTER TABLE _schema_versions
    DROP CONSTRAINT IF EXISTS schema_versions_applied_via_check;
ALTER TABLE _schema_versions DROP COLUMN IF EXISTS runner_version;
ALTER TABLE _schema_versions DROP COLUMN IF EXISTS applied_via;
ALTER TABLE _schema_versions DROP COLUMN IF EXISTS applied_as;
