-- ============================================================================
-- 263_visa_evaluate_response_hmac.sql
-- Authenticate the complete durable Visa Oracle replay envelope.
--
-- response_sha256 remains an unkeyed corruption checksum.  response_hmac is
-- the authenticity boundary over RFC8785(response_body), domain-separated
-- from facts, request-binding, and Decision HMACs.  Existing completed rows
-- cannot be authenticated retroactively, so only their replay material is
-- invalidated fail-closed. The immutable key/request binding and original
-- frozen clock/expiry remain, preventing reuse with a different request.
-- ============================================================================

DO $$
BEGIN
    IF to_regclass('public.visa_evaluate_idempotency') IS NOT NULL THEN
        DROP TRIGGER IF EXISTS trg_guard_visa_evaluate_idempotency_mutation
            ON public.visa_evaluate_idempotency;
    END IF;
END;
$$;

ALTER TABLE IF EXISTS public.visa_evaluate_idempotency
    ADD COLUMN response_hmac BYTEA CHECK (
        response_hmac IS NULL OR octet_length(response_hmac) = 32
    ),
    ADD COLUMN response_hmac_key_id TEXT CHECK (
        response_hmac_key_id IS NULL
        OR response_hmac_key_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'
    );

UPDATE public.visa_evaluate_idempotency
SET response_body = NULL,
    response_sha256 = NULL,
    response_hmac = NULL,
    response_hmac_key_id = NULL,
    completed_at = NULL
WHERE response_body IS NOT NULL;

ALTER TABLE public.visa_evaluate_idempotency
    ADD CONSTRAINT visa_evaluate_idempotency_response_auth_complete CHECK (
        (
            response_body IS NULL
            AND response_hmac IS NULL
            AND response_hmac_key_id IS NULL
        )
        OR
        (
            response_body IS NOT NULL
            AND response_hmac IS NOT NULL
            AND response_hmac_key_id IS NOT NULL
        )
    );

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
       OR NEW.response_hmac IS NULL
       OR NEW.response_hmac_key_id IS NULL
       OR NEW.completed_at IS NULL THEN
        RAISE EXCEPTION 'idempotency completion must be atomic and authenticated';
    END IF;
    RETURN NEW;
END;
$$;

DO $$
BEGIN
    IF to_regclass('public.visa_evaluate_idempotency') IS NOT NULL THEN
        CREATE TRIGGER trg_guard_visa_evaluate_idempotency_mutation
        BEFORE UPDATE OR DELETE ON public.visa_evaluate_idempotency
        FOR EACH ROW EXECUTE FUNCTION public.guard_visa_evaluate_idempotency_mutation();
    END IF;
END;
$$;

-- === ROLLBACK ===

DO $$
BEGIN
    IF to_regclass('public.visa_evaluate_idempotency') IS NOT NULL THEN
        DROP TRIGGER IF EXISTS trg_guard_visa_evaluate_idempotency_mutation
            ON public.visa_evaluate_idempotency;
    END IF;
END;
$$;

ALTER TABLE IF EXISTS public.visa_evaluate_idempotency
    DROP CONSTRAINT IF EXISTS visa_evaluate_idempotency_response_auth_complete,
    DROP COLUMN IF EXISTS response_hmac,
    DROP COLUMN IF EXISTS response_hmac_key_id;

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

DO $$
BEGIN
    IF to_regclass('public.visa_evaluate_idempotency') IS NOT NULL THEN
        CREATE TRIGGER trg_guard_visa_evaluate_idempotency_mutation
        BEFORE UPDATE OR DELETE ON public.visa_evaluate_idempotency
        FOR EACH ROW EXECUTE FUNCTION public.guard_visa_evaluate_idempotency_mutation();
    END IF;
END;
$$;
