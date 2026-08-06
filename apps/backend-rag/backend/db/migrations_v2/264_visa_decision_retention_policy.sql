-- ============================================================================
-- 264_visa_decision_retention_policy.sql
-- Zero-approved, policy-driven retention for durable Visa Oracle decisions.
--
-- This migration deliberately seeds NO duration and NO policy row. Every new
-- SHADOW or ENFORCE decision insert fails closed until Zero records an explicit
-- duration, anchor, effective period, approver, and approval reference.
-- Existing history remains readable and receives no fabricated retroactive
-- deadline; its disposition/backfill is an explicit Zero decision.
--
-- Purging is exposed as a bounded database primitive but no scheduler cadence
-- is invented here. Legal-hold transitions keep per-decision history that
-- cascades with the policy-retained parent; deletion batches survive only as
-- aggregate evidence
-- without a public/stable applicant or decision identifier.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE public.visa_decision_retention_policies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    environment         TEXT NOT NULL
        CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
    policy_version      TEXT NOT NULL
        CHECK (policy_version ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'),
    retention_interval  INTERVAL NOT NULL
        CHECK (retention_interval > INTERVAL '0 seconds'),
    idempotency_retention_interval INTERVAL NOT NULL,
    legal_hold_review_interval INTERVAL NOT NULL
        CHECK (legal_hold_review_interval > INTERVAL '0 seconds'),
    retention_anchor    TEXT NOT NULL
        CHECK (retention_anchor IN ('EVALUATED_AT', 'CREATED_AT')),
    effective_period    TSTZRANGE NOT NULL,
    approved_by         TEXT NOT NULL
        CHECK (approved_by ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$'),
    approval_reference  TEXT NOT NULL
        CHECK (length(approval_reference) BETWEEN 1 AND 2048),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (NOT isempty(effective_period)),
    CHECK (lower(effective_period) IS NOT NULL),
    CHECK (lower_inc(effective_period)),
    CHECK (upper(effective_period) IS NULL OR NOT upper_inc(effective_period)),
    CHECK (
        idempotency_retention_interval > INTERVAL '0 seconds'
        AND idempotency_retention_interval <= retention_interval
    ),
    UNIQUE (environment, policy_version),
    EXCLUDE USING gist (environment WITH =, effective_period WITH &&)
);

COMMENT ON TABLE public.visa_decision_retention_policies IS
    'Zero-approved retention authority; activation requires a separated policy-writer owner/role.';

CREATE FUNCTION public.guard_visa_decision_retention_policy_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'visa_decision_retention_policies is append-only';
    END IF;
    IF (to_jsonb(OLD) - 'effective_period')
           IS DISTINCT FROM (to_jsonb(NEW) - 'effective_period')
       OR lower(OLD.effective_period) IS DISTINCT FROM lower(NEW.effective_period)
       OR upper(OLD.effective_period) IS NOT NULL
       OR upper(NEW.effective_period) IS NULL
       OR upper(NEW.effective_period) <= lower(NEW.effective_period) THEN
        RAISE EXCEPTION 'retention policy update may only close one open effective_period';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM public.visa_decisions AS decision
         WHERE decision.retention_policy_id = OLD.id
           AND NOT (NEW.effective_period @> decision.evaluated_at)
    ) OR EXISTS (
        SELECT 1
          FROM public.visa_evaluate_idempotency AS replay
         WHERE replay.retention_policy_id = OLD.id
           AND NOT (NEW.effective_period @> replay.reserved_at)
    ) THEN
        RAISE EXCEPTION 'retention policy close would strand an existing binding';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_decision_retention_policies_guard
BEFORE UPDATE OR DELETE ON public.visa_decision_retention_policies
FOR EACH ROW EXECUTE FUNCTION public.guard_visa_decision_retention_policy_mutation();

CREATE TRIGGER visa_decision_retention_policies_no_wipe
BEFORE TRUNCATE ON public.visa_decision_retention_policies
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

-- Idempotency replay retention is part of the same Zero-approved policy as
-- decision retention. Pre-264 rows keep their original deadline and a NULL
-- binding: no retroactive authority is invented. The NOT VALID constraint is
-- enforced for every new row while preserving that explicit legacy cohort.
ALTER TABLE public.visa_evaluate_idempotency
    ADD COLUMN environment TEXT CHECK (
        environment IN ('TEST', 'STAGING', 'PRODUCTION')
    ),
    ADD COLUMN retention_policy_id UUID
        REFERENCES public.visa_decision_retention_policies (id),
    ALTER COLUMN expires_at DROP DEFAULT,
    ADD CONSTRAINT visa_evaluate_idempotency_retention_binding_pair CHECK (
        (environment IS NULL AND retention_policy_id IS NULL)
        OR
        (environment IS NOT NULL AND retention_policy_id IS NOT NULL)
    );

ALTER TABLE public.visa_evaluate_idempotency
    ADD CONSTRAINT visa_evaluate_idempotency_retention_required CHECK (
        environment IS NOT NULL AND retention_policy_id IS NOT NULL
    ) NOT VALID;

CREATE FUNCTION public.bind_visa_evaluate_idempotency_retention_policy()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    policy RECORD;
    expected_expires_at TIMESTAMPTZ;
BEGIN
    IF NEW.reserved_at IS DISTINCT FROM statement_timestamp()
       OR NEW.created_at IS DISTINCT FROM statement_timestamp() THEN
        RAISE EXCEPTION 'idempotency reserved_at and created_at must use the database statement clock';
    END IF;
    IF NEW.environment IS NULL THEN
        RAISE EXCEPTION 'idempotency reservation requires an environment';
    END IF;

    BEGIN
        SELECT id, idempotency_retention_interval
          INTO STRICT policy
          FROM public.visa_decision_retention_policies
         WHERE environment = NEW.environment
           AND effective_period @> NEW.reserved_at
         FOR SHARE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'idempotency reservation has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'idempotency retention policy authority is ambiguous';
    END;

    expected_expires_at := NEW.reserved_at + policy.idempotency_retention_interval;
    IF expected_expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'idempotency retention deadline has already elapsed';
    END IF;
    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'idempotency retention policy does not match active policy';
    END IF;
    IF NEW.expires_at IS NOT NULL
       AND NEW.expires_at IS DISTINCT FROM expected_expires_at THEN
        RAISE EXCEPTION 'idempotency retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.expires_at := expected_expires_at;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_evaluate_idempotency_retention_binding
