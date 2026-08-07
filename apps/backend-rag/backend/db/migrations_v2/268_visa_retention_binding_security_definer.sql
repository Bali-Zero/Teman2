-- Migration 268: retention-binding triggers need SECURITY DEFINER under the
-- least-privilege runtime model.
--
-- ============================================================================
-- WHY THIS IS A NEW MIGRATION, NOT AN EDIT TO 264
-- ============================================================================
--   Migration 264 (`264_visa_decision_retention_policy.sql`) is
--   already-applied history against production -- `migration_base.py` /
--   `migration_manager.py` never re-run an applied migration's SQL body, so
--   its on-disk text is an immutable record of what already executed (same
--   convention 253's own header documents for 251). This migration is the
--   roll-forward correction, targeting the LIVE post-264, post-D1-repair
--   schema state -- 264's on-disk file stays SECURITY INVOKER; the
--   prod-vs-repo drift this migration closes is deliberate and recorded
--   here, not silently edited away.
--
-- ============================================================================
-- THE DEFECT (2026-08-07 prod incident)
-- ============================================================================
--   The "D1" least-privilege repair moved ownership of the Visa Oracle
--   ledger tables (and several already-`SECURITY DEFINER` functions) to
--   `visa_ledger_owner`, leaving the runtime role (`backend_rag_v2`)
--   SELECT-only on `visa_decision_retention_policies` / `visa_decisions` /
--   `visa_decision_payloads`. Three migration-264 trigger functions were
--   never converted to `SECURITY DEFINER` because, at the time they were
--   written, the runtime role WAS the table owner and the gap was invisible:
--
--     * `bind_visa_evaluate_idempotency_retention_policy` (BEFORE INSERT on
--       `visa_evaluate_idempotency`)
--     * `bind_visa_decision_retention_policy` (BEFORE INSERT on
--       `visa_decisions`)
--     * `bind_visa_decision_payload_retention` (BEFORE INSERT on
--       `visa_decision_payloads`)
--
--   Each runs a `SELECT ... FOR SHARE` against a `visa_ledger_owner`-owned
--   table to resolve the active Zero-approved retention policy. Postgres'
--   `FOR SHARE` row-lock requires the UPDATE privilege, not merely SELECT --
--   a fact about row-locking, not about this schema. Once the runtime role
--   was reduced to SELECT-only (correctly, per the least-privilege repair),
--   every one of these three triggers -- running `SECURITY INVOKER`, i.e.
--   with the CALLING role's privileges -- started failing every INSERT into
--   the three tables it guards with `insufficient_privilege`, surfacing to
--   callers as `TEMPORARILY_UNAVAILABLE` / `IDEMPOTENCY_UNAVAILABLE`. See
--   `lesson_least_privilege_repair_breaks_invoker_triggers_that_lock_rows_
--   2026_08_07.md` for the full incident writeup, including why no test
--   caught it (CI/fullstack-smoke connect as a superuser, which is always
--   both owner and invoker, so the INVOKER-vs-DEFINER distinction never
--   mattered there) and why `operational_preflight.py`'s 622-check was also
--   blind (these three functions were never added to `SENSITIVE_FUNCTIONS`
--   -- fixed in this same PR, a separate commit).
--
--   The cure applied directly to production on 2026-08-07 (single manual
--   transaction, superuser session, verified beforehand that every body
--   already pins `SET search_path = pg_catalog, pg_temp` and references
--   only schema-qualified `public.*` relations -- both prerequisites for a
--   safe `SECURITY DEFINER` flip) was exactly the three `ALTER FUNCTION`
--   pairs below: `SECURITY DEFINER` + `OWNER TO visa_ledger_owner`. This
--   migration codifies that same cure so a fresh clone/CI/staging rebuild
--   converges on the same state without a human re-typing it, and so
--   `_schema_versions` eventually records that migration 268 is the
--   intended, on-the-record state of production (it was not applied via the
--   ordinary migration runner in prod on 2026-08-07 -- this migration's
--   later, routine `apply-all` run against prod is expected to be a pure
--   idempotent confirmation of already-live state, not a live behavior
--   change).
--
-- ============================================================================
-- WHY `OWNER TO` IS ROLE-GUARDED *AND* IDEMPOTENT *AND* BEST-EFFORT
-- ============================================================================
--   `ALTER FUNCTION ... OWNER TO <role>` requires the executing session to
--   be either superuser or (the function's CURRENT owner AND a member of
--   the TARGET role) -- see 253's own P0-2 note ("Function OWNERSHIP ... is
--   a superuser-only operation this non-superuser migration role cannot
--   perform -- it remains the operator provisioning script's job"). That
--   constraint does not go away just because `visa_ledger_owner` now exists:
--
--     * On a superuser connection (CI's `test` role, or a local dev
--       superuser) the ALTER always succeeds regardless of ordering --
--       superuser bypasses every membership check. This is also why a test
--       exercising the actual bug (see the accompanying test file) must
--       explicitly restrict a SEPARATE low-privilege role rather than rely
--       on the connecting role's own posture.
--     * On the ordinary, non-superuser migration role (`backend_rag_v2`),
--       once ownership has ALREADY moved to `visa_ledger_owner` (prod, after
--       the 2026-08-07 manual cure), `backend_rag_v2` is no longer even the
--       CURRENT owner of these three functions -- so re-running this
--       migration's `OWNER TO` clause would unconditionally fail with
--       `insufficient_privilege` if attempted, regardless of role-guard.
--       The DO block below therefore checks the FUNCTION's actual current
--       owner first and skips the `ALTER` entirely when it is already
--       `visa_ledger_owner` (idempotent no-op, no privilege check ever
--       attempted -- this is the prod re-run path).
--     * When the current owner is NOT YET `visa_ledger_owner` (a fresh
--       environment that has not had the D1-style repair's ownership
--       transfer applied out-of-band), the block attempts the transfer and,
--       if the executing role lacks the required membership, degrades to a
--       `RAISE NOTICE` -- deliberately NOT a hard failure, because per the
--       253 precedent this specific ALTER is expected to be beyond a
--       non-superuser migration role's reach in that state; arming it is
--       the operator provisioning script's job, same as always. This differs
--       from this migration's own `REVOKE .. FROM PUBLIC` / `SECURITY
--       DEFINER` statements below, which are unconditional and always
--       within the current owner's own privilege regardless of
--       `visa_ledger_owner`'s existence.
--
--   `SECURITY DEFINER` alone (independent of who ends up owning the
--   function) is what fixes the runtime behavior: the function executes
--   with ITS OWNER's privileges rather than the caller's. In every
--   environment where the current owner already has (or, being a
--   superuser, trivially has) UPDATE on the locked table -- which is true
--   both in prod post-ownership-transfer AND in every existing test/CI
--   superuser connection -- the `FOR SHARE` lock resolves regardless of
--   whether the `OWNER TO` clause itself was able to fire. The three
--   `ALTER ... SECURITY DEFINER` statements are therefore issued
--   unconditionally, before the role-guarded ownership attempt, while the
--   connecting role is still guaranteed to be the current owner.
--
-- ============================================================================
-- EXECUTE FROM PUBLIC
-- ============================================================================
--   264 revoked `EXECUTE ... FROM PUBLIC` for every OTHER privileged
--   function it introduced but never did so for these three trigger
--   functions -- Postgres grants EXECUTE to PUBLIC by default at CREATE
--   FUNCTION time, so today every role can directly `SELECT
--   public.bind_visa_evaluate_idempotency_retention_policy()`. A bare
--   direct call fails at runtime (`RETURNS trigger` functions may only be
--   invoked as triggers), so this was never an information-disclosure
--   defect on its own -- but making these three `SECURITY DEFINER` is
--   exactly the moment an unconditional PUBLIC EXECUTE grant on a
--   DEFINER-privileged function becomes worth closing as defense-in-depth,
--   same rationale 267 gives for the analogous cleanup on
--   `visa_replace_activation_set`. Costs nothing, deferred to no role guard.
--
-- NOTE: `-- === ROLLBACK ===` marker is mandatory (migration_base.py:29) for
--   migrations > 111.

-- ----------------------------------------------------------------------------
-- Step 1: SECURITY DEFINER (unconditional -- the connecting role is still the
-- current owner of all three at this point in every environment).
-- ----------------------------------------------------------------------------

ALTER FUNCTION public.bind_visa_evaluate_idempotency_retention_policy() SECURITY DEFINER;
ALTER FUNCTION public.bind_visa_decision_retention_policy() SECURITY DEFINER;
ALTER FUNCTION public.bind_visa_decision_payload_retention() SECURITY DEFINER;

-- ----------------------------------------------------------------------------
-- Step 2: close the unconditional default PUBLIC EXECUTE exposure (unconditional,
-- same rationale as 267 -- costs nothing, no role dependency).
-- ----------------------------------------------------------------------------

REVOKE ALL ON FUNCTION public.bind_visa_evaluate_idempotency_retention_policy() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.bind_visa_decision_retention_policy() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.bind_visa_decision_payload_retention() FROM PUBLIC;

-- ----------------------------------------------------------------------------
-- Step 3: best-effort, idempotent ownership transfer to visa_ledger_owner.
-- Role-guarded (251/253 convention: role absent -> RAISE NOTICE, no-op) AND
-- current-owner-guarded (idempotent no-op if already transferred) AND
-- privilege-guarded (insufficient_privilege degrades to RAISE NOTICE, not a
-- hard failure -- see the header note on why this differs from 253's
-- fail-loud GRANT precedent).
-- ----------------------------------------------------------------------------

DO $visa_268_owner_transfer$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    target_function constant text[] := ARRAY[
        'public.bind_visa_evaluate_idempotency_retention_policy()',
        'public.bind_visa_decision_retention_policy()',
        'public.bind_visa_decision_payload_retention()'
    ];
    signature text;
    current_owner text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ledger_owner) THEN
        RAISE NOTICE 'visa retention-binding SECURITY DEFINER (268): role % absent -- skipping ownership transfer, same convention as 251/253',
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
                    RAISE NOTICE 'visa retention-binding SECURITY DEFINER (268): ownership transfer of % to % requires operator action (current owner %, insufficient privilege) -- deferring to operator provisioning, same as 251/253''s OWNER-TO note',
                        signature, ledger_owner, current_owner;
            END;
        END IF;
    END LOOP;
END;
$visa_268_owner_transfer$;

-- === ROLLBACK ===

-- Reverting SECURITY DEFINER -> SECURITY INVOKER restores 264's original
-- functional behavior regardless of who ends up owning the function -- the
-- caller's own privileges govern again, exactly as before this migration.
-- This ALSO requires being the current owner (or superuser): if this
-- migration's own forward ownership transfer succeeded against a
-- non-superuser connection (never expected via the ordinary migration
-- runner per the header above, but possible under a superuser test
-- connection that also transferred ownership), a rollback run by a
-- DIFFERENT, non-superuser role would hit the same one-way privilege wall
-- 253 already documents for ownership-transferred objects -- reverting
-- ownership itself back off visa_ledger_owner is intentionally left to
-- operator action, same as the forward direction.

ALTER FUNCTION public.bind_visa_evaluate_idempotency_retention_policy() SECURITY INVOKER;
ALTER FUNCTION public.bind_visa_decision_retention_policy() SECURITY INVOKER;
ALTER FUNCTION public.bind_visa_decision_payload_retention() SECURITY INVOKER;

GRANT EXECUTE ON FUNCTION public.bind_visa_evaluate_idempotency_retention_policy() TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.bind_visa_decision_retention_policy() TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.bind_visa_decision_payload_retention() TO PUBLIC;
