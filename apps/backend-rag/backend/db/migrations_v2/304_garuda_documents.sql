-- ============================================================================
-- 304_garuda_documents.sql
-- GARUDA VOA document-upload persistence: garuda_documents + garuda_document_review_fields.
-- Each ledger-owned block (forward and rollback) is preceded by RESET ROLE and followed by a block that restores backend_rag_v2 only if it was the effective role before.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- (0) Widen the policy_scope CHECK of visa_decision_retention_policies with GARUDA_DOCUMENT
-- ----------------------------------------------------------------------------

-- Stores current_user in the transaction-local custom GUC garuda.migration_304_resume_role, then RESET ROLE.
SELECT set_config('garuda.migration_304_resume_role', current_user, true);
RESET ROLE;

-- Replaces the policy_scope CHECK only when its definition does not already contain GARUDA_DOCUMENT.
DO $garuda_304_widen_scope_check$
DECLARE
    scope_check_name text;
    scope_check_def text;
BEGIN
    SELECT conname, pg_get_constraintdef(oid)
      INTO scope_check_name, scope_check_def
      FROM pg_constraint
     WHERE conrelid = 'public.visa_decision_retention_policies'::regclass
       AND contype = 'c'
       AND pg_get_constraintdef(oid) LIKE 'CHECK ((policy_scope = ANY (ARRAY[%';
    IF scope_check_name IS NULL THEN
        RAISE EXCEPTION 'garuda 304: could not locate the policy_scope enum CHECK to widen';
    END IF;

    IF scope_check_def LIKE '%GARUDA_DOCUMENT%' THEN
        RETURN;
    END IF;

    EXECUTE format(
        'ALTER TABLE public.visa_decision_retention_policies DROP CONSTRAINT %I',
        scope_check_name
    );
    EXECUTE
        'ALTER TABLE public.visa_decision_retention_policies '
        'ADD CONSTRAINT visa_decision_retention_policies_policy_scope_check '
        'CHECK (policy_scope IN (''VISA_DECISION'', ''GARUDA_CHECK'', ''GARUDA_ORDER'', ''GARUDA_MAGIC_LINK'', ''GARUDA_DOCUMENT''))';
END;
$garuda_304_widen_scope_check$;

-- SET ROLE backend_rag_v2 only when it is the recorded role, exists, and session_user may assume it (SET on PG>=16, MEMBER on 15).
DO $garuda_304_resume_runtime_role_after_scope$
BEGIN
    IF current_setting('garuda.migration_304_resume_role', true) = 'backend_rag_v2' THEN
        IF to_regrole('backend_rag_v2') IS NOT NULL THEN
            IF current_setting('server_version_num')::int >= 160000 THEN
                IF pg_has_role(session_user, 'backend_rag_v2', 'SET') THEN
                    EXECUTE 'SET ROLE backend_rag_v2';
                END IF;
            ELSIF pg_has_role(session_user, 'backend_rag_v2', 'MEMBER') THEN
                EXECUTE 'SET ROLE backend_rag_v2';
            END IF;
        END IF;
    END IF;
END;
$garuda_304_resume_runtime_role_after_scope$;

-- ----------------------------------------------------------------------------
-- (1) garuda_documents -- one row per scoped idempotency key
-- ----------------------------------------------------------------------------

CREATE TABLE public.garuda_documents (
    key_sha256              BYTEA PRIMARY KEY CHECK (octet_length(key_sha256) = 32),
    canonical_payload_sha256 BYTEA NOT NULL CHECK (octet_length(canonical_payload_sha256) = 32),
    -- 32 lowercase hex characters (the uuid4().hex format).
    document_id              TEXT NOT NULL UNIQUE CHECK (document_id ~ '^[0-9a-f]{32}$'),
    environment               TEXT NOT NULL CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
    processing_state          TEXT NOT NULL CHECK (
        processing_state IN ('PROCESSING', 'LOW_CONFIDENCE', 'READY_FOR_REVIEW', 'UNREADABLE')
    ),
    retention_policy_id       UUID NOT NULL REFERENCES public.visa_decision_retention_policies (id),
    retention_until           TIMESTAMPTZ NOT NULL,
    -- NOW() is transaction_timestamp(), the clock bind_garuda_document_retention_policy() compares against.
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (retention_until > created_at)
);

COMMENT ON TABLE public.garuda_documents IS
    'GARUDA VOA document-upload outcome, one row per scoped Idempotency-Key; the table has no column for document bytes or extracted field values.';
COMMENT ON COLUMN public.garuda_documents.key_sha256 IS
    'sha256 of the length-prefixed (actor_id, operation, environment, Idempotency-Key) tuple; the table has no column for the raw key.';
COMMENT ON COLUMN public.garuda_documents.canonical_payload_sha256 IS
    'sha256 of document_kind || upload bytes; the table has no column for the bytes.';

