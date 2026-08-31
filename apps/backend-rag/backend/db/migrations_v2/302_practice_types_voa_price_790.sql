-- Migration 302: align the CRM's VOA price with the official price sheet
--
-- Ruled by the owner on 2026-08-31: e-VOA is 790.000 IDR, the extension is
-- 850.000 IDR. The canonical sheet
-- (backend/data/bali_zero_official_prices_2026.json) already carries both,
-- stamped verified_on 2026-08-25. Postgres did not.
--
--   practice_types.code = 'visa_b1_voa'  base_price 750000 -> 790000
--   practice_types.code = 'ext_b1_voa'   base_price 850000 -- already correct
--
-- WHY THIS MATTERED, AND WHY IT IS NOT COSMETIC
-- =============================================================================
--   `practice_types.base_price` is not a display value. When a practice is
--   created without an explicit price, crm_practices.py:491 quotes it:
--
--       quoted_price = practice.quoted_price or practice_type_row["base_price"]
--
--   and invoice_service.py bills that amount. So the row was a live 40.000 IDR
--   under-quote on every VOA practice opened without a manual price, while
--   GARUDA VOA — which resolves through PricingService against the JSON on
--   every request — quoted 790.000 for the same service. Two live surfaces,
--   one service, two prices.
--
--   The row has read 750000 since migration 221 (2026-06-09). Nothing re-reads
--   the sheet at runtime, so the two stores can only be aligned by a migration
--   like this one; there is no sync job and no CI test comparing them. That
--   structural gap is NOT closed here and is tracked in PENDING-ARMS — this
--   migration fixes the one divergence that exists today, not the mechanism
--   that let it open.
--
-- SCOPE
-- =============================================================================
--   One column of one row. No schema change, no ownership transfer, no grant.
--   `updated_at` is bumped so the change is visible to anything auditing the
--   catalogue by timestamp.
--
--   Idempotent: the WHERE clause is code-scoped and value-guarded, so a rerun
--   after the value is already 790000 updates zero rows rather than churning
--   updated_at. Verified by the runner's own re-apply path.
--
--   Deliberately NOT touched: rows whose price merely looks implausible
--   (Tax Consulting 1.000, Property Purchase 2.000, and three siblings). All
--   five are is_active = false and therefore cannot default a quote; changing
--   them would be a pricing decision nobody has made.

UPDATE practice_types
   SET base_price = 790000,
       updated_at = CURRENT_TIMESTAMP
 WHERE code = 'visa_b1_voa'
   AND base_price IS DISTINCT FROM 790000;

-- Postcondition: refuse to record this migration as applied if the row is not
-- what the owner ruled. A silent no-op here would leave the CRM under-quoting
-- VOA while the migration log claims the price was aligned.
DO $$
DECLARE
    current_price numeric;
BEGIN
    SELECT base_price INTO current_price
      FROM practice_types
     WHERE code = 'visa_b1_voa';

    IF current_price IS NULL THEN
        RAISE NOTICE 'practice_types row visa_b1_voa is absent -- skipping; this database has not applied migration 221';
        RETURN;
    END IF;

    IF current_price IS DISTINCT FROM 790000 THEN
        RAISE EXCEPTION
            'migration 302: practice_types.visa_b1_voa is % , expected 790000 -- the CRM would keep quoting the wrong VOA price while this migration recorded success',
            current_price;
    END IF;
END;
$$;

-- === ROLLBACK ===

-- Restores the pre-ruling value. Kept honest rather than convenient: rolling
-- this back reinstates the 40.000 IDR under-quote against the owner's 2026-08-31
-- ruling, so it exists for local/CI teardown, not as an operational option.
UPDATE practice_types
   SET base_price = 750000,
       updated_at = CURRENT_TIMESTAMP
 WHERE code = 'visa_b1_voa';
