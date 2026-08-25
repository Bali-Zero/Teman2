-- ============================================================================
-- 282_garuda_orders.sql
-- GARUDA VOA — L3 checkout + orders (products/garuda-voa/LANES.md).
--
-- MERGE-ORDER DEPENDENCY (flag for the orchestrator): this migration is
-- numbered on top of L1's 281_garuda_voa_retention.sql, which introduces
-- the `policy_scope` column (VISA_DECISION | GARUDA_CHECK | GARUDA_ORDER)
-- on `visa_decision_retention_policies` that `active_garuda_order_policy_
-- available()` below reads. As of this commit 281 exists only on
-- agent/air-m5/backend-rag/garuda-l1-retention-0824, not yet on
-- feature/garuda-voa (LANES.md's own prerequisite chain: "L1 must MERGE
-- before any lane persists a row"). If a different migration lands as 281
-- on the integration branch before this one, RENUMBER this file before
-- merging it -- do not let two files claim the same number (cicatrix W40).
--
-- Five artifacts, one file, disjoint from every other lane's ownership
-- (L3 owns services/garuda_orders/**, services/payments/**, and -- for
-- persistence -- this migration):
--   1. garuda_orders            -- the order/payment aggregate (STATE-MACHINE.md)
--   2. garuda_order_idempotency -- customer-command replay cache (262's pattern)
--   3. garuda_payment_inbox     -- durable webhook dedup (inbound_webhook_repo's
--                                 ON CONFLICT DO NOTHING pattern, provider-scoped)
--   4. garuda_order_journal     -- append-only EventEnvelope journal (events.yaml)
--   5. garuda_order_outbox      -- transactional outbox for customer emails
--
-- SM-G04 (frozen contract): `price_idr` is written ONCE at OP-00 from
-- `garuda_flow.pricing.price_for_case` and never recomputed or split. No
-- column here may ever represent a fee/PNBP/component -- enforced by the
-- same `test_the_price_is_one_field_and_never_a_computation` contract test
-- lane L3 does not own, but this schema must never give it something to
-- catch: exactly one price_idr integer, nothing else.
-- ============================================================================

-- (1) Order / payment aggregate ------------------------------------------------

CREATE TABLE public.garuda_orders (
    order_id                TEXT PRIMARY KEY
                             CHECK (order_id ~ '^[A-Za-z0-9_-]{16,128}$'),
    result_id_ref           TEXT NOT NULL
                             CHECK (result_id_ref ~ '^[A-Za-z0-9_-]{16,128}$'),
    -- Soft reference by design: garuda_voa_checks is L2's evolving table
    -- and this product's public result identifier is not yet the same
    -- shape as the historical `hash` PK (SM-G02: >=128 effective bits vs
    -- the legacy VARCHAR(20)). L3 validates existence through the
    -- orchestrator-wired EligibilityCheckLookup port at the app layer
    -- (services/garuda_orders/ports.py), not a cross-lane FK.
    case_type               TEXT NOT NULL CHECK (case_type IN ('issuance', 'extension')),

    -- Applicant (Q3/contract Applicant schema) -- the ONLY PII this lane
    -- persists, required to build the practice; never returned by a public
    -- GET beyond what OrderView's contract-frozen shape allows.
    applicant_full_name     TEXT NOT NULL,
    applicant_email         TEXT NOT NULL,
    applicant_phone         TEXT NOT NULL,
    applicant_passport_number TEXT NOT NULL,

    price_idr               INT NOT NULL CHECK (price_idr > 0),
    price_catalogue_key     TEXT NOT NULL,

    state                   TEXT NOT NULL DEFAULT 'created'
                             CHECK (state IN ('created', 'awaiting_payment', 'paid',
                                               'failed', 'expired', 'refunded')),

    provider                TEXT NOT NULL DEFAULT 'xendit',
    provider_session_id     TEXT UNIQUE,
    provider_charge_id      TEXT,
    checkout_expires_at     TIMESTAMPTZ,

    browser_observation     TEXT NOT NULL DEFAULT 'browser_not_returned'
                             CHECK (browser_observation IN ('browser_not_returned',
                                                             'browser_return_observed')),
    browser_return_nonce    TEXT,

    -- OP-F05 / Q2 / Q10 remediation case. Exactly one open case per order
    -- at a time (a second late `paid` on an already-open case is OP-09, not
    -- a second case) and exactly two resolutions, never a third.
    late_case_open          BOOLEAN NOT NULL DEFAULT FALSE,
    late_case_resolution    TEXT
                             CHECK (late_case_resolution IN ('honoured', 'refunded_in_full')),
    late_case_staff_reference TEXT,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    CHECK (
        (late_case_open = FALSE AND late_case_resolution IS NULL)
        OR (late_case_open = TRUE AND late_case_resolution IS NULL)
        OR (late_case_open = FALSE AND late_case_resolution IS NOT NULL)
    )
);

COMMENT ON TABLE public.garuda_orders IS
    'GARUDA VOA order/payment aggregate (STATE-MACHINE.md order half). One row per checkout.';
COMMENT ON COLUMN public.garuda_orders.price_idr IS
    'SM-G04: the ONE all-inclusive integer IDR price, frozen at OP-00. Never a fee/PNBP component.';
COMMENT ON COLUMN public.garuda_orders.late_case_open IS
    'OP-F05 remediation case (Q2/Q10). Closed exclusively by resolveLateOrder -- honoured or refunded_in_full, never neither.';

CREATE INDEX idx_garuda_orders_state_checkout_expiry
    ON public.garuda_orders (state, checkout_expires_at)
    WHERE state = 'awaiting_payment';

CREATE INDEX idx_garuda_orders_result_id_ref
    ON public.garuda_orders (result_id_ref);

-- Defense-in-depth CAS guard (SM-G07): the app layer already does
-- `UPDATE ... WHERE order_id = $1 AND state = $2`, but a trigger closes the
-- gap for any future direct write that skips the app layer.
CREATE OR REPLACE FUNCTION public.guard_garuda_order_state_transition()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $func$
DECLARE
    forbidden BOOLEAN;
BEGIN
    IF OLD.state = NEW.state THEN
        RETURN NEW; -- OP-09 no-op / non-state-changing update (e.g. browser observation)
    END IF;
    forbidden := CASE
        WHEN OLD.state = 'created' AND NEW.state IN ('paid', 'refunded', 'failed', 'expired') THEN TRUE
        WHEN OLD.state = 'awaiting_payment' AND NEW.state = 'created' THEN TRUE
        WHEN OLD.state = 'paid' AND NEW.state IN ('created', 'awaiting_payment', 'failed', 'expired') THEN TRUE
        WHEN OLD.state = 'refunded' THEN TRUE
        WHEN OLD.state = 'failed' AND NEW.state IN ('created', 'awaiting_payment', 'paid', 'refunded') THEN TRUE
        WHEN OLD.state = 'expired' AND NEW.state IN ('created', 'awaiting_payment', 'paid', 'refunded') THEN TRUE
        ELSE FALSE
    END;
    IF forbidden THEN
        RAISE EXCEPTION 'garuda_orders: forbidden transition % -> %', OLD.state, NEW.state
            USING ERRCODE = '23514';
    END IF;
    NEW.updated_at := statement_timestamp();
    RETURN NEW;
END;
$func$;

CREATE TRIGGER trg_guard_garuda_order_state_transition
BEFORE UPDATE ON public.garuda_orders
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_order_state_transition();

-- (1a) GARUDA_ORDER retention authority read -- SM-G01 / OP-F07 -----------------
-- Mirrors garuda_flow.retention.active_garuda_check_policy_available exactly
-- (same table, GARUDA_ORDER scope instead of GARUDA_CHECK -- L1's migration
-- 281 already widened the CHECK constraint to admit this value). This reads
-- L1's shared authority table; it does NOT modify or duplicate it, and it is
-- not a second retention authority (ARCHITECTURE.md D2).
CREATE OR REPLACE FUNCTION public.active_garuda_order_policy_available(
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
      AND policy_scope = 'GARUDA_ORDER'
      AND effective_period @> p_created_at;
$func$;

COMMENT ON FUNCTION public.active_garuda_order_policy_available IS
    'SM-G01 read for OP-00: one Zero-approved GARUDA_ORDER policy must cover this clock, or the funnel fails closed (PERSISTENCE_POLICY_UNAVAILABLE).';

-- (2) Customer-command idempotency ---------------------------------------------
-- Same shape as 262_visa_evaluate_idempotency.sql, generalized to any
-- garuda_orders customer command (OP-00 createOrder, OP-07 browser return
-- observation). Scoped by actor+operation at the Python layer before
-- hashing -- see repository.py::_idempotency_key_sha256.

CREATE TABLE public.garuda_order_idempotency (
    key_sha256              BYTEA PRIMARY KEY CHECK (octet_length(key_sha256) = 32),
    canonical_payload_sha256 BYTEA NOT NULL CHECK (octet_length(canonical_payload_sha256) = 32),
    -- Set as soon as the order row exists, BEFORE the external provider
    -- call — lets a crashed/retried attempt resume from "order exists,
    -- checkout session pending" instead of either re-creating the order
    -- or being stuck as a permanent in-flight reservation.
    order_id                TEXT REFERENCES public.garuda_orders (order_id),
    response_status         INT,
    response_body           JSONB,
    completed_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    expires_at              TIMESTAMPTZ NOT NULL DEFAULT (statement_timestamp() + INTERVAL '30 days'),
    CHECK (expires_at > created_at),
    CHECK (
        (response_body IS NULL AND response_status IS NULL AND completed_at IS NULL)
        OR (response_body IS NOT NULL AND response_status IS NOT NULL AND completed_at IS NOT NULL)
    )
);

COMMENT ON TABLE public.garuda_order_idempotency IS
    'Idempotency-Key replay cache for garuda_orders customer commands (OP-00, OP-07). Raw keys never stored -- only their SHA-256.';

CREATE INDEX idx_garuda_order_idempotency_expires_at
    ON public.garuda_order_idempotency (expires_at);

CREATE OR REPLACE FUNCTION public.guard_garuda_order_idempotency_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $func$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF clock_timestamp() < OLD.expires_at THEN
            RAISE EXCEPTION 'unexpired garuda_order_idempotency rows are immutable';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.key_sha256 IS DISTINCT FROM NEW.key_sha256
       OR OLD.canonical_payload_sha256 IS DISTINCT FROM NEW.canonical_payload_sha256
       OR OLD.created_at IS DISTINCT FROM NEW.created_at
       OR OLD.expires_at IS DISTINCT FROM NEW.expires_at THEN
        RAISE EXCEPTION 'garuda_order_idempotency request binding is immutable';
    END IF;
    IF OLD.order_id IS NOT NULL AND NEW.order_id IS DISTINCT FROM OLD.order_id THEN
        RAISE EXCEPTION 'garuda_order_idempotency order_id is immutable once bound';
    END IF;
    IF OLD.response_body IS NOT NULL THEN
        RAISE EXCEPTION 'completed garuda_order_idempotency rows are immutable';
    END IF;
    -- Two permitted UPDATE shapes on an incomplete row: (a) bind order_id
    -- only, as soon as the order exists but before the provider call —
    -- response fields stay NULL; (b) complete, with all three response
    -- fields set together. Anything in between (some-but-not-all response
    -- fields set) is the one shape this guards against.
    IF NEW.response_body IS NULL AND NEW.response_status IS NULL AND NEW.completed_at IS NULL THEN
        RETURN NEW;
    END IF;
    IF NEW.response_body IS NULL OR NEW.response_status IS NULL OR NEW.completed_at IS NULL THEN
        RAISE EXCEPTION 'garuda_order_idempotency completion must be atomic';
    END IF;
    RETURN NEW;
END;
$func$;

CREATE TRIGGER trg_guard_garuda_order_idempotency_mutation
BEFORE UPDATE OR DELETE ON public.garuda_order_idempotency
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_order_idempotency_mutation();

-- (3) Payment webhook inbox (durable dedup) ------------------------------------
-- OP-F02/OP-F03/OP-08/OP-09: a provider event is durably recorded exactly
-- once per (provider, provider_event_id), whatever it reconciles to. The
-- inbox row is the source of truth for "have we seen this event", separate
-- from whatever business state it produced.

CREATE TABLE public.garuda_payment_inbox (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    provider                TEXT NOT NULL,
    provider_event_id       TEXT NOT NULL,
    canonical_payload_sha256 BYTEA NOT NULL CHECK (octet_length(canonical_payload_sha256) = 32),
    order_id                TEXT REFERENCES public.garuda_orders (order_id),
    transition_id           TEXT,
    outcome                 TEXT NOT NULL DEFAULT 'received'
                             CHECK (outcome IN ('received', 'committed', 'quarantined', 'rejected')),
    received_at             TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    processed_at            TIMESTAMPTZ,
    UNIQUE (provider, provider_event_id)
);

COMMENT ON TABLE public.garuda_payment_inbox IS
    'Durable webhook dedup inbox. UNIQUE (provider, provider_event_id) is the OP-09 duplicate-delivery guard.';

CREATE INDEX idx_garuda_payment_inbox_order_id
    ON public.garuda_payment_inbox (order_id);

-- (4) Append-only domain event journal -----------------------------------------
-- Mirrors events.yaml's EventEnvelope. `transition_id` is validated against
-- the SAME closed enum the frozen contract admits (including OP-F04/OP-F05,
-- DECISIONS.md Q10) so a journal row can never name a transition the wire
-- contract does not recognise.

CREATE TABLE public.garuda_order_journal (
    event_id                TEXT PRIMARY KEY CHECK (event_id ~ '^[A-Za-z0-9_-]{16,128}$'),
    event_name              TEXT NOT NULL,
    occurred_at             TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    aggregate_type          TEXT NOT NULL CHECK (aggregate_type IN ('order', 'practice')),
    aggregate_id            TEXT NOT NULL,
    transition_id           TEXT NOT NULL
                             CHECK (transition_id IN (
                                 'OP-00', 'OP-01', 'OP-02', 'OP-03', 'OP-04', 'OP-05', 'OP-06',
                                 'OP-07', 'OP-08', 'OP-09', 'OP-F04', 'OP-F05',
                                 'PR-01', 'PR-02', 'PR-03', 'PR-04', 'PR-05', 'PR-06', 'PR-07',
                                 'PR-08', 'PR-09', 'PR-10', 'PR-11', 'PR-12'
                             )),
    idempotency_key_digest  BYTEA CHECK (idempotency_key_digest IS NULL OR octet_length(idempotency_key_digest) = 32),
    canonical_payload_digest BYTEA CHECK (canonical_payload_digest IS NULL OR octet_length(canonical_payload_digest) = 32),
    customer_visible        BOOLEAN NOT NULL,
    -- PII-free by construction: only enums, ids, amounts, and dates that are
    -- already public per the contract may go here -- never applicant fields.
    detail                  JSONB NOT NULL DEFAULT '{}'::jsonb
);

COMMENT ON TABLE public.garuda_order_journal IS
    'Append-only EventEnvelope journal (events.yaml). No PII in detail -- enums/ids/amounts/dates only.';

CREATE INDEX idx_garuda_order_journal_aggregate
    ON public.garuda_order_journal (aggregate_type, aggregate_id, occurred_at);

CREATE OR REPLACE FUNCTION public.guard_garuda_order_journal_append_only()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $func$
BEGIN
    RAISE EXCEPTION 'garuda_order_journal is append-only -- % is forbidden', TG_OP
        USING ERRCODE = '23514';
END;
$func$;

CREATE TRIGGER trg_guard_garuda_order_journal_append_only
BEFORE UPDATE OR DELETE ON public.garuda_order_journal
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_order_journal_append_only();

-- (5) Transactional outbox (customer emails / downstream work) ----------------
-- Deliberately its own small table rather than the generic `events_outbox`
-- (services/events/outbox.py): that table is the EventBus's PG LISTEN/NOTIFY
-- replay layer for internal pub/sub, a different consumer and a different
-- delivery contract than "send exactly one customer email per commuted
-- state change" (SM-G07/PR-0x "outbox ... email once").

CREATE TABLE public.garuda_order_outbox (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id                TEXT NOT NULL REFERENCES public.garuda_orders (order_id),
    journal_event_id        TEXT NOT NULL REFERENCES public.garuda_order_journal (event_id),
    job_type                TEXT NOT NULL,
    payload                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    dispatched_at           TIMESTAMPTZ,
    attempts                INT NOT NULL DEFAULT 0,
    UNIQUE (journal_event_id, job_type)
);

COMMENT ON TABLE public.garuda_order_outbox IS
    'Transactional outbox: written in the same transaction as its journal_event_id. UNIQUE(journal_event_id, job_type) makes "email once" structural.';

CREATE INDEX idx_garuda_order_outbox_undispatched
    ON public.garuda_order_outbox (created_at)
    WHERE dispatched_at IS NULL;

-- === ROLLBACK ===

-- squawk-ignore: prefer-robust-stmts -- this section deliberately runs the
-- destructive teardown for local/CI rollback only; it is never applied to
-- a live database by the migration runner's forward path.
DROP TABLE IF EXISTS public.garuda_order_outbox;
DROP TRIGGER IF EXISTS trg_guard_garuda_order_journal_append_only ON public.garuda_order_journal;
DROP FUNCTION IF EXISTS public.guard_garuda_order_journal_append_only();
DROP TABLE IF EXISTS public.garuda_order_journal;
DROP TABLE IF EXISTS public.garuda_payment_inbox;
DROP TRIGGER IF EXISTS trg_guard_garuda_order_idempotency_mutation ON public.garuda_order_idempotency;
DROP FUNCTION IF EXISTS public.guard_garuda_order_idempotency_mutation();
DROP TABLE IF EXISTS public.garuda_order_idempotency;
DROP FUNCTION IF EXISTS public.active_garuda_order_policy_available(TEXT, TIMESTAMPTZ);
DROP TRIGGER IF EXISTS trg_guard_garuda_order_state_transition ON public.garuda_orders;
DROP FUNCTION IF EXISTS public.guard_garuda_order_state_transition();
DROP TABLE IF EXISTS public.garuda_orders;
