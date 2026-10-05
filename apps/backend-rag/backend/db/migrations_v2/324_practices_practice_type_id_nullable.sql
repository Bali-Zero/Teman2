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
-- Idempotent. No-op on prod (already nullable) and on bootstrap-built CI
-- (the bootstrap script issues the same statement before the v2 runner
-- applies this migration, which then records itself as applied).

ALTER TABLE practices ALTER COLUMN practice_type_id DROP NOT NULL;

-- === ROLLBACK ===
-- Restoring NOT NULL is deliberately conditional: prod has held this
-- column nullable and rows may legitimately store NULL today. A bare
-- SET NOT NULL would fail on the first such row — the same reason 132
-- and 137 omit the restoration.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.practices WHERE practice_type_id IS NULL) THEN
    EXECUTE 'ALTER TABLE public.practices ALTER COLUMN practice_type_id SET NOT NULL';
  END IF;
END $$;
