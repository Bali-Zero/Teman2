-- ============================================================================
-- 313_garuda_practice_artifacts.sql
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
-- NUMBERING: this file was 312 until the rebase, and 312 is now taken --
-- `312_research_os_naga_claims.sql` (Research OS lane, merged 2026-09-12
-- 06:4xZ as 890e731b91) landed while this branch was in review. That is
-- cicatrix W40 arriving exactly where it was predicted to: a migration
-- number is not reserved by writing it, only by merging it, and
-- `scripts/lint_migration_numbers.py` can only measure the tree it runs
-- on -- which is why it runs AFTER the rebase and never before. Measured
-- on fresh `origin/main` with `git ls-tree`: 307-312 occupied, 313 free.
-- The other lane's 312 was checked for overlap with this one and has none
-- (`grep -i garuda` on it: zero hits) -- different tables, roles and
-- scopes, so the two are neighbours in number only.
--
-- OWNERSHIP: created while the session holds `backend_rag_v2`
-- (`assume_runtime_role`, migration_base.py), then handed to
-- `visa_ledger_owner` -- table, guard function and retention-binding
-- function alike -- by the two transfer blocks in (2) and (3bis).
-- `garuda_*` tables are otherwise owned by `backend_rag_v2` (spec SS3) and
-- this one is the deliberate exception, ruled by the Imperatore (decision
-- #16, 2026-09-12) on Sol's F8: this is the only `garuda_*` table whose
-- whole value proposition is that the runtime CANNOT rewrite history on
-- it, and an owner can always take a guard apart. See (3bis) for the
-- statements that were reachable while `backend_rag_v2` owned it, and the
-- LEAST PRIVILEGE note below for what the split does and does not buy.
-- The ledger owner is the same role (2) already required for its trigger's
-- lock-taking privilege on `visa_decision_retention_policies`, exactly as
-- measured for `garuda_documents` (304, unmerged -- read via `git show
-- origin/agent/air-m5/ops/garuda-voa-documents:.../304_garuda_
-- documents.sql`).
--
-- LEAST PRIVILEGE (spec SS3: "'append-only' is a grant, not an
-- adjective"). PostgreSQL gives a table's OWNER every privilege
-- unconditionally: REVOKE against an owner is a no-op, and no ACL entry
-- can make an owner's own removal fail. An earlier draft of this file
-- accepted that as a caveat -- `backend_rag_v2` owned the table, the
-- grants in (4) merely documented the intent, and the guard trigger in (3)
-- was called "the REAL enforcement". Sol's F8 showed the last step of that
-- reasoning to be false: the owner can take the guard apart (disable it,
-- remove it, or replace its body) before writing whatever it likes, so a
-- guard owned by the role it constrains constrains nobody.
--
-- (3bis) therefore moves the table and the guard function to
-- `visa_ledger_owner`. What that buys, precisely: the runtime role holds
-- ONLY the three grants in (4) -- SELECT, INSERT, and UPDATE of
-- `superseded_at`/`superseded_by` -- and reaches the guard only by
-- triggering it. Removals, trigger management and any rewrite of the
-- guard's body now require a role no production process logs in as. What
-- it does NOT buy: anyone able to authenticate AS `visa_ledger_owner`, or
-- as a superuser, is outside every boundary in this file -- that is a
-- credential-custody property, not a schema one.
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

DO $garuda_313_widen_scope_check$
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
        RAISE EXCEPTION 'garuda practice artifacts (313): could not locate the policy_scope enum CHECK to widen';
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
$garuda_313_widen_scope_check$;

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
    -- database enforces, not just a caller's discipline. Always set in the
    -- SAME update as superseded_by (Imperatore decision #13-revision,
    -- 2026-09-11: "always supersede, never 409, made observable") -- the
    -- guard trigger refuses either column changing without the other.
    superseded_at       TIMESTAMPTZ,
    -- The new row's artifact_id that replaced this one -- NULL exactly when
    -- superseded_at is NULL (decision #13-revision). Self-referencing FK,
    -- not a separate lookup table: a supersession is a fact about this one
    -- row, and the CHECK below refuses a row naming itself.
    --
    -- DEFERRABLE INITIALLY DEFERRED, on purpose: `postgres_repository.py::
    -- insert_superseding` marks the OLD row's superseded_by = <new
    -- artifact_id> BEFORE the new row is inserted (the partial unique
    -- index `ux_garuda_practice_artifacts_live` requires that order --
    -- inserting the new live row first would transiently give it two live
    -- rows for the same practice_id). A NOT DEFERRABLE FK checks
    -- immediately after that UPDATE and fails closed with "not present in
    -- garuda_practice_artifacts", because the referenced row does not
    -- exist yet at that point in the SAME transaction -- measured directly
    -- (asyncpg.ForeignKeyViolationError) while building this migration.
    -- Deferring the check to COMMIT is what lets both statements land in
    -- the one order the unique index tolerates -- and, since Sol's F7, it
    -- is also the only moment at which the successor's practice_id can be
    -- compared with this row's. The reference is therefore the COMPOSITE,
    -- still-deferred foreign key declared at the END of this table, not a
    -- column-level one -- read it for the case the single-column version
    -- accepted.
    superseded_by       TEXT,
    -- NOW() (== transaction_timestamp()): the retention-binding trigger
    -- below checks `NEW.created_at IS DISTINCT FROM transaction_timestamp()`
    -- (304's exact convention) -- see that migration's own comment for why
    -- statement_timestamp() would be wrong here.
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retention_policy_id UUID NOT NULL REFERENCES public.visa_decision_retention_policies (id),
    retention_until     TIMESTAMPTZ NOT NULL,
    CHECK (retention_until > created_at),
    CHECK (superseded_at IS NULL OR superseded_at > created_at),
    -- The two supersession columns are set together or not at all --
    -- structural backstop for the guard trigger's identical rule.
    CHECK ((superseded_at IS NULL) = (superseded_by IS NULL)),
    CHECK (superseded_by IS NULL OR superseded_by <> artifact_id),
    -- The successor must belong to the SAME practice, and the database is
    -- what says so. Sol's O1 refutation (2026-09-11, finding F7, BLOCKER)
    -- built the case the earlier single-column FK accepted: point a
    -- Delivered practice's sole live row at an artifact_id belonging to
    -- ANOTHER practice. Every other structure in this file waves it
    -- through -- the FK resolves (the target row does exist), the guard
    -- trigger in (3) checks that OLD.practice_id does not CHANGE but never
    -- looks at where superseded_by points, and the partial unique index is
    -- satisfied by construction because it only ever counts live rows.
    -- The result is a practice with zero live artifacts whose
    -- `garuda_practices.artifact_id` still names the row just retired:
    -- Delivered, pointer stale, customer GET 404 forever, and no error
    -- anywhere.
    --
    -- Composite FK rather than a guard-trigger lookup, because the guard
    -- CANNOT do this check: `postgres_repository.insert_superseding` marks
    -- the old row BEFORE inserting the successor (the partial unique index
    -- tolerates no other order), so at BEFORE UPDATE time the successor
    -- row does not exist yet and any SELECT for it would fail every legal
    -- supersession. Deferring to COMMIT is the only moment both rows are
    -- on the table -- the same reason the reference was DEFERRABLE
    -- already. `MATCH SIMPLE` (the default) leaves the constraint
    -- unchecked while superseded_by IS NULL, which is exactly the live-row
    -- case; practice_id is NOT NULL, so no other partial-null shape exists.
    UNIQUE (artifact_id, practice_id),
    FOREIGN KEY (superseded_by, practice_id)
        REFERENCES public.garuda_practice_artifacts (artifact_id, practice_id)
        DEFERRABLE INITIALLY DEFERRED
);

COMMENT ON TABLE public.garuda_practice_artifacts IS
    'GARUDA VOA delivered artifact (product step 8, PR-11). One row per artifact version; at most one live (superseded_at IS NULL) row per practice, enforced by ux_garuda_practice_artifacts_live below. Never holds document bytes -- storage_key names an object in the PRIVATE garuda-voa-artifacts Tigris bucket (spec SS3), never nuzantara-warroom-images (public-read).';
COMMENT ON COLUMN public.garuda_practice_artifacts.superseded_at IS
    'NULL = live. Set exactly once by a correction, together with superseded_by; the guard trigger (3) refuses any other UPDATE and every DELETE for the runtime role. Physical row deletion is the retention sweep''s own role (spec SS6, decision #7a) -- not built by this migration.';
COMMENT ON COLUMN public.garuda_practice_artifacts.superseded_by IS
    'NULL = live. Set exactly once, together with superseded_at, to the artifact_id of the row that replaced this one (decision #13-revision) -- the guard trigger (3) enforces both columns move together and never again after that, and the composite deferred FK enforces that the successor belongs to the SAME practice (Sol finding F7).';

-- One live artifact per practice is a database fact, not a convention
-- (spec SS2) -- also the index the customer/staff read paths use to find
-- "the live row for this practice" in one lookup.
CREATE UNIQUE INDEX IF NOT EXISTS ux_garuda_practice_artifacts_live
    ON public.garuda_practice_artifacts (practice_id)
    WHERE superseded_at IS NULL;

-- Retention sweep's own scan (spec SS6: "the same retention-purge path the
-- other GARUDA_* scopes use"). Not partial: a superseded row's OBJECT stays
-- in the bucket -- there is no delete member on the object-store port
-- (decision #13-revision) -- physical deletion of either the object or the
-- row is the retention sweep's own future role (spec SS6, decision #7a),
-- not built by this migration.
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
-- Remember the role this session is ACTUALLY on before dropping it. The
-- resume blocks below restore THIS value rather than naming a role
-- literally: `assume_runtime_role` (migration_base.py) is an unconditional
-- no-op in the single-DSN shape (CI, laptops, Fly until the dedicated
-- secret exists), so in that shape the session never was `backend_rag_v2`
-- to begin with -- and a superuser is a member of every role by
-- `pg_has_role`'s definition, so a resume that asks "may I become
-- backend_rag_v2?" answers yes and leaves the session somewhere it never
-- was. Sol's O2 (2026-09-12, new finding 2, MAJOR) traced that to the
-- migration manager's own next statement running under a role nobody
-- chose. Restoring what was measured cannot have that failure mode.
SELECT set_config('garuda313.prior_role', current_role, false);
RESET ROLE;
DO $garuda_313_owner_transfer$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    signature constant text := 'public.bind_garuda_practice_artifact_retention_policy()';
    fn oid;
    current_owner text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ledger_owner) THEN
        RAISE NOTICE 'garuda practice artifacts (313): role % absent -- skipping ownership transfer, same convention as 251/253/268/281/301/304',
            ledger_owner;
        RETURN;
    END IF;

    fn := to_regprocedure(signature);
    IF fn IS NULL THEN
        RAISE NOTICE 'garuda practice artifacts (313): % not present -- nothing to transfer', signature;
        RETURN;
    END IF;

    SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;

    IF current_owner IS DISTINCT FROM ledger_owner THEN
        BEGIN
            EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE NOTICE 'garuda practice artifacts (313): ALTER denied (current owner %) -- this session is neither superuser nor a member of %',
                    current_owner, ledger_owner;
        END;
        SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;
    END IF;

    IF current_owner IS DISTINCT FROM ledger_owner THEN
        RAISE EXCEPTION
            'garuda practice artifacts (313): % is still owned by % -- the SECURITY DEFINER trigger cannot take its FOR SHARE lock on visa_decision_retention_policies, so putPracticeArtifact would answer 500 on write. Refusing to record this migration as applied while that is true: run the ALTER on a superuser connection, then re-apply.',
            signature, current_owner;
    END IF;
END;
$garuda_313_owner_transfer$;

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
DO $garuda_313_resume_runtime_role$
DECLARE
    prior_role text := current_setting('garuda313.prior_role', true);
    can_restore boolean;
BEGIN
    -- No-op whenever the session is already where it started (the common
    -- case: nothing had assumed another role in the first place).
    IF prior_role IS NOT NULL AND prior_role <> '' AND prior_role IS DISTINCT FROM current_role THEN
        -- The SAME fail-safe bracket 304 uses, and for the same reason,
        -- even though the session demonstrably WAS on this role a moment
        -- ago: nested IFs rather than one AND-combined expression (operand
        -- evaluation order is not guaranteed -- Codex #8), `to_regrole`
        -- rather than a `pg_roles` SELECT, and the privilege probe split
        -- by server version because PG16 added the `SET` privilege type
        -- while PG15 and earlier only understand `MEMBER`. Interpolated
        -- with `format('%I')`, never concatenated (Imperatore decision
        -- #20, 2026-09-12).
        IF to_regrole(prior_role) IS NOT NULL THEN
            IF current_setting('server_version_num')::int >= 160000 THEN
                can_restore := pg_has_role(session_user, prior_role, 'SET');
            ELSE
                can_restore := pg_has_role(session_user, prior_role, 'MEMBER');
            END IF;
            IF can_restore THEN
                EXECUTE format('SET ROLE %I', prior_role);
            ELSE
                RAISE NOTICE 'garuda practice artifacts (313): session_user % may no longer assume %, leaving the session on its login role',
                    session_user, prior_role;
            END IF;
        END IF;
    END IF;
END;
$garuda_313_resume_runtime_role$;

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
        -- OLD.superseded_by is NOT NULL too whenever OLD.superseded_at is
        -- (table CHECK enforces the pair) -- one guard covers both: a row
        -- may be superseded exactly once, never a second time.
        RAISE EXCEPTION 'garuda_practice_artifacts: superseded_at/superseded_by are immutable once set';
    END IF;
    IF NEW.superseded_at IS NULL OR NEW.superseded_by IS NULL THEN
        RAISE EXCEPTION 'garuda_practice_artifacts: the only permitted UPDATE sets superseded_at and superseded_by together';
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
        RAISE EXCEPTION 'garuda_practice_artifacts: only superseded_at and superseded_by may change on UPDATE';
    END IF;
    RETURN NEW;
END;
$func$;

DROP TRIGGER IF EXISTS trg_guard_garuda_practice_artifacts_mutation ON public.garuda_practice_artifacts;
CREATE TRIGGER trg_guard_garuda_practice_artifacts_mutation
BEFORE UPDATE OR DELETE ON public.garuda_practice_artifacts
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_practice_artifacts_mutation();

-- ----------------------------------------------------------------------------
-- (3bis) THE TABLE'S OWN OWNERSHIP TRANSFER -- what turns (3) from a
-- convention into a boundary (Imperatore decision #16, 2026-09-12, on Sol
-- finding F8 BLOCKER; same shape as 304's bracket, decision #12).
--
-- The module header above says, honestly, that the guard trigger is "the
-- REAL enforcement" because ACL cannot bind an owner. Sol's F8 pushed that
-- sentence one step further and it did not hold: a trigger cannot bind an
-- owner EITHER. While `backend_rag_v2` owned this table and the guard
-- function, the runtime role could disable the trigger, remove it, replace
-- the guard's body with `RETURN NEW`, or empty the table wholesale -- each
-- a single owner-only statement, none of them blocked by anything in this
-- file, all of them leaving no row behind to show it happened.
-- "Append-only" was then a property of whichever code happened to be
-- running, not of the database.
--
-- Moving both the table and the guard function to `visa_ledger_owner` (a
-- NOLOGIN role -- the same owner (2) already requires for the retention
-- trigger) is what makes the difference: those statements are owner-only
-- privileges with no GRANT that confers them, so after this block the
-- runtime role's entire vocabulary on this table is the three grants in
-- (4) -- SELECT, INSERT, and UPDATE of two columns -- and the guard it can
-- no longer reach decides the rest.
--
-- Fail-safe, identically to (2): role absent (this session's local
-- nuzantara_test, CI's `postgres:15`) is a NOTICE and a no-op, so the
-- schema this file builds stays the same everywhere; role present but the
-- transfer refused is an EXCEPTION, because recording the migration as
-- applied would then publish a boundary that is not there. The verdict is
-- read from the MEASURED owner after the ALTER, never from the ALTER's
-- silence.
-- ----------------------------------------------------------------------------

-- Remember the role this session is ACTUALLY on before dropping it. The
-- resume blocks below restore THIS value rather than naming a role
-- literally: `assume_runtime_role` (migration_base.py) is an unconditional
-- no-op in the single-DSN shape (CI, laptops, Fly until the dedicated
-- secret exists), so in that shape the session never was `backend_rag_v2`
-- to begin with -- and a superuser is a member of every role by
-- `pg_has_role`'s definition, so a resume that asks "may I become
-- backend_rag_v2?" answers yes and leaves the session somewhere it never
-- was. Sol's O2 (2026-09-12, new finding 2, MAJOR) traced that to the
-- migration manager's own next statement running under a role nobody
-- chose. Restoring what was measured cannot have that failure mode.
SELECT set_config('garuda313.prior_role', current_role, false);
RESET ROLE;
DO $garuda_313_table_owner_transfer$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    guard_signature constant text := 'public.guard_garuda_practice_artifacts_mutation()';
    tbl constant text := 'public.garuda_practice_artifacts';
    guard_fn oid;
    table_owner text;
    guard_owner text;
    extra_signature text;
    extra_fn oid;
    extra_owner text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ledger_owner) THEN
        RAISE NOTICE 'garuda practice artifacts (313): role % absent -- skipping table/guard ownership transfer, same convention as (2)',
            ledger_owner;
        RETURN;
    END IF;

    -- The table first: owning it is what confers the trigger-management and
    -- whole-table-emptying privileges.
    SELECT pg_get_userbyid(relowner) INTO table_owner
      FROM pg_class WHERE oid = to_regclass(tbl);
    IF table_owner IS DISTINCT FROM ledger_owner THEN
        BEGIN
            EXECUTE format('ALTER TABLE %s OWNER TO %I', tbl, ledger_owner);
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE NOTICE 'garuda practice artifacts (313): table owner change denied (current owner %) -- this session is neither superuser nor a member of %',
                    table_owner, ledger_owner;
        END;
        SELECT pg_get_userbyid(relowner) INTO table_owner
          FROM pg_class WHERE oid = to_regclass(tbl);
    END IF;

    -- Then the guard function: owning it is what confers CREATE OR REPLACE
    -- on its body. A table the runtime cannot alter, guarded by a function
    -- the runtime CAN rewrite, is not a boundary.
    --
    -- ...and, with it, the read helper. `active_garuda_practice_artifact_
    -- policy_available` is a plain STABLE SQL function with no privilege of
    -- its own, so moving it buys no security -- it buys ONE regime. The
    -- shape-D fixture (PG17, all three roles, non-superuser migrator)
    -- caught what having two costs: the rollback assumes the ledger owner
    -- before its removals, and this one object was still owned by the
    -- runtime role, so the rollback aborted with "must be owner of
    -- function ..." BEFORE reaching anything else -- nothing removed, the
    -- migration left fully applied, and the operator told the undo ran.
    -- That is finding F9's own outcome, surviving inside F9's cure, for the
    -- single object its author did not enumerate. Every object this file
    -- creates now has the same owner, so the rollback has one regime to
    -- get right instead of two.
    FOR extra_signature IN
        SELECT unnest(ARRAY[
            'public.active_garuda_practice_artifact_policy_available(TEXT, TIMESTAMPTZ)'
        ])
    LOOP
        extra_fn := to_regprocedure(extra_signature);
        IF extra_fn IS NULL THEN
            RAISE EXCEPTION 'garuda practice artifacts (313): % is not present -- refusing to continue',
                extra_signature;
        END IF;
        SELECT pg_get_userbyid(proowner) INTO extra_owner FROM pg_proc WHERE oid = extra_fn;
        IF extra_owner IS DISTINCT FROM ledger_owner THEN
            BEGIN
                EXECUTE format('ALTER FUNCTION %s OWNER TO %I', extra_signature, ledger_owner);
            EXCEPTION
                WHEN insufficient_privilege THEN
                    RAISE NOTICE 'garuda practice artifacts (313): owner change denied for % (current owner %)',
                        extra_signature, extra_owner;
            END;
            SELECT pg_get_userbyid(proowner) INTO extra_owner FROM pg_proc WHERE oid = extra_fn;
        END IF;
        IF extra_owner IS DISTINCT FROM ledger_owner THEN
            RAISE EXCEPTION
                'garuda practice artifacts (313): % is owned by %, expected % -- the rollback assumes the ledger owner before removing it and would abort with "must be owner of", leaving this migration applied while reporting an undo. Refusing to record it as applied.',
                extra_signature, extra_owner, ledger_owner;
        END IF;
    END LOOP;

    guard_fn := to_regprocedure(guard_signature);
    IF guard_fn IS NULL THEN
        RAISE EXCEPTION 'garuda practice artifacts (313): % is not present after (3) created it -- refusing to continue',
            guard_signature;
    END IF;
    SELECT pg_get_userbyid(proowner) INTO guard_owner FROM pg_proc WHERE oid = guard_fn;
    IF guard_owner IS DISTINCT FROM ledger_owner THEN
        BEGIN
            EXECUTE format('ALTER FUNCTION %s OWNER TO %I', guard_signature, ledger_owner);
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE NOTICE 'garuda practice artifacts (313): guard function owner change denied (current owner %) -- this session is neither superuser nor a member of %',
                    guard_owner, ledger_owner;
        END;
        SELECT pg_get_userbyid(proowner) INTO guard_owner FROM pg_proc WHERE oid = guard_fn;
    END IF;

    IF table_owner IS DISTINCT FROM ledger_owner OR guard_owner IS DISTINCT FROM ledger_owner THEN
        RAISE EXCEPTION
            'garuda practice artifacts (313): table is owned by % and the guard function by %, expected % for both -- the runtime role could still disable the trigger, rewrite the guard body or empty the table, so the append-only boundary this migration publishes would not exist. Refusing to record it as applied: run the two owner changes on a superuser connection, then re-apply.',
            table_owner, guard_owner, ledger_owner;
    END IF;
END;
$garuda_313_table_owner_transfer$;

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

DO $garuda_313_runtime_grants$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'backend_rag_v2') THEN
        -- PL/pgSQL has no direct GRANT statement -- EXECUTE, same as
        -- 244_compliance_alerts_runtime_grants.sql's own grant block.
        EXECUTE 'GRANT SELECT, INSERT ON TABLE public.garuda_practice_artifacts TO backend_rag_v2';
        EXECUTE 'GRANT UPDATE (superseded_at, superseded_by) ON TABLE public.garuda_practice_artifacts TO backend_rag_v2';
    END IF;
END;
$garuda_313_runtime_grants$;

-- (3bis) left the session on its own login role so the grants above could
-- be issued by the table's new owner. Hand it back to the runtime role,
-- same guarded shape (and the same measured reasons) as (2)'s resume
-- block: a bare `SET ROLE` aborts on every environment that does not
-- provision `backend_rag_v2`, and the role-existence and
-- can-actually-assume checks stay in NESTED ifs rather than one
-- `AND`-combined expression (Codex #8's refutation: operand evaluation
-- order is not guaranteed).
DO $garuda_313_resume_runtime_role_after_grants$
DECLARE
    prior_role text := current_setting('garuda313.prior_role', true);
    can_restore boolean;
BEGIN
    -- No-op whenever the session is already where it started (the common
    -- case: nothing had assumed another role in the first place).
    IF prior_role IS NOT NULL AND prior_role <> '' AND prior_role IS DISTINCT FROM current_role THEN
        -- The SAME fail-safe bracket 304 uses, and for the same reason,
        -- even though the session demonstrably WAS on this role a moment
        -- ago: nested IFs rather than one AND-combined expression (operand
        -- evaluation order is not guaranteed -- Codex #8), `to_regrole`
        -- rather than a `pg_roles` SELECT, and the privilege probe split
        -- by server version because PG16 added the `SET` privilege type
        -- while PG15 and earlier only understand `MEMBER`. Interpolated
        -- with `format('%I')`, never concatenated (Imperatore decision
        -- #20, 2026-09-12).
        IF to_regrole(prior_role) IS NOT NULL THEN
            IF current_setting('server_version_num')::int >= 160000 THEN
                can_restore := pg_has_role(session_user, prior_role, 'SET');
            ELSE
                can_restore := pg_has_role(session_user, prior_role, 'MEMBER');
            END IF;
            IF can_restore THEN
                EXECUTE format('SET ROLE %I', prior_role);
            ELSE
                RAISE NOTICE 'garuda practice artifacts (313): session_user % may no longer assume %, leaving the session on its login role',
                    session_user, prior_role;
            END IF;
        END IF;
    END IF;
END;
$garuda_313_resume_runtime_role_after_grants$;

-- === ROLLBACK ===

-- THE ROLLBACK'S OWN PRIVILEGE BRACKET (Sol finding F9 MAJOR, cured under
-- Imperatore decision #16 -- "bracket anche sul rollback").
--
-- The forward half moves three objects to `visa_ledger_owner`: the
-- retention trigger function (2), and since (3bis) the table and the guard
-- function too. The rollback half removes exactly those objects -- and
-- `migration_base.py` runs it on a session that has assumed
-- `backend_rag_v2`, which after the forward half owns NONE of them. Every
-- removal statement below would raise `must be owner of ...`, aborting the
-- rollback transaction: the forward migration stays fully applied while
-- the operator is told the rollback ran. An undo that silently does
-- nothing is worse than no undo, because it is trusted.
--
-- So: hand the session back to its login role, then assume the ledger
-- owner if this session may. Guarded exactly like (2) and (4)'s resume
-- blocks -- absent role or unassumable role is a no-op, which is right on
-- the environments that never had the roles in the first place and where
-- the table is therefore still owned by whoever created it. The symmetric
-- resume at the very end of this file puts the runtime role back.
-- Remember the role this session is ACTUALLY on before dropping it. The
-- resume blocks below restore THIS value rather than naming a role
-- literally: `assume_runtime_role` (migration_base.py) is an unconditional
-- no-op in the single-DSN shape (CI, laptops, Fly until the dedicated
-- secret exists), so in that shape the session never was `backend_rag_v2`
-- to begin with -- and a superuser is a member of every role by
-- `pg_has_role`'s definition, so a resume that asks "may I become
-- backend_rag_v2?" answers yes and leaves the session somewhere it never
-- was. Sol's O2 (2026-09-12, new finding 2, MAJOR) traced that to the
-- migration manager's own next statement running under a role nobody
-- chose. Restoring what was measured cannot have that failure mode.
SELECT set_config('garuda313.prior_role', current_role, false);
RESET ROLE;
DO $garuda_313_rollback_assume_owner$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    can_assume boolean;
BEGIN
    IF to_regrole(ledger_owner) IS NOT NULL THEN
        IF current_setting('server_version_num')::int >= 160000 THEN
            can_assume := pg_has_role(session_user, ledger_owner, 'SET');
        ELSE
            can_assume := pg_has_role(session_user, ledger_owner, 'MEMBER');
        END IF;
        IF can_assume THEN
            EXECUTE format('SET ROLE %I', ledger_owner);
        ELSE
            RAISE NOTICE 'garuda practice artifacts (313) rollback: session_user % cannot assume % -- the removals below will only succeed if this session is superuser',
                session_user, ledger_owner;
        END IF;
    END IF;
END;
$garuda_313_rollback_assume_owner$;

DROP TRIGGER IF EXISTS trg_guard_garuda_practice_artifacts_mutation ON public.garuda_practice_artifacts;
DROP FUNCTION IF EXISTS public.guard_garuda_practice_artifacts_mutation();
DROP TRIGGER IF EXISTS garuda_practice_artifacts_retention_binding ON public.garuda_practice_artifacts;
-- bind_garuda_practice_artifact_retention_policy() is owned by
-- visa_ledger_owner after (2)'s transfer, so the next statement requires a
-- session that owns it or is superuser. 304's rollback accepts that caveat
-- silently; this one does not -- the bracket at the top of this section is
-- what makes the requirement true instead of hoped for.
DROP FUNCTION IF EXISTS public.bind_garuda_practice_artifact_retention_policy();
DROP FUNCTION IF EXISTS public.active_garuda_practice_artifact_policy_available(TEXT, TIMESTAMPTZ);
DROP TABLE IF EXISTS public.garuda_practice_artifacts;

-- (0)'s widened policy_scope CHECK is NOT narrowed back here, and this is
-- a deliberate change from the version of this file written before 304
-- merged.
--
-- While 304 was unmerged, `GARUDA_DOCUMENT` existed on `main` only because
-- block (0) put it there, so this rollback owned it and narrowed it back
-- under an append-only guard (no row may already use the value). 304 is on
-- `main` and live in production since 2026-09-12 05:20Z, applied as
-- `backend_rag_v2 (session_user=backend_rag_migrator)`. The scope is now
-- 304's, and (0) is the idempotent no-op its own comment always promised
-- it would become -- measured, not assumed: 304's widened list on
-- `origin/main` and (0)'s are the same five values.
--
-- A rollback that narrows anyway is a live defect the moment the guard
-- does not fire, which is any database where 304 has been APPLIED but no
-- `GARUDA_DOCUMENT` policy row has been inserted yet: 313's undo would
-- then remove a value 304's schema depends on, and 304 is not even being
-- rolled back. Undoing this migration must not reach outside it. Narrowing
-- the scope belongs to 304's own rollback, which carries the identical
-- append-only guard for it.
DO $garuda_313_leave_policy_scope_widened$
BEGIN
    RAISE NOTICE 'garuda 313 rollback: policy_scope stays WIDENED -- GARUDA_DOCUMENT belongs to migration 304 (live since 2026-09-12), not to this migration; narrowing it here would break 304 without rolling it back.';
END;
$garuda_313_leave_policy_scope_widened$;

-- Symmetric close of the bracket opened at the top of this section: leave
-- the session on the role `migration_base.py` handed us, never on
-- visa_ledger_owner. A rollback that returns with a different current_role
-- than it was given would hand the next statement in the same session a
-- privilege set nobody chose.
-- The save/restore pair for THIS half was taken at the top of the rollback
-- section, before the ledger owner was assumed; saving again here would
-- record `visa_ledger_owner` as the role to return to and hand it straight
-- back. Only the reset belongs here.
RESET ROLE;
DO $garuda_313_rollback_resume_runtime_role$
DECLARE
    prior_role text := current_setting('garuda313.prior_role', true);
    can_restore boolean;
BEGIN
    -- No-op whenever the session is already where it started (the common
    -- case: nothing had assumed another role in the first place).
    IF prior_role IS NOT NULL AND prior_role <> '' AND prior_role IS DISTINCT FROM current_role THEN
        -- The SAME fail-safe bracket 304 uses, and for the same reason,
        -- even though the session demonstrably WAS on this role a moment
        -- ago: nested IFs rather than one AND-combined expression (operand
        -- evaluation order is not guaranteed -- Codex #8), `to_regrole`
        -- rather than a `pg_roles` SELECT, and the privilege probe split
        -- by server version because PG16 added the `SET` privilege type
        -- while PG15 and earlier only understand `MEMBER`. Interpolated
        -- with `format('%I')`, never concatenated (Imperatore decision
        -- #20, 2026-09-12).
        IF to_regrole(prior_role) IS NOT NULL THEN
            IF current_setting('server_version_num')::int >= 160000 THEN
                can_restore := pg_has_role(session_user, prior_role, 'SET');
            ELSE
                can_restore := pg_has_role(session_user, prior_role, 'MEMBER');
            END IF;
            IF can_restore THEN
                EXECUTE format('SET ROLE %I', prior_role);
            ELSE
                RAISE NOTICE 'garuda practice artifacts (313): session_user % may no longer assume %, leaving the session on its login role',
                    session_user, prior_role;
            END IF;
        END IF;
    END IF;
END;
$garuda_313_rollback_resume_runtime_role$;
