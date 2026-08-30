-- ============================================================================
-- 286_garuda_voa_check_results.sql
-- GARUDA VOA -- the product-era public eligibility CHECK row (composition
-- lane, products/garuda-voa/LANES.md prerequisite chain, post-freeze).
--
-- WHY A NEW TABLE, NOT AN EXTENSION OF garuda_voa_checks
-- ----------------------------------------------------------------------------
-- L2's CheckStore protocol (services/garuda_flow/public_api.py) requires
-- create(idempotency_key, canonical_request, outcome) -> StoredCheck and
-- get(result_id, session_secret) -> StoredCheck | None, where result_id
-- is an opaque >=128-bit id (contract ResultId, ^[A-Za-z0-9_-]{22,128}$)
-- and session_secret is a bearer the browser holds and presents back.
--
-- garuda_voa_checks (migration 261) cannot back that contract: its own
-- COMMENT ON COLUMN hash calls it "16-char URL-safe hash ... Public
-- identifier in /visa/voa/<hash>" -- the LEGACY archive identifier, primary
-- key VARCHAR(20). It has no result_id, no session_secret, no
-- idempotency_key column, and migration 281's own header already calls it
-- "the retired historical archive ... no live writer, no production traffic
-- touches this table today" (backend/services/garuda_flow/repository.py is
-- read-only, owner-GET-only). Bolting the product-era shape onto a retired
-- archive table would resurrect it for new live traffic and mix two
-- generations of identifier in one payload shape -- exactly the pattern this
-- organism has separately learned to distrust (a document corpus holding two
-- generations in two payload shapes: one probe sees a fraction and stays
-- silent about the rest). A companion table keyed by result_id, standalone
-- (no FK to the legacy hash PK -- there is no natural 1:1 relationship: a
-- product-era check has no corresponding archive row and never will), is the
-- smaller and honest surface.
--
-- ONE RETENTION AUTHORITY, SAME SCOPE (ARCHITECTURE.md D2): this table's rows
-- are the SAME data class the archive table's GARUDA_CHECK policy_scope
-- already names ("anonymous eligibility check" -- enum/date/bool/ISO-code
-- only, no PII, D1's public/anonymous domain) -- migration 281 already
-- widened visa_decision_retention_policies with that scope and Python's
-- backend.services.garuda_flow.retention.active_garuda_check_policy_
-- available() already reads it. This migration does NOT add a new scope
-- (that would be a second policy_scope value governing the identical data
-- class -- the two-half-policies trap D2 exists to prevent) -- it reuses
-- GARUDA_CHECK for a second table, exactly the way one retention duration
-- can legitimately govern more than one data store of the same kind.
--
-- FAIL-CLOSED BY CONSTRUCTION, same shape as 281/284/285: no new GARUDA_CHECK
-- policy row is seeded here (281 already established that no scope's row is
-- ever a migration default) -- this migration's INSERT trigger fails closed
-- exactly like the archive table's until Zero signs (or re-signs, if the
-- existing GARUDA_CHECK policy needs re-scoping to cover both tables) a
-- policy row. See the PR body for what specifically the L1 gap needs next.
--
-- PII BOUNDARY (D1, unchanged): only enum / date / bool / ISO-code columns,
-- identical discipline to migration 261's header. canonical_request in the
-- Python layer already carries no name/passport/email/phone (verified
-- against EligibilityCheckRequest in app/routers/garuda_voa_public.py).
--
-- WHAT THIS MIGRATION ADDS
-- ----------------------------------------------------------------------------
--   (a) garuda_voa_check_results -- one row per issued result_id.
--   (b) BEFORE INSERT retention-binding trigger, GARUDA_CHECK scope, mirrors
--       bind_garuda_voa_check_retention_policy (281) exactly.
--   (c) garuda_voa_check_idempotency -- create-path replay cache, scoped by
--       the raw Idempotency-Key alone (this route is unauthenticated/public,
--       there is no actor to additionally scope by -- same posture as
--       262_visa_evaluate_idempotency.sql).
--   (d) Widen guard_visa_decision_retention_policy_mutation (264, widened
--       by 281/285) once more so closing a GARUDA_CHECK policy cannot strand
--       a bound row in EITHER table.
--   (e) A bounded purge primitive reusing visa_decision_retention_batches
--       (264) for evidence, same as 281's purge_garuda_voa_checks.
--
-- Deliberately NOT added: a legal-hold ledger. Unlike the archive table
-- (which built one for its own historical audit posture), this table carries
-- no PII and no customer-identifying data at all -- there is nothing here an
-- investigation would ever need to freeze mid-lifetime beyond what the
-- retention window and purge bound already provide. If a future need for
-- legal hold on this table is identified, it is a new forward migration
-- mirroring 281's shape, not a retrofit of this one.
--
-- Self-service deletion (LANES.md L1 scope: "purge, coarse aggregates,
-- self-service deletion") is a DIFFERENT capability from the bounded purge:
-- CheckStore.delete() (the contract's deleteEligibilityResult) is a
-- customer-initiated DELETE, not gated on retention having elapsed -- a
-- customer may withdraw consent and ask for erasure at any time, which is
-- exactly the property the archive table's DELETE guard does NOT have (it
-- forbids DELETE except through the elapsed-retention bounded purge). This
-- table therefore carries NO delete-blocking guard trigger -- a plain DELETE
-- is a legitimate, direct, customer-facing operation here.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- (a) garuda_voa_check_results
-- ----------------------------------------------------------------------------

CREATE TABLE public.garuda_voa_check_results (
    result_id                  TEXT PRIMARY KEY
                                CHECK (result_id ~ '^[A-Za-z0-9_-]{22,128}$'),
    -- sha256 hex of the opaque bearer set as the garuda_result_session
    -- cookie -- raw value never persisted (same discipline as
    -- garuda_account_sessions.session_secret_hash, migration 285).
    session_secret_hash        CHAR(64) NOT NULL,
    environment                 TEXT NOT NULL
                                 CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),

    -- Intake (D1's whole PII contract; enum/date/bool/ISO-code only,
    -- identical field set to migration 261's anonymous-check columns).
    case_type                   TEXT NOT NULL CHECK (case_type IN ('issuance', 'extension')),
    nationality                  VARCHAR(3) NOT NULL,
    entry_date                   DATE NOT NULL,
    passport_expiry_date         DATE NOT NULL,
    voa_expiry_date               DATE,
    extension_already_used        BOOLEAN NOT NULL DEFAULT FALSE,
    purpose                       TEXT NOT NULL,
    travellers                    INT NOT NULL CHECK (travellers >= 1),
    self_pay                      BOOLEAN NOT NULL,

    decision                      TEXT NOT NULL CHECK (decision IN ('ACCEPT', 'DECLINE')),
    reason_codes                  JSONB NOT NULL DEFAULT '[]'::jsonb,
    published_filing_deadline     DATE,
    price_idr                     INT CHECK (price_idr IS NULL OR price_idr > 0),
    price_source                  TEXT,

    retention_notice_acknowledged_at TIMESTAMPTZ NOT NULL,
    retention_policy_id            UUID
                                    -- squawk-ignore adding-foreign-key-constraint
                                    REFERENCES public.visa_decision_retention_policies (id),
    retention_until                TIMESTAMPTZ,

    created_at                     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CHECK (
        (decision = 'ACCEPT' AND published_filing_deadline IS NOT NULL
            AND price_idr IS NOT NULL AND price_source IS NOT NULL
            AND jsonb_array_length(reason_codes) = 0)
        OR
        (decision = 'DECLINE' AND published_filing_deadline IS NULL
            AND price_idr IS NULL AND price_source IS NULL
            AND jsonb_array_length(reason_codes) >= 1)
    ),
    CHECK (
        (retention_policy_id IS NULL AND retention_until IS NULL)
        OR (retention_policy_id IS NOT NULL AND retention_until IS NOT NULL)
    )
);

COMMENT ON TABLE public.garuda_voa_check_results IS
    'GARUDA VOA product-era public eligibility check (contract-frozen CheckStore). One row per result_id. Standalone from the retired garuda_voa_checks archive (261) -- see file header. No PII by design.';
COMMENT ON COLUMN public.garuda_voa_check_results.result_id IS
    'Opaque >=128-bit id (contract ResultId). Public identifier in /visa/voa/eligibility-checks/{result_id} and the GET/DELETE path parameter.';
COMMENT ON COLUMN public.garuda_voa_check_results.session_secret_hash IS
    'sha256 hex of the bearer set as the garuda_result_session cookie on create. Raw value never persisted.';
COMMENT ON COLUMN public.garuda_voa_check_results.price_source IS
    'Server-side provenance only (garuda_flow.pricing.price_for_case) -- never serialized on the wire.';

CREATE INDEX idx_garuda_voa_check_results_retention_purge
    ON public.garuda_voa_check_results (retention_until)
    WHERE retention_until IS NOT NULL;

-- ----------------------------------------------------------------------------
-- (b) Fail-closed retention binding -- GARUDA_CHECK scope, reused (D2).
-- ----------------------------------------------------------------------------

CREATE FUNCTION public.bind_garuda_voa_check_result_retention_policy()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    policy RECORD;
    expected_until TIMESTAMPTZ;
BEGIN
    IF NEW.created_at IS DISTINCT FROM transaction_timestamp() THEN
        RAISE EXCEPTION 'garuda check result created_at must use the database transaction clock';
    END IF;

    BEGIN
        SELECT id, retention_interval, retention_anchor
          INTO STRICT policy
          FROM public.visa_decision_retention_policies
         WHERE environment = NEW.environment
           AND policy_scope = 'GARUDA_CHECK'
           AND effective_period @> NEW.created_at
         FOR SHARE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'garuda check result has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'garuda check result retention policy authority is ambiguous';
    END;

    IF policy.retention_anchor <> 'CREATED_AT' THEN
        RAISE EXCEPTION 'unsupported retention anchor for GARUDA_CHECK scope';
    END IF;
    expected_until := NEW.created_at + policy.retention_interval;
    IF expected_until <= clock_timestamp() THEN
        RAISE EXCEPTION 'garuda check result retention deadline has already elapsed';
    END IF;

    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'garuda check result retention policy does not match active policy';
    END IF;
    IF NEW.retention_until IS NOT NULL
       AND NEW.retention_until IS DISTINCT FROM expected_until THEN
        RAISE EXCEPTION 'garuda check result retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.retention_until := expected_until;
    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.bind_garuda_voa_check_result_retention_policy() FROM PUBLIC;

CREATE TRIGGER garuda_voa_check_results_retention_binding
BEFORE INSERT ON public.garuda_voa_check_results
FOR EACH ROW EXECUTE FUNCTION public.bind_garuda_voa_check_result_retention_policy();

-- ----------------------------------------------------------------------------
-- (c) Create-path idempotency (scoped by raw Idempotency-Key alone -- public,
--     unauthenticated route, no actor to additionally scope by).
-- ----------------------------------------------------------------------------

CREATE TABLE public.garuda_voa_check_idempotency (
    key_sha256               BYTEA PRIMARY KEY CHECK (octet_length(key_sha256) = 32),
    canonical_payload_sha256 BYTEA NOT NULL CHECK (octet_length(canonical_payload_sha256) = 32),
    -- Deliberately NOT a foreign key: self-service deletion (CheckStore.
    -- delete()) must be able to erase a garuda_voa_check_results row at
    -- any time regardless of an outstanding idempotency cache entry --
    -- an FK here (with or without ON DELETE CASCADE/SET NULL) collides
    -- with the append-only completed-row guard below, which correctly
    -- forbids exactly the UPDATE/DELETE a cascade would need to perform.
    -- A dangling result_id after deletion is harmless: the only reader
    -- (a create-path replay) already handles a missing row explicitly.
    result_id                TEXT,
    completed_at              TIMESTAMPTZ,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    expires_at                TIMESTAMPTZ NOT NULL DEFAULT (statement_timestamp() + INTERVAL '30 days'),
    CHECK (expires_at > created_at)
);

COMMENT ON TABLE public.garuda_voa_check_idempotency IS
    'Idempotency-Key replay cache for createEligibilityCheck and deleteEligibilityResult (key namespace-prefixed per operation at the Python layer). Raw keys never stored -- only their SHA-256.';

CREATE INDEX idx_garuda_voa_check_idempotency_expires_at
    ON public.garuda_voa_check_idempotency (expires_at);

CREATE FUNCTION public.guard_garuda_voa_check_idempotency_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF clock_timestamp() < OLD.expires_at THEN
            RAISE EXCEPTION 'unexpired garuda_voa_check_idempotency rows are immutable';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.key_sha256 IS DISTINCT FROM NEW.key_sha256
       OR OLD.canonical_payload_sha256 IS DISTINCT FROM NEW.canonical_payload_sha256
       OR OLD.created_at IS DISTINCT FROM NEW.created_at
       OR OLD.expires_at IS DISTINCT FROM NEW.expires_at THEN
        RAISE EXCEPTION 'garuda_voa_check_idempotency request binding is immutable';
    END IF;
    IF OLD.completed_at IS NOT NULL THEN
        RAISE EXCEPTION 'completed garuda_voa_check_idempotency rows are immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_garuda_voa_check_idempotency_mutation
BEFORE UPDATE OR DELETE ON public.garuda_voa_check_idempotency
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_voa_check_idempotency_mutation();

-- ----------------------------------------------------------------------------
-- (d) Widen the strand-check guard once more (264 -> 281 -> 285 -> here).
--     CREATE OR REPLACE is safe: no applied migration's on-disk text is
--     edited, this is a fresh statement replacing the function body at
--     apply time (253/267/268/281/285 precedent).
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.guard_visa_decision_retention_policy_mutation()
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
    ) OR EXISTS (
        SELECT 1
          FROM public.garuda_voa_checks AS garuda_check
         WHERE garuda_check.retention_policy_id = OLD.id
           AND NOT (NEW.effective_period @> garuda_check.created_at)
    ) OR EXISTS (
        SELECT 1
          FROM public.garuda_magic_link_tokens AS magic_link
         WHERE magic_link.retention_policy_id = OLD.id
           AND NOT (NEW.effective_period @> magic_link.created_at)
    ) OR EXISTS (
        SELECT 1
          FROM public.garuda_voa_check_results AS check_result
         WHERE check_result.retention_policy_id = OLD.id
           AND NOT (NEW.effective_period @> check_result.created_at)
    ) THEN
        RAISE EXCEPTION 'retention policy close would strand an existing binding';
    END IF;
    RETURN NEW;
