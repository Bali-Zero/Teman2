-- ============================================================
-- 125_invoices_unique_practice.sql
-- Guard against duplicate invoices per practice.
-- Date: 2026-04-20
--
-- SCAR: invoice_service._update_practice_with_invoice used ON CONFLICT
-- (invoice_number), but invoice_number changes across months
-- (format INV-YYYYMM-<practice_id>). Running invoice regeneration in a new
-- month produced a NEW invoice row with a NEW number for the same
-- practice_id, bypassing the conflict target. Practice 204 ended up with
-- two invoices (INV-202603-00204 and INV-202604-00204).
--
-- Fix: add UNIQUE (practice_id) so only one invoice per practice can exist.
-- Any regeneration updates-in-place.
--
-- The `invoices` table predates the migrations_v2 folder (created in a
-- legacy Python migration that is no longer in the ordered list). Fresh CI
-- test envs start from an empty schema and may not have the table when
-- this migration runs. The whole operation is wrapped in a DO block that
-- no-ops when the table is absent; in prod the table exists and the block
-- executes normally. Idempotent on the constraint too.
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'invoices'
    ) THEN
        RAISE NOTICE 'Migration 125: invoices table not present; skipping (CI/fresh schema).';
        RETURN;
    END IF;

    -- Preflight: keep the most recent invoice per practice, delete the rest.
    DELETE FROM invoices a
    USING invoices b
    WHERE a.practice_id = b.practice_id
      AND a.id < b.id;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'invoices_practice_id_key'
    ) THEN
        ALTER TABLE invoices
            ADD CONSTRAINT invoices_practice_id_key UNIQUE (practice_id);
    END IF;
END $$;

-- === ROLLBACK ===
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'invoices'
    ) THEN
        ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_practice_id_key;
    END IF;
END $$;
