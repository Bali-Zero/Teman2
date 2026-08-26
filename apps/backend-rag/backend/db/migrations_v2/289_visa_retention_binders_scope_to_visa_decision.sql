-- ============================================================================
-- 289 — the Visa Oracle's two retention binders must resolve their OWN scope
-- ============================================================================
--
-- THE DEFECT (2026-08-26 prod outage, Visa Oracle answered nobody)
-- ----------------------------------------------------------------------------
--   Migration 264 created `visa_decision_retention_policies` as a table with
--   exactly ONE active row per environment, enforced by an exclusion
--   constraint over (environment, effective_period). Two trigger functions
--   and one Python reader were written against that guarantee, and each
--   resolves "the" active policy with nothing but:
--
--       WHERE environment = <env> AND effective_period @> <clock>
--
--   Migration 281 (GARUDA VOA) turned that table into the ONE retention
--   authority for four different data classes: it added `policy_scope`
--   (VISA_DECISION | GARUDA_CHECK | GARUDA_ORDER; 285 widened it with
--   GARUDA_MAGIC_LINK) and — correctly — widened the exclusion constraint to
--   `policy_scope WITH =`. From that moment the invariant is "one active row
--   per (environment, scope)", not "one active row per environment".
--
--   281 taught every GARUDA-side reader to filter by scope. It did not
--   revisit the two pre-existing Visa Oracle binders, which have no scope
--   predicate and use `INTO STRICT`. They stayed correct only for as long as
--   the table held no non-VISA_DECISION row.
--
--   The first GARUDA policy row was activated in production at
--   2026-08-26 04:40:27Z. From that instant the unscoped predicate matches
--   2 rows, then 4 (magic-link and order policies activated 06:28:56Z), and:
--
--     * `retention.active_policy_available()` (Python, `count(*) == 1`)
--       returns False, so every /api/visa-oracle/evaluate call answers
--       HTTP 200 `TEMPORARILY_UNAVAILABLE / RETENTION_POLICY_UNAVAILABLE`
--       -- reproduced live against balizero.com;
--     * had that gate been fixed alone, `INTO STRICT` in these two functions
--       would have raised TOO_MANY_ROWS on the first insert
--       ('decision retention policy authority is ambiguous'), converting a
--       graceful outage into a 500. Both sides must move together.
--
--   Measured on prod before this migration:
--       environment='PRODUCTION' AND effective_period @> now()            -> 4
--       ... AND policy_scope='VISA_DECISION'                              -> 1
--
--   What is NOT claimed: that this is when real visitors began being turned
--   away. `visa_decisions` cannot answer that -- the gate refuses BEFORE any
--   INSERT, so a blocked call leaves no row, and the table already shows
--   multi-day gaps (16-18 and 21-22 August) while the gate was healthy. Its
--   last row predates 04:40:27Z by ~43 hours, which this defect therefore
--   does NOT explain. Two facts are established and no more: the invariant
--   broke at 04:40:27Z, and the gate is broken now.
--
-- THE FIX
-- ----------------------------------------------------------------------------
--   Give both binders the scope predicate 281's exclusion constraint already
--   partitions on. Nothing else in either body changes — the definitions
--   below are `pg_get_functiondef()` of the live functions with one added
--   `AND policy_scope = 'VISA_DECISION'` line each.
--
--   `TOO_MANY_ROWS` handling is deliberately kept: with the scope predicate
--   it now means what it always claimed to mean — two active policies for
--   THIS scope — which the exclusion constraint makes impossible. It is a
--   backstop, not dead code.
--
--   `bind_visa_decision_payload_retention` is NOT touched: it resolves its
--   parent by `visa_decisions.id`, never by an active-policy lookup.
--
-- OWNERSHIP / SECURITY DEFINER
-- ----------------------------------------------------------------------------
--   Both functions are owned by `visa_ledger_owner` and are SECURITY DEFINER
--   (268). `CREATE OR REPLACE FUNCTION` preserves owner and ACL, but the
--   volatility/security/search_path attributes come from the statement
--   itself: omitting `SECURITY DEFINER` here would silently demote them to
--   SECURITY INVOKER and re-open the exact 2026-08-07 prod incident 268
--   closed. Both attributes and `SET search_path` are therefore restated
--   verbatim below, in both directions.
--
-- NOTE: `-- === ROLLBACK ===` marker is mandatory (migration_base.py) for
--   migrations > 111.