END;
$$;

-- ----------------------------------------------------------------------------
-- (e) Bounded purge -- reuses visa_decision_retention_batches for evidence,
--     same shape as purge_garuda_voa_checks (281).
-- ----------------------------------------------------------------------------

CREATE FUNCTION public.purge_garuda_voa_check_results(p_limit INTEGER, p_requested_by TEXT)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    candidate_ids TEXT[];
    deleted_count INTEGER;
BEGIN
    IF p_limit IS NULL OR p_limit < 1 OR p_limit > 1000 THEN
        RAISE EXCEPTION 'purge limit must be between 1 and 1000';
    END IF;
    IF p_requested_by IS NULL
       OR p_requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'purge requested_by has invalid format';
    END IF;

    SELECT array_agg(candidate.result_id)
      INTO candidate_ids
      FROM (
          SELECT check_result.result_id
            FROM public.garuda_voa_check_results AS check_result
           WHERE check_result.retention_until < clock_timestamp()
           ORDER BY check_result.retention_until, check_result.result_id
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
        check_result.retention_policy_id,
        count(*)::INTEGER,
        session_user || ':' || p_requested_by
      FROM public.garuda_voa_check_results AS check_result
     WHERE check_result.result_id = ANY(candidate_ids)
     GROUP BY check_result.retention_policy_id;

    DELETE FROM public.garuda_voa_check_results
     WHERE result_id = ANY(candidate_ids);
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

REVOKE ALL ON FUNCTION public.purge_garuda_voa_check_results(INTEGER, TEXT) FROM PUBLIC;
COMMENT ON FUNCTION public.purge_garuda_voa_check_results(INTEGER, TEXT) IS
    'Bounded GARUDA VOA check-result purge primitive; requires an explicit operator grant and scheduler.';

DO $garuda_286_owner_transfer$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    target_function constant text[] := ARRAY[
        'public.bind_garuda_voa_check_result_retention_policy()',
        'public.purge_garuda_voa_check_results(integer, text)'
    ];
    signature text;
    current_owner text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ledger_owner) THEN
        RAISE NOTICE 'garuda check results (286): role % absent -- skipping ownership transfer, same convention as 251/253/268/281',
            ledger_owner;
        RETURN;
    END IF;

    FOREACH signature IN ARRAY target_function
    LOOP
        current_owner := (
            SELECT pg_get_userbyid(proowner)
              FROM pg_proc
             WHERE oid = signature::regprocedure
        );
        IF current_owner IS DISTINCT FROM ledger_owner THEN
            BEGIN
                EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
            EXCEPTION
                WHEN insufficient_privilege THEN
                    RAISE NOTICE 'garuda check results (286): ownership transfer of % to % requires operator action (current owner %, insufficient privilege) -- deferring to operator provisioning, same as 251/253/268/281',
                        signature, ledger_owner, current_owner;
            END;
        END IF;
    END LOOP;
