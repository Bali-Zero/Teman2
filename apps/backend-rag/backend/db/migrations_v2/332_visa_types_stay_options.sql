-- Migration 332: preserve discrete initial-stay choices in their official units.
-- Owner ruling, E30 brief 2026-10-18: years stay years, never converted to days.
-- NULL means unknown. An empty array has no stated options.

SET lock_timeout = '5s';
SET statement_timeout = '60s';

ALTER TABLE visa_types ADD COLUMN IF NOT EXISTS stay_options JSONB;

CREATE OR REPLACE FUNCTION visa_types_stay_options_valid(options JSONB)
RETURNS BOOLEAN
LANGUAGE SQL IMMUTABLE PARALLEL SAFE
AS $function$
    SELECT CASE
        WHEN options IS NULL THEN TRUE
        WHEN jsonb_typeof(options) <> 'array' THEN FALSE
        ELSE NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements(options) AS choices(choice)
            WHERE (CASE
                WHEN jsonb_typeof(choice) <> 'object' THEN FALSE
                ELSE (choice - 'value' - 'unit' = '{}'::jsonb)
                    AND choice ->> 'unit' IN ('DAY', 'MONTH', 'YEAR')
                    AND CASE WHEN jsonb_typeof(choice -> 'value') = 'number'
                        THEN (choice ->> 'value')::numeric > 0
                            AND mod((choice ->> 'value')::numeric, 1) = 0
                        ELSE FALSE
                    END
            END) IS NOT TRUE
        )
    END;
$function$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vt_stay_options_chk'
                   AND conrelid = 'visa_types'::regclass) THEN
        ALTER TABLE visa_types ADD CONSTRAINT vt_stay_options_chk
            CHECK (visa_types_stay_options_valid(stay_options));
    END IF;
END $$;

-- === ROLLBACK ===

-- Only this migration's projection column, constraint and helper are removed.
ALTER TABLE visa_types
    -- squawk-ignore ban-drop-constraint
    DROP CONSTRAINT IF EXISTS vt_stay_options_chk,
    -- squawk-ignore ban-drop-column
    DROP COLUMN IF EXISTS stay_options;
-- squawk-ignore ban-drop-function
DROP FUNCTION IF EXISTS visa_types_stay_options_valid(JSONB);
