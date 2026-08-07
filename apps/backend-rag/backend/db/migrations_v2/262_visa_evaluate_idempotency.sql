-- ============================================================================
-- 262_visa_evaluate_idempotency.sql
-- Durable, PII-minimized replay contract for POST /api/visa-oracle/evaluate.
--
-- The raw Idempotency-Key and raw ApplicantFacts are never stored.  A key is
-- bound once to a domain-separated HMAC of the canonical request and to a
-- database-frozen clock; retries therefore evaluate the same bitemporal
-- RulePack instant and return the validated JSONB response selected by the
-- first completion.  The response contains only the public decision envelope
-- (no applicant answers).
-- ============================================================================

CREATE TABLE public.visa_evaluate_idempotency (
    key_sha256       BYTEA PRIMARY KEY CHECK (octet_length(key_sha256) = 32),
    request_hmac     BYTEA NOT NULL CHECK (octet_length(request_hmac) = 32),
    request_hmac_key_id TEXT NOT NULL CHECK (
        request_hmac_key_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'
    ),
    reserved_at      TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    response_body    JSONB,
    response_sha256  BYTEA CHECK (
        response_sha256 IS NULL OR octet_length(response_sha256) = 32
    ),
    completed_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    expires_at       TIMESTAMPTZ NOT NULL DEFAULT (statement_timestamp() + INTERVAL '24 hours'),
    CHECK (jsonb_typeof(response_body) = 'object' OR response_body IS NULL),
    CHECK (expires_at > created_at),
    CHECK (
        (response_body IS NULL AND response_sha256 IS NULL AND completed_at IS NULL)
        OR
        (response_body IS NOT NULL AND response_sha256 IS NOT NULL AND completed_at IS NOT NULL)
    )
);

COMMENT ON TABLE public.visa_evaluate_idempotency IS
    'PII-minimized Visa Oracle response replay cache. Raw keys and applicant facts are forbidden.';

CREATE INDEX idx_visa_evaluate_idempotency_expires_at
    ON public.visa_evaluate_idempotency (expires_at);

CREATE OR REPLACE FUNCTION public.guard_visa_evaluate_idempotency_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF clock_timestamp() < OLD.expires_at THEN
            RAISE EXCEPTION 'unexpired visa_evaluate_idempotency rows are immutable';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.key_sha256 IS DISTINCT FROM NEW.key_sha256
       OR OLD.request_hmac IS DISTINCT FROM NEW.request_hmac
       OR OLD.request_hmac_key_id IS DISTINCT FROM NEW.request_hmac_key_id
       OR OLD.reserved_at IS DISTINCT FROM NEW.reserved_at
       OR OLD.created_at IS DISTINCT FROM NEW.created_at
       OR OLD.expires_at IS DISTINCT FROM NEW.expires_at THEN
        RAISE EXCEPTION 'visa_evaluate_idempotency request binding is immutable';
    END IF;
    IF OLD.response_body IS NOT NULL THEN
        RAISE EXCEPTION 'completed visa_evaluate_idempotency rows are immutable';
    END IF;
    IF NEW.response_body IS NULL
       OR NEW.response_sha256 IS NULL
       OR NEW.completed_at IS NULL THEN
        RAISE EXCEPTION 'idempotency completion must be atomic';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_visa_evaluate_idempotency_mutation
BEFORE UPDATE OR DELETE ON public.visa_evaluate_idempotency
FOR EACH ROW EXECUTE FUNCTION public.guard_visa_evaluate_idempotency_mutation();

-- === ROLLBACK ===

DROP TABLE IF EXISTS public.visa_evaluate_idempotency;
DROP FUNCTION IF EXISTS public.guard_visa_evaluate_idempotency_mutation();
