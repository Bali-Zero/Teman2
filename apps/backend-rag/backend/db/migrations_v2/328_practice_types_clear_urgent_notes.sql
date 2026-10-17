-- Migration 328: clear the urgent-processing surcharge notes from four CRM catalogue rows
--
-- Ruled by the owner on 2026-10-17, second wave of the ruling that retired the
-- Urgent 1/2/3 Hari surcharges (migration 327): with no urgent service sold,
-- the "+ Rp N for urgent processing" notes that Reset Molina, Mutation
-- Passport, EPO and ERP still carried are stale. The canonical sheet
-- (backend/data/bali_zero_official_prices_2026.json) blanks the same notes in
-- this PR; the public mirror, the price list and the brochure follow from it.
-- Here the CRM catalogue's practice_types.description, which carried the same
-- surcharge as "Plus 400k urgent" and the like, is cleared.
--
-- Only the four codes whose description is still exactly the surcharge text
-- measured on production on 2026-10-17 are touched (predicate on code AND
-- text), so a description edited since is left alone. The two rows that say
-- "Including Urgent" (visa_c7_music_art, kitas_remote_worker_offshore) are
-- out of scope: the owner has not ruled on them. NULL is the column's "no
-- description" value: 52 of 121 rows at writing, none use ''. The rollback
-- restores the same four strings only where the description is NULL; a row
-- that was NULL before this migration for another reason would receive the
-- surcharge text on rollback (known limitation of a value-clearing step).
--
-- Numbered 328: production ledger max at writing is 327; no open branch
-- carries 328 or 329.
--
-- Idempotent: NULL never equals the surcharge text, so a rerun matches nothing.

UPDATE practice_types
SET description = NULL,
    updated_at = CURRENT_TIMESTAMP
WHERE (code, description) IN (
    ('other_reset_molina', 'Plus 400k urgent'),
    ('other_mutation_passport', 'Plus 350k urgent'),
    ('other_epo', 'Plus 300k urgent'),
    ('other_erp', 'Plus 500k urgent')
);

-- Postcondition: refuse to record this migration as applied while any of
-- the four rows still names the urgent surcharge.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM practice_types
        WHERE (code, description) IN (
            ('other_reset_molina', 'Plus 400k urgent'),
            ('other_mutation_passport', 'Plus 350k urgent'),
            ('other_epo', 'Plus 300k urgent'),
            ('other_erp', 'Plus 500k urgent')
        )
    ) THEN
        RAISE EXCEPTION 'migration 328: a practice_types row still names the urgent surcharge';
    END IF;
END $$;

-- === ROLLBACK ===
UPDATE practice_types
SET description = CASE code
        WHEN 'other_reset_molina' THEN 'Plus 400k urgent'
        WHEN 'other_mutation_passport' THEN 'Plus 350k urgent'
        WHEN 'other_epo' THEN 'Plus 300k urgent'
        WHEN 'other_erp' THEN 'Plus 500k urgent'
    END,
    updated_at = CURRENT_TIMESTAMP
WHERE code IN (
    'other_reset_molina',
    'other_mutation_passport',
    'other_epo',
    'other_erp'
)
  AND description IS NULL;
