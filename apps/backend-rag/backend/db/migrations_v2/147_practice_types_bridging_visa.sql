-- Migration 147: add Bridging Visa to practice_types catalog
--
-- Purpose: register a new Bali Zero service "Bridging Visa" so that it
-- appears in the New Process form dropdown at kita.balizero.com/process/new
-- with the default price 3,500,000 IDR auto-filled.
--
-- A Bridging Visa is a temporary single-entry visa used to bridge two
-- immigration states (e.g. while waiting for a KITAS approval after an
-- onshore conversion). Categorised under `single_entry_visa` to share
-- the same group as the other short-stay visa products.
--
-- Idempotent: ON CONFLICT(code) DO UPDATE makes reruns safe and picks up
-- future price/duration tweaks without duplicate rows. Same pattern used
-- by the legacy migration_122_practice_types_visa_d1_5yr.py.

INSERT INTO practice_types (
    code, name, description, category, base_price,
    typical_duration_days, is_active
)
VALUES (
    'visa_bridging',
    'Bridging Visa',
    NULL,
    'single_entry_visa',
    3500000,
    60,
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
-- Soft-disable instead of DELETE: practices.practice_type_id and
-- practices.practice_type_code both have FK constraints onto practice_types,
-- so a live row with referencing practices cannot be hard-deleted without
-- breaking those rows. is_active=false hides the entry from the catalog
-- endpoint (`/api/crm/practices/types/catalog` filters WHERE is_active=true)
-- without violating referential integrity. Safe to run on any DB state:
-- a no-op if the row does not exist or is already inactive.
UPDATE practice_types SET is_active = false WHERE code = 'visa_bridging';