END;
$garuda_286_owner_transfer$;

-- === ROLLBACK ===

DROP FUNCTION IF EXISTS public.purge_garuda_voa_check_results(INTEGER, TEXT);

CREATE OR REPLACE FUNCTION public.guard_visa_decision_retention_policy_mutation()
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
    ) OR EXISTS (
        SELECT 1
          FROM public.garuda_voa_checks AS garuda_check
         WHERE garuda_check.retention_policy_id = OLD.id
           AND NOT (NEW.effective_period @> garuda_check.created_at)
    ) OR EXISTS (
        SELECT 1
          FROM public.garuda_magic_link_tokens AS magic_link
         WHERE magic_link.retention_policy_id = OLD.id
           AND NOT (NEW.effective_period @> magic_link.created_at)
    ) THEN
        RAISE EXCEPTION 'retention policy close would strand an existing binding';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_guard_garuda_voa_check_idempotency_mutation ON public.garuda_voa_check_idempotency;
DROP FUNCTION IF EXISTS public.guard_garuda_voa_check_idempotency_mutation();
DROP TABLE IF EXISTS public.garuda_voa_check_idempotency;

DROP TRIGGER IF EXISTS garuda_voa_check_results_retention_binding ON public.garuda_voa_check_results;
DROP FUNCTION IF EXISTS public.bind_garuda_voa_check_result_retention_policy();
DROP INDEX IF EXISTS public.idx_garuda_voa_check_results_retention_purge;
DROP TABLE IF EXISTS public.garuda_voa_check_results;
