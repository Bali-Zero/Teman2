-- ============================================================================
-- 285_garuda_magic_link.sql
-- GARUDA VOA -- L4 magic-link authentication persistence
-- (products/garuda-voa/L4-CONTINUATION.md "part 2 of 3").
--
-- Numbering: 284 (L3 checkout+orders) is the highest migration on
-- feature/garuda-voa and every open garuda-l* lane branch as of this
-- commit (checked immediately before writing this file, not assumed --
-- W40). If a different migration lands as 285 on the integration branch
-- first, RENUMBER this file before merging it.
--
-- DECISION MADE EXPLICIT (L4-CONTINUATION.md, "the lane must decide where
-- fields live before writing code, not during"):
--
-- 1. This does NOT reuse `magic_link_tokens` (migration 237). That table is
--    the LIVE, already-shipped FASE 6 client-portal login mechanism
--    (`backend/services/portal/magic_link_service.py`): it authenticates an
--    already-registered `team_members` row by email, has no `result_id`,
--    no `idempotency_key`, and no session-secret concept, and it has zero
--    retention-policy binding of its own today. GARUDA's magic link
--    authenticates an anonymous eligibility-check RESULT OWNER (result_id +
--    email, no registration), needs `idempotency_key` on both operations,
--    and mints an opaque account-session secret on exchange -- three fields
--    that have no home on 237's row shape. Conflating the two would bolt
--    GARUDA-only columns onto a shared table another product already
--    writes in production, and would force retention/fail-closed machinery
--    to also account for that product's traffic. A new, disjoint table is
--    the smaller and safer surface; 237 is untouched by this migration.
--
-- 2. `account_session_secret` (the opaque bearer `exchangeMagicLink` mints
--    and the router sets as the `garuda_session` cookie) has no home in any
--    existing table. `backend/app/utils/cookie_auth.py` is a STATELESS JWT
--    mechanism (`nz_access_token`) for the SAME reason 237 does not fit:
--    a JWT cannot hold "opaque secret the server matches by hash", which
--    the `MagicLinkStore` Protocol docstring makes a hard requirement
--    (CodeQL `py/clear-text-storage-sensitive-data`, 2026-08-25 review).
--    `garuda_orders_router.py:74` (`_require_magic_session_actor`) already
--    expects exactly this shape -- a `garuda_session` cookie value that
--    some verifier turns into an actor -- so this migration creates the
--    table that verifier will read. Wiring that verifier onto
--    `app.state.garuda_magic_session_verifier` is NOT done by this
--    migration or this lane: `_require_magic_session_actor`'s own
--    `verifier(cookie)` call is SYNCHRONOUS, which a real Postgres-backed
--    check cannot satisfy without an `await` this lane does not own adding
--    (`garuda_orders_router.py` is L3's file -- LANES.md file-ownership).
--    Flagged for the orchestrator in the PR body, not fixed here.
--
-- Retention: widens the SAME Zero-approved authority migration 281 already
-- widened for GARUDA_CHECK/GARUDA_ORDER (ARCHITECTURE.md D2, "one
-- authority, not two") with a fourth scope, GARUDA_MAGIC_LINK, rather than
-- inventing a table-specific policy. Deliberately NOT replicating 281's
-- full legal-hold/purge/evidence machinery here: those exist for durable
-- customer-decision records with a real retrospective-audit need; a
-- magic-link token is a self-expiring (15-minute) authentication artefact,
-- already sha256-hashed at rest, holding nothing an investigator would
-- need to freeze mid-lifetime. Retention basis argued below, per row type.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- (0) Widen the one retention authority with a fourth scope
-- ----------------------------------------------------------------------------

DO $garuda_285_widen_scope_check$
DECLARE
    scope_check_name text;
BEGIN
    -- The inline `policy_scope ... CHECK (policy_scope IN (...))` column
    -- constraint 281 added renders back as `CHECK ((policy_scope = ANY
    -- (ARRAY[...])))` -- distinct from 281's OTHER policy_scope-mentioning
    -- constraint (`visa_decision_retention_policies_scope_anchor`, which
    -- renders as `CHECK ((policy_scope <> 'GARUDA_CHECK'::text) OR ...)`),
    -- so this LIKE pattern picks the enum check alone. Same "find by shape,
    -- never a hardcoded name" discipline 281 itself uses for the UNIQUE/
    -- EXCLUDE constraints it widened.
    SELECT conname INTO scope_check_name
      FROM pg_constraint
     WHERE conrelid = 'public.visa_decision_retention_policies'::regclass
       AND contype = 'c'
       AND pg_get_constraintdef(oid) LIKE 'CHECK ((policy_scope = ANY (ARRAY[%';
    IF scope_check_name IS NULL THEN
        RAISE EXCEPTION 'garuda 285: could not locate the policy_scope enum CHECK to widen';
    END IF;
    EXECUTE format(
        'ALTER TABLE public.visa_decision_retention_policies DROP CONSTRAINT %I',
        scope_check_name
    );
END;
$garuda_285_widen_scope_check$;

ALTER TABLE public.visa_decision_retention_policies
    ADD CONSTRAINT visa_decision_retention_policies_policy_scope_check
        CHECK (policy_scope IN ('VISA_DECISION', 'GARUDA_CHECK', 'GARUDA_ORDER', 'GARUDA_MAGIC_LINK'));

-- Widen the "closing this policy would strand an existing binding" guard
-- (264, already widened by 281) to also cover garuda_magic_link_tokens
-- bindings, once the table exists below. CREATE OR REPLACE is safe: no
-- applied migration's on-disk text is edited (253/267/268/281 precedent).
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

-- ----------------------------------------------------------------------------
-- (1) garuda_magic_link_tokens
--
-- Retention basis: a magic-link token is an authentication artefact with a
-- fixed 15-minute TTL (`MAGIC_LINK_TTL_MINUTES`, magic_link.py). It has no
-- reason to outlive its own expiry by more than the window a security
-- investigation of a specific abuse report needs (e.g. "who requested links
-- for this email in the days around an incident"). Chosen: 14 days past
-- expiry -- long enough to cover a realistic report-and-look-back cycle,
-- short enough that this table never becomes a de-facto email/result_id
-- correlation log. This is a number to be confirmed by Zero like every
-- other retention_interval in this repo (the INSERT below is a schema
-- capability, not itself an approval) -- 14 days is proposed, not asserted
-- as final.
-- ----------------------------------------------------------------------------

CREATE TABLE public.garuda_magic_link_tokens (
    token_hash          CHAR(64) PRIMARY KEY,  -- sha256 hex; raw token is NEVER persisted
    result_id           TEXT NOT NULL CHECK (result_id ~ '^[A-Za-z0-9_-]{22,128}$'),
    email               TEXT NOT NULL,
    environment         TEXT NOT NULL CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
    expires_at          TIMESTAMPTZ NOT NULL,
    used_at             TIMESTAMPTZ,
    retention_policy_id UUID NOT NULL REFERENCES public.visa_decision_retention_policies (id),
    retention_until     TIMESTAMPTZ NOT NULL,
    -- NOW() (== transaction_timestamp()), NOT statement_timestamp(): the
    -- retention-binding trigger below checks `NEW.created_at IS DISTINCT
    -- FROM transaction_timestamp()` (281's exact convention for
    -- garuda_voa_checks.created_at, migration 261 line 43 `DEFAULT NOW()`)
    -- -- caught live: this INSERT is not the transaction's first statement
    -- (the idempotency reservation runs first in the same transaction), so
    -- statement_timestamp() here would differ from transaction_timestamp()
    -- by the gap between the two statements and the trigger would reject
    -- every real row.
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (expires_at > created_at)
);

COMMENT ON TABLE public.garuda_magic_link_tokens IS
    'GARUDA VOA magic-link auth (L4). One row per issued link. token_hash is sha256 of the raw token -- raw token lives only in the email body.';
COMMENT ON COLUMN public.garuda_magic_link_tokens.token_hash IS
    'sha256 hex of the raw urlsafe token. Unique by being the primary key -- a collision here would mean two live tokens hash identically.';

CREATE INDEX idx_garuda_magic_link_tokens_email_created
    ON public.garuda_magic_link_tokens (email, created_at DESC);

CREATE INDEX idx_garuda_magic_link_tokens_retention_purge
    ON public.garuda_magic_link_tokens (retention_until);

-- Fail-closed retention binding -- identical shape to
-- `bind_garuda_voa_check_retention_policy` (281) and
-- `active_garuda_order_policy_available` (284), scoped to
-- GARUDA_MAGIC_LINK / CREATED_AT anchor (this table has no
-- decision-evaluation timestamp distinct from row creation).
CREATE FUNCTION public.active_garuda_magic_link_policy_available(
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
      AND policy_scope = 'GARUDA_MAGIC_LINK'
      AND effective_period @> p_created_at;
$func$;

COMMENT ON FUNCTION public.active_garuda_magic_link_policy_available IS
    'Pre-INSERT read for PostgresMagicLinkStore.issue(): one Zero-approved GARUDA_MAGIC_LINK policy must cover this clock, or the funnel fails closed (PERSISTENCE_POLICY_UNAVAILABLE) before any row is attempted.';

CREATE FUNCTION public.bind_garuda_magic_link_token_retention_policy()
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
        RAISE EXCEPTION 'garuda magic-link token created_at must use the database transaction clock';
    END IF;

    BEGIN
        SELECT id, retention_interval, retention_anchor
          INTO STRICT policy
          FROM public.visa_decision_retention_policies
         WHERE environment = NEW.environment
           AND policy_scope = 'GARUDA_MAGIC_LINK'
           AND effective_period @> NEW.created_at
         FOR SHARE;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE EXCEPTION 'garuda magic-link token has no active Zero-approved retention policy';
        WHEN TOO_MANY_ROWS THEN
            RAISE EXCEPTION 'garuda magic-link token retention policy authority is ambiguous';
    END;

    IF policy.retention_anchor <> 'CREATED_AT' THEN
        RAISE EXCEPTION 'unsupported retention anchor for GARUDA_MAGIC_LINK scope';
    END IF;
    expected_until := NEW.created_at + policy.retention_interval;
    IF expected_until <= clock_timestamp() THEN
        RAISE EXCEPTION 'garuda magic-link token retention deadline has already elapsed';
    END IF;

    IF NEW.retention_policy_id IS NOT NULL
       AND NEW.retention_policy_id IS DISTINCT FROM policy.id THEN
        RAISE EXCEPTION 'garuda magic-link token retention policy does not match active policy';
    END IF;
    IF NEW.retention_until IS NOT NULL
       AND NEW.retention_until IS DISTINCT FROM expected_until THEN
        RAISE EXCEPTION 'garuda magic-link token retention deadline does not match active policy';
    END IF;

    NEW.retention_policy_id := policy.id;
    NEW.retention_until := expected_until;
    RETURN NEW;
END;
$func$;

REVOKE ALL ON FUNCTION public.bind_garuda_magic_link_token_retention_policy() FROM PUBLIC;

CREATE TRIGGER garuda_magic_link_tokens_retention_binding
BEFORE INSERT ON public.garuda_magic_link_tokens
FOR EACH ROW EXECUTE FUNCTION public.bind_garuda_magic_link_token_retention_policy();

-- Rows are immutable except the single-use `used_at` transition (NULL ->
-- set, exactly once); deletion is only permitted once retention has
-- actually elapsed. Same "close/consume, never silently mutate" discipline
-- as `guard_garuda_order_idempotency_mutation` (284).
CREATE FUNCTION public.guard_garuda_magic_link_token_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $func$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF clock_timestamp() < OLD.retention_until THEN
            RAISE EXCEPTION 'unexpired garuda_magic_link_tokens rows are immutable';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.used_at IS NOT NULL AND NEW.used_at IS DISTINCT FROM OLD.used_at THEN
        RAISE EXCEPTION 'garuda_magic_link_tokens.used_at is immutable once consumed';
    END IF;
    IF (to_jsonb(OLD) - 'used_at') IS DISTINCT FROM (to_jsonb(NEW) - 'used_at') THEN
        RAISE EXCEPTION 'garuda_magic_link_tokens rows are immutable except used_at';
    END IF;
    RETURN NEW;
END;
$func$;

CREATE TRIGGER trg_guard_garuda_magic_link_token_mutation
BEFORE UPDATE OR DELETE ON public.garuda_magic_link_tokens
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_magic_link_token_mutation();

-- ----------------------------------------------------------------------------
-- (2) garuda_magic_link_idempotency
--
-- Same shape as `garuda_order_idempotency` (284), generalized across BOTH
-- `requestMagicLink` (issue) and `exchangeMagicLink` (exchange) -- reused
-- per L4-CONTINUATION.md ("L3 already solved this shape ... reuse rather
-- than invent a third"). No `order_id`-equivalent column: neither
-- operation's cached response names a persistent resource id a replay
-- would need to resume (`issue` is always an empty 202; `exchange`'s
-- cached body carries only the non-secret ExchangeOutcome fields -- see
-- `backend/services/garuda_portal/idempotency.py`).
--
-- Retention: a shorter fixed TTL than 284's 30 days -- these are auth
-- replay-guards for a 15-minute-lived credential, not a payment record;
-- 1 day comfortably covers any realistic client retry window without
-- turning into a second correlation log alongside the tokens table above.
-- ----------------------------------------------------------------------------

CREATE TABLE public.garuda_magic_link_idempotency (
    key_sha256               BYTEA PRIMARY KEY CHECK (octet_length(key_sha256) = 32),
    canonical_payload_sha256 BYTEA NOT NULL CHECK (octet_length(canonical_payload_sha256) = 32),
    response_status          INT,
    response_body            JSONB,
    completed_at              TIMESTAMPTZ,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    expires_at                TIMESTAMPTZ NOT NULL DEFAULT (statement_timestamp() + INTERVAL '1 day'),
    CHECK (expires_at > created_at),
    CHECK (
        (response_body IS NULL AND response_status IS NULL AND completed_at IS NULL)
        OR (response_body IS NOT NULL AND response_status IS NOT NULL AND completed_at IS NOT NULL)
    )
);

COMMENT ON TABLE public.garuda_magic_link_idempotency IS
    'Idempotency-Key replay cache for requestMagicLink + exchangeMagicLink. Raw keys never stored -- only their scoped SHA-256 (backend.services.garuda_orders.idempotency.scoped_key_sha256).';

CREATE INDEX idx_garuda_magic_link_idempotency_expires_at
    ON public.garuda_magic_link_idempotency (expires_at);

CREATE FUNCTION public.guard_garuda_magic_link_idempotency_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $func$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF clock_timestamp() < OLD.expires_at THEN
            RAISE EXCEPTION 'unexpired garuda_magic_link_idempotency rows are immutable';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.key_sha256 IS DISTINCT FROM NEW.key_sha256
       OR OLD.canonical_payload_sha256 IS DISTINCT FROM NEW.canonical_payload_sha256
       OR OLD.created_at IS DISTINCT FROM NEW.created_at
       OR OLD.expires_at IS DISTINCT FROM NEW.expires_at THEN
        RAISE EXCEPTION 'garuda_magic_link_idempotency request binding is immutable';
    END IF;
    IF OLD.response_body IS NOT NULL THEN
        RAISE EXCEPTION 'completed garuda_magic_link_idempotency rows are immutable';
    END IF;
    IF NEW.response_body IS NULL AND NEW.response_status IS NULL AND NEW.completed_at IS NULL THEN
        RETURN NEW;
    END IF;
    IF NEW.response_body IS NULL OR NEW.response_status IS NULL OR NEW.completed_at IS NULL THEN
        RAISE EXCEPTION 'garuda_magic_link_idempotency completion must be atomic';
    END IF;
    RETURN NEW;
END;
$func$;

CREATE TRIGGER trg_guard_garuda_magic_link_idempotency_mutation
BEFORE UPDATE OR DELETE ON public.garuda_magic_link_idempotency
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_magic_link_idempotency_mutation();

-- ----------------------------------------------------------------------------
-- (3) garuda_account_sessions
--
-- The session `exchangeMagicLink` establishes (DECISIONS.md Q1: "a session
-- whose lifetime is a separate decision (proposed: 30 days, re-authenticated
-- by a new link)"). Fixed 30-day TTL per that proposed number, not a second
-- Zero-approval policy gate -- same tier as the idempotency cache above
-- (an operational-lifetime table, not a durable customer-decision record),
-- not the tier `visa_decision_retention_policies` governs. `session_secret`
-- itself is NEVER stored -- only its sha256 hash, matching the Protocol's
-- hard requirement for every bearer the browser holds and presents back.
-- ----------------------------------------------------------------------------

CREATE TABLE public.garuda_account_sessions (
    session_secret_hash CHAR(64) PRIMARY KEY,  -- sha256 hex; raw secret lives only in the garuda_session cookie
    result_id            TEXT NOT NULL CHECK (result_id ~ '^[A-Za-z0-9_-]{22,128}$'),
    email                 TEXT NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    expires_at            TIMESTAMPTZ NOT NULL DEFAULT (statement_timestamp() + INTERVAL '30 days'),
    CHECK (expires_at > created_at)
);

COMMENT ON TABLE public.garuda_account_sessions IS
    'GARUDA VOA account session minted by exchangeMagicLink (L4). session_secret_hash is sha256 of the opaque bearer set as the garuda_session cookie -- raw value never persisted.';

CREATE INDEX idx_garuda_account_sessions_expires_at
    ON public.garuda_account_sessions (expires_at);

-- === ROLLBACK ===

DROP TABLE IF EXISTS public.garuda_account_sessions;
DROP TRIGGER IF EXISTS trg_guard_garuda_magic_link_idempotency_mutation ON public.garuda_magic_link_idempotency;
DROP FUNCTION IF EXISTS public.guard_garuda_magic_link_idempotency_mutation();
DROP TABLE IF EXISTS public.garuda_magic_link_idempotency;
DROP TRIGGER IF EXISTS trg_guard_garuda_magic_link_token_mutation ON public.garuda_magic_link_tokens;
DROP FUNCTION IF EXISTS public.guard_garuda_magic_link_token_mutation();
DROP TRIGGER IF EXISTS garuda_magic_link_tokens_retention_binding ON public.garuda_magic_link_tokens;
DROP FUNCTION IF EXISTS public.bind_garuda_magic_link_token_retention_policy();
DROP FUNCTION IF EXISTS public.active_garuda_magic_link_policy_available(TEXT, TIMESTAMPTZ);
DROP TABLE IF EXISTS public.garuda_magic_link_tokens;

-- Narrowing the policy_scope CHECK back to pre-285's list is only safe if
-- no row has ever used the value being removed -- visa_decision_retention_
-- policies is append-only (264's guard trigger blocks UPDATE/DELETE/
-- TRUNCATE unconditionally), so a 'GARUDA_MAGIC_LINK'-scoped row, once
-- inserted, can never be removed to make room for a narrower constraint.
-- Bug found 2026-08-25 (PR #4902 follow-up): the original unconditional
-- DROP/ADD CONSTRAINT pair here always fails with CheckViolationError the
-- moment this rollback runs in any database where a GARUDA_MAGIC_LINK
-- policy was ever seeded -- which every test exercising the issue()/
-- exchange() path does. 281's own rollback avoids this same trap a
-- different way: it DROPS the whole policy_scope column instead of
-- narrowing its CHECK, so there is no remaining column for stale values to
-- violate. This migration cannot do the same (264 already owns
-- policy_scope; 285 only widened its CHECK, it did not add the column) --
-- so the correct, honest rollback is: narrow the CHECK when it is safe to,
-- and otherwise leave it widened rather than fail the whole rollback. A
-- one-way widening once the value has been used even once is the correct
-- semantics for an append-only table, not a workaround.
DO $garuda_285_narrow_policy_scope$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.visa_decision_retention_policies
         WHERE policy_scope = 'GARUDA_MAGIC_LINK'
    ) THEN
        RAISE NOTICE 'garuda 285 rollback: visa_decision_retention_policies has row(s) with policy_scope = ''GARUDA_MAGIC_LINK'' -- the append-only guard makes them impossible to remove, so the policy_scope CHECK is left WIDENED (285''s state) rather than narrowed back to pre-285''s list. This is a one-way widening, same as any append-only enum on this table.';
    ELSE
        ALTER TABLE public.visa_decision_retention_policies
            DROP CONSTRAINT IF EXISTS visa_decision_retention_policies_policy_scope_check;
        ALTER TABLE public.visa_decision_retention_policies
            ADD CONSTRAINT visa_decision_retention_policies_policy_scope_check
                CHECK (policy_scope IN ('VISA_DECISION', 'GARUDA_CHECK', 'GARUDA_ORDER'));
    END IF;
END;
$garuda_285_narrow_policy_scope$;
