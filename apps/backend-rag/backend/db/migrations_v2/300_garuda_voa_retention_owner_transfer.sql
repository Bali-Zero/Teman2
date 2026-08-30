-- 300_garuda_voa_retention_owner_transfer.sql
--
-- WHAT IS WRONG, AND WHY NOTHING WENT RED
-- =============================================================================
--   Migrations 281 (GARUDA_CHECK retention, 2026-08-26) and 286 (check
--   results, same day) each end with a `DO` block that transfers the functions
--   they create to `visa_ledger_owner`. Both migrations are recorded APPLIED in
--   `_schema_versions`. The transfers never took.
--
--   Measured on the production primary on 2026-08-30, five functions were still
--   owned by the application role `backend_rag_v2`:
--
--       bind_legacy_garuda_voa_checks_retention_policy(p_limit integer, p_requested_by text)
--       garuda_voa_check_retention_evidence()
--       purge_garuda_voa_checks(p_limit integer, p_requested_by text)
--       set_garuda_voa_check_legal_hold(p_hash character varying, p_legal_hold boolean,
--           p_requested_by text, p_case_reference text, p_reason_code text,
--           p_approved_by text, p_review_due_at timestamp with time zone)
--       purge_garuda_voa_check_results(p_limit integer, p_requested_by text)
--
--   The cause is the handler 281 and 286 share. `ALTER FUNCTION ... OWNER TO`
--   requires the session to be superuser, or to be the current owner AND a
--   member of the target role. The migration runner connects as
--   `backend_rag_v2`, which is neither a superuser nor a member of
--   `visa_ledger_owner`, so every ALTER raised `insufficient_privilege`; the
--   handler caught it, emitted a NOTICE, and the migration was recorded applied
--   anyway. A NOTICE in a deploy log is not an alarm. Nothing was red, for four
--   days, on both migrations at once.
--
--   That is the "esiste != armato" shape (superscar #2) in its migration form,
--   and it is exactly the defect an adversarial reviewer rejected in migration
--   299's first draft for copying the same handler verbatim. This file is the
--   companion cure: 299 codifies the one transfer 285 forgot, 300 codifies the
--   five that 281 and 286 announced and did not perform.
--
-- WHY THIS IS NOT AN OUTAGE FIX
-- =============================================================================
--   Unlike 299, no endpoint was answering 500 on account of these five. They
--   are not BEFORE INSERT trigger functions on a hot write path: they are the
--   bounded purge / evidence / legal-hold / legacy-binding primitives, invoked
--   by an operator or a scheduler that does not yet run. The ownership was a
--   latent trap, not a live failure — the same trap 285 walked into.
--
--   The five ALTERs were applied to the production primary by hand on
--   2026-08-30, in one superuser transaction, before this migration was
--   written. Production is therefore already correct:
--
--       SELECT p.proname, pg_get_userbyid(p.proowner)
--         FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
--        WHERE n.nspname = 'public' AND p.prosecdef
--          AND pg_get_userbyid(p.proowner) <> 'visa_ledger_owner';
--       -> 0 rows
--
--   This file exists so a fresh database, a rebuild, or an environment that
--   never received that manual transaction converges to the same state instead
--   of coming up with the trap re-armed and no record that it is there.
--
-- WHAT THIS FILE DELIBERATELY DOES NOT DO
-- =============================================================================
--   The other four functions in the 281/286 family --
--   `bind_garuda_voa_check_retention_policy()`,
--   `bind_garuda_voa_check_result_retention_policy()`,
--   `guard_garuda_voa_checks_retention_mutation()` and
--   `guard_garuda_voa_check_legal_hold_events_mutation()` -- were measured
--   ledger-owned on production in the same read, so they are not named here.
--   Two of them are SECURITY DEFINER and are therefore covered from now on by
--   the class-level `definer:public-security-definer-ledger-owned` check added
--   to `operational_preflight.py` alongside this migration. The remaining two
--   are plain invoker trigger guards that take no row lock, so their ownership
--   is not load-bearing.
--
--   That class check, not this list, is the part that stops a migration 30x
--   from doing this a third time. A hand-maintained list is what let migration
--   285 through: this file cures the five that exist, the invariant catches the
--   next one nobody remembers to add.
--
-- WHY THE TRANSFER IS ROLE-GUARDED, IDEMPOTENT, AND ENDS IN AN ASSERTION
-- =============================================================================
--   Role-guarded and `to_regprocedure` rather than a `::regprocedure` cast, so
--   an absent role or an absent function skips instead of raising -- the
--   fresh-database ordering hazard 299's review flagged.
--
--   The ALTER is still attempted, and its privilege failure still explained.
--   But the block then RE-READS `pg_proc.proowner` and RAISES if the
--   postcondition does not hold. On a superuser connection (CI, a fresh clone)
--   the ALTER succeeds and the assertion is silent. Anywhere else it fails
--   loudly, which is the honest state: the cure is not in force. It must not be
--   possible for this migration to be recorded applied while the ownership is
--   still wrong. That is the whole point of the file, and it is precisely what
--   281 and 286 got wrong.

DO $garuda_300_owner_transfer$
DECLARE
    ledger_owner constant text := 'visa_ledger_owner';
    target_function constant text[] := ARRAY[
        'public.bind_legacy_garuda_voa_checks_retention_policy(integer, text)',
        'public.garuda_voa_check_retention_evidence()',
        'public.purge_garuda_voa_checks(integer, text)',
        'public.set_garuda_voa_check_legal_hold(varchar, boolean, text, text, text, text, timestamptz)',
        'public.purge_garuda_voa_check_results(integer, text)'
    ];
    signature text;
    fn oid;
    current_owner text;
    still_wrong text[] := ARRAY[]::text[];
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ledger_owner) THEN
        RAISE NOTICE 'garuda retention (300): role % absent -- skipping ownership transfer, same convention as 251/253/268/281/286/299',
            ledger_owner;
        RETURN;
    END IF;

    FOREACH signature IN ARRAY target_function
    LOOP
        fn := to_regprocedure(signature);
        IF fn IS NULL THEN
            RAISE NOTICE 'garuda retention (300): % not present -- nothing to transfer', signature;
            CONTINUE;
        END IF;

        SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;

        IF current_owner IS DISTINCT FROM ledger_owner THEN
            BEGIN
                EXECUTE format('ALTER FUNCTION %s OWNER TO %I', signature, ledger_owner);
            EXCEPTION
                WHEN insufficient_privilege THEN
                    RAISE NOTICE 'garuda retention (300): ALTER of % denied (current owner %) -- this session is neither superuser nor a member of %',
                        signature, current_owner, ledger_owner;
            END;
            SELECT pg_get_userbyid(proowner) INTO current_owner FROM pg_proc WHERE oid = fn;
        END IF;

        -- Collect rather than raise on the first: an operator repairing this
        -- by hand needs the whole list in one pass, not one name per attempt.
        IF current_owner IS DISTINCT FROM ledger_owner THEN
            still_wrong := still_wrong || format('%s (owned by %s)', signature, current_owner);
        END IF;
    END LOOP;

    IF array_length(still_wrong, 1) IS NOT NULL THEN
        RAISE EXCEPTION
            'garuda retention (300): % of the 5 GARUDA_CHECK retention functions are still not owned by % -- %. Migrations 281 and 286 announced this transfer and were recorded applied without performing it; refusing to repeat that. Run the ALTERs on a superuser connection (or as a member of %), then re-apply.',
            array_length(still_wrong, 1),
            ledger_owner,
            array_to_string(still_wrong, '; '),
            ledger_owner;
    END IF;
END;
$garuda_300_owner_transfer$;

-- === ROLLBACK ===

-- Deliberately a no-op that says so, not a symmetric undo.
--
-- The mechanical inverse of this migration is `ALTER FUNCTION ... OWNER TO
-- backend_rag_v2` on all five, which re-creates the exact latent trap that
-- migration 285 later fell into and that cost the GARUDA magic-link endpoint
-- weeks of silent 500s. A rollback that faithfully restores a known trap is
-- worse than none: it hands a future operator a one-command way to re-arm it
-- while believing they are being careful. Same reasoning, and the same verdict,
-- as migration 299's rollback section.
--
-- If ownership genuinely must be reverted, that is a deliberate operator action
-- with its own reasoning, not the mechanical inverse of this file.

DO $garuda_300_owner_rollback$
BEGIN
    RAISE NOTICE 'garuda retention (300 rollback): intentionally does nothing -- restoring ownership to backend_rag_v2 would re-arm the SECURITY DEFINER trap this migration closes.';
END;
$garuda_300_owner_rollback$;
