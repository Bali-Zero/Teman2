-- ============================================================================
-- 282_visa_oracle_consultant_requests_retention_policy.sql
--
-- Integer bound at write time (scar W40 -- a reservation in a doc nobody
-- re-checks decays). Measured fresh this turn:
--   git ls-tree -r --name-only origin/main -- apps/backend-rag/backend/db/migrations_v2/
--     -> highest present is 280 (280_research_os_objects_truncate_guard.sql)
--   git ls-tree -r --name-only HEAD -- apps/backend-rag/backend/db/migrations_v2/
--     -> highest present is 281 (281_visa_oracle_consultant_requests.sql, this
--        branch's own merge -- not yet on origin/main)
--   gh pr list --state open --limit 500 --json number,files | grep migrations_v2
--     -> exactly one hit: #4854 adds 281_garuda_voa_retention.sql, on
--        base branch feature/garuda-voa (a DIFFERENT feature branch, not
--        this one and not main). Its 281 collides with THIS branch's own
--        281, not with 282 -- flagged in the integration report, not fixed
--        here; resolving it is that PR's or the integration branch's job.
-- -> next available integer on every source checked: 282.
--
-- Closes a retention gap in migration 281: visa_oracle_consultant_requests
-- is a durable, person-linked store (evaluation_id, client_id) written at
-- the moment a visitor invokes the "Talk to a consultant" control, and 281
-- shipped it with no expires_at/TTL/purge path. backend/services/visa_engine/
-- retention.py governs two sibling stores (visa_decisions via migration 264,
-- visa_evaluate_idempotency via the same migration) through a Zero-approved,
-- policy-driven mechanism; this migration extends that SAME mechanism to a
-- third store rather than inventing a second one, per that module's own
-- rule: "No retention duration lives in application code. Zero-approved
-- policy rows are the only source of a duration/anchor."
--
-- This migration deliberately seeds NO duration and NO policy row, exactly
-- as 264 did for its two tables. Zero decides HOW LONG; this migration only
-- builds HOW. Until a policy row exists, purge_visa_oracle_consultant_requests
-- finds zero governed rows (the join below has nothing to match) and returns
-- 0 with no evidence batch written -- a documented no-op, mirroring the
-- abstain behaviour retention.py's active_policy_available() encodes for the
-- decisions/idempotency pair.
--
-- ONE DELIBERATE DIVERGENCE from 264's shape, spelled out because the
-- integration report calls it out as the load-bearing design decision here:
-- 264 binds retention_policy_id/retention_until onto EACH ROW at INSERT time
-- (a BEFORE INSERT trigger + a NOT VALID NOT NULL constraint), which fails
-- closed -- every new visa_decisions/visa_evaluate_idempotency insert starts
-- raising until Zero supplies a policy. visa_oracle_consultant_requests is
-- the durable side of a LIVE, mandate-critical, contract-frozen customer
-- control (C3 ConsultantAssignmentEvent, docs/plans/2026-08-24-visa-oracle-
-- live/contracts/FROZEN.md -- "a visible 'Talk to a consultant' control on
-- EVERY screen ... invokable at ANY moment"). Reproducing 264's fail-closed
-- bind-on-insert here would silently start rejecting every consultant
-- request the instant this migration deploys, until Zero manually inserts a
-- policy row -- an operational outage on a live button that nothing in this
-- migration's mandate asked for and that this migration does not own the
-- authority to schedule. Instead, retention_policy_id/retention_until are
-- resolved DYNAMICALLY at purge/evidence read time by joining each row's
-- anchor timestamp (requested_at or created_at, per the active policy's own
-- retention_anchor) against the policy's effective_period. A row whose
-- anchor timestamp falls outside every policy's effective_period (including
-- every row written before any policy ever existed) is simply never a purge
-- candidate -- no fabricated retroactive deadline, same principle 264's own
-- header states for visa_decisions history. visa_oracle_consultant_requests
-- itself gets no new column and no new constraint, and the C3 write path
-- (backend/services/visa_engine/consultant_assignment_service.py) is
-- untouched. ONE thing on that table DOES change, discovered empirically
-- (the "expired row actually deleted" test failed against the very first
-- draft of this migration, for the right reason): 281's own
-- guard_visa_oracle_consultant_requests_append_only() rejects EVERY
-- UPDATE/DELETE unconditionally, with no bounded-capability carve-out --
-- unlike every sibling guard 264 ships (bind_visa_decision_retention_policy
--'s, visa_decision_payloads', visa_evaluate_idempotency's), which all
-- permit exactly one path through: current_user is the table owner (true
-- only inside a SECURITY DEFINER function owned by that owner) AND a
-- purge-scoped session GUC is set to a validly-formatted requested_by. 281
-- shipped before any purge function existed to need that carve-out, so its
-- omission was invisible until this migration tried to delete a row.
-- CREATE OR REPLACE below widens that ONE function to the same shape as
-- its siblings -- append-only for everyone except the bounded purge path
-- below, which sets 'visa.consultant_request_retention_requested_by' via
-- set_config before its DELETE. UPDATE remains unconditionally rejected;
-- this table has no legal-hold or completion-transition use for it.
--
-- No environment column exists on visa_oracle_consultant_requests (unlike
-- visa_decisions/visa_evaluate_idempotency, which both carry one), so this
-- policy table is NOT environment-scoped -- one Zero-approved timeline
-- governs every row regardless of TEST/STAGING/PRODUCTION. Adding an
-- environment column to a table whose migration 281 explicitly freezes at
-- "exactly the seven wire fields" would be its own deliberate, separately-
-- reviewed change; this migration does not make it.
--
-- Its own policy table, NOT a reuse of visa_decision_retention_policies:
-- that table is signed-off machinery for a different store with a
-- different sensitivity (visa eligibility decisions vs. a "talk to a human"
-- request log), and widening it to cover a second store is a refactor
-- nobody asked for.
-- ============================================================================

SET lock_timeout = '5s';
SET statement_timeout = '60s';

CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Widen 281's blanket append-only guard to admit exactly one path: the
-- bounded retention purge below, running SECURITY DEFINER as the table
-- owner with a validly-formatted requested_by GUC set. Same ownership +
-- GUC shape as every sibling guard in migration 264. Trigger
-- trg_guard_visa_oracle_consultant_requests_append_only (created by 281)
-- keeps pointing at this same function name/OID -- CREATE OR REPLACE is
-- enough, no DROP/CREATE TRIGGER needed.
CREATE OR REPLACE FUNCTION public.guard_visa_oracle_consultant_requests_append_only()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
    requested_by TEXT;
    table_owner NAME;
BEGIN
    IF TG_OP = 'DELETE' THEN
        requested_by := current_setting(
            'visa.consultant_request_retention_requested_by', TRUE
        );
        SELECT pg_get_userbyid(relation.relowner)
          INTO table_owner
          FROM pg_class AS relation
          JOIN pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname = 'visa_oracle_consultant_requests';
        IF current_user <> table_owner THEN
            RAISE EXCEPTION
                'visa_oracle_consultant_requests delete must use the bounded retention purge';
        END IF;
        IF requested_by IS NULL
           OR requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
            RAISE EXCEPTION
                'visa_oracle_consultant_requests delete must use the bounded retention purge';
        END IF;
        RETURN OLD;
    END IF;
    RAISE EXCEPTION
        'visa_oracle_consultant_requests is append-only — % not permitted', TG_OP;
END;
$$;

CREATE TABLE public.visa_oracle_consultant_request_retention_policies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_version      TEXT NOT NULL
        CHECK (policy_version ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'),
    retention_interval  INTERVAL NOT NULL
        CHECK (retention_interval > INTERVAL '0 seconds'),
    retention_anchor    TEXT NOT NULL
        CHECK (retention_anchor IN ('REQUESTED_AT', 'CREATED_AT')),
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
    UNIQUE (policy_version),
    EXCLUDE USING gist (effective_period WITH &&)
);

COMMENT ON TABLE public.visa_oracle_consultant_request_retention_policies IS
    'Zero-approved retention authority for visa_oracle_consultant_requests; '
    'no environment scoping (the governed table carries none). Activation '
    'requires a separated policy-writer owner/role, same as migration 264.';

CREATE FUNCTION public.guard_visa_oracle_consultant_request_retention_policy_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'visa_oracle_consultant_request_retention_policies is append-only';
    END IF;
    IF (to_jsonb(OLD) - 'effective_period')
           IS DISTINCT FROM (to_jsonb(NEW) - 'effective_period')
       OR lower(OLD.effective_period) IS DISTINCT FROM lower(NEW.effective_period)
       OR upper(OLD.effective_period) IS NOT NULL
       OR upper(NEW.effective_period) IS NULL
       OR upper(NEW.effective_period) <= lower(NEW.effective_period) THEN
        RAISE EXCEPTION
            'retention policy update may only close one open effective_period';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER visa_oracle_consultant_request_retention_policies_guard
BEFORE UPDATE OR DELETE ON public.visa_oracle_consultant_request_retention_policies
FOR EACH ROW
EXECUTE FUNCTION public.guard_visa_oracle_consultant_request_retention_policy_mutation();

CREATE TRIGGER visa_oracle_consultant_request_retention_policies_no_wipe
BEFORE TRUNCATE ON public.visa_oracle_consultant_request_retention_policies
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TABLE public.visa_oracle_consultant_request_retention_batches (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    retention_policy_id UUID NOT NULL
        REFERENCES public.visa_oracle_consultant_request_retention_policies (id),
    affected_count      INTEGER NOT NULL CHECK (affected_count > 0),
    executor_label      TEXT NOT NULL CHECK (
        executor_label ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$'
    ),
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

COMMENT ON TABLE public.visa_oracle_consultant_request_retention_batches IS
    'Append-only purge evidence; no evaluation_id/client_id/row identifier.';

CREATE TRIGGER visa_oracle_consultant_request_retention_batches_immutable
BEFORE UPDATE OR DELETE ON public.visa_oracle_consultant_request_retention_batches
FOR EACH ROW EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

CREATE TRIGGER visa_oracle_consultant_request_retention_batches_no_wipe
BEFORE TRUNCATE ON public.visa_oracle_consultant_request_retention_batches
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_visa_write_substrate_mutation();

-- Bounded, policy-driven purge. Candidates are resolved dynamically: a row
-- is governed by the policy whose effective_period covers its anchor
-- timestamp (requested_at or created_at per that policy's retention_anchor),
-- and is a delete candidate once anchor + retention_interval has elapsed. A
-- row outside every policy's effective_period is never a candidate -- no
-- policy, no authority to delete, same as an empty result from
-- retention.py's active_policy_available() for the sibling tables.
CREATE FUNCTION public.purge_visa_oracle_consultant_requests(
    p_limit INTEGER,
    p_requested_by TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    deleted_ids UUID[];
    deleted_policy_ids UUID[];
    deleted_count INTEGER;
BEGIN
    IF p_limit IS NULL OR p_limit < 1 OR p_limit > 1000 THEN
        RAISE EXCEPTION 'purge limit must be between 1 and 1000';
    END IF;
    IF p_requested_by IS NULL
       OR p_requested_by !~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$' THEN
        RAISE EXCEPTION 'purge requested_by has invalid format';
    END IF;

    -- Opens the ONE path the widened append-only guard above admits: this
    -- function runs SECURITY DEFINER as the table owner, and this GUC is
    -- the bounded-capability marker that guard checks for.
    PERFORM set_config(
        'visa.consultant_request_retention_requested_by', p_requested_by, TRUE
    );

    WITH candidates AS (
        SELECT r.id AS request_id, p.id AS policy_id
          FROM public.visa_oracle_consultant_requests AS r
          JOIN public.visa_oracle_consultant_request_retention_policies AS p
            ON p.effective_period @> (
                 CASE p.retention_anchor
                     WHEN 'REQUESTED_AT' THEN r.requested_at
                     ELSE r.created_at
                 END
               )
         WHERE (
                 CASE p.retention_anchor
                     WHEN 'REQUESTED_AT' THEN r.requested_at
                     ELSE r.created_at
                 END
               ) + p.retention_interval < clock_timestamp()
         ORDER BY r.created_at, r.id
         LIMIT p_limit
         FOR UPDATE OF r SKIP LOCKED
    ),
    deleted AS (
        DELETE FROM public.visa_oracle_consultant_requests AS r
         USING candidates
         WHERE r.id = candidates.request_id
        RETURNING r.id, candidates.policy_id
    )
    SELECT array_agg(deleted.id), array_agg(deleted.policy_id)
      INTO deleted_ids, deleted_policy_ids
      FROM deleted;

    deleted_count := COALESCE(array_length(deleted_ids, 1), 0);

    IF deleted_count > 0 THEN
        INSERT INTO public.visa_oracle_consultant_request_retention_batches (
            retention_policy_id, affected_count, executor_label
        )
        SELECT policy_id, count(*)::INTEGER, session_user || ':' || p_requested_by
          FROM unnest(deleted_policy_ids) AS policy_id
         GROUP BY policy_id;
    END IF;

    RETURN deleted_count;
END;
$$;

REVOKE ALL ON FUNCTION public.purge_visa_oracle_consultant_requests(INTEGER, TEXT)
    FROM PUBLIC;
COMMENT ON FUNCTION public.purge_visa_oracle_consultant_requests(INTEGER, TEXT) IS
    'Bounded, policy-driven purge for visa_oracle_consultant_requests; '
    'requires an explicit operator grant and scheduler. No-op (returns 0, '
    'writes no evidence) while no Zero-approved policy governs any row.';

-- Applicant/evaluation-identifier-free evidence, same shape as migration
-- 264's visa_idempotency_retention_evidence(): a backlog count and the
-- maximum purge lag, computed against the SAME dynamic policy join the
-- purge function above uses, so the two never disagree about what counts
-- as expired.
CREATE FUNCTION public.visa_oracle_consultant_requests_retention_evidence()
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
    ),
    governed AS (
        SELECT
            (
                CASE p.retention_anchor
                    WHEN 'REQUESTED_AT' THEN r.requested_at
                    ELSE r.created_at
                END
            ) + p.retention_interval AS expires_at
          FROM public.visa_oracle_consultant_requests AS r
          JOIN public.visa_oracle_consultant_request_retention_policies AS p
            ON p.effective_period @> (
                 CASE p.retention_anchor
                     WHEN 'REQUESTED_AT' THEN r.requested_at
                     ELSE r.created_at
                 END
               )
    )
    SELECT
        count(governed.expires_at) FILTER (
            WHERE governed.expires_at <= observation.observed_at
        )::BIGINT AS expired_rows,
        COALESCE(
            max(
                GREATEST(
                    EXTRACT(EPOCH FROM observation.observed_at - governed.expires_at),
                    0
                )
            ) FILTER (WHERE governed.expires_at <= observation.observed_at),
            0
        )::DOUBLE PRECISION AS max_lag_seconds,
        observation.observed_at
    FROM observation
    LEFT JOIN governed ON TRUE
    GROUP BY observation.observed_at;
$$;

REVOKE ALL ON FUNCTION public.visa_oracle_consultant_requests_retention_evidence()
    FROM PUBLIC;
COMMENT ON FUNCTION public.visa_oracle_consultant_requests_retention_evidence() IS
    'PII-free consultant-request purge backlog and max purge lag; '
    'operator grant required.';

-- === ROLLBACK ===
SET lock_timeout = '5s';
SET statement_timeout = '60s';

DROP FUNCTION IF EXISTS public.visa_oracle_consultant_requests_retention_evidence();
DROP FUNCTION IF EXISTS public.purge_visa_oracle_consultant_requests(INTEGER, TEXT);

-- Restores 281's original blanket-reject body verbatim (trigger
-- trg_guard_visa_oracle_consultant_requests_append_only, created by 281,
-- keeps pointing at this same function name/OID).
CREATE OR REPLACE FUNCTION public.guard_visa_oracle_consultant_requests_append_only()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    RAISE EXCEPTION
        'visa_oracle_consultant_requests is append-only — % not permitted',
        TG_OP;
END;
$$;

DROP TRIGGER IF EXISTS visa_oracle_consultant_request_retention_batches_no_wipe
    ON public.visa_oracle_consultant_request_retention_batches;
DROP TRIGGER IF EXISTS visa_oracle_consultant_request_retention_batches_immutable
    ON public.visa_oracle_consultant_request_retention_batches;
DROP TABLE IF EXISTS public.visa_oracle_consultant_request_retention_batches;

DROP TRIGGER IF EXISTS visa_oracle_consultant_request_retention_policies_no_wipe
    ON public.visa_oracle_consultant_request_retention_policies;
DROP TRIGGER IF EXISTS visa_oracle_consultant_request_retention_policies_guard
    ON public.visa_oracle_consultant_request_retention_policies;
DROP TABLE IF EXISTS public.visa_oracle_consultant_request_retention_policies;
DROP FUNCTION IF EXISTS
    public.guard_visa_oracle_consultant_request_retention_policy_mutation();
