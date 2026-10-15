-- Migration 324: add the D2 Business (5 Years) service to the CRM catalogue
--
-- Ruled by the owner on 2026-10-15: D2 Business multiple-entry visa, 5-year
-- validity, final selling price 13.000.000 IDR. The canonical sheet
-- (backend/data/bali_zero_official_prices_2026.json) already carries the row
-- as "D2 Business (5 Years)" since #8540, and PricingService serves it live.
-- Postgres did not.
--
-- `practice_types.base_price` is what crm_practices.py quotes when a practice
-- is opened without an explicit price, and what invoice_service.py bills, so
-- without this row the CRM cannot open the service at the ruled price.
--
-- Mirrors the siblings seeded by migration 157 (visa_d2_business_1yr / _2yr)
-- and visa_d1_tourism_5yr: same category, same description shape, 1825 days.
-- Measured 2026-10-15 on production: the code does not exist yet.
--
-- Idempotent: ON CONFLICT re-asserts the ruled values.

INSERT INTO practice_types (code, name, description, category, base_price, typical_duration_days, is_active)
VALUES
    ('visa_d2_business_5yr', 'D2 Business (5 Years)', 'Multiple-entry business visa valid 5 years for business meetings and non-employment activities.', 'multiple_entry_visa', 13000000, 1825, true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    base_price = EXCLUDED.base_price,
    typical_duration_days = EXCLUDED.typical_duration_days,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;

-- Postcondition: refuse to record this migration as applied unless the row is
-- live at the ruled price.
DO $$
DECLARE
    current_price numeric;
BEGIN
    SELECT base_price INTO current_price
      FROM practice_types
     WHERE code = 'visa_d2_business_5yr' AND is_active;

    IF current_price IS DISTINCT FROM 13000000 THEN
        RAISE EXCEPTION
            'migration 324: practice_types.visa_d2_business_5yr is % , expected 13000000 active',
            current_price;
    END IF;
END;
$$;

-- === ROLLBACK ===

-- Deactivates rather than deletes: practices may already reference the row.
UPDATE practice_types
   SET is_active = false,
       updated_at = CURRENT_TIMESTAMP
 WHERE code = 'visa_d2_business_5yr';
