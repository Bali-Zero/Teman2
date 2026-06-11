-- Migration 221: add B1 - VOA visa services to the practice_types catalog
--
-- Purpose: register two new Bali Zero services so they appear in the New
-- Process form dropdown at kita.balizero.com/process/new:
--
--   1. B1 - VOA              -- Rp 750,000  (category: single_entry_visa)
--   2. Extension B1 - VOA    -- Rp 850,000  (category: visa_extension)
--
-- B1 / VOA = Visa on Arrival. The fresh-issue product sits in Single Entry
-- Visa alongside the other C-series single-entry visas; the extension sits in
-- Visa Extension next to the existing ext_c1_tourism. Code convention matches
-- the live rows: single-entry visas are `visa_*`, extensions are `ext_*`.
--
-- Idempotent: ON CONFLICT(code) DO UPDATE makes reruns safe and picks up
-- future price tweaks without duplicate rows. Same pattern as migration 148
-- (Bridging Visa) and 220 (practice_types catalog additions).

INSERT INTO practice_types (
    code, name, description, category, base_price,
    typical_duration_days, is_active
)
VALUES
    (
        'visa_b1_voa',
        'B1 - VOA',
        NULL,
        'single_entry_visa',
        750000,
        NULL,
        true
    ),
    (
        'ext_b1_voa',
        'Extension B1 - VOA',
        NULL,
        'visa_extension',
        850000,
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
WHERE code IN ('visa_b1_voa', 'ext_b1_voa');
