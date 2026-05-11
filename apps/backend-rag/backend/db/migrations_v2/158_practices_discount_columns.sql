-- Migration 158: add discount support to practices + invoices
--
-- Owner approval 2026-05-06: discount feature for the New Process form.
-- A team member can apply a fixed-IDR discount to a practice; the invoice
-- PDF shows it as a separate line ("Subtotal / Discount / Total").
--
-- Decisions (Q1–Q5 with owner):
--   Q1=a  fixed IDR amount (no percentage)
--   Q2=a  invoice shows 3-row breakdown: Subtotal / Discount / Total
--   Q3=c  audit trail in metadata.discount_log (no hard cap on amount)
--   Q4=a  two dedicated columns on practices (queryable for reports)
--   Q5=c  reason is free text, optional
--
-- Storage: practices.discount_amount NUMERIC(12,2) and discount_reason TEXT.
-- The audit trail (who/when/why) lives in practices.metadata.discount_log
-- because that column is already a jsonb catch-all and the volume is low.
-- Invoices table also gets a discount_amount_idr mirror for analytics.
--
-- Idempotent: ALTER TABLE ... ADD COLUMN IF NOT EXISTS. Same pattern as
-- migration_148_practice_types_bridging_visa.

-- =====================================================================
-- 1. practices: discount columns
-- =====================================================================

ALTER TABLE practices
    ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(12, 2) DEFAULT NULL;

ALTER TABLE practices
    ADD COLUMN IF NOT EXISTS discount_reason TEXT DEFAULT NULL;

COMMENT ON COLUMN practices.discount_amount IS
    'Fixed-IDR discount applied to quoted_price for invoice purposes. NULL or 0 means no discount. Final invoice total = quoted_price - discount_amount.';
COMMENT ON COLUMN practices.discount_reason IS
    'Optional free-text reason for the discount (e.g. "Pay-in-advance", "Loyalty"). Surfaced on the invoice PDF only when populated.';

-- Constraint: discount_amount must be non-negative when set.
-- (We deliberately do NOT enforce discount <= quoted_price at the DB level
-- because quoted_price is also nullable; the application layer enforces it.)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'practices_discount_amount_nonneg'
    ) THEN
        ALTER TABLE practices
            ADD CONSTRAINT practices_discount_amount_nonneg
            CHECK (discount_amount IS NULL OR discount_amount >= 0);
    END IF;
END $$;

-- =====================================================================
-- 2. invoices: discount mirror column for analytics + reporting
--
-- The `invoices` table predates migrations_v2 (created in a legacy Python
-- migration no longer in the ordered list). Fresh CI/test schemas may not
-- have it; in prod it always exists. Same pattern as migration 125.
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'invoices'
    ) THEN
        RAISE NOTICE 'Migration 158: invoices table not present; skipping invoices block (CI/fresh schema).';
        RETURN;
    END IF;

    ALTER TABLE invoices
        ADD COLUMN IF NOT EXISTS discount_amount_idr NUMERIC(15, 2) NOT NULL DEFAULT 0;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'invoices_discount_nonneg'
    ) THEN
        ALTER TABLE invoices
            ADD CONSTRAINT invoices_discount_nonneg
            CHECK (discount_amount_idr >= 0);
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'invoices'
    ) THEN
        EXECUTE $cmt$COMMENT ON COLUMN invoices.discount_amount_idr IS 'Discount applied at invoice generation time. amount_idr already stores the post-discount total; this column preserves the discount for reporting (sum of discounts given per period).'$cmt$;
    END IF;
END $$;

-- =====================================================================
-- 3. Index hint for reports ("how much discount did we give last month?")
-- =====================================================================

CREATE INDEX IF NOT EXISTS idx_practices_discount_nonzero
    ON practices (created_at DESC)
    WHERE discount_amount IS NOT NULL AND discount_amount > 0;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'invoices'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_invoices_discount_nonzero ON invoices (generated_at DESC) WHERE discount_amount_idr > 0';
    END IF;
END $$;

-- === ROLLBACK ===
-- Soft rollback path: drop the new constraints + indexes + columns.
-- Data loss: any populated discount_amount / discount_reason values are
-- erased. Invoice rows lose discount_amount_idr but the amount_idr (total
-- after discount) remains intact, so historical totals stay queryable.
-- If a true rollback is needed, dump the discount values to a sidecar
-- table BEFORE running this rollback.

DROP INDEX IF EXISTS idx_invoices_discount_nonzero;
DROP INDEX IF EXISTS idx_practices_discount_nonzero;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
         WHERE table_schema = 'public' AND table_name = 'invoices'
    ) THEN
        ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_discount_nonneg;
        ALTER TABLE invoices DROP COLUMN IF EXISTS discount_amount_idr;
    END IF;
END $$;

ALTER TABLE practices DROP CONSTRAINT IF EXISTS practices_discount_amount_nonneg;
ALTER TABLE practices DROP COLUMN IF EXISTS discount_reason;
ALTER TABLE practices DROP COLUMN IF EXISTS discount_amount;
