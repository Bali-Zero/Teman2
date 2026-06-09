-- Migration 220: add three Bali Zero services to the practice_types catalog
--
-- Purpose: register three new services so they appear in the New Process
-- form dropdown at kita.balizero.com/process/new:
--
--   1. Dissolving Company          -- Rp 13,000,000  (category: company)
--   2. Create User RPTKA           -- Rp    500,000  (category: other)
--   3. Custom                      -- Quote (no base) (category: other)
--
-- Notes:
-- * "Dissolving Company" is the full company-dissolution service under
--   Company Services. It is DISTINCT from the existing `tax_close_pma_company`
--   ("Close PMA Company", category=tax, base_price=NULL) -- that one stays
--   untouched. Owner confirmed: separate Company-Services entry, fixed 13M.
-- * "Create User RPTKA" sits next to the existing `other_cancel_rptka`
--   (Cancel RPTKA, 1M) in the Other Process group.
-- * "Custom" carries base_price = NULL so the dropdown renders it as
--   "Quote" and the catalog endpoint leaves quoted_price empty; the
--   operator types the price (and any discount) by hand in the form.
--   Same UX pattern already used by `company_revision` (Revision Company).
--
-- Idempotent: ON CONFLICT(code) DO UPDATE makes reruns safe and picks up
-- future price/duration tweaks without duplicate rows. Same pattern as
-- migration 148 (Bridging Visa).

INSERT INTO practice_types (
    code, name, description, category, base_price,
    typical_duration_days, is_active
)
VALUES
    (
        'company_dissolving',
        'Dissolving Company',
        NULL,
        'company',
        13000000,
        NULL,
        true
    ),
    (
        'other_create_user_rptka',
        'Create User RPTKA',
        NULL,
        'other',
        500000,
        NULL,
        true
    ),
    (
        'other_custom',
        'Custom',
        'Custom service - set the price and line items manually in the form.',
        'other',
        NULL,
        NULL,
        true
    )
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    base_price = EXCLUDED.base_price,
    typical_duration_days = EXCLUDED.typical_duration_days,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;

-- === ROLLBACK ===
-- Reversal is a soft-disable, never a hard row removal: practices.practice_type_id
-- and practices.practice_type_code both carry FK constraints onto practice_types,
-- so a live row that already has referencing practices cannot be hard-removed
-- without breaking those rows. Setting is_active=false hides the entry from the
-- catalog endpoint (/api/crm/practices/types/catalog filters WHERE is_active=true)
-- while preserving referential integrity. Safe to run on any DB state: a no-op if
-- the rows do not exist or are already inactive.
UPDATE practice_types
SET is_active = false
WHERE code IN ('company_dissolving', 'other_create_user_rptka', 'other_custom');
