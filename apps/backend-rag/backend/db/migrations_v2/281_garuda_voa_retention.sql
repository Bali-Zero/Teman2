-- ============================================================================
-- 281_garuda_voa_retention.sql
-- GARUDA VOA -- extend the ONE Zero-approved retention authority
-- (visa_decision_retention_policies, migration 264) to cover
-- garuda_voa_checks, instead of hand-rolling a second policy table.
--
-- This is L1 of the GARUDA VOA product build (products/garuda-voa/LANES.md).
-- ARCHITECTURE.md decision D2 rules explicitly for this shape: widen the
-- existing policy table with a `policy_scope` column and widen its UNIQUE/
-- EXCLUDE constraints to include it, rather than a parallel
-- `garuda_retention_policies` table. Q5 in DECISIONS.md: "signed" here means
-- the guarded, approved, append-only row this table already is -- NOT a
-- cryptographic signature. No key is introduced or looked for here.
--
-- FAIL-CLOSED BY CONSTRUCTION, same as 264: no GARUDA_CHECK policy row is
-- seeded by this migration. Every garuda_voa_checks INSERT fails until Zero
-- records an explicit duration/anchor/effective-period/approver for scope
-- GARUDA_CHECK, exactly as 264 already requires for VISA_DECISION. This is
-- precisely why L1 must merge before any lane persists a row
-- (products/garuda-voa/LANES.md, "Prerequisite chain").
--
-- Three traps this migration deliberately avoids (ARCHITECTURE.md D2):
--   1. The new binding trigger is SECURITY DEFINER from birth, not added
--      later as a roll-forward correction the way 268 had to fix 264's
--      original three trigger functions. `FOR SHARE` against a table this
--      runtime role only has SELECT on requires the function to run with
--      its (ledger-owner) owner's privileges, not the caller's.
--   2. No applied migration (264/266/268/261/276) is edited in place --
--      everything here is additive/new.
--   3. No migration number is reserved in advance; this file binds the
--      first free number as of commit time (280 was highest on origin/main
--      at authoring time -- W40 is the numbering-collision scar this rule
--      exists to prevent).
--
-- WHAT THIS MIGRATION ADDS
-- ============================================================================
--   (a) `policy_scope` on visa_decision_retention_policies (VISA_DECISION |
--       GARUDA_CHECK | GARUDA_ORDER), widening its UNIQUE and EXCLUDE
--       constraints to key on scope too, so a VISA_DECISION policy and a
--       GARUDA_CHECK policy can both be live for the same environment at
--       once without colliding. Existing (pre-migration) policy rows -- if
--       any are already live in an environment -- keep meaning exactly what
--       they always meant: DEFAULT 'VISA_DECISION' backfills them as that
--       scope, which is the only scope that has ever existed. GARUDA_ORDER
--       is reserved here as a vocabulary member for L3's future order
--       tables (products/garuda-voa/LANES.md L3) -- no L3 table exists on
--       disk yet, so no binding trigger for it is created by this
--       migration; that is L3's own migration when it lands.
--   (b) retention columns + BEFORE INSERT binding trigger on
--       garuda_voa_checks, mirroring bind_visa_decision_retention_policy:
--       the database derives retention_until server-side from the single
--       active GARUDA_CHECK policy for the row's environment; a caller
--       that supplies a mismatching value fails the whole insert.
--       garuda_voa_checks has no `evaluated_at` column (migration 261 --
--       it is a frozen-at-submission verdict row, not a bitemporal
--       decision), so GARUDA_CHECK policies are constrained to
--       retention_anchor = 'CREATED_AT' only.
--   (c) an explicit retention-notice-acknowledgement gate: a NEW row must
--       carry a non-null `retention_notice_acknowledged_at`, or the insert
--       fails closed. This is the DB-level half of
--       retention-fail-closed.feature's "Missing explicit acknowledgement"
--       scenario; verifying the acknowledgement was not inferred from a
--       page view or a preselected control is a UI-layer property L2/L6
--       must hold -- a column cannot prove that, it can only refuse a NULL.
--   (d) legal-hold support for garuda_voa_checks: a `legal_hold` column, a
--       dedicated append-only `garuda_voa_check_legal_hold_events` table
--       (a parallel-table shape is fine for this satellite ledger -- D2's
--       "one authority, not two" ruling is about the POLICY table
--       specifically; `visa_decision_legal_hold_events` FK's to
--       visa_decisions.id (UUID) and cannot address a VARCHAR(20) hash
--       without weakening a live production ledger's NOT NULL FK), and a
--       bounded `set_garuda_voa_check_legal_hold` primitive mirroring
--       `set_visa_decision_legal_hold`.
--   (e) a bounded purge primitive, `purge_garuda_voa_checks`, that skips
--       legal-hold rows and records aggregate evidence by REUSING
--       `visa_decision_retention_batches` (migration 264) -- that table is
--       already generic aggregate purge evidence keyed only by
--       retention_policy_id, with no decision-specific identifier, so
--       reusing it for garuda purge batches keeps purge evidence under the
--       same one authority rather than forking a second batches table.
--   (f) `garuda_voa_check_retention_evidence()`, PII-free backlog/lag
--       observability mirroring `visa_decision_retention_evidence`
--       (migration 266).
--   (g) `bind_legacy_garuda_voa_checks_retention_policy`, the bounded
--       disposition primitive retention-fail-closed.feature's "Legacy
--       GARUDA rows become governed rather than exempt" scenario requires:
--       once a GARUDA_CHECK policy exists, this binds pre-migration rows
--       (retention_policy_id IS NULL) to it using their real created_at as
--       anchor. Unlike the INSERT trigger, this explicitly PERMITS a
--       computed deadline that has already elapsed -- that is the correct
--       outcome for a legacy row (it becomes purge-eligible under the
--       newly authoritative policy), not an error. No retention duration
--       is invented; the row's true age is simply exposed under whatever
--       policy Zero actually signs.
--
-- Every new function is REVOKE ALL ... FROM PUBLIC and (best-effort,
-- role-guarded, exactly 268's idempotent pattern) OWNER TO
-- visa_ledger_owner, so the SECURITY DEFINER boundary is closed the same
-- way from the very first migration that introduces these functions --
-- there is no window where they are SECURITY INVOKER or PUBLIC-executable.
--
-- garuda_voa_checks currently has no `environment` value on its existing
-- (pre-migration) rows -- historically the only environment this table
-- ever served was the live PRODUCTION pilot (migration 276: "Historical
-- GARUDA VOA verdict archive"). This migration backfills environment =
-- 'PRODUCTION' for those rows as a factual label, not a retention
-- disposition -- it does NOT touch retention_policy_id/retention_until for
-- any existing row, which stay NULL (ungoverned) until an operator
-- explicitly runs the bounded backfill in (g) above.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- (a) policy_scope on the one retention authority
-- ----------------------------------------------------------------------------

ALTER TABLE public.visa_decision_retention_policies
    ADD COLUMN policy_scope TEXT NOT NULL DEFAULT 'VISA_DECISION'
        CHECK (policy_scope IN ('VISA_DECISION', 'GARUDA_CHECK', 'GARUDA_ORDER'));

ALTER TABLE public.visa_decision_retention_policies
    ADD CONSTRAINT visa_decision_retention_policies_scope_anchor CHECK (
        policy_scope <> 'GARUDA_CHECK' OR retention_anchor = 'CREATED_AT'
    );

-- Constraint names are not hardcoded: 264 let Postgres auto-generate them,
-- and the deterministic <table>_<cols>_key / _excl naming convention
-- truncates past 63 bytes on a table+column combination this long, so a
-- guessed literal name is not reliable. Find each by shape (contype) and
-- drop it dynamically instead.
DO $garuda_281_widen_constraints$
DECLARE
    unique_name  text;
    exclude_name text;
BEGIN
    SELECT conname INTO unique_name
      FROM pg_constraint
     WHERE conrelid = 'public.visa_decision_retention_policies'::regclass
       AND contype = 'u';
    EXECUTE format(
        'ALTER TABLE public.visa_decision_retention_policies DROP CONSTRAINT %I',
        unique_name
    );

    SELECT conname INTO exclude_name
      FROM pg_constraint
     WHERE conrelid = 'public.visa_decision_retention_policies'::regclass
       AND contype = 'x';
    EXECUTE format(
        'ALTER TABLE public.visa_decision_retention_policies DROP CONSTRAINT %I',
        exclude_name
    );
END;
$garuda_281_widen_constraints$;

ALTER TABLE public.visa_decision_retention_policies
    ADD CONSTRAINT visa_decision_retention_policies_scope_version_key
        UNIQUE (environment, policy_scope, policy_version),
    ADD CONSTRAINT visa_decision_retention_policies_scope_period_excl
        EXCLUDE USING gist (
            environment WITH =,
            policy_scope WITH =,
            effective_period WITH &&
        );

-- Widen the "closing this policy would strand an existing binding" guard
-- (264) to also cover garuda_voa_checks bindings, once they exist below.
-- CREATE OR REPLACE is safe here: no applied migration's on-disk text is
-- edited, this is a fresh statement in a new migration file replacing the
-- function body at apply time, same convention 253/267/268 already use for
-- roll-forward function corrections.
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
    ) THEN
        RAISE EXCEPTION 'retention policy close would strand an existing binding';
    END IF;
    RETURN NEW;
END;
$$;

-- ----------------------------------------------------------------------------
-- (b)+(c)+(d) garuda_voa_checks retention columns
-- ----------------------------------------------------------------------------

ALTER TABLE public.garuda_voa_checks
    ADD COLUMN environment TEXT
        CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION'));

-- Factual backfill only (see file header): this table's pre-migration rows
-- are all from the live production pilot. No retention disposition is
-- touched here.
UPDATE public.garuda_voa_checks SET environment = 'PRODUCTION' WHERE environment IS NULL;

-- garuda_voa_checks is the retired historical archive (migration 276): a
-- handful of rows, no live writer, no production traffic touches this
-- table today. The scan SET NOT NULL performs is momentary at this size —
-- same reasoning the workflow's blanket constraint-missing-not-valid
-- exclusion already applies to every other near-empty table in this repo.
-- A NOT VALID CHECK (squawk's suggested alternative) would still need a
-- separate VALIDATE pass to ever become enforced, which buys nothing here.
ALTER TABLE public.garuda_voa_checks
    -- squawk-ignore adding-not-nullable-field
    ALTER COLUMN environment SET NOT NULL;

ALTER TABLE public.garuda_voa_checks
    ADD COLUMN legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN retention_policy_id UUID
        -- squawk-ignore adding-foreign-key-constraint
        REFERENCES public.visa_decision_retention_policies (id),
    ADD COLUMN retention_until TIMESTAMPTZ,
    ADD COLUMN retention_notice_acknowledged_at TIMESTAMPTZ,
    ADD CONSTRAINT garuda_voa_checks_retention_binding_pair CHECK (
        (retention_policy_id IS NULL AND retention_until IS NULL)
        OR
        (retention_policy_id IS NOT NULL AND retention_until IS NOT NULL)
    );

-- NOT VALID preserves every pre-migration row: no fabricated retroactive
-- deadline. Enforced for every NEW row regardless; legacy disposition is
-- the explicit bounded backfill in (g), never silent.
ALTER TABLE public.garuda_voa_checks
    ADD CONSTRAINT garuda_voa_checks_retention_required CHECK (
        retention_policy_id IS NOT NULL AND retention_until IS NOT NULL
    ) NOT VALID;

CREATE INDEX idx_garuda_voa_checks_retention_purge
    ON public.garuda_voa_checks (retention_until, hash)
    WHERE legal_hold = FALSE AND retention_until IS NOT NULL;

CREATE FUNCTION public.bind_garuda_voa_check_retention_policy()
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
        RAISE EXCEPTION 'garuda check created_at must use the database transaction clock';
    END IF;
    IF NEW.legal_hold THEN
        RAISE EXCEPTION 'new garuda_voa_checks rows cannot begin under legal hold';
    END IF;
    IF NEW.retention_notice_acknowledged_at IS NULL THEN
        RAISE EXCEPTION 'garuda check requires an explicit retention notice acknowledgement';
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
            RAISE EXCEPTION 'garuda check has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'garuda check retention policy authority is ambiguous';
    END;

    IF policy.retention_anchor <> 'CREATED_AT' THEN
        RAISE EXCEPTION 'unsupported retention anchor for GARUDA_CHECK scope';
    END IF;
    expected_until := NEW.created_at + policy.retention_interval;
    IF expected_until <= clock_timestamp() THEN
        RAISE EXCEPTION 'garuda check retention deadline has already elapsed';
    END IF;

    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'garuda check retention policy does not match active policy';
    END IF;
    IF NEW.retention_until IS NOT NULL
       AND NEW.retention_until IS DISTINCT FROM expected_until THEN
        RAISE EXCEPTION 'garuda check retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.retention_until := expected_until;
    RETURN NEW;
END;
$$;

CREATE TRIGGER garuda_voa_checks_retention_binding
BEFORE INSERT ON public.garuda_voa_checks
FOR EACH ROW EXECUTE FUNCTION public.bind_garuda_voa_check_retention_policy();

-- ----------------------------------------------------------------------------
-- Legal hold: dedicated append-only ledger (see file header for why this is
-- a parallel table, not a widened visa_decision_legal_hold_events).
-- ----------------------------------------------------------------------------

CREATE TABLE public.garuda_voa_check_legal_hold_events (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    garuda_hash         VARCHAR(20) NOT NULL
        REFERENCES public.garuda_voa_checks (hash) ON DELETE CASCADE,
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

COMMENT ON TABLE public.garuda_voa_check_legal_hold_events IS
    'Meaningful per-check hold history, deleted atomically with its policy-retained parent (garuda_voa_checks).';

CREATE FUNCTION public.guard_garuda_voa_check_legal_hold_events_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    requested_by TEXT;
    table_owner  NAME;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'garuda_voa_check_legal_hold_events is append-only';
    END IF;
    requested_by := current_setting('visa.retention_requested_by', TRUE);
    SELECT pg_get_userbyid(relation.relowner)
      INTO table_owner
      FROM pg_class AS relation
      JOIN pg_namespace AS namespace
        ON namespace.oid = relation.relnamespace
     WHERE namespace.nspname = 'public'
       AND relation.relname = 'garuda_voa_check_legal_hold_events';
    IF current_user <> table_owner THEN
        RAISE EXCEPTION 'legal-hold history deletion requires the parent retention purge';
    END IF;
    IF requested_by IS NULL
       OR requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'legal-hold history deletion requires the parent retention purge';
    END IF;
    RETURN OLD;
END;
$$;

CREATE TRIGGER garuda_voa_check_legal_hold_events_guard
BEFORE UPDATE OR DELETE ON public.garuda_voa_check_legal_hold_events
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_voa_check_legal_hold_events_mutation();

CREATE TRIGGER garuda_voa_check_legal_hold_events_no_wipe
BEFORE TRUNCATE ON public.garuda_voa_check_legal_hold_events
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

-- ----------------------------------------------------------------------------
-- garuda_voa_checks mutation guard: view_count/share_count stay freely
-- writable (existing app contract, migration 261 comment); legal_hold
-- toggles only via the bounded privacy capability with audit evidence;
-- DELETE only via the bounded purge primitive.
-- ----------------------------------------------------------------------------

CREATE FUNCTION public.guard_garuda_voa_checks_retention_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    requested_by            TEXT;
    audit_actor             TEXT;
    hold_case_reference     TEXT;
    hold_reason_code        TEXT;
    hold_approved_by        TEXT;
    hold_review_due_at_text TEXT;
    hold_review_due_at      TIMESTAMPTZ;
    hold_review_interval    INTERVAL;
    table_owner             NAME;
BEGIN
    requested_by := current_setting('visa.retention_requested_by', TRUE);
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
           AND relation.relname = 'garuda_voa_checks';
        IF current_user <> table_owner THEN
            RAISE EXCEPTION 'garuda_voa_checks delete must use the bounded retention purge';
        END IF;
        IF requested_by IS NULL
           OR requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
            RAISE EXCEPTION 'garuda_voa_checks delete must use the bounded retention purge';
        END IF;
        IF OLD.retention_until IS NOT NULL
           AND OLD.retention_until < clock_timestamp()
           AND OLD.legal_hold = FALSE THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'garuda_voa_checks delete requires elapsed retention and legal_hold=false';
    END IF;

    -- Free-write carve-out: view_count/share_count, unrelated to retention.
    IF (to_jsonb(OLD) - 'view_count' - 'share_count')
           IS NOT DISTINCT FROM (to_jsonb(NEW) - 'view_count' - 'share_count') THEN
        RETURN NEW;
    END IF;

    -- Legacy disposition carve-out: bind_legacy_garuda_voa_checks_retention_policy
    -- (g) moves a legacy row from NULL/NULL to a bound policy/deadline pair,
    -- nothing else. Gated on the same bounded-capability signal the purge
    -- and legal-hold paths already use.
    IF OLD.retention_policy_id IS NULL AND OLD.retention_until IS NULL
       AND NEW.retention_policy_id IS NOT NULL AND NEW.retention_until IS NOT NULL
       AND (to_jsonb(OLD) - 'retention_policy_id' - 'retention_until')
               IS NOT DISTINCT FROM (to_jsonb(NEW) - 'retention_policy_id' - 'retention_until')
    THEN
        IF requested_by IS NULL
           OR requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
            RAISE EXCEPTION 'legacy retention disposition requires the bounded backfill capability';
        END IF;
        RETURN NEW;
    END IF;

    IF (to_jsonb(OLD) - 'legal_hold') IS DISTINCT FROM (to_jsonb(NEW) - 'legal_hold')
       OR OLD.legal_hold IS NOT DISTINCT FROM NEW.legal_hold THEN
        RAISE EXCEPTION 'garuda_voa_checks update may only change view_count/share_count or legal_hold';
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

    INSERT INTO public.garuda_voa_check_legal_hold_events (
        garuda_hash, retention_policy_id, event_type,
        old_legal_hold, new_legal_hold, executor_label,
        case_reference, reason_code, approved_by, review_due_at
    ) VALUES (
        OLD.hash,
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

CREATE TRIGGER garuda_voa_checks_retention_guard
BEFORE UPDATE OR DELETE ON public.garuda_voa_checks
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_voa_checks_retention_mutation();

CREATE TRIGGER garuda_voa_checks_no_wipe
BEFORE TRUNCATE ON public.garuda_voa_checks
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

-- ----------------------------------------------------------------------------
-- (e) bounded purge -- reuses visa_decision_retention_batches for evidence.
-- ----------------------------------------------------------------------------

CREATE FUNCTION public.purge_garuda_voa_checks(p_limit INTEGER, p_requested_by TEXT)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    candidate_hashes VARCHAR(20)[];
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

    SELECT array_agg(candidate.hash)
      INTO candidate_hashes
      FROM (
          SELECT garuda_check.hash
            FROM public.garuda_voa_checks AS garuda_check
           WHERE garuda_check.retention_until < clock_timestamp()
             AND garuda_check.legal_hold = FALSE
           ORDER BY garuda_check.retention_until, garuda_check.hash
           LIMIT p_limit
           FOR UPDATE SKIP LOCKED
      ) AS candidate;

    IF candidate_hashes IS NULL THEN
        RETURN 0;
    END IF;

    INSERT INTO public.visa_decision_retention_batches (
        retention_policy_id, affected_count, executor_label
    )
    SELECT
        garuda_check.retention_policy_id,
        count(*)::INTEGER,
        session_user || ':' || p_requested_by
      FROM public.garuda_voa_checks AS garuda_check
     WHERE garuda_check.hash = ANY(candidate_hashes)
     GROUP BY garuda_check.retention_policy_id;

    DELETE FROM public.garuda_voa_checks
     WHERE hash = ANY(candidate_hashes);
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- ----------------------------------------------------------------------------
-- (f) PII-free observability
-- ----------------------------------------------------------------------------

CREATE FUNCTION public.garuda_voa_check_retention_evidence()
RETURNS TABLE (
    expired_rows BIGINT,
    expired_held_rows BIGINT,
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
        count(garuda_check.hash) FILTER (
            WHERE garuda_check.retention_until <= observation.observed_at
              AND garuda_check.legal_hold = FALSE
        )::BIGINT AS expired_rows,
        count(garuda_check.hash) FILTER (
            WHERE garuda_check.retention_until <= observation.observed_at
              AND garuda_check.legal_hold = TRUE
        )::BIGINT AS expired_held_rows,
        COALESCE(
            max(
                GREATEST(
                    EXTRACT(EPOCH FROM observation.observed_at - garuda_check.retention_until),
                    0
                )
            ) FILTER (
                WHERE garuda_check.retention_until <= observation.observed_at
                  AND garuda_check.legal_hold = FALSE
            ),
            0
        )::DOUBLE PRECISION AS max_lag_seconds,
        observation.observed_at
    FROM observation
    LEFT JOIN public.garuda_voa_checks AS garuda_check
      ON garuda_check.retention_until IS NOT NULL
    GROUP BY observation.observed_at;
$$;

-- ----------------------------------------------------------------------------
-- Legal hold transition primitive (mirrors set_visa_decision_legal_hold).
-- ----------------------------------------------------------------------------

CREATE FUNCTION public.set_garuda_voa_check_legal_hold(
    p_hash VARCHAR(20),
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
    target_hash      VARCHAR(20);
    target_policy_id UUID;
    changed_count    INTEGER;
BEGIN
    IF p_hash IS NULL OR p_legal_hold IS NULL THEN
        RAISE EXCEPTION 'legal hold requires hash and state';
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

    SELECT garuda_check.hash, garuda_check.retention_policy_id
      INTO target_hash, target_policy_id
      FROM public.garuda_voa_checks AS garuda_check
     WHERE garuda_check.hash = p_hash
     FOR UPDATE;
    IF target_hash IS NULL THEN
        RETURN FALSE;
    END IF;
    IF target_policy_id IS NULL THEN
        RAISE EXCEPTION 'legacy garuda check requires explicit disposition before legal hold';
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
    UPDATE public.garuda_voa_checks
       SET legal_hold = p_legal_hold
     WHERE hash = target_hash
       AND legal_hold IS DISTINCT FROM p_legal_hold;
    GET DIAGNOSTICS changed_count = ROW_COUNT;
    RETURN changed_count = 1;
END;
$$;

-- ----------------------------------------------------------------------------
-- (g) legacy disposition -- explicit, bounded, never silent.
-- ----------------------------------------------------------------------------

CREATE FUNCTION public.bind_legacy_garuda_voa_checks_retention_policy(
    p_limit INTEGER,
    p_requested_by TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    bound_count INTEGER := 0;
    legacy_row RECORD;
    policy RECORD;
    computed_until TIMESTAMPTZ;
BEGIN
    IF p_limit IS NULL OR p_limit < 1 OR p_limit > 1000 THEN
        RAISE EXCEPTION 'legacy backfill limit must be between 1 and 1000';
    END IF;
    IF p_requested_by IS NULL
       OR p_requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'legacy backfill requested_by has invalid format';
    END IF;

    PERFORM set_config('visa.retention_requested_by', p_requested_by, TRUE);

    FOR legacy_row IN
        SELECT garuda_check.hash, garuda_check.environment, garuda_check.created_at
          FROM public.garuda_voa_checks AS garuda_check
         WHERE garuda_check.retention_policy_id IS NULL
         ORDER BY garuda_check.created_at, garuda_check.hash
         LIMIT p_limit
         FOR UPDATE SKIP LOCKED
    LOOP
        SELECT policy_row.id, policy_row.retention_interval
          INTO policy
          FROM public.visa_decision_retention_policies AS policy_row
         WHERE policy_row.environment = legacy_row.environment
           AND policy_row.policy_scope = 'GARUDA_CHECK'
           AND policy_row.effective_period @> legacy_row.created_at;

        -- No active policy covers this row yet (e.g. its created_at
        -- predates the policy's effective_period lower bound): leave it
        -- ungoverned, do not invent coverage. Not counted as bound.
        CONTINUE WHEN policy.id IS NULL;

        computed_until := legacy_row.created_at + policy.retention_interval;

        UPDATE public.garuda_voa_checks
           SET retention_policy_id = policy.id,
               retention_until = computed_until
         WHERE hash = legacy_row.hash;
        bound_count := bound_count + 1;
    END LOOP;

    RETURN bound_count;
END;
$$;

-- ----------------------------------------------------------------------------
-- Close the SECURITY DEFINER boundary on every function this migration
-- introduces: EXECUTE revoked from PUBLIC, ownership best-effort (role-
-- guarded, idempotent, privilege-guarded -- exactly 268's pattern) moved to
-- visa_ledger_owner.
-- ----------------------------------------------------------------------------

REVOKE ALL ON FUNCTION public.bind_garuda_voa_check_retention_policy() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.guard_garuda_voa_check_legal_hold_events_mutation() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.guard_garuda_voa_checks_retention_mutation() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.purge_garuda_voa_checks(INTEGER, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.garuda_voa_check_retention_evidence() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.set_garuda_voa_check_legal_hold(
    VARCHAR, BOOLEAN, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.bind_legacy_garuda_voa_checks_retention_policy(INTEGER, TEXT)
    FROM PUBLIC;

COMMENT ON FUNCTION public.purge_garuda_voa_checks(INTEGER, TEXT) IS
    'Bounded GARUDA VOA check purge primitive; requires an explicit operator grant and scheduler.';
COMMENT ON FUNCTION public.garuda_voa_check_retention_evidence() IS
    'PII-free purge backlog, held-expired count and max purge lag for garuda_voa_checks; operator grant required.';
COMMENT ON FUNCTION public.set_garuda_voa_check_legal_hold(
    VARCHAR, BOOLEAN, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
) IS
    'Bounded legal-hold transition with append-only event evidence; privacy operator grant required.';
COMMENT ON FUNCTION public.bind_legacy_garuda_voa_checks_retention_policy(INTEGER, TEXT) IS
    'Bounded, explicit disposition of pre-migration garuda_voa_checks rows onto an active GARUDA_CHECK policy; never invents coverage or a fabricated deadline.';

DO $garuda_281_owner_transfer$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    target_function constant text[] := ARRAY[
        'public.bind_garuda_voa_check_retention_policy()',
        'public.guard_garuda_voa_check_legal_hold_events_mutation()',
        'public.guard_garuda_voa_checks_retention_mutation()',
        'public.purge_garuda_voa_checks(integer, text)',
        'public.garuda_voa_check_retention_evidence()',
        'public.set_garuda_voa_check_legal_hold(varchar, boolean, text, text, text, text, timestamptz)',
        'public.bind_legacy_garuda_voa_checks_retention_policy(integer, text)'
    ];
    signature text;
    current_owner text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ledger_owner) THEN
        RAISE NOTICE 'garuda retention (281): role % absent -- skipping ownership transfer, same convention as 251/253/268',
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
                    RAISE NOTICE 'garuda retention (281): ownership transfer of % to % requires operator action (current owner %, insufficient privilege) -- deferring to operator provisioning, same as 251/253/268',
                        signature, ledger_owner, current_owner;
            END;
        END IF;
    END LOOP;
END;
$garuda_281_owner_transfer$;

-- === ROLLBACK ===

DROP FUNCTION IF EXISTS public.bind_legacy_garuda_voa_checks_retention_policy(INTEGER, TEXT);
DROP FUNCTION IF EXISTS public.set_garuda_voa_check_legal_hold(
    VARCHAR, BOOLEAN, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ
);
DROP FUNCTION IF EXISTS public.garuda_voa_check_retention_evidence();
DROP FUNCTION IF EXISTS public.purge_garuda_voa_checks(INTEGER, TEXT);

DROP TRIGGER IF EXISTS garuda_voa_checks_no_wipe ON public.garuda_voa_checks;
DROP TRIGGER IF EXISTS garuda_voa_checks_retention_guard ON public.garuda_voa_checks;
DROP FUNCTION IF EXISTS public.guard_garuda_voa_checks_retention_mutation();

DROP TRIGGER IF EXISTS garuda_voa_check_legal_hold_events_no_wipe
    ON public.garuda_voa_check_legal_hold_events;
DROP TRIGGER IF EXISTS garuda_voa_check_legal_hold_events_guard
    ON public.garuda_voa_check_legal_hold_events;
DROP FUNCTION IF EXISTS public.guard_garuda_voa_check_legal_hold_events_mutation();
DROP TABLE IF EXISTS public.garuda_voa_check_legal_hold_events;

DROP TRIGGER IF EXISTS garuda_voa_checks_retention_binding ON public.garuda_voa_checks;
DROP FUNCTION IF EXISTS public.bind_garuda_voa_check_retention_policy();

DROP INDEX IF EXISTS public.idx_garuda_voa_checks_retention_purge;
ALTER TABLE public.garuda_voa_checks
    DROP CONSTRAINT IF EXISTS garuda_voa_checks_retention_required,
    DROP CONSTRAINT IF EXISTS garuda_voa_checks_retention_binding_pair,
    DROP COLUMN IF EXISTS retention_notice_acknowledged_at,
    DROP COLUMN IF EXISTS retention_until,
    DROP COLUMN IF EXISTS retention_policy_id,
    DROP COLUMN IF EXISTS legal_hold,
    DROP COLUMN IF EXISTS environment;

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
    ) THEN
        RAISE EXCEPTION 'retention policy close would strand an existing binding';
    END IF;
    RETURN NEW;
END;
$$;

ALTER TABLE public.visa_decision_retention_policies
    DROP CONSTRAINT IF EXISTS visa_decision_retention_policies_scope_period_excl,
    DROP CONSTRAINT IF EXISTS visa_decision_retention_policies_scope_version_key;

DO $garuda_281_restore_constraints$
BEGIN
    ALTER TABLE public.visa_decision_retention_policies
        ADD CONSTRAINT visa_decision_retention_policies_environment_policy_version_key
            UNIQUE (environment, policy_version);
EXCEPTION
    WHEN duplicate_table THEN
        NULL;
END;
$garuda_281_restore_constraints$;

-- Rollback-only, never executed forward (migration_base.py runs only the
-- forward DDL — same family as this file's own disallowed-unique-constraint
-- exclusion precedent, migration 175). This name is byte-for-byte 264's
-- original identifier: Postgres already truncated it to the identical 63
-- bytes the first time 264 ran, so a rollback re-creating it truncates the
-- same way and restores the exact prior state — not a new defect.
ALTER TABLE public.visa_decision_retention_policies
    -- squawk-ignore identifier-too-long
    ADD CONSTRAINT visa_decision_retention_policies_environment_effective_period_excl
        EXCLUDE USING gist (environment WITH =, effective_period WITH &&);

ALTER TABLE public.visa_decision_retention_policies
    DROP CONSTRAINT IF EXISTS visa_decision_retention_policies_scope_anchor,
    DROP COLUMN IF EXISTS policy_scope;