CREATE OR REPLACE FUNCTION public.bind_visa_decision_retention_policy()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    policy RECORD;
    expected_until TIMESTAMPTZ;
BEGIN
    -- created_at is structurally DB-owned below. evaluated_at remains the
    -- engine/bitemporal clock by contract; its authoritative skew semantics
    -- are a separate Zero activation decision (F16), not invented here.
    IF NEW.created_at IS DISTINCT FROM transaction_timestamp() THEN
        RAISE EXCEPTION 'decision created_at must use the database transaction clock';
    END IF;
    IF NEW.legal_hold THEN
        RAISE EXCEPTION 'new visa_decisions rows cannot begin under legal hold';
    END IF;

    BEGIN
        SELECT id, retention_interval, retention_anchor
          INTO STRICT policy
         FROM public.visa_decision_retention_policies
         WHERE environment = NEW.environment
           AND policy_scope = 'VISA_DECISION'
           AND effective_period @> NEW.evaluated_at
         FOR SHARE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'decision has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'decision retention policy authority is ambiguous';
    END;

    expected_until := (
        CASE policy.retention_anchor
            WHEN 'EVALUATED_AT' THEN NEW.evaluated_at
            WHEN 'CREATED_AT' THEN NEW.created_at
        END
    ) + policy.retention_interval;
    IF expected_until <= clock_timestamp() THEN
        RAISE EXCEPTION 'decision retention deadline has already elapsed';
    END IF;

    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'decision retention policy does not match active policy';
    END IF;
    IF NEW.retention_until IS NOT NULL
       AND NEW.retention_until IS DISTINCT FROM expected_until THEN
        RAISE EXCEPTION 'decision retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.retention_until := expected_until;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.bind_visa_evaluate_idempotency_retention_policy()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    policy RECORD;
    expected_expires_at TIMESTAMPTZ;
BEGIN
    IF NEW.reserved_at IS DISTINCT FROM statement_timestamp()
       OR NEW.created_at IS DISTINCT FROM statement_timestamp() THEN
        RAISE EXCEPTION 'idempotency reserved_at and created_at must use the database statement clock';
    END IF;
    IF NEW.environment IS NULL THEN
        RAISE EXCEPTION 'idempotency reservation requires an environment';
    END IF;

    BEGIN
        SELECT id, idempotency_retention_interval
          INTO STRICT policy
          FROM public.visa_decision_retention_policies
         WHERE environment = NEW.environment
           AND policy_scope = 'VISA_DECISION'
           AND effective_period @> NEW.reserved_at
         FOR SHARE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'idempotency reservation has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'idempotency retention policy authority is ambiguous';
    END;

    expected_expires_at := NEW.reserved_at + policy.idempotency_retention_interval;
    IF expected_expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'idempotency retention deadline has already elapsed';
    END IF;
    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'idempotency retention policy does not match active policy';
    END IF;
    IF NEW.expires_at IS NOT NULL
       AND NEW.expires_at IS DISTINCT FROM expected_expires_at THEN
        RAISE EXCEPTION 'idempotency retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.expires_at := expected_expires_at;
    RETURN NEW;
END;
$$;

-- === ROLLBACK ===

