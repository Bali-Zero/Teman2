-- ============================================================================
-- 305_garuda_practices_assignment.sql
-- GARUDA VOA — step 8, staff surface: practice assignment columns.
--
-- MERGE-ORDER DEPENDENCY (same convention as 284/285/286/287's own headers):
-- numbered on top of 303 (the latest migration on `origin/main` at the time
-- this file was written). Re-check `db/migrations_v2/` immediately before
-- merging this file -- renumber rather than let two files claim the same
-- number (cicatrix W40).
--
-- SCOPE: adds ONLY the columns `garuda_practices` needs so a staff member
-- can be assigned ownership of a practice and so a non-admin team member's
-- read/write visibility can be filtered to `assigned_to = actor`
-- (`garuda_staff_router.py`, `get_practices_user_filter`-style pattern
-- already used by `routers/crm_practices.py`). No ownership change, no
-- function creation -- this migration is applicable by the runner role
-- `backend_rag_v2` itself: migration 300's header names the class of
-- migration that is NOT (function ownership), and this one only ever
-- touches a table, never a function.
--
-- LOCK DISCIPLINE (memory: "IF NOT EXISTS takes the lock before it checks"
-- -- #5545 pattern, `discovery_if_not_exists_ddl_locks_before_it_checks_
-- so_a_no_op_migration_hangs_the_deploy_2026_09_02.md`): `garuda_practices`
-- is a low-traffic table (one row per paid order, written only by PR-01 and
-- staff transitions), but the ALTER still takes an ACCESS EXCLUSIVE lock
-- for its duration regardless of table size. `SET LOCAL lock_timeout` bounds
-- how long this migration will wait for that lock before failing loudly
-- instead of hanging the deploy behind a stuck reader/writer. Pre-checking
-- `pg_attribute` first means a re-run of this migration (idempotent retry
-- after a partial-apply crash) is a fast no-op read rather than a second
-- ALTER attempt.
-- ============================================================================

-- Applies for the rest of this migration's transaction (the runner applies
-- each file's forward section inside one transaction) -- a plain top-level
-- statement, not inside the DO block below, so it takes effect before the
-- ALTER TABLE the block may issue, regardless of PL/pgSQL statement timing.
SET LOCAL lock_timeout = '5s';

DO $garuda_practices_assignment$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_attribute
         WHERE attrelid = 'public.garuda_practices'::regclass
           AND attname = 'assigned_to'
           AND NOT attisdropped
    ) THEN
        ALTER TABLE public.garuda_practices
            ADD COLUMN assigned_to TEXT NULL,
            ADD COLUMN assigned_at TIMESTAMPTZ NULL,
            ADD COLUMN assigned_by TEXT NULL;
    END IF;
END;
$garuda_practices_assignment$;

COMMENT ON COLUMN public.garuda_practices.assigned_to IS
    'Lower-cased staff email owning this practice. NULL = unassigned (admin-visible only until assigned). Written exclusively by garuda_staff_router.py::assign_practice.';
COMMENT ON COLUMN public.garuda_practices.assigned_at IS
    'Timestamp of the last assignment write. NULL iff assigned_to IS NULL.';
COMMENT ON COLUMN public.garuda_practices.assigned_by IS
    'Lower-cased staff email of the admin who performed the last assignment. NULL iff assigned_to IS NULL.';

CREATE INDEX IF NOT EXISTS idx_garuda_practices_assigned_to
    ON public.garuda_practices (assigned_to);

-- === ROLLBACK ===

-- This section deliberately runs the destructive teardown for local/CI
-- rollback only; it is never applied to a live database by the migration
-- runner's forward path.
DROP INDEX IF EXISTS public.idx_garuda_practices_assigned_to;
ALTER TABLE public.garuda_practices
    DROP COLUMN IF EXISTS assigned_by,
    DROP COLUMN IF EXISTS assigned_at,
    DROP COLUMN IF EXISTS assigned_to;
