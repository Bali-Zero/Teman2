-- 299_garuda_magic_link_binding_owner.sql
--
-- WHAT IS BROKEN IN PRODUCTION (measured 2026-08-30)
-- =============================================================================
--   `POST /api/visa/voa/auth/magic-links` answers 500 INTERNAL_ERROR to every
--   call, and has since migration 285 shipped: `garuda_magic_link_tokens` holds
--   zero rows, so no magic link has ever been minted. The whole authenticated
--   half of the GARUDA VOA product is unreachable behind it.
--
--   The exception is `asyncpg.exceptions.InsufficientPrivilegeError`, raised by
--   the BEFORE INSERT trigger `bind_garuda_magic_link_token_retention_policy`
--   at its very first statement:
--
--       SELECT id, retention_interval, retention_anchor
--         INTO STRICT policy
--         FROM public.visa_decision_retention_policies
--        WHERE ... FOR SHARE;
--
--   `visa_decision_retention_policies` is owned by `visa_ledger_owner`, and the
--   application role `backend_rag_v2` holds only SELECT on it. A row-locking
--   clause needs more than SELECT, so `FOR SHARE` is denied. Measured directly
--   against production, guilt and innocence:
--
--       SELECT id FROM visa_decision_retention_policies ... FOR SHARE;
--         -> ERROR: permission denied for table visa_decision_retention_policies
--       the same query without FOR SHARE
--         -> 56083f63-8c68-458c-ada2-7dc842da9ef2
--
--   The trigger IS already `SECURITY DEFINER` -- but it is owned by
--   `backend_rag_v2`, so defining it that way bought nothing: it runs with the
--   privileges of a role that cannot take the lock either. Its working twin
--   `bind_garuda_voa_check_retention_policy` is `SECURITY DEFINER` owned by
--   `visa_ledger_owner`, which is exactly why the eligibility-check path is
--   healthy while this one is not.
--
-- THIS IS A RECURRENCE, NOT A NEW DEFECT
-- =============================================================================
--   Migration 268 cured this same shape on 2026-08-07 for the visa-engine
--   triggers (see its header, and the integration test
--   `backend/tests/scripts/visa_engine/test_retention_binding_security_definer.py`,
--   which reproduces the incident against a throwaway cluster). Migration 281
--   then carried the cure forward for the GARUDA_CHECK family with an explicit,
--   role-guarded ownership transfer.
--
--   Migration 285 created a new SECURITY DEFINER trigger that locks the same
--   table and simply omitted that transfer. Nothing failed at migration time --
--   the defect is only observable on the first real INSERT, which is why it
--   surfaced as a silent 500 weeks later. The accompanying lint test added with
--   this migration is the part that stops a migration 30x from doing it a third
--   time; this file alone only fixes the one function.
--
-- WHY THE TRANSFER IS ROLE-GUARDED, IDEMPOTENT AND BEST-EFFORT
-- =============================================================================
--   `ALTER FUNCTION ... OWNER TO <role>` requires the session to be superuser,
--   or to be the function's current owner AND a member of the target role.
--   Measured 2026-08-30: nobody is a member of `visa_ledger_owner`, and the
--   migration runner connects as `backend_rag_v2`. So against production this
--   block is EXPECTED to raise a NOTICE and defer, exactly as 251/253/268/281
--   do; the ALTER lands on a superuser connection (CI, a fresh clone, or the
--   operator's provisioning step). This mirrors 268's history verbatim: the
--   cure was applied to production in one manual superuser transaction and the
--   migration exists so every other environment converges without a human
--   retyping it.

DO $garuda_299_owner_transfer$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    target_function constant text[] := ARRAY[
        'public.bind_garuda_magic_link_token_retention_policy()'
    ];
    signature text;
    current_owner text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ledger_owner) THEN
        RAISE NOTICE 'garuda magic-link (299): role % absent -- skipping ownership transfer, same convention as 251/253/268/281',
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
                    RAISE NOTICE 'garuda magic-link (299): ownership transfer of % to % requires operator action (current owner %, insufficient privilege) -- deferring to operator provisioning, same as 251/253/268/281',
                        signature, ledger_owner, current_owner;
            END;
        END IF;
    END LOOP;
END;
$garuda_299_owner_transfer$;

-- === ROLLBACK ===

DO $garuda_299_owner_rollback$
DECLARE
    app_owner constant text := 'backend_rag_v2';
    signature constant text := 'public.bind_garuda_magic_link_token_retention_policy()';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = app_owner) THEN
        RAISE NOTICE 'garuda magic-link (299 rollback): role % absent -- nothing to restore', app_owner;
        RETURN;
    END IF;
    BEGIN
        EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, app_owner);
    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE 'garuda magic-link (299 rollback): restoring ownership of % to % requires operator action',
                signature, app_owner;
    END;
END;
$garuda_299_owner_rollback$;
