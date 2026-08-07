-- ============================================================================
-- 265_visa_decision_trace_integrity.sql
-- Persist the deterministic evaluation-trace digest and final decision HMAC.
--
-- Existing rows remain valid and nullable: older engine builds wrote neither
-- field, and inventing cryptographic evidence retroactively would be false.
-- New writers persist both values. Pair/length constraints prevent partial or
-- malformed integrity metadata while keeping legacy shadow writers compatible.
-- ============================================================================

ALTER TABLE public.visa_decisions
    ADD COLUMN IF NOT EXISTS trace_sha256 BYTEA,
    ADD COLUMN IF NOT EXISTS decision_hmac BYTEA,
    ADD COLUMN IF NOT EXISTS decision_hmac_key_id TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.visa_decisions'::regclass
          AND conname = 'visa_decisions_trace_sha256_length'
    ) THEN
        ALTER TABLE public.visa_decisions
            ADD CONSTRAINT visa_decisions_trace_sha256_length
            CHECK (
                trace_sha256 IS NULL
                OR octet_length(trace_sha256) = 32
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.visa_decisions'::regclass
          AND conname = 'visa_decisions_integrity_binding'
    ) THEN
        ALTER TABLE public.visa_decisions
            ADD CONSTRAINT visa_decisions_integrity_binding
            CHECK (
                (
                    decision_hmac IS NULL
                    AND decision_hmac_key_id IS NULL
                )
                OR (
                    trace_sha256 IS NOT NULL
                    AND decision_hmac IS NOT NULL
                    AND octet_length(decision_hmac) = 32
                    AND decision_hmac_key_id
                        ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$'
                )
            );
    END IF;
END
$$;

COMMENT ON COLUMN public.visa_decisions.trace_sha256 IS
    'SHA-256 of the canonical same-pass deterministic evaluation trace';
COMMENT ON COLUMN public.visa_decisions.decision_hmac IS
    'HMAC-SHA256 authenticating the final public decision and trace digest';
COMMENT ON COLUMN public.visa_decisions.decision_hmac_key_id IS
    'Operator key identifier for decision_hmac; never secret key material';

-- === ROLLBACK ===

ALTER TABLE public.visa_decisions
    DROP CONSTRAINT IF EXISTS visa_decisions_integrity_binding,
    DROP CONSTRAINT IF EXISTS visa_decisions_trace_sha256_length,
    DROP COLUMN IF EXISTS decision_hmac_key_id,
    DROP COLUMN IF EXISTS decision_hmac,
    DROP COLUMN IF EXISTS trace_sha256;