CREATE INDEX idx_garuda_documents_retention_purge
    ON public.garuda_documents (retention_until);

-- True when exactly one GARUDA_DOCUMENT policy of the given environment covers the given instant.
CREATE FUNCTION public.active_garuda_document_policy_available(
    p_environment TEXT,
    p_created_at TIMESTAMPTZ
) RETURNS BOOLEAN
LANGUAGE sql
STABLE
SET search_path = pg_catalog, public
AS $func$
    SELECT count(*) = 1
    FROM public.visa_decision_retention_policies
    WHERE environment = p_environment
      AND policy_scope = 'GARUDA_DOCUMENT'
      AND effective_period @> p_created_at;
$func$;

COMMENT ON FUNCTION public.active_garuda_document_policy_available IS
    'True when exactly one GARUDA_DOCUMENT retention policy of the given environment covers the given instant.';

-- Binds each inserted row to the single active GARUDA_DOCUMENT policy and sets retention_until from it.
CREATE FUNCTION public.bind_garuda_document_retention_policy()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $func$
DECLARE
    policy RECORD;
    expected_until TIMESTAMPTZ;
BEGIN
    IF NEW.created_at IS DISTINCT FROM transaction_timestamp() THEN
        RAISE EXCEPTION 'garuda document created_at must use the database transaction clock';
    END IF;

    BEGIN
        SELECT id, retention_interval, retention_anchor
          INTO STRICT policy
          FROM public.visa_decision_retention_policies
         WHERE environment = NEW.environment
           AND policy_scope = 'GARUDA_DOCUMENT'
           AND effective_period @> NEW.created_at
         FOR SHARE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'garuda document has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'garuda document retention policy authority is ambiguous';
    END;

    IF policy.retention_anchor <> 'CREATED_AT' THEN
        RAISE EXCEPTION 'unsupported retention anchor for GARUDA_DOCUMENT scope';
    END IF;
    expected_until := NEW.created_at + policy.retention_interval;
    IF expected_until <= clock_timestamp() THEN
        RAISE EXCEPTION 'garuda document retention deadline has already elapsed';
    END IF;

    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'garuda document retention policy does not match active policy';
    END IF;
    IF NEW.retention_until IS NOT NULL
       AND NEW.retention_until IS DISTINCT FROM expected_until THEN
        RAISE EXCEPTION 'garuda document retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.retention_until := expected_until;
    RETURN NEW;
END;
$func$;

REVOKE ALL ON FUNCTION public.bind_garuda_document_retention_policy() FROM PUBLIC;

CREATE TRIGGER garuda_documents_retention_binding
BEFORE INSERT ON public.garuda_documents
FOR EACH ROW EXECUTE FUNCTION public.bind_garuda_document_retention_policy();

-- ----------------------------------------------------------------------------
-- (2) Transfer bind_garuda_document_retention_policy() to visa_ledger_owner
-- ----------------------------------------------------------------------------

-- Stores current_user in the transaction-local custom GUC garuda.migration_304_resume_role, then RESET ROLE.
SELECT set_config('garuda.migration_304_resume_role', current_user, true);
RESET ROLE;

-- Transfers the binder when visa_ledger_owner exists, then raises if visa_ledger_owner is still not its owner.
DO $garuda_304_owner_transfer$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    signature constant text := 'public.bind_garuda_document_retention_policy()';
    fn oid;
    current_owner text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ledger_owner) THEN
        RAISE NOTICE 'garuda documents (304): role % absent -- skipping ownership transfer',
            ledger_owner;
        RETURN;
    END IF;

    fn := to_regprocedure(signature);
    IF fn IS NULL THEN
        RAISE NOTICE 'garuda documents (304): % not present -- nothing to transfer', signature;
        RETURN;
    END IF;

    SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;

    IF current_owner IS DISTINCT FROM ledger_owner THEN
        BEGIN
            EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE NOTICE 'garuda documents (304): ALTER denied to current_user % (current owner %, target owner %)',
                    current_user, current_owner, ledger_owner;
        END;
        SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;
    END IF;

    IF current_owner IS DISTINCT FROM ledger_owner THEN
        RAISE EXCEPTION
            'garuda documents (304): % is still owned by % -- refusing to record this migration as applied.',
            signature, current_owner;
    END IF;
END;
$garuda_304_owner_transfer$;