-- Restores 264's two bodies exactly, with ONE deliberate delta: the
-- `SECURITY DEFINER` attribute, which 264 did not ship and 268 added by
-- `ALTER FUNCTION`. Restating it here is not cosmetic -- `CREATE OR REPLACE`
-- takes security and search_path from the statement, so a rollback that
-- omitted it would silently demote both functions to SECURITY INVOKER and
-- re-open the 2026-08-07 production incident 268 exists to close. That is
-- the whole difference: verified line-by-line against
-- `git show <base>:...264_visa_decision_retention_policy.sql`, the two
-- bodies differ from 264's by that attribute and nothing else.
--
-- An adversarial review of this migration found the first draft of this
-- section had silently dropped three plpgsql comment lines from the decision
-- binder (the `created_at is structurally DB-owned` note), which would have
-- left a rolled-back database holding a THIRD variant of the function that
-- never existed anywhere. Behaviourally identical, textually novel -- and a
-- claim of "verbatim" that was not true. Restored; the claim is now checked
-- rather than asserted.
--
-- Rolling this back re-arms the 2026-08-26 outage on any database whose
-- policy table holds an active non-VISA_DECISION row -- which is every
-- database that has applied 281 and activated a GARUDA policy. It is only
-- meaningful together with rolling back 281.

CREATE OR REPLACE FUNCTION public.bind_visa_decision_retention_policy()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    policy RECORD;
    expected_until TIMESTAMPTZ;
BEGIN
    -- created_at is structurally DB-owned below. evaluated_at remains the
    -- engine/bitemporal clock by contract; its authoritative skew semantics
    -- are a separate Zero activation decision (F16), not invented here.
    IF NEW.created_at IS DISTINCT FROM transaction_timestamp() THEN
        RAISE EXCEPTION 'decision created_at must use the database transaction clock';
    END IF;
    IF NEW.legal_hold THEN
        RAISE EXCEPTION 'new visa_decisions rows cannot begin under legal hold';
    END IF;

    BEGIN
        SELECT id, retention_interval, retention_anchor
          INTO STRICT policy
         FROM public.visa_decision_retention_policies
         WHERE environment = NEW.environment
           AND effective_period @> NEW.evaluated_at
         FOR SHARE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'decision has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'decision retention policy authority is ambiguous';
    END;

    expected_until := (
        CASE policy.retention_anchor
            WHEN 'EVALUATED_AT' THEN NEW.evaluated_at
            WHEN 'CREATED_AT' THEN NEW.created_at
        END
    ) + policy.retention_interval;
    IF expected_until <= clock_timestamp() THEN
        RAISE EXCEPTION 'decision retention deadline has already elapsed';
    END IF;

    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'decision retention policy does not match active policy';
    END IF;
    IF NEW.retention_until IS NOT NULL
       AND NEW.retention_until IS DISTINCT FROM expected_until THEN
        RAISE EXCEPTION 'decision retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.retention_until := expected_until;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.bind_visa_evaluate_idempotency_retention_policy()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    policy RECORD;
    expected_expires_at TIMESTAMPTZ;
BEGIN
    IF NEW.reserved_at IS DISTINCT FROM statement_timestamp()
       OR NEW.created_at IS DISTINCT FROM statement_timestamp() THEN
        RAISE EXCEPTION 'idempotency reserved_at and created_at must use the database statement clock';
    END IF;
    IF NEW.environment IS NULL THEN
        RAISE EXCEPTION 'idempotency reservation requires an environment';
    END IF;

    BEGIN
        SELECT id, idempotency_retention_interval
          INTO STRICT policy
          FROM public.visa_decision_retention_policies
         WHERE environment = NEW.environment
           AND effective_period @> NEW.reserved_at
         FOR SHARE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'idempotency reservation has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'idempotency retention policy authority is ambiguous';
    END;

    expected_expires_at := NEW.reserved_at + policy.idempotency_retention_interval;
    IF expected_expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'idempotency retention deadline has already elapsed';
    END IF;
    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'idempotency retention policy does not match active policy';
    END IF;
    IF NEW.expires_at IS NOT NULL
       AND NEW.expires_at IS DISTINCT FROM expected_expires_at THEN
        RAISE EXCEPTION 'idempotency retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.expires_at := expected_expires_at;
    RETURN NEW;
END;
$$;