BEFORE INSERT ON public.visa_evaluate_idempotency
FOR EACH ROW EXECUTE FUNCTION public.bind_visa_evaluate_idempotency_retention_policy();

CREATE OR REPLACE FUNCTION public.guard_visa_evaluate_idempotency_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    requested_by TEXT;
    dsr_requested_by TEXT;
    table_owner NAME;
BEGIN
    IF TG_OP = 'DELETE' THEN
        requested_by := current_setting('visa.idempotency_retention_requested_by', TRUE);
        dsr_requested_by := current_setting('visa.dsr_requested_by', TRUE);
        SELECT pg_get_userbyid(relation.relowner)
          INTO table_owner
          FROM pg_class AS relation
          JOIN pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname = 'visa_evaluate_idempotency';
        IF current_user <> table_owner THEN
            RAISE EXCEPTION 'idempotency delete must use a bounded retention capability';
        END IF;
        IF dsr_requested_by IS NOT NULL
           AND dsr_requested_by ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
            RETURN OLD;
        END IF;
        IF requested_by IS NULL
           OR requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
            RAISE EXCEPTION 'idempotency delete must use a bounded retention capability';
        END IF;
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
       OR OLD.expires_at IS DISTINCT FROM NEW.expires_at
       OR OLD.environment IS DISTINCT FROM NEW.environment
       OR OLD.retention_policy_id IS DISTINCT FROM NEW.retention_policy_id THEN
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