-- SET ROLE backend_rag_v2 only when it is the recorded role, exists, and session_user may assume it (SET on PG>=16, MEMBER on 15).
DO $garuda_304_resume_runtime_role_after_transfer$
BEGIN
    IF current_setting('garuda.migration_304_resume_role', true) = 'backend_rag_v2' THEN
        IF to_regrole('backend_rag_v2') IS NOT NULL THEN
            IF current_setting('server_version_num')::int >= 160000 THEN
                IF pg_has_role(session_user, 'backend_rag_v2', 'SET') THEN
                    EXECUTE 'SET ROLE backend_rag_v2';
                END IF;
            ELSIF pg_has_role(session_user, 'backend_rag_v2', 'MEMBER') THEN
                EXECUTE 'SET ROLE backend_rag_v2';
            END IF;
        END IF;
    END IF;
END;
$garuda_304_resume_runtime_role_after_transfer$;

-- ----------------------------------------------------------------------------
-- (3) Row guard: UPDATE raises; DELETE raises while clock_timestamp() < retention_until
-- ----------------------------------------------------------------------------

CREATE FUNCTION public.guard_garuda_document_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $func$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF clock_timestamp() < OLD.retention_until THEN
            RAISE EXCEPTION 'unexpired garuda_documents rows are immutable';
        END IF;
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'garuda_documents rows are immutable once inserted';
END;
$func$;

CREATE TRIGGER trg_guard_garuda_document_mutation
BEFORE UPDATE OR DELETE ON public.garuda_documents
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_document_mutation();

-- ----------------------------------------------------------------------------
-- (4) garuda_document_review_fields -- field name + confirmation flag, cascade-deleted with the parent row
-- ----------------------------------------------------------------------------

CREATE TABLE public.garuda_document_review_fields (
    document_id           TEXT NOT NULL REFERENCES public.garuda_documents (document_id) ON DELETE CASCADE,
    field_path             TEXT NOT NULL CHECK (
        field_path IN ('full_name', 'passport_number', 'nationality', 'passport_expiry_date')
    ),
    confirmation_required   BOOLEAN NOT NULL,
    PRIMARY KEY (document_id, field_path)
);

COMMENT ON TABLE public.garuda_document_review_fields IS
    'Review-field name and confirmation_required flag per document; the table has no column for the extracted field value.';

-- === ROLLBACK ===

-- Stores current_user in the transaction-local custom GUC garuda.migration_304_resume_role, then RESET ROLE.
SELECT set_config('garuda.migration_304_resume_role', current_user, true);
RESET ROLE;

DROP TRIGGER IF EXISTS trg_guard_garuda_document_mutation ON public.garuda_documents;
DROP FUNCTION IF EXISTS public.guard_garuda_document_mutation();
DROP TABLE IF EXISTS public.garuda_document_review_fields;
DROP TRIGGER IF EXISTS garuda_documents_retention_binding ON public.garuda_documents;
DROP FUNCTION IF EXISTS public.bind_garuda_document_retention_policy();
DROP FUNCTION IF EXISTS public.active_garuda_document_policy_available(TEXT, TIMESTAMPTZ);
DROP TABLE IF EXISTS public.garuda_documents;

-- Narrows the policy_scope CHECK only when no GARUDA_DOCUMENT policy row exists; otherwise leaves it widened.
DO $garuda_304_narrow_policy_scope$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.visa_decision_retention_policies
         WHERE policy_scope = 'GARUDA_DOCUMENT'
    ) THEN
        RAISE NOTICE 'garuda 304 rollback: visa_decision_retention_policies has row(s) with policy_scope = ''GARUDA_DOCUMENT'' -- the policy_scope CHECK is left WIDENED.';
    ELSE
        ALTER TABLE public.visa_decision_retention_policies
            DROP CONSTRAINT IF EXISTS visa_decision_retention_policies_policy_scope_check;
        ALTER TABLE public.visa_decision_retention_policies
            ADD CONSTRAINT visa_decision_retention_policies_policy_scope_check
                CHECK (policy_scope IN ('VISA_DECISION', 'GARUDA_CHECK', 'GARUDA_ORDER', 'GARUDA_MAGIC_LINK'));
    END IF;
END;
$garuda_304_narrow_policy_scope$;

-- SET ROLE backend_rag_v2 only when it is the recorded role, exists, and session_user may assume it (SET on PG>=16, MEMBER on 15).
DO $garuda_304_resume_runtime_role_after_rollback$
BEGIN
    IF current_setting('garuda.migration_304_resume_role', true) = 'backend_rag_v2' THEN
        IF to_regrole('backend_rag_v2') IS NOT NULL THEN
            IF current_setting('server_version_num')::int >= 160000 THEN
                IF pg_has_role(session_user, 'backend_rag_v2', 'SET') THEN
                    EXECUTE 'SET ROLE backend_rag_v2';
                END IF;
            ELSIF pg_has_role(session_user, 'backend_rag_v2', 'MEMBER') THEN
                EXECUTE 'SET ROLE backend_rag_v2';
            END IF;
        END IF;
    END IF;
END;
$garuda_304_resume_runtime_role_after_rollback$;
