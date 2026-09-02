-- ============================================================================
-- 305_garuda_practices_assignment.sql
-- GARUDA VOA — step 8, staff surface: assignment, active-block identity,
-- and append-only transition evidence.
--
-- MERGE-ORDER DEPENDENCY (same convention as 284/285/286/287's own headers):
-- numbered on top of 303 (the latest migration on `origin/main` at the time
-- this file was written). Re-check `db/migrations_v2/` immediately before
-- merging this file -- renumber rather than let two files claim the same
-- number (cicatrix W40).
--
-- CORRECTED (cross-family refuter, findings #1-3): this file previously (a)
-- asserted table ownership without measuring it, (b) guarded the THREE
-- assignment columns behind ONE `pg_attribute` check on `assigned_to` alone
-- -- a partial-apply state (assigned_to present, assigned_at/assigned_by
-- absent, e.g. a crash between two ALTERs, or a hand-repair that added one
-- column) would skip the whole ALTER block and then the unconditional
-- `COMMENT ON COLUMN assigned_at` below would raise `column does not exist`
-- -- exactly the "esiste != armato" migration-theater shape
-- cicatrix-superscar.md family #2 warns against, reproduced in a migration
-- file rather than a cron job. Both are fixed below: an explicit owner
-- preflight, and native `ADD COLUMN IF NOT EXISTS` per column (Postgres
-- >= 9.6) so each of the SIX columns this file adds is independently
-- idempotent under ANY partial state, never gated behind another column's
-- existence.
--
-- SCOPE:
-- 1. `assigned_to`/`assigned_at`/`assigned_by` -- staff ownership, filtered
--    read/write visibility (`garuda_staff_router.py`,
--    `get_practices_user_filter`-style pattern already used by
--    `routers/crm_practices.py`).
-- 2. `active_block_id` -- the journal `event_id` of the `practice.blocked`
--    event that most recently blocked this practice (PR-03/05/08), NULL
--    once resolved. PR-09/10 (resume) must compare the staff-supplied
--    `resolved_block_id` against THIS identity, not merely against
--    `resume_target` (a bare state name) -- otherwise a resume command
--    could resolve an unrelated, already-superseded block (cross-family
--    refuter finding #9).
-- 3. `garuda_practice_evidence` -- append-only record binding an
--    `evidence_id` (PR-04 filing / PR-06 approval / PR-07 rejection) to the
--    practice AND the transition that recorded it, so "evidence verified
--    and bound to this practice" (STATE-MACHINE.md rows PR-04/06/07) is a
--    real, queryable fact rather than a claim the router makes and drops
--    (cross-family refuter finding #8). No `artifact_id`/`artifact_digest`
--    table is needed for PR-11: those columns already exist on
--    `garuda_practices` itself (this migration's own predecessor, 287) --
--    adding a second copy here would be exactly the kind of duplicate
--    identity this file's own `active_block_id` column exists to avoid.
--
-- No function creation, no `SECURITY DEFINER` trigger -- 300/301's ownership
-- disease class does not apply here structurally. The preflight below still
-- measures rather than assumes, because "no function means no risk" was
-- itself an unmeasured assumption in this file's first draft.
--
-- LOCK DISCIPLINE (memory: "IF NOT EXISTS takes the lock before it checks"
-- -- #5545 pattern): `garuda_practices` is low-traffic (one row per paid
-- order), but each `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` still takes
-- an ACCESS EXCLUSIVE lock for its duration regardless of table size.
-- `SET LOCAL lock_timeout` bounds the wait so a stuck reader/writer fails
-- this migration loudly instead of hanging the deploy.
-- ============================================================================

-- Applies for the rest of this migration's transaction (the runner applies
-- each file's forward section inside one transaction) -- a plain top-level
-- statement, so it is in effect before any ALTER TABLE below.
SET LOCAL lock_timeout = '5s';

-- Owner preflight (refuter finding #2): `ALTER TABLE ... ADD COLUMN`
-- requires the session to own the table, or hold membership in the owning
-- role -- the same class of requirement `300_garuda_voa_retention_owner_
-- transfer.sql`/`301_garuda_magic_link_binding_owner.sql` measure for
-- FUNCTION ownership rather than assume. Measured against production
-- 2026-09-02 (team-lead, cross-family refuter disposition): every
-- `garuda_*` table including `garuda_practices` is owned by
-- `backend_rag_v2`, the migration runner's own role -- so this preflight
-- is expected to pass silently everywhere this migration actually runs.
-- It still RAISES rather than assumes, because a future environment
-- (a restored snapshot, a hand-repaired database) could genuinely differ,
-- and a raised exception here is far cheaper than a half-applied
-- migration recorded as clean.
-- `ALTER TABLE ADD COLUMN` succeeds when `current_user` either literally IS
-- the owning role, or holds INHERITED membership in it (`pg_has_role(...,
-- 'MEMBER')` -- the same "member" privilege type Postgres itself checks
-- internally for ALTER, distinct from the narrower 'USAGE' membership type
-- that only grants SET ROLE without inheritance). A first draft of this
-- check compared `current_user` for LITERAL equality only, which raises a
-- false-positive EXCEPTION for the legitimate membership case measured
-- locally in this repo's own test fixtures (`nuzantara` granted membership
-- in `balizero`, the table's actual owner) -- exactly the shape a future
-- dedicated migration role (`STEP5-PRIVILEGE-DECISION.md` option D,
-- `backend_rag_migrator IN ROLE backend_rag_v2`) would also take.
DO $garuda_practices_assignment_owner_check$
DECLARE
    table_owner text;
BEGIN
    SELECT pg_catalog.pg_get_userbyid(relowner) INTO table_owner
      FROM pg_catalog.pg_class
     WHERE oid = 'public.garuda_practices'::regclass;
    IF table_owner IS DISTINCT FROM current_user
       AND NOT pg_catalog.pg_has_role(current_user, table_owner, 'MEMBER') THEN
        RAISE EXCEPTION
            'garuda_practices assignment (305): table owned by % and this '
            'migration runs as % -- ALTER TABLE ADD COLUMN requires table '
            'ownership or inherited membership in the owning role. Run this '
            'migration as %, or grant % membership in that role.',
            table_owner, current_user, table_owner, current_user;
    END IF;
END;
$garuda_practices_assignment_owner_check$;

-- Each column is its own atomic, natively-idempotent statement -- immune
-- to the partial-state bug named above by construction, not by an extra
-- catalog check this file would have to keep in sync with the column list.
ALTER TABLE public.garuda_practices ADD COLUMN IF NOT EXISTS assigned_to TEXT NULL;
ALTER TABLE public.garuda_practices ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ NULL;
ALTER TABLE public.garuda_practices ADD COLUMN IF NOT EXISTS assigned_by TEXT NULL;
ALTER TABLE public.garuda_practices ADD COLUMN IF NOT EXISTS active_block_id TEXT NULL;

COMMENT ON COLUMN public.garuda_practices.assigned_to IS
    'Lower-cased staff email owning this practice. NULL = unassigned (admin-visible only until assigned). Written exclusively by garuda_staff_router.py::assign_practice.';
COMMENT ON COLUMN public.garuda_practices.assigned_at IS
    'Timestamp of the last assignment write. NULL iff assigned_to IS NULL.';
COMMENT ON COLUMN public.garuda_practices.assigned_by IS
    'Lower-cased staff email of the admin who performed the last assignment. NULL iff assigned_to IS NULL.';
COMMENT ON COLUMN public.garuda_practices.active_block_id IS
    'garuda_order_journal.event_id of the practice.blocked event that most recently blocked this practice (PR-03/05/08). NULL unless state = Blocked. PR-09/10 (resume) must require resolved_block_id = active_block_id, never merely a resume_target state-name match -- see this migration''s own header.';

CREATE INDEX IF NOT EXISTS idx_garuda_practices_assigned_to
    ON public.garuda_practices (assigned_to);

-- (2) Append-only transition evidence -------------------------------------

CREATE TABLE IF NOT EXISTS public.garuda_practice_evidence (
    practice_id     TEXT NOT NULL REFERENCES public.garuda_practices (practice_id),
    transition_id   TEXT NOT NULL,
    evidence_id     TEXT NOT NULL CHECK (evidence_id ~ '^[A-Za-z0-9_-]{16,128}$'),
    kind            TEXT NOT NULL CHECK (kind IN ('filing', 'approval', 'rejection')),
    recorded_by     TEXT NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    UNIQUE (practice_id, evidence_id)
);

COMMENT ON TABLE public.garuda_practice_evidence IS
    'Append-only: binds a staff-supplied evidence_id (PR-04 filing / PR-06 approval / PR-07 rejection) to the practice AND the transition_id that recorded it. UNIQUE(practice_id, evidence_id) makes an idempotent replay of the same command a no-op INSERT (ON CONFLICT DO NOTHING at the call site), never a duplicate row.';

CREATE INDEX IF NOT EXISTS idx_garuda_practice_evidence_practice_id
    ON public.garuda_practice_evidence (practice_id);

-- === ROLLBACK ===

-- This section deliberately runs the destructive teardown for local/CI
-- rollback only; it is never applied to a live database by the migration
-- runner's forward path.
DROP TABLE IF EXISTS public.garuda_practice_evidence;
DROP INDEX IF EXISTS public.idx_garuda_practices_assigned_to;
ALTER TABLE public.garuda_practices
    DROP COLUMN IF EXISTS active_block_id,
    DROP COLUMN IF EXISTS assigned_by,
    DROP COLUMN IF EXISTS assigned_at,
    DROP COLUMN IF EXISTS assigned_to;
