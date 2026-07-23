-- Migration 255: Visa Oracle SHADOW evidence substrate
--
-- Migration 252 intentionally persisted only the minimum decision projection.
-- That projection cannot prove the objective ENFORCE gate: decision_id changes
-- across evaluations of the same Match request, and the row carries neither the
-- Match category nor the candidate codes/claim-to-source map.  This roll-forward
-- adds only PII-free audit metadata needed to measure G-a (volume/breadth) and
-- G-c (grounding).  Existing rows remain valid but deliberately fail closed in
-- the evidence collector because their new nullable correlators are absent.
--
-- request_fingerprint is SHA-256(match_hash), never the public Match token and
-- never applicant data.  The 16-character Match token is randomly generated and
-- high entropy; hashing preserves request-level deduplication without persisting
-- or exposing the token itself.  candidate_summary and grounding_summary contain
-- only engine identifiers, reason codes, and source-record UUIDs.
--
-- This migration does not change VISA_ENGINE_MATCH_MODE and cannot arm ENFORCE.

ALTER TABLE public.visa_decisions
    ADD COLUMN request_fingerprint BYTEA
        CHECK (
            request_fingerprint IS NULL
            OR octet_length(request_fingerprint) = 32
        ),
    ADD COLUMN request_category TEXT
        CHECK (
            request_category IS NULL
            OR request_category IN (
                'work_remote',
                'investor',
                'work_employee',
                'family',
                'long_tourism',
                'retirement',
                'student',
                'other'
            )
        ),
    ADD COLUMN candidate_summary JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(candidate_summary) = 'array'),
    ADD COLUMN grounding_summary JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(grounding_summary) = 'array');

CREATE INDEX idx_visa_decisions_shadow_request_fingerprint
    ON public.visa_decisions (request_fingerprint)
    WHERE engine_surface = 'MATCH' AND engine_mode = 'SHADOW';

CREATE INDEX idx_visa_decisions_shadow_request_category
    ON public.visa_decisions (request_category, evaluated_at)
    WHERE engine_surface = 'MATCH' AND engine_mode = 'SHADOW';

-- === ROLLBACK ===
DROP INDEX IF EXISTS public.idx_visa_decisions_shadow_request_category;
DROP INDEX IF EXISTS public.idx_visa_decisions_shadow_request_fingerprint;

ALTER TABLE IF EXISTS public.visa_decisions
    DROP COLUMN IF EXISTS grounding_summary,
    DROP COLUMN IF EXISTS candidate_summary,
    DROP COLUMN IF EXISTS request_category,
    DROP COLUMN IF EXISTS request_fingerprint;
