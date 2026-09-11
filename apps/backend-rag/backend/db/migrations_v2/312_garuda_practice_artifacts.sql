-- ============================================================================
-- 312_garuda_practice_artifacts.sql
-- GARUDA VOA W3A phase 2 -- the artifact: one immutable file, at most one
-- live per practice.
--
-- Spec: docs/plans/2026-09-11-garuda-voa-artifact-delivery-spec.md SS2-SS3.
-- Cures PENDING-ARMS row 1847 (opened 2026-09-02, ops/garuda-voa-step8-
-- portal, codex-gpt-5.6-sol council finding #3): "the staff transition
-- engine records OPAQUE evidence/artifact ids and never verifies their
-- content nor serves the artifact." `garuda_practices.artifact_id` /
-- `artifact_digest` (287) have had no referent at all until this table:
-- no row, bucket or route resolved one to bytes.
--
-- NUMBERING: 310 and 311 are taken on origin/main (310_practice_status_log.sql,
-- 311_practice_types_open_inquiry.sql -- Imperatore decision #11, 2026-09-11,
-- measured with `git ls-tree` on origin/main, not on this branch's older base).
-- Renumber again at rebase if a later 312 lands first (cicatrix W40) --
-- `scripts/lint_migration_numbers.py` catches a collision only against the
-- tree it runs on, so run it AFTER the rebase, never before.
--
-- OWNERSHIP: created while the session holds `backend_rag_v2`
-- (`assume_runtime_role`, migration_base.py) -- owned by `backend_rag_v2`
-- like every other `garuda_*` table (spec SS3), NOT by `visa_ledger_owner`.
-- Only the retention-binding trigger function in (2) needs the ledger
-- owner's lock-taking privilege on `visa_decision_retention_policies`,
-- exactly as measured for `garuda_documents` (304, unmerged -- read via
-- `git show origin/agent/air-m5/ops/garuda-voa-documents:.../304_garuda_
-- documents.sql`).
--
-- LEAST PRIVILEGE, HONESTLY CAVEATED (spec SS3: "'append-only' is a grant,
-- not an adjective"). PostgreSQL gives a table's OWNER every privilege
-- unconditionally; REVOKE against the owner is a no-op, and there is no ACL
-- entry that can make an owner's own DELETE fail. Because `backend_rag_v2`
-- is both this table's owner and the sole runtime writer in production, the
-- GRANT statements in (4) (SELECT + INSERT, and UPDATE scoped to the single
-- column `superseded_at`) document the INTENDED boundary and would bind a
-- future non-owner grantee (a read-only reporting role, or a split-ownership
-- migration the way 300/301 later did for magic-link retention) -- but
-- cannot themselves stop `backend_rag_v2` from writing outside that
-- boundary. The guard trigger in (3) is the REAL enforcement: it runs
-- regardless of which role's privileges apply and rejects any DELETE and
-- any UPDATE that is not exactly "set superseded_at once, nothing else."
--
-- SCOPE DEPENDENCY (phase_2_gate condition 2, brief.yml): retention is
-- bound to the existing `GARUDA_DOCUMENT` policy_scope, widened onto
-- `visa_decision_retention_policies` by migration 304 -- NOT merged to
-- `main` yet (PR #5526, suspended) at the time this file was written. Block
-- (0) below is a VERBATIM copy of 304's own idempotent "widen only if not
-- already widened" guard (find-by-shape, no hardcoded constraint name),
-- duplicated here rather than assumed present, for exactly one reason: this
-- migration must be independently testable (real-Postgres CI, tests/db/)
-- against a database that has run every migration ON `main` through this
-- branch's base, which does NOT include 304. Once 304 lands for real, this
-- block measures the enum already widened and returns immediately -- an
-- idempotent no-op, not a second competing definition.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- (0) Widen the one retention authority with the GARUDA_DOCUMENT scope, if
-- it is not already there. See the module header above for why this
-- duplicates 304's own block instead of assuming 304 has landed.
-- ----------------------------------------------------------------------------

DO $garuda_312_widen_scope_check$
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
        RAISE EXCEPTION 'garuda practice artifacts (312): could not locate the policy_scope enum CHECK to widen';
    END IF;

    IF scope_check_def LIKE '%GARUDA_DOCUMENT%' THEN
        -- Already widened (304 applied, or a prior emergency application).
        -- Nothing for this migration to do.
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
$garuda_312_widen_scope_check$;

-- ----------------------------------------------------------------------------
-- (1) garuda_practice_artifacts -- one row per artifact version.
--
-- Identity: `artifact_id` keeps the existing `^[A-Za-z0-9_-]{16,128}$` shape
-- (287 / staff_transitions.py::_ID_PATTERN) so no already-written
-- `garuda_practices.artifact_id` value becomes invalid, but phase 2
-- GENERATES it server-side (service layer), never accepts one from a staff
-- form (spec SS2). `artifact_digest` is the lowercase-hex SHA-256 of the
-- exact bytes stored, matching the frozen contract's
-- `DeliverPracticeTransition.artifact_digest` pattern (SS5's cure of fact
-- 17's looser runtime check).
--
-- byte_length's upper CHECK (25 MiB) is a generous defense-in-depth
-- ceiling, not the real limit -- the service enforces the actual byte
-- ceiling at write time (spec SS5, "an explicit byte ceiling... is what
-- keeps buffering safe") before a single row is attempted here.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.garuda_practice_artifacts (
    artifact_id         TEXT PRIMARY KEY
                        CHECK (artifact_id ~ '^[A-Za-z0-9_-]{16,128}$'),
    practice_id         TEXT NOT NULL REFERENCES public.garuda_practices (practice_id),
    -- Tigris key layout `artifacts/{environment}/{practice_id}/{artifact_id}`
    -- (spec SS3) -- UNIQUE so two rows can never alias the same object.
    storage_key         TEXT NOT NULL UNIQUE,
    artifact_digest     TEXT NOT NULL CHECK (artifact_digest ~ '^[a-f0-9]{64}$'),
    byte_length         BIGINT NOT NULL
                        CHECK (byte_length > 0 AND byte_length <= 26214400),
    -- Allowlist of exactly one value today (spec SS2: "the deliverable...
    -- the e-VOA grant or its equivalent official output" -- a document, not
    -- a video). A CHECK, not a free TEXT column, so a future content type
    -- is a migration, never a silent widening of what this table accepts.
    content_type        TEXT NOT NULL CHECK (content_type = 'application/pdf'),
    -- The staff actor whose putPracticeArtifact call produced this row
    -- (services/garuda_portal/staff_auth.py actor email) -- same shape as
    -- garuda_practices.assigned_to, no extra regex (staff emails are not
    -- independently validated at that call site either).
    produced_by         TEXT NOT NULL,
    environment         TEXT NOT NULL CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
    -- NULL = live (the one row a practice's active artifact_id/artifact_digest
    -- may point at -- enforced by the partial unique index below, not by
    -- convention). Set exactly once, by a correction superseding this row
    -- (spec SS2); the guard trigger in (3) makes "exactly once" a fact the
    -- database enforces, not just a caller's discipline.
    superseded_at       TIMESTAMPTZ,
    -- NOW() (== transaction_timestamp()): the retention-binding trigger
    -- below checks `NEW.created_at IS DISTINCT FROM transaction_timestamp()`
    -- (304's exact convention) -- see that migration's own comment for why
    -- statement_timestamp() would be wrong here.
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retention_policy_id UUID NOT NULL REFERENCES public.visa_decision_retention_policies (id),
    retention_until     TIMESTAMPTZ NOT NULL,
    CHECK (retention_until > created_at),
    CHECK (superseded_at IS NULL OR superseded_at > created_at)
);

COMMENT ON TABLE public.garuda_practice_artifacts IS
    'GARUDA VOA delivered artifact (product step 8, PR-11). One row per artifact version; at most one live (superseded_at IS NULL) row per practice, enforced by ux_garuda_practice_artifacts_live below. Never holds document bytes -- storage_key names an object in the PRIVATE garuda-voa-artifacts Tigris bucket (spec SS3), never nuzantara-warroom-images (public-read).';
COMMENT ON COLUMN public.garuda_practice_artifacts.superseded_at IS
    'NULL = live. Set exactly once by a correction; the guard trigger (3) refuses any other UPDATE and every DELETE for the runtime role. Physical row deletion is the retention sweep''s own role (spec SS6, decision #7a) -- not built by this migration.';

-- One live artifact per practice is a database fact, not a convention
-- (spec SS2) -- also the index the customer/staff read paths use to find
-- "the live row for this practice" in one lookup.
CREATE UNIQUE INDEX IF NOT EXISTS ux_garuda_practice_artifacts_live
    ON public.garuda_practice_artifacts (practice_id)
    WHERE superseded_at IS NULL;

-- Retention sweep's own scan (spec SS6: "the same retention-purge path the
-- other GARUDA_* scopes use"). Not partial: a superseded row's OBJECT is
-- already deleted immediately (SS2), but its ROW still waits for the sweep.
CREATE INDEX IF NOT EXISTS idx_garuda_practice_artifacts_retention_purge
    ON public.garuda_practice_artifacts (retention_until);

-- ----------------------------------------------------------------------------
-- (2) Fail-closed retention binding -- identical shape to
-- `active_garuda_document_policy_available` / `bind_garuda_document_
-- retention_policy` (304), scoped to GARUDA_DOCUMENT / CREATED_AT (spec
-- SS6: "the signed 30 days were authored for the intake cache tier... Phase
-- 2 builds against 30 d / CREATED_AT as ruled").
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.active_garuda_practice_artifact_policy_available(
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

COMMENT ON FUNCTION public.active_garuda_practice_artifact_policy_available IS
    'Pre-INSERT read for the artifact repository''s put path: one Zero-approved GARUDA_DOCUMENT policy must cover this clock, or the write fails closed (SERVICE_UNAVAILABLE) before any row is attempted.';

CREATE OR REPLACE FUNCTION public.bind_garuda_practice_artifact_retention_policy()
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
        RAISE EXCEPTION 'garuda practice artifact created_at must use the database transaction clock';
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
            RAISE EXCEPTION 'garuda practice artifact has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'garuda practice artifact retention policy authority is ambiguous';
    END;

    IF policy.retention_anchor <> 'CREATED_AT' THEN
        RAISE EXCEPTION 'unsupported retention anchor for GARUDA_DOCUMENT scope';
    END IF;
    expected_until := NEW.created_at + policy.retention_interval;
    IF expected_until <= clock_timestamp() THEN
        RAISE EXCEPTION 'garuda practice artifact retention deadline has already elapsed';
    END IF;

    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'garuda practice artifact retention policy does not match active policy';
    END IF;
    IF NEW.retention_until IS NOT NULL
       AND NEW.retention_until IS DISTINCT FROM expected_until THEN
        RAISE EXCEPTION 'garuda practice artifact retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.retention_until := expected_until;
    RETURN NEW;
END;
$func$;

REVOKE ALL ON FUNCTION public.bind_garuda_practice_artifact_retention_policy() FROM PUBLIC;

-- DROP-then-CREATE (Postgres has no `CREATE TRIGGER IF NOT EXISTS`), same
-- convergence idiom as 310_practice_status_log.sql -- makes this file safe
-- to re-apply directly (this migration's own real-Postgres test in
-- tests/db/ does exactly that, same reason 310's test does).
DROP TRIGGER IF EXISTS garuda_practice_artifacts_retention_binding ON public.garuda_practice_artifacts;
CREATE TRIGGER garuda_practice_artifacts_retention_binding
BEFORE INSERT ON public.garuda_practice_artifacts
FOR EACH ROW EXECUTE FUNCTION public.bind_garuda_practice_artifact_retention_policy();

-- THE OWNERSHIP TRANSFER -- replicated from 304's own shape verbatim
-- (measured at evidence/2026-09/agent-air-m5-ops-garuda-voa-0911-c652d82b/
-- migration-304-owner-bracket.patch plus 304's own DO $garuda_304_owner_
-- transfer$ block), except the function signature and block tag. Without
-- it the SECURITY DEFINER trigger above stays owned by backend_rag_v2,
-- which cannot take the FOR SHARE lock on visa_decision_retention_policies
-- either -- the SAME production outage 301 fixed for magic-link would
-- recur here on the first real write.
RESET ROLE;
DO $garuda_312_owner_transfer$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    signature constant text := 'public.bind_garuda_practice_artifact_retention_policy()';
    fn oid;
    current_owner text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ledger_owner) THEN
        RAISE NOTICE 'garuda practice artifacts (312): role % absent -- skipping ownership transfer, same convention as 251/253/268/281/301/304',
            ledger_owner;
        RETURN;
    END IF;

    fn := to_regprocedure(signature);
    IF fn IS NULL THEN
        RAISE NOTICE 'garuda practice artifacts (312): % not present -- nothing to transfer', signature;
        RETURN;
    END IF;

    SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;

    IF current_owner IS DISTINCT FROM ledger_owner THEN
        BEGIN
            EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE NOTICE 'garuda practice artifacts (312): ALTER denied (current owner %) -- this session is neither superuser nor a member of %',
                    current_owner, ledger_owner;
        END;
        SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;
    END IF;

    IF current_owner IS DISTINCT FROM ledger_owner THEN
        RAISE EXCEPTION
            'garuda practice artifacts (312): % is still owned by % -- the SECURITY DEFINER trigger cannot take its FOR SHARE lock on visa_decision_retention_policies, so putPracticeArtifact would answer 500 on write. Refusing to record this migration as applied while that is true: run the ALTER on a superuser connection, then re-apply.',
            signature, current_owner;
    END IF;
END;
$garuda_312_owner_transfer$;

-- MEASURED DEVIATION from 304's literal patch: an unconditional `SET ROLE
-- backend_rag_v2` aborts this migration's OWN real-Postgres test with
-- `role "backend_rag_v2" does not exist" -- verified directly against both
-- this session's local nuzantara_test AND CI's `postgres:15` service
-- container (.github/workflows/tests.yml), neither of which provisions
-- that role. 304's bare statement assumes an environment where it always
-- exists (Fly, or a dedicated-migrator DSN); migration_base.py's own
-- `assume_runtime_role` docstring only promises the statement is a no-op
-- "under the single-DSN runtime" WHEN `backend_rag_v2` is itself the
-- connecting login role, which neither environment measured here does.
-- Guarded so the schema this file builds is identical when the role
-- exists, and a clean no-op (current_role untouched) when it does not,
-- rather than an aborted migration. This deviation is PRESERVED, not
-- dropped, by decision #7b's fail-safe shape below -- the required shape
-- is itself guarded on role existence, only MORE defensive than what was
-- here (it also confirms session_user can actually assume the role before
-- attempting to, which the existence check alone does not): `to_regrole`
-- null-check (never a `pg_roles` SELECT -- same primitive `to_regprocedure`
-- above uses for the function, applied to a role instead), a NESTED `IF`
-- for each condition (never `AND`-combined -- Codex #8's own refutation of
-- the earlier guarded-bracket draft: `AND` operand evaluation order is not
-- guaranteed, so a role-existence check and a permission check must not
-- share one boolean expression), then `pg_has_role(session_user, ...)`
-- gated on server version -- PG16 added the `SET` privilege type (able to
-- assume the role without inheriting its privileges by default); PG15 and
-- earlier only understand `MEMBER`. `EXECUTE format(...)` (`%I`) rather
-- than a literal `EXECUTE 'SET ROLE backend_rag_v2'`, matching the
-- `format(...)`/`%I` convention the owner-transfer block above already
-- uses for `ALTER FUNCTION ... OWNER TO`.
DO $garuda_312_resume_runtime_role$
DECLARE
    target_role constant text := 'backend_rag_v2';
    can_assume boolean;
BEGIN
    IF to_regrole(target_role) IS NOT NULL THEN
        IF current_setting('server_version_num')::int >= 160000 THEN
            can_assume := pg_has_role(session_user, target_role, 'SET');
        ELSE
            can_assume := pg_has_role(session_user, target_role, 'MEMBER');
        END IF;
        IF can_assume THEN
            EXECUTE format('SET ROLE %I', target_role);
        END IF;
    END IF;
END;
$garuda_312_resume_runtime_role$;

-- ----------------------------------------------------------------------------
-- (3) The guard trigger -- the REAL "append-only, one mutable column"
-- enforcement (see the module header's LEAST PRIVILEGE note: ACL alone
-- cannot bind an owner-role writer). Runs for every role, including
-- backend_rag_v2 itself.
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.guard_garuda_practice_artifacts_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $func$
BEGIN
    IF TG_OP = 'DELETE' THEN
        -- Physical deletion is the retention sweep's own role, not yet
        -- built (spec SS6, decision #7a -- ledgered, not code in this
        -- migration). Unconditional refusal for now: there is no caller
        -- today for whom this operation on this table is ever correct.
        RAISE EXCEPTION 'garuda_practice_artifacts rows cannot be removed by this role -- physical removal is the retention sweep''s own role (decision #7a, not yet built)';
    END IF;

    -- TG_OP = 'UPDATE' from here.
    IF OLD.superseded_at IS NOT NULL THEN
        RAISE EXCEPTION 'garuda_practice_artifacts: superseded_at is immutable once set';
    END IF;
    IF NEW.superseded_at IS NULL THEN
        RAISE EXCEPTION 'garuda_practice_artifacts: the only permitted UPDATE sets superseded_at';
    END IF;
    IF NEW.artifact_id IS DISTINCT FROM OLD.artifact_id
       OR NEW.practice_id IS DISTINCT FROM OLD.practice_id
       OR NEW.storage_key IS DISTINCT FROM OLD.storage_key
       OR NEW.artifact_digest IS DISTINCT FROM OLD.artifact_digest
       OR NEW.byte_length IS DISTINCT FROM OLD.byte_length
       OR NEW.content_type IS DISTINCT FROM OLD.content_type
       OR NEW.produced_by IS DISTINCT FROM OLD.produced_by
       OR NEW.environment IS DISTINCT FROM OLD.environment
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.retention_policy_id IS DISTINCT FROM OLD.retention_policy_id
       OR NEW.retention_until IS DISTINCT FROM OLD.retention_until
    THEN
        RAISE EXCEPTION 'garuda_practice_artifacts: only superseded_at may change on UPDATE';
    END IF;
    RETURN NEW;
END;
$func$;

DROP TRIGGER IF EXISTS trg_guard_garuda_practice_artifacts_mutation ON public.garuda_practice_artifacts;
CREATE TRIGGER trg_guard_garuda_practice_artifacts_mutation
BEFORE UPDATE OR DELETE ON public.garuda_practice_artifacts
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_practice_artifacts_mutation();

-- ----------------------------------------------------------------------------
-- (4) Runtime grants -- documents the intended boundary; see the module
-- header's LEAST PRIVILEGE note for why this cannot itself bind the owner
-- role. No unconditional-removal grant appears anywhere, on purpose.
--
-- Guarded on role existence, same measured reason as the resume-role block
-- in (2): backend_rag_v2 is absent on the environments this migration's own
-- test runs against (this session's local nuzantara_test, CI's
-- `postgres:15` service), and a bare GRANT ... TO a nonexistent role fails
-- the whole migration exactly like the bare SET ROLE did -- same convention
-- as 244_compliance_alerts_runtime_grants.sql, which guards its own grant
-- block on `pg_roles` for the identical reason.
-- ----------------------------------------------------------------------------

DO $garuda_312_runtime_grants$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'backend_rag_v2') THEN
        -- PL/pgSQL has no direct GRANT statement -- EXECUTE, same as
        -- 244_compliance_alerts_runtime_grants.sql's own grant block.
        EXECUTE 'GRANT SELECT, INSERT ON TABLE public.garuda_practice_artifacts TO backend_rag_v2';
        EXECUTE 'GRANT UPDATE (superseded_at) ON TABLE public.garuda_practice_artifacts TO backend_rag_v2';
    END IF;
END;
$garuda_312_runtime_grants$;

-- === ROLLBACK ===

DROP TRIGGER IF EXISTS trg_guard_garuda_practice_artifacts_mutation ON public.garuda_practice_artifacts;
DROP FUNCTION IF EXISTS public.guard_garuda_practice_artifacts_mutation();
DROP TRIGGER IF EXISTS garuda_practice_artifacts_retention_binding ON public.garuda_practice_artifacts;
-- Same caveat 304's rollback accepts silently: bind_garuda_practice_artifact_
-- retention_policy() is owned by visa_ledger_owner after (2)'s transfer, so
-- this next statement requires a session that owns it (or superuser) --
-- exactly as 304's own rollback requires for its twin.
DROP FUNCTION IF EXISTS public.bind_garuda_practice_artifact_retention_policy();
DROP FUNCTION IF EXISTS public.active_garuda_practice_artifact_policy_available(TEXT, TIMESTAMPTZ);
DROP TABLE IF EXISTS public.garuda_practice_artifacts;

-- Narrowing (0)'s widened policy_scope CHECK back is only safe if no row
-- has ever used 'GARUDA_DOCUMENT' -- same reasoning, and the same bug
-- class, as 304's / 285's rollback (visa_decision_retention_policies is
-- append-only; a used scope value can never be removed to make room for a
-- narrower constraint).
DO $garuda_312_narrow_policy_scope$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.visa_decision_retention_policies
         WHERE policy_scope = 'GARUDA_DOCUMENT'
    ) THEN
        RAISE NOTICE 'garuda 312 rollback: visa_decision_retention_policies has row(s) with policy_scope = ''GARUDA_DOCUMENT'' -- the append-only guard makes them impossible to remove, so the policy_scope CHECK is left WIDENED (post-(0) state) rather than narrowed back.';
    ELSE
        ALTER TABLE public.visa_decision_retention_policies
            DROP CONSTRAINT IF EXISTS visa_decision_retention_policies_policy_scope_check;
        ALTER TABLE public.visa_decision_retention_policies
            ADD CONSTRAINT visa_decision_retention_policies_policy_scope_check
                CHECK (policy_scope IN ('VISA_DECISION', 'GARUDA_CHECK', 'GARUDA_ORDER', 'GARUDA_MAGIC_LINK'));
    END IF;
END;
$garuda_312_narrow_policy_scope$;
