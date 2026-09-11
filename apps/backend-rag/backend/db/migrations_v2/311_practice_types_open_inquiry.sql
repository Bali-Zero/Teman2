-- Migration 311: `open_inquiry` placeholder practice type
--
-- Purpose (Ari's proposal, 2026-09-11): at kita.balizero.com/process/new the
-- team no longer has to pick a service category to open an INQUIRY. The
-- practice is created against this placeholder type and the real service is
-- chosen later, before the practice moves to `waiting_documents`
-- (gate enforced in crm_practices.update_practice).
--
-- Why a placeholder row instead of practice_type_id = NULL: ~40 read paths
-- (kanban, portal, analytics, shared memory) INNER JOIN practice_types, so a
-- NULL type would silently hide the inquiry everywhere. A real row keeps
-- every JOIN intact.
--
-- category = 'inquiry' is deliberately NOT in CATEGORY_ORDER, and the
-- catalog endpoint also filters the code explicitly, so the placeholder never
-- appears in the service dropdown.
--
-- Idempotent: ON CONFLICT(code) DO UPDATE, same pattern as migrations 148/220.

INSERT INTO practice_types (
    code, name, description, category, base_price,
    typical_duration_days, is_active
)
VALUES
    (
        'open_inquiry',
        'Open Inquiry (service to be defined)',
        'Placeholder while the inquiry is open. Pick the real service before moving to Waiting Documents.',
        'inquiry',
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
-- Soft-disable only: practices may already reference the row via
-- practice_type_id. Hidden from the catalog, referential integrity preserved.
UPDATE practice_types
SET is_active = false
WHERE code = 'open_inquiry';