CREATE TABLE public.visa_idempotency_retention_batches (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    executor_label          TEXT NOT NULL CHECK (
        executor_label ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
    ),
    operation_type          TEXT NOT NULL CHECK (
        operation_type IN ('ONLINE_RECLAIM', 'WORKER_PURGE')
    ),
    expired_rows_before     BIGINT NOT NULL CHECK (expired_rows_before >= 0),
    max_lag_seconds_before  DOUBLE PRECISION NOT NULL
        CHECK (max_lag_seconds_before >= 0),
    deleted_count           INTEGER NOT NULL CHECK (deleted_count >= 0),
    occurred_at             TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

COMMENT ON TABLE public.visa_idempotency_retention_batches IS
    'Append-only applicant/key-identifier-free evidence; executor labels are operational data.';

CREATE TRIGGER visa_idempotency_retention_batches_immutable
BEFORE UPDATE OR DELETE ON public.visa_idempotency_retention_batches
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TRIGGER visa_idempotency_retention_batches_no_wipe
BEFORE TRUNCATE ON public.visa_idempotency_retention_batches
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE FUNCTION public.visa_idempotency_retention_evidence()
RETURNS TABLE (
    expired_rows BIGINT,
    max_lag_seconds DOUBLE PRECISION,
    observed_at TIMESTAMPTZ
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH observation AS (
        SELECT clock_timestamp() AS observed_at
    )
    SELECT
        count(replay.key_sha256)::BIGINT AS expired_rows,
        COALESCE(
            max(
                GREATEST(
                    EXTRACT(EPOCH FROM observation.observed_at - replay.expires_at),
                    0
                )
            ),
            0
        )::DOUBLE PRECISION AS max_lag_seconds,
        observation.observed_at
    FROM observation
    LEFT JOIN public.visa_evaluate_idempotency AS replay
      ON replay.expires_at <= observation.observed_at
    GROUP BY observation.observed_at;
$$;

CREATE FUNCTION public.purge_visa_evaluate_idempotency(
    p_limit INTEGER,
    p_requested_by TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    observed_at TIMESTAMPTZ := clock_timestamp();
    expired_rows_before BIGINT;
    max_lag_seconds_before DOUBLE PRECISION;
    deleted_count INTEGER;
BEGIN
    IF p_limit IS NULL OR p_limit < 1 OR p_limit > 1000 THEN
        RAISE EXCEPTION 'purge limit must be between 1 and 1000';
    END IF;
    IF p_requested_by IS NULL
       OR p_requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'purge requested_by has invalid format';
    END IF;
    PERFORM set_config(
        'visa.idempotency_retention_requested_by',
        p_requested_by,
        TRUE
    );

    SELECT
        count(*)::BIGINT,
        COALESCE(
            max(GREATEST(EXTRACT(EPOCH FROM observed_at - expires_at), 0)),
            0
        )::DOUBLE PRECISION
      INTO expired_rows_before, max_lag_seconds_before
      FROM public.visa_evaluate_idempotency
     WHERE expires_at <= observed_at;

    WITH candidates AS (
        SELECT replay.key_sha256
          FROM public.visa_evaluate_idempotency AS replay
         WHERE replay.expires_at <= observed_at
         ORDER BY replay.expires_at, replay.key_sha256
         LIMIT p_limit
         FOR UPDATE SKIP LOCKED
    )
    DELETE FROM public.visa_evaluate_idempotency AS replay
     USING candidates
     WHERE replay.key_sha256 = candidates.key_sha256;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    INSERT INTO public.visa_idempotency_retention_batches (
        executor_label, operation_type, expired_rows_before,
        max_lag_seconds_before, deleted_count
    ) VALUES (
        session_user || ':' || p_requested_by, 'WORKER_PURGE', expired_rows_before,
        max_lag_seconds_before, deleted_count
    );
    RETURN deleted_count;
END;
$$;

CREATE FUNCTION public.visa_idempotency_key_usage_evidence()
RETURNS TABLE (
    key_purpose TEXT,
    key_id TEXT,
    active_rows BIGINT,
    latest_expiry TIMESTAMPTZ,
    observed_at TIMESTAMPTZ
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    WITH observation AS (
        SELECT clock_timestamp() AS observed_at
    ), key_usage AS (
        SELECT
            'REQUEST_HMAC'::TEXT AS key_purpose,
            replay.request_hmac_key_id AS key_id,
            replay.expires_at
        FROM public.visa_evaluate_idempotency AS replay, observation
        WHERE replay.expires_at > observation.observed_at

        UNION ALL

        SELECT
            'RESPONSE_HMAC'::TEXT,
            replay.response_hmac_key_id,
            replay.expires_at
        FROM public.visa_evaluate_idempotency AS replay, observation
        WHERE replay.expires_at > observation.observed_at
          AND replay.response_hmac_key_id IS NOT NULL

        UNION ALL

        SELECT
            'DECISION_INTEGRITY_HMAC'::TEXT,
            replay.response_body #>> '{decision,decision_integrity,key_id}',
            replay.expires_at
        FROM public.visa_evaluate_idempotency AS replay, observation
        WHERE replay.expires_at > observation.observed_at
          AND replay.response_body #>> '{decision,decision_integrity,key_id}' IS NOT NULL
    )
    SELECT
        key_usage.key_purpose,
        key_usage.key_id,
        count(*)::BIGINT,
        max(key_usage.expires_at),
        observation.observed_at
    FROM key_usage, observation
    GROUP BY key_usage.key_purpose, key_usage.key_id, observation.observed_at
    ORDER BY key_usage.key_purpose, key_usage.key_id;
$$;

CREATE FUNCTION public.prepare_visa_evaluate_idempotency_reservation(
    p_key_sha256 BYTEA,
    p_limit INTEGER,
    p_requested_by TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    observed_at TIMESTAMPTZ := clock_timestamp();
    expired_rows_before BIGINT;
    max_lag_seconds_before DOUBLE PRECISION;
    reclaimed_count INTEGER;
    swept_count INTEGER := 0;
    deleted_count INTEGER;
BEGIN
    IF p_key_sha256 IS NULL OR octet_length(p_key_sha256) <> 32 THEN
        RAISE EXCEPTION 'reservation key hash must be 32 bytes';
    END IF;
    IF p_limit IS NULL OR p_limit < 1 OR p_limit > 128 THEN
        RAISE EXCEPTION 'online retention limit must be between 1 and 128';
    END IF;
    IF p_requested_by IS NULL
       OR p_requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'online retention requested_by has invalid format';
    END IF;

    SELECT
        count(*)::BIGINT,
        COALESCE(
            max(GREATEST(EXTRACT(EPOCH FROM observed_at - expires_at), 0)),
            0
        )::DOUBLE PRECISION
      INTO expired_rows_before, max_lag_seconds_before
      FROM public.visa_evaluate_idempotency
     WHERE expires_at <= observed_at;

    PERFORM set_config(
        'visa.idempotency_retention_requested_by',
        p_requested_by,
        TRUE
    );
    DELETE FROM public.visa_evaluate_idempotency
     WHERE key_sha256 = p_key_sha256
       AND expires_at <= observed_at;
    GET DIAGNOSTICS reclaimed_count = ROW_COUNT;

    IF reclaimed_count < p_limit THEN
        WITH candidates AS (
            SELECT replay.key_sha256
              FROM public.visa_evaluate_idempotency AS replay
             WHERE replay.expires_at <= observed_at
               AND replay.key_sha256 <> p_key_sha256
             ORDER BY replay.expires_at, replay.key_sha256
             LIMIT (p_limit - reclaimed_count)
             FOR UPDATE SKIP LOCKED
        )
        DELETE FROM public.visa_evaluate_idempotency AS replay
         USING candidates
         WHERE replay.key_sha256 = candidates.key_sha256;
        GET DIAGNOSTICS swept_count = ROW_COUNT;
    END IF;
    deleted_count := reclaimed_count + swept_count;

    IF deleted_count > 0 THEN
        INSERT INTO public.visa_idempotency_retention_batches (
            executor_label, operation_type, expired_rows_before,
            max_lag_seconds_before, deleted_count
        ) VALUES (
            session_user || ':' || p_requested_by, 'ONLINE_RECLAIM', expired_rows_before,
            max_lag_seconds_before, deleted_count
        );
    END IF;
    RETURN deleted_count;
END;
$$;

-- PUBLIC revocation is necessary but not sufficient: PostgreSQL function/table
-- owners retain privileges. This migration intentionally invents no production
-- roles or grants. G0 remains blocked until Zero transfers ownership away from
-- the serving/runtime role and grants only the narrow policy-writer, online
-- reclaim, purge/evidence, and hold-transition capabilities.
REVOKE ALL ON FUNCTION public.visa_idempotency_retention_evidence() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.visa_idempotency_key_usage_evidence() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.purge_visa_evaluate_idempotency(INTEGER, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.prepare_visa_evaluate_idempotency_reservation(
    BYTEA, INTEGER, TEXT
) FROM PUBLIC;

COMMENT ON FUNCTION public.visa_idempotency_retention_evidence() IS
    'Applicant/key-identifier-free backlog and maximum purge lag; requires an operator grant.';
COMMENT ON FUNCTION public.visa_idempotency_key_usage_evidence() IS
    'Applicant-free active key-id usage for safe HMAC retirement; requires an operator grant.';
COMMENT ON FUNCTION public.purge_visa_evaluate_idempotency(INTEGER, TEXT) IS
    'Bounded idempotency purge; requires an explicit operator grant and scheduler.';
COMMENT ON FUNCTION public.prepare_visa_evaluate_idempotency_reservation(
    BYTEA, INTEGER, TEXT
) IS
    'Bounded online expired-key reclaim/sweep; app requires EXECUTE, never table DELETE.';

CREATE TABLE public.visa_decision_legal_hold_events (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    decision_row_id     UUID NOT NULL REFERENCES public.visa_decisions (id)
        ON DELETE CASCADE,
    retention_policy_id UUID NOT NULL
        REFERENCES public.visa_decision_retention_policies (id),
    event_type          TEXT NOT NULL
        CHECK (event_type IN ('LEGAL_HOLD_SET', 'LEGAL_HOLD_RELEASED')),
    old_legal_hold      BOOLEAN NOT NULL,
    new_legal_hold      BOOLEAN NOT NULL,
    executor_label      TEXT NOT NULL CHECK (
        executor_label ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
    ),
    case_reference      TEXT NOT NULL CHECK (
        case_reference ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'
    ),
    reason_code         TEXT NOT NULL CHECK (
        reason_code ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'
    ),
    approved_by         TEXT NOT NULL CHECK (
        approved_by ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$'
    ),
    review_due_at       TIMESTAMPTZ,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (
        (event_type = 'LEGAL_HOLD_SET' AND old_legal_hold = FALSE AND new_legal_hold = TRUE)
        OR
        (event_type = 'LEGAL_HOLD_RELEASED' AND old_legal_hold = TRUE AND new_legal_hold = FALSE)
    ),
    CHECK (
        (event_type = 'LEGAL_HOLD_SET' AND review_due_at IS NOT NULL)
        OR (event_type = 'LEGAL_HOLD_RELEASED' AND review_due_at IS NULL)
    )
);

COMMENT ON TABLE public.visa_decision_legal_hold_events IS
    'Meaningful per-decision hold history, deleted atomically with its policy-retained parent.';

CREATE FUNCTION public.guard_visa_decision_legal_hold_events_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    requested_by TEXT;
    dsr_requested_by TEXT;
    table_owner NAME;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'visa_decision_legal_hold_events is append-only';
    END IF;
    requested_by := current_setting('visa.retention_requested_by', TRUE);
    dsr_requested_by := current_setting('visa.dsr_requested_by', TRUE);
    SELECT pg_get_userbyid(relation.relowner)
      INTO table_owner
      FROM pg_class AS relation
      JOIN pg_namespace AS namespace
        ON namespace.oid = relation.relnamespace
     WHERE namespace.nspname = 'public'
       AND relation.relname = 'visa_decision_legal_hold_events';
    IF current_user <> table_owner THEN
        RAISE EXCEPTION 'legal-hold history deletion requires the parent retention purge';
    END IF;
    IF dsr_requested_by IS NOT NULL
       AND dsr_requested_by ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RETURN OLD;
    END IF;
    IF requested_by IS NULL
       OR requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'legal-hold history deletion requires the parent retention purge';
    END IF;
    RETURN OLD;
END;
$$;

CREATE TRIGGER visa_decision_legal_hold_events_guard
BEFORE UPDATE OR DELETE ON public.visa_decision_legal_hold_events
FOR EACH ROW EXECUTE FUNCTION public.guard_visa_decision_legal_hold_events_mutation();

CREATE TRIGGER visa_decision_legal_hold_events_no_wipe
BEFORE TRUNCATE ON public.visa_decision_legal_hold_events
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TABLE public.visa_decision_retention_batches (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    retention_policy_id UUID NOT NULL
        REFERENCES public.visa_decision_retention_policies (id),
    affected_count      INTEGER NOT NULL CHECK (affected_count > 0),
    executor_label      TEXT NOT NULL CHECK (
        executor_label ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
    ),
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

COMMENT ON TABLE public.visa_decision_retention_batches IS
    'Aggregate purge evidence with no decision/public applicant identifier.';

CREATE TRIGGER visa_decision_retention_batches_immutable
BEFORE UPDATE OR DELETE ON public.visa_decision_retention_batches
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TRIGGER visa_decision_retention_batches_no_wipe
BEFORE TRUNCATE ON public.visa_decision_retention_batches
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TABLE public.visa_decision_dsr_erasure_batches (
    id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_reference           TEXT NOT NULL CHECK (
        case_reference ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'
    ),
    decision_rows_deleted    INTEGER NOT NULL CHECK (decision_rows_deleted = 1),
    payload_rows_deleted     INTEGER NOT NULL CHECK (payload_rows_deleted BETWEEN 0 AND 1),
    idempotency_rows_deleted INTEGER NOT NULL CHECK (idempotency_rows_deleted >= 0),
    executor_label           TEXT NOT NULL CHECK (
        executor_label ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
    ),
    occurred_at              TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

COMMENT ON TABLE public.visa_decision_dsr_erasure_batches IS
    'Append-only aggregate DSR erasure evidence; contains no applicant or decision identifier.';

CREATE TRIGGER visa_decision_dsr_erasure_batches_immutable
BEFORE UPDATE OR DELETE ON public.visa_decision_dsr_erasure_batches
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TRIGGER visa_decision_dsr_erasure_batches_no_wipe
BEFORE TRUNCATE ON public.visa_decision_dsr_erasure_batches
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

ALTER TABLE public.visa_decisions
    ADD COLUMN retention_policy_id UUID
        REFERENCES public.visa_decision_retention_policies (id),
    ADD COLUMN retention_until TIMESTAMPTZ,
    ADD COLUMN legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    ADD CONSTRAINT visa_decisions_retention_binding_pair CHECK (
        (retention_policy_id IS NULL AND retention_until IS NULL)
        OR
        (retention_policy_id IS NOT NULL AND retention_until IS NOT NULL)
    );

-- NOT VALID preserves all pre-migration audit rows whose policy cannot be
-- invented retroactively. PostgreSQL still enforces this constraint for every
-- new SHADOW or ENFORCE row; an explicit Zero-approved disposition/backfill is
-- required before validation.
ALTER TABLE public.visa_decisions
    ADD CONSTRAINT visa_decisions_retention_required CHECK (
        retention_policy_id IS NOT NULL AND retention_until IS NOT NULL
    ) NOT VALID;

CREATE INDEX idx_visa_decisions_retention_purge
    ON public.visa_decisions (retention_until, id)
    WHERE legal_hold = FALSE AND retention_until IS NOT NULL;

CREATE FUNCTION public.bind_visa_decision_retention_policy()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    policy RECORD;
    expected_until TIMESTAMPTZ;
BEGIN
    -- created_at is structurally DB-owned below. evaluated_at remains the
    -- engine/bitemporal clock by contract; its authoritative skew semantics
    -- are a separate Zero activation decision (F16), not invented here.
    IF NEW.created_at IS DISTINCT FROM transaction_timestamp() THEN
        RAISE EXCEPTION 'decision created_at must use the database transaction clock';
    END IF;
    IF NEW.legal_hold THEN
        RAISE EXCEPTION 'new visa_decisions rows cannot begin under legal hold';
    END IF;

    BEGIN
        SELECT id, retention_interval, retention_anchor
          INTO STRICT policy
         FROM public.visa_decision_retention_policies
         WHERE environment = NEW.environment
           AND effective_period @> NEW.evaluated_at
         FOR SHARE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'decision has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'decision retention policy authority is ambiguous';
    END;

    expected_until := (
        CASE policy.retention_anchor
            WHEN 'EVALUATED_AT' THEN NEW.evaluated_at
            WHEN 'CREATED_AT' THEN NEW.created_at
        END
    ) + policy.retention_interval;
    IF expected_until <= clock_timestamp() THEN
        RAISE EXCEPTION 'decision retention deadline has already elapsed';
    END IF;

    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'decision retention policy does not match active policy';
    END IF;
    IF NEW.retention_until IS NOT NULL
       AND NEW.retention_until IS DISTINCT FROM expected_until THEN
        RAISE EXCEPTION 'decision retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.retention_until := expected_until;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_decisions_retention_binding
BEFORE INSERT ON public.visa_decisions
FOR EACH ROW EXECUTE FUNCTION public.bind_visa_decision_retention_policy();

-- Payload retention is not caller-selected. The only supported schedule is
-- the parent decision's policy-derived deadline, and a new payload cannot be
-- introduced while either side claims a legal hold. FOR SHARE serializes the
-- insert with parent hold transitions and deletion.
CREATE FUNCTION public.bind_visa_decision_payload_retention()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    parent RECORD;
BEGIN
    BEGIN
        SELECT retention_until, legal_hold
          INTO STRICT parent
          FROM public.visa_decisions
         WHERE id = NEW.decision_id
         FOR SHARE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'payload requires an existing retained decision';
    END;

    IF parent.retention_until IS NULL THEN
        RAISE EXCEPTION 'legacy decision without a retention binding cannot receive a payload';
    END IF;
    IF parent.retention_until <= clock_timestamp() THEN
        RAISE EXCEPTION 'expired decision cannot receive a payload';
    END IF;
    IF parent.legal_hold OR NEW.legal_hold THEN
        RAISE EXCEPTION 'new payload cannot begin under legal hold';
    END IF;
    IF NEW.purge_after IS DISTINCT FROM parent.retention_until THEN
        RAISE EXCEPTION 'payload retention deadline must equal the parent policy deadline';
    END IF;

    NEW.purge_after := parent.retention_until;
    NEW.legal_hold := FALSE;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_decision_payloads_retention_binding
BEFORE INSERT ON public.visa_decision_payloads
FOR EACH ROW EXECUTE FUNCTION public.bind_visa_decision_payload_retention();

DROP TRIGGER visa_decision_payloads_guard ON public.visa_decision_payloads;

CREATE OR REPLACE FUNCTION public.reject_visa_decision_payloads_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    requested_by TEXT;
    dsr_requested_by TEXT;
    parent RECORD;
    table_owner NAME;
BEGIN
    IF TG_OP = 'DELETE' THEN
        requested_by := current_setting('visa.retention_requested_by', TRUE);
        dsr_requested_by := current_setting('visa.dsr_requested_by', TRUE);
        SELECT pg_get_userbyid(relation.relowner)
          INTO table_owner
          FROM pg_class AS relation
          JOIN pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname = 'visa_decision_payloads';
        IF current_user <> table_owner THEN
            RAISE EXCEPTION 'payload delete must use the bounded retention purge';
        END IF;
        IF dsr_requested_by IS NOT NULL
           AND dsr_requested_by ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$'
           AND OLD.legal_hold = FALSE THEN
            RETURN OLD;
        END IF;
        IF requested_by IS NULL
           OR requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
            RAISE EXCEPTION 'payload delete must use the bounded retention purge';
        END IF;
        IF OLD.purge_after <= clock_timestamp() AND OLD.legal_hold = FALSE THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'payload delete requires elapsed retention and legal_hold=false';
    END IF;

    IF OLD.decision_id IS DISTINCT FROM NEW.decision_id
       OR OLD.encryption_algorithm IS DISTINCT FROM NEW.encryption_algorithm
       OR OLD.encryption_key_id IS DISTINCT FROM NEW.encryption_key_id
       OR OLD.nonce IS DISTINCT FROM NEW.nonce
       OR OLD.ciphertext IS DISTINCT FROM NEW.ciphertext
       OR OLD.aad IS DISTINCT FROM NEW.aad
       OR OLD.ciphertext_sha256 IS DISTINCT FROM NEW.ciphertext_sha256
       OR OLD.purge_after IS DISTINCT FROM NEW.purge_after
       OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
        RAISE EXCEPTION 'visa_decision_payloads is append-only outside parent hold synchronization';
    END IF;
    SELECT retention_until, legal_hold
      INTO STRICT parent
      FROM public.visa_decisions
     WHERE id = NEW.decision_id;
    IF parent.retention_until IS NULL THEN
        RAISE EXCEPTION 'legacy payload hold disposition requires explicit Zero approval';
    END IF;
    IF OLD.legal_hold IS NOT DISTINCT FROM NEW.legal_hold
       OR NEW.legal_hold IS DISTINCT FROM parent.legal_hold THEN
        RAISE EXCEPTION 'payload legal_hold must be synchronized by its parent decision';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_decision_payloads_guard
BEFORE UPDATE OR DELETE ON public.visa_decision_payloads
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_decision_payloads_mutation();

DROP TRIGGER visa_decisions_immutable ON public.visa_decisions;

CREATE FUNCTION public.guard_visa_decisions_retention_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    requested_by TEXT;
    dsr_requested_by TEXT;
    audit_actor TEXT;
    hold_case_reference TEXT;
    hold_reason_code TEXT;
    hold_approved_by TEXT;
    hold_review_due_at_text TEXT;
    hold_review_due_at TIMESTAMPTZ;
    hold_review_interval INTERVAL;
    table_owner NAME;
BEGIN
    requested_by := current_setting('visa.retention_requested_by', TRUE);
    dsr_requested_by := current_setting('visa.dsr_requested_by', TRUE);
    audit_actor := session_user;
    IF requested_by IS NOT NULL AND requested_by <> '' THEN
        audit_actor := audit_actor || ':' || requested_by;
    END IF;

    IF TG_OP = 'DELETE' THEN
        SELECT pg_get_userbyid(relation.relowner)
          INTO table_owner
          FROM pg_class AS relation
          JOIN pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname = 'visa_decisions';
        IF current_user <> table_owner THEN
            RAISE EXCEPTION 'visa_decisions delete must use the bounded retention purge';
        END IF;
        IF dsr_requested_by IS NOT NULL
           AND dsr_requested_by ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$'
           AND OLD.legal_hold = FALSE THEN
            RETURN OLD;
        END IF;
        IF requested_by IS NULL
           OR requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
            RAISE EXCEPTION 'visa_decisions delete must use the bounded retention purge';
        END IF;
        IF OLD.retention_until IS NOT NULL
           AND OLD.retention_until < clock_timestamp()
           AND OLD.legal_hold = FALSE THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'visa_decisions delete requires elapsed retention and legal_hold=false';
    END IF;

    IF (to_jsonb(OLD) - 'legal_hold') IS DISTINCT FROM (to_jsonb(NEW) - 'legal_hold')
       OR OLD.legal_hold IS NOT DISTINCT FROM NEW.legal_hold THEN
        RAISE EXCEPTION 'visa_decisions update may only change legal_hold';
    END IF;

    hold_case_reference := current_setting('visa.legal_hold_case_reference', TRUE);
    hold_reason_code := current_setting('visa.legal_hold_reason_code', TRUE);
    hold_approved_by := current_setting('visa.legal_hold_approved_by', TRUE);
    hold_review_due_at_text := current_setting('visa.legal_hold_review_due_at', TRUE);
    IF requested_by IS NULL
       OR requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$'
       OR hold_case_reference IS NULL
       OR hold_case_reference !~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'
       OR hold_reason_code IS NULL
       OR hold_reason_code !~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'
       OR hold_approved_by IS NULL
       OR hold_approved_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'legal hold transition requires the bounded privacy capability';
    END IF;
    IF NEW.legal_hold THEN
        IF hold_review_due_at_text IS NULL OR hold_review_due_at_text = '' THEN
            RAISE EXCEPTION 'legal hold requires a review deadline';
        END IF;
        BEGIN
            hold_review_due_at := hold_review_due_at_text::TIMESTAMPTZ;
        EXCEPTION
            WHEN invalid_datetime_format THEN
                RAISE EXCEPTION 'legal hold review deadline has invalid format';
        END;
        SELECT policy.legal_hold_review_interval
          INTO STRICT hold_review_interval
          FROM public.visa_decision_retention_policies AS policy
         WHERE policy.id = OLD.retention_policy_id;
        IF hold_review_due_at <= clock_timestamp()
           OR hold_review_due_at > clock_timestamp() + hold_review_interval THEN
            RAISE EXCEPTION 'legal hold review deadline exceeds the approved interval';
        END IF;
    ELSIF hold_review_due_at_text IS NOT NULL AND hold_review_due_at_text <> '' THEN
        RAISE EXCEPTION 'legal hold release must not create a future review deadline';
    END IF;

    INSERT INTO public.visa_decision_legal_hold_events (
        decision_row_id, retention_policy_id, event_type,
        old_legal_hold, new_legal_hold, executor_label,
        case_reference, reason_code, approved_by, review_due_at
    ) VALUES (
        OLD.id,
        OLD.retention_policy_id,
        CASE WHEN NEW.legal_hold THEN 'LEGAL_HOLD_SET' ELSE 'LEGAL_HOLD_RELEASED' END,
        OLD.legal_hold,
        NEW.legal_hold,
        audit_actor,
        hold_case_reference,
        hold_reason_code,
        hold_approved_by,
        hold_review_due_at
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_decisions_retention_guard
BEFORE UPDATE OR DELETE ON public.visa_decisions
FOR EACH ROW EXECUTE FUNCTION public.guard_visa_decisions_retention_mutation();

CREATE FUNCTION public.sync_visa_decision_payload_hold()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    UPDATE public.visa_decision_payloads
       SET legal_hold = NEW.legal_hold
     WHERE decision_id = NEW.id
       AND legal_hold IS DISTINCT FROM NEW.legal_hold;
    RETURN NEW;
END;
$$;

-- AFTER makes the parent's persisted hold visible to the child guard. A child
-- failure still aborts the complete parent transaction and its audit event.
CREATE TRIGGER visa_decisions_payload_hold_sync
AFTER UPDATE OF legal_hold ON public.visa_decisions
FOR EACH ROW EXECUTE FUNCTION public.sync_visa_decision_payload_hold();

CREATE FUNCTION public.purge_visa_decisions(p_limit INTEGER, p_requested_by TEXT)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    candidate_ids UUID[];
    deleted_count INTEGER;
BEGIN
    IF p_limit IS NULL OR p_limit < 1 OR p_limit > 1000 THEN
        RAISE EXCEPTION 'purge limit must be between 1 and 1000';
    END IF;
    IF p_requested_by IS NULL
       OR p_requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'purge requested_by has invalid format';
    END IF;

    PERFORM set_config('visa.retention_requested_by', p_requested_by, TRUE);

    SELECT array_agg(candidate.id)
      INTO candidate_ids
      FROM (
          SELECT decision.id
            FROM public.visa_decisions AS decision
           WHERE decision.retention_until < clock_timestamp()
             AND decision.legal_hold = FALSE
             AND NOT EXISTS (
                 SELECT 1
                   FROM public.visa_decision_payloads AS payload
                  WHERE payload.decision_id = decision.id
                    AND (
                        payload.legal_hold = TRUE
                        OR payload.purge_after >= clock_timestamp()
                    )
             )
           ORDER BY decision.retention_until, decision.id
           LIMIT p_limit
           FOR UPDATE SKIP LOCKED
      ) AS candidate;

    IF candidate_ids IS NULL THEN
        RETURN 0;
    END IF;

    INSERT INTO public.visa_decision_retention_batches (
        retention_policy_id, affected_count, executor_label
    )
    SELECT
        decision.retention_policy_id,
        count(*)::INTEGER,
        session_user || ':' || p_requested_by
      FROM public.visa_decisions AS decision
     WHERE decision.id = ANY(candidate_ids)
     GROUP BY decision.retention_policy_id;

    DELETE FROM public.visa_decision_payloads
     WHERE decision_id = ANY(candidate_ids)
       AND purge_after < clock_timestamp()
       AND legal_hold = FALSE;

    DELETE FROM public.visa_decisions
     WHERE id = ANY(candidate_ids);
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

CREATE FUNCTION public.erase_visa_decision_for_dsr(
    p_decision_id UUID,
    p_case_reference TEXT,
    p_requested_by TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    target_row_id UUID;
    target_legal_hold BOOLEAN;
    payload_deleted INTEGER := 0;
    idempotency_deleted INTEGER := 0;
    decision_deleted INTEGER := 0;
BEGIN
    IF p_decision_id IS NULL THEN
        RAISE EXCEPTION 'DSR erasure requires a decision_id';
    END IF;
    IF p_case_reference IS NULL
       OR p_case_reference !~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$' THEN
        RAISE EXCEPTION 'DSR case_reference has invalid format';
    END IF;
    IF p_requested_by IS NULL
       OR p_requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'DSR requested_by has invalid format';
    END IF;

    SELECT decision.id, decision.legal_hold
      INTO target_row_id, target_legal_hold
      FROM public.visa_decisions AS decision
     WHERE decision.decision_id = p_decision_id
     FOR UPDATE;
    IF target_row_id IS NULL THEN
        RETURN 0;
    END IF;
    IF target_legal_hold THEN
        RAISE EXCEPTION 'DSR erasure blocked by active legal hold';
    END IF;

    PERFORM set_config('visa.dsr_requested_by', p_requested_by, TRUE);

    DELETE FROM public.visa_evaluate_idempotency AS replay
     WHERE replay.response_body #>> '{decision,decision_id}' = p_decision_id::TEXT;
    GET DIAGNOSTICS idempotency_deleted = ROW_COUNT;

    DELETE FROM public.visa_decision_payloads
     WHERE decision_id = target_row_id AND legal_hold = FALSE;
    GET DIAGNOSTICS payload_deleted = ROW_COUNT;

    DELETE FROM public.visa_decisions
     WHERE id = target_row_id AND legal_hold = FALSE;
    GET DIAGNOSTICS decision_deleted = ROW_COUNT;
    IF decision_deleted <> 1 THEN
        RAISE EXCEPTION 'DSR decision deletion did not complete atomically';
    END IF;

    INSERT INTO public.visa_decision_dsr_erasure_batches (
        case_reference, decision_rows_deleted, payload_rows_deleted,
        idempotency_rows_deleted, executor_label
    ) VALUES (
        p_case_reference, decision_deleted, payload_deleted,
        idempotency_deleted, session_user || ':' || p_requested_by
    );
    RETURN decision_deleted;
END;
$$;

CREATE FUNCTION public.set_visa_decision_legal_hold(
    p_decision_id UUID,
    p_legal_hold BOOLEAN,
    p_requested_by TEXT,
    p_case_reference TEXT,
    p_reason_code TEXT,
    p_approved_by TEXT,
    p_review_due_at TIMESTAMPTZ
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    target_row_id UUID;
    target_policy_id UUID;
    changed_count INTEGER;
BEGIN
    IF p_decision_id IS NULL OR p_legal_hold IS NULL THEN
        RAISE EXCEPTION 'legal hold requires decision_id and state';
    END IF;
    IF p_requested_by IS NULL
       OR p_requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'legal hold requested_by has invalid format';
    END IF;
    IF p_case_reference IS NULL
       OR p_case_reference !~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$' THEN
        RAISE EXCEPTION 'legal hold case_reference has invalid format';
    END IF;
    IF p_reason_code IS NULL
       OR p_reason_code !~ '^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$' THEN
        RAISE EXCEPTION 'legal hold reason_code has invalid format';
    END IF;
    IF p_approved_by IS NULL
       OR p_approved_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'legal hold approved_by has invalid format';
    END IF;
    IF p_legal_hold AND p_review_due_at IS NULL THEN
        RAISE EXCEPTION 'legal hold requires a review deadline';
    END IF;
    IF NOT p_legal_hold AND p_review_due_at IS NOT NULL THEN
        RAISE EXCEPTION 'legal hold release must not create a review deadline';
    END IF;

    SELECT decision.id, decision.retention_policy_id
      INTO target_row_id, target_policy_id
      FROM public.visa_decisions AS decision
     WHERE decision.decision_id = p_decision_id
     FOR UPDATE;
    IF target_row_id IS NULL THEN
        RETURN FALSE;
    END IF;
    IF target_policy_id IS NULL THEN
        RAISE EXCEPTION 'legacy decision requires explicit disposition before legal hold';
    END IF;

    PERFORM set_config('visa.retention_requested_by', p_requested_by, TRUE);
    PERFORM set_config('visa.legal_hold_case_reference', p_case_reference, TRUE);
    PERFORM set_config('visa.legal_hold_reason_code', p_reason_code, TRUE);
    PERFORM set_config('visa.legal_hold_approved_by', p_approved_by, TRUE);
    PERFORM set_config(
        'visa.legal_hold_review_due_at',
        COALESCE(p_review_due_at::TEXT, ''),
        TRUE
    );
    UPDATE public.visa_decisions
       SET legal_hold = p_legal_hold
     WHERE id = target_row_id
       AND legal_hold IS DISTINCT FROM p_legal_hold;
    GET DIAGNOSTICS changed_count = ROW_COUNT;
    RETURN changed_count = 1;
END;
$$;

-- PUBLIC revocation does not remove the owner's implicit EXECUTE privilege.
-- The owner/runtime separation and narrow grant described above are mandatory
-- activation prerequisites; this migration does not pretend to provision them.
REVOKE ALL ON FUNCTION public.purge_visa_decisions(INTEGER, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.erase_visa_decision_for_dsr(UUID, TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.set_visa_decision_legal_hold(
    UUID, BOOLEAN, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) FROM PUBLIC;
COMMENT ON FUNCTION public.purge_visa_decisions(INTEGER, TEXT) IS
    'Bounded Visa Oracle purge primitive; requires an explicit operator grant and scheduler.';
COMMENT ON FUNCTION public.erase_visa_decision_for_dsr(UUID, TEXT, TEXT) IS
    'Bounded, legal-hold-aware DSR erasure; requires a separated privacy operator grant.';
COMMENT ON FUNCTION public.set_visa_decision_legal_hold(
    UUID, BOOLEAN, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) IS
    'Bounded legal-hold transition with append-only event evidence; privacy operator grant required.';

-- === ROLLBACK ===

DROP FUNCTION IF EXISTS public.set_visa_decision_legal_hold(
    UUID, BOOLEAN, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
);
DROP FUNCTION IF EXISTS public.erase_visa_decision_for_dsr(UUID, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.purge_visa_decisions(INTEGER, TEXT);
DROP FUNCTION IF EXISTS public.prepare_visa_evaluate_idempotency_reservation(
    BYTEA, INTEGER, TEXT
);
DROP FUNCTION IF EXISTS public.purge_visa_evaluate_idempotency(INTEGER, TEXT);
DROP FUNCTION IF EXISTS public.visa_idempotency_key_usage_evidence();
DROP FUNCTION IF EXISTS public.visa_idempotency_retention_evidence();

DROP TRIGGER IF EXISTS visa_decisions_payload_hold_sync ON public.visa_decisions;
DROP FUNCTION IF EXISTS public.sync_visa_decision_payload_hold();

DROP TRIGGER IF EXISTS visa_decisions_retention_guard ON public.visa_decisions;
DROP FUNCTION IF EXISTS public.guard_visa_decisions_retention_mutation();

DROP TRIGGER IF EXISTS visa_decision_payloads_retention_binding
    ON public.visa_decision_payloads;
DROP FUNCTION IF EXISTS public.bind_visa_decision_payload_retention();

DROP TRIGGER IF EXISTS visa_decision_payloads_guard
    ON public.visa_decision_payloads;
CREATE OR REPLACE FUNCTION public.reject_visa_decision_payloads_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.purge_after IS NOT NULL
           AND OLD.purge_after < now()
           AND OLD.legal_hold = FALSE THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'visa_decision_payloads is append-only (delete requires purge_after elapsed and legal_hold=false)';
    END IF;

    IF OLD.decision_id IS DISTINCT FROM NEW.decision_id
       OR OLD.encryption_algorithm IS DISTINCT FROM NEW.encryption_algorithm
       OR OLD.encryption_key_id IS DISTINCT FROM NEW.encryption_key_id
       OR OLD.nonce IS DISTINCT FROM NEW.nonce
       OR OLD.ciphertext IS DISTINCT FROM NEW.ciphertext
       OR OLD.aad IS DISTINCT FROM NEW.aad
       OR OLD.ciphertext_sha256 IS DISTINCT FROM NEW.ciphertext_sha256
       OR OLD.purge_after IS DISTINCT FROM NEW.purge_after
       OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
        RAISE EXCEPTION 'visa_decision_payloads is append-only outside the legal_hold-only carve-out';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_decision_payloads_guard
BEFORE UPDATE OR DELETE ON public.visa_decision_payloads
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_decision_payloads_mutation();

DROP TRIGGER IF EXISTS visa_decisions_retention_binding ON public.visa_decisions;
DROP FUNCTION IF EXISTS public.bind_visa_decision_retention_policy();

CREATE TRIGGER visa_decisions_immutable
BEFORE UPDATE OR DELETE ON public.visa_decisions
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

DROP INDEX IF EXISTS public.idx_visa_decisions_retention_purge;
ALTER TABLE public.visa_decisions
    DROP CONSTRAINT IF EXISTS visa_decisions_retention_required,
    DROP CONSTRAINT IF EXISTS visa_decisions_retention_binding_pair,
    DROP COLUMN IF EXISTS legal_hold,
    DROP COLUMN IF EXISTS retention_until,
    DROP COLUMN IF EXISTS retention_policy_id;

DROP TRIGGER IF EXISTS visa_evaluate_idempotency_retention_binding
    ON public.visa_evaluate_idempotency;
DROP FUNCTION IF EXISTS public.bind_visa_evaluate_idempotency_retention_policy();

ALTER TABLE public.visa_evaluate_idempotency
    DROP CONSTRAINT IF EXISTS visa_evaluate_idempotency_retention_required,
    DROP CONSTRAINT IF EXISTS visa_evaluate_idempotency_retention_binding_pair,
    DROP COLUMN IF EXISTS retention_policy_id,
    DROP COLUMN IF EXISTS environment,
    ALTER COLUMN expires_at SET DEFAULT (
        statement_timestamp() + INTERVAL '24 hours'
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

DROP TABLE IF EXISTS public.visa_idempotency_retention_batches;
DROP TABLE IF EXISTS public.visa_decision_dsr_erasure_batches;
DROP TABLE IF EXISTS public.visa_decision_retention_batches;
DROP TABLE IF EXISTS public.visa_decision_legal_hold_events;
DROP FUNCTION IF EXISTS public.guard_visa_decision_legal_hold_events_mutation();
DROP TABLE IF EXISTS public.visa_decision_retention_policies;
DROP FUNCTION IF EXISTS public.guard_visa_decision_retention_policy_mutation();
