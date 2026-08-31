-- 301_garuda_magic_link_binding_owner.sql
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
--   surfaced as a silent 500 weeks later. This file alone only fixes the one
--   function.
--
--   AN EARLIER DRAFT OF THIS PARAGRAPH SAID a lint shipped alongside to stop a
--   migration 30x doing it a third time. IT DOES NOT — see the section below on
--   what is and is not in force. The sentence is corrected here, and not merely
--   further down, because THIS is the section an author of migration 302 reads
--   to learn whether the shape is guarded; a correction 52 lines later is a
--   correction they never reach.
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

-- WHY THIS ONE DOES NOT MERELY NOTICE-AND-DEFER LIKE 281
-- =============================================================================
--   Adversarial review (codex gpt-5.6-sol, xhigh) rejected the first draft of
--   this migration for copying 281's handler verbatim, and was right: 281 was
--   codifying a transfer ALREADY applied to production by hand, so its NOTICE
--   path was a no-op confirmation. Here the transfer has NOT happened yet, so a
--   NOTICE would let the runner record migration 301 as applied while the
--   outage stands -- a permanent false green in `_schema_versions`, and exactly
--   the "esiste != armato" disease this repo keeps paying for.
--
--   So the ALTER is still attempted and its failure still explained, but the
--   block ends by asserting the POSTCONDITION and raising if the world does not
--   match it. On a superuser connection (CI, fresh clone) the ALTER succeeds and
--   the assertion is silent. On production it fails loudly until an operator
--   runs the ALTER, which is the honest state: the cure is not in force.
--
--   EXACTLY HOW FAR THAT GUARANTEE REACHES (kimi-code/k3, adversarial round
--   2026-08-30 -- it read the paragraph above as covering every path, and it
--   does not). The postcondition is asserted on ONE of three paths. The two
--   early RETURNs below exit before it:
--     * role `visa_ledger_owner` absent  -> NOTICE, return
--     * the function not present yet     -> NOTICE, return
--   In both, the runner records 301 as applied and nothing ever re-runs it. So
--   in an environment where the role is provisioned AFTER migrations, or where
--   the function is created later, this file leaves the transfer undone and
--   says so only in a NOTICE nobody reads.
--
--   That deferral is deliberate and INHERITED, not introduced here: it is the
--   251/253/268/281 convention, and raising instead would refuse to bootstrap
--   any clone that has not provisioned the role yet -- a worse failure than
--   the one it prevents. What was wrong was the CLAIM, which promised a
--   guarantee three paths wide for something one path wide. Corrected here
--   rather than softened elsewhere.
--
--   THERE IS NO STANDING NET UNDER THAT HOLE TODAY, and saying so is the
--   point. An earlier draft of this header promised one: a static lint,
--   `test_retention_lock_triggers_are_ledger_owned.py`, shipped alongside this
--   migration. That lint was WITHDRAWN before merge — the Gear-3 gate proved it
--   ships green on the exact class it exists to catch (an `E'...'` escape
--   string or an unclosed dollar tag desynchronises its scanner from Postgres,
--   after which a commented-out `ALTER ... OWNER TO` is read as a real
--   transfer). Its fourth attempt was still unsound in the same direction as
--   its third, so under rule 8 it went back to design rather than to a fifth
--   patch: `docs/specs/2026-08-31-security-definer-ledger-lock-lint.md`.
--
--   What DOES see these two functions now is the live preflight owner check,
--   whose inventory this PR extends. That check asks Postgres rather than
--   parsing SQL text, so none of the lint's holes apply to it — but it runs
--   against a cluster, not in CI on a diff, which is the coverage that is
--   genuinely missing until the spec is built.
--
--   `to_regprocedure` (not a `::regprocedure` cast) so an absent function
--   yields NULL instead of raising -- the same review flagged the cast as a
--   fresh-database ordering hazard.

DO $garuda_301_owner_transfer$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    signature constant text := 'public.bind_garuda_magic_link_token_retention_policy()';
    fn oid;
    current_owner text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ledger_owner) THEN
        RAISE NOTICE 'garuda magic-link (301): role % absent -- skipping ownership transfer, same convention as 251/253/268/281',
            ledger_owner;
        RETURN;
    END IF;

    fn := to_regprocedure(signature);
    IF fn IS NULL THEN
        RAISE NOTICE 'garuda magic-link (301): % not present -- nothing to transfer', signature;
        RETURN;
    END IF;

    SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;

    IF current_owner IS DISTINCT FROM ledger_owner THEN
        BEGIN
            EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE NOTICE 'garuda magic-link (301): ALTER denied (current owner %) -- this session is neither superuser nor a member of %',
                    current_owner, ledger_owner;
        END;
        SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;
    END IF;

    IF current_owner IS DISTINCT FROM ledger_owner THEN
        RAISE EXCEPTION
            'garuda magic-link (301): % is still owned by % -- the SECURITY DEFINER trigger cannot take its FOR SHARE lock on visa_decision_retention_policies, so magic-link issuance still answers 500. Refusing to record this migration as applied while that is true: run the ALTER on a superuser connection, then re-apply.',
            signature, current_owner;
    END IF;
END;
$garuda_301_owner_transfer$;

-- === ROLLBACK ===

-- Deliberately a no-op that says so, not a symmetric undo.
--
-- The "undo" of this migration is `ALTER FUNCTION ... OWNER TO backend_rag_v2`,
-- which is precisely the state that kept magic-link issuance answering 500 with
-- zero tokens ever minted. A rollback section that faithfully restores a known
-- outage is worse than none: it hands a future operator a one-command way to
-- re-break production while believing they are being careful. Flagged by the
-- adversarial review of this PR and honored.
--
-- If the ownership genuinely must be reverted, it is a deliberate operator
-- action with its own reasoning, not the mechanical inverse of this file.

DO $garuda_301_owner_rollback$
BEGIN
    RAISE NOTICE 'garuda magic-link (301 rollback): intentionally does nothing -- restoring ownership to backend_rag_v2 would re-create the production outage this migration cures.';
END;
$garuda_301_owner_rollback$;
