-- 324_practices_practice_type_id_nullable.sql
--
-- Promote the last bootstrap-only `DROP NOT NULL` into migrations_v2.
--
-- `ci_bootstrap_schema.py` issues
--   ALTER TABLE practices ALTER COLUMN practice_type_id DROP NOT NULL
-- claiming it mirrors prod, and until this file nothing corroborated that
-- claim — of the three `DROP NOT NULL` families in the bootstrap
-- (lkpm_reports.realized_*/cumulative_*, team_members.full_name,
-- practices.practice_type_id) the first two each have a committed
-- migration counterpart (132, 137) and this one had none.
--
-- Settled 2026-10-05 against the production leader (read-only,
-- information_schema.columns): is_nullable = 'YES' — prod genuinely
-- enforces no NOT NULL on this column. This file is the migration
-- counterpart that records that fact.
--
-- Nullability is NOT where the product guarantees a type. The CRM read
-- paths (kanban, portal, analytics, shared memory — see migration 311)
-- INNER JOIN practice_types, so a practice with a NULL type is invisible
-- in the product; the write path resolves code->id and INSERTs the
-- column unconditionally (app/routers/crm_practices.py), and migration
-- 311 routes no-type inquiries through a placeholder practice_types row
-- precisely because a NULL type would hide them.
--
-- The SQLModel CRM module (backend/app/modules/crm/models.py) still
-- declares the column nullable=False — a known, intentional divergence
-- from prod, same class as team_members.full_name (migration 137).
--
-- Idempotent. On prod (already nullable) and on bootstrap-built CI (the
-- bootstrap script issues the same statement before the v2 runner applies
-- this migration, which then records itself as applied) the statement
-- changes no constraint — though it still takes ACCESS EXCLUSIVE on the
-- table for the catalog rewrite, same as any ALTER COLUMN.

ALTER TABLE practices ALTER COLUMN practice_type_id DROP NOT NULL;

-- === ROLLBACK ===
-- Contract (council round 1, findings F2/F3): on prod and on bootstrap-built
-- CI the column was ALREADY nullable before this migration ran, so there is
-- strictly nothing to restore — the only environment where the forward
-- changes state is a fresh SQLModel create_all DB (Strategy 01 Step 4
-- cutover), where the column starts NOT NULL. The rollback below restores
-- that state when it can, and SAYS SO when it declines:
--   * NULL rows present  → pre-migration state was nullable; SET NOT NULL
--     would both fail and be wrong, so it is declined with a WARNING that
--     lands in the server log — never silent (migration_base.py's own rule:
--     "Raising this is preferable to silently ignoring rollback").
--   * no NULL rows       → SET NOT NULL, restoring the create_all shape.
-- The LOCK serializes against an INSERT landing a NULL row between the
-- check and the ALTER (a bare check-then-alter can still fail on a race).
DO $$
BEGIN
  LOCK TABLE public.practices IN ACCESS EXCLUSIVE MODE;
  IF EXISTS (SELECT 1 FROM public.practices WHERE practice_type_id IS NULL) THEN
    RAISE WARNING 'rollback 324 declined: practices.practice_type_id holds NULL rows; the pre-migration state on prod/CI was nullable, so there is nothing to restore';
  ELSE
    ALTER TABLE public.practices ALTER COLUMN practice_type_id SET NOT NULL;
  END IF;
END $$;
