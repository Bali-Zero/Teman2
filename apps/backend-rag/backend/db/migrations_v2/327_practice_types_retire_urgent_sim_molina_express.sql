-- Migration 327: retire five services from the CRM catalogue
--
-- Ruled by the owner on 2026-10-17: the Urgent 1/2/3 Hari processing
-- surcharges, the Driving License (SIM) service and the Created Molina
-- Express service are no longer sold. The canonical sheet
-- (backend/data/bali_zero_official_prices_2026.json) drops the rows in the
-- same PR; the public mirror, the price list and the brochure follow from it.
--
-- Soft retirement, not DELETE: measured on production on 2026-10-17, live
-- practices still reference urgent_1_day (1), urgent_3_days (2) and
-- other_driving_license (7) through practices.practice_type_id. The rows
-- keep base_price so historical quotes stay readable; is_active = false is
-- what the CRM catalogue route (crm_practices.get_practice_types_catalog),
-- the update-by-code path and, from this PR, create_practice honour
-- (`... AND is_active = true`), so a retired code cannot open a new practice.
--
-- Reset Molina (other_reset_molina) is NOT retired: the ruling named only
-- the five rows below.
--
-- Numbered 327: production ledger max at writing is 326, and open branches
-- carry 324 and 325 (the runner selects pending files by number).
--
-- Idempotent: re-asserts is_active = false on rerun.

UPDATE practice_types
SET is_active = false,
    updated_at = CURRENT_TIMESTAMP
WHERE code IN (
    'urgent_1_day',
    'urgent_2_days',
    'urgent_3_days',
    'other_driving_license',
    'other_create_molina_express'
);

-- Postcondition: refuse to record this migration as applied while any of
-- the five rows is still active.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM practice_types
        WHERE code IN (
            'urgent_1_day',
            'urgent_2_days',
            'urgent_3_days',
            'other_driving_license',
            'other_create_molina_express'
        )
          AND is_active = true
    ) THEN
        RAISE EXCEPTION 'migration 327: a retired practice_types row is still active';
    END IF;
END $$;

-- === ROLLBACK ===
UPDATE practice_types
SET is_active = true,
    updated_at = CURRENT_TIMESTAMP
WHERE code IN (
    'urgent_1_day',
    'urgent_2_days',
    'urgent_3_days',
    'other_driving_license',
    'other_create_molina_express'
);
