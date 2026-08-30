-- ============================================================================
-- 287_garuda_practices.sql
-- GARUDA VOA — L4 practice-serving (products/garuda-voa/LANES.md, L4 row).
--
-- MERGE-ORDER DEPENDENCY (flag for the orchestrator, same convention as
-- 284/285/286's own headers): numbered on top of 284 (L3 garuda_orders),
-- 285 (L4 magic-link), 286 (L2 check-results, open PR #4920 at the time
-- this file was written). Re-check `db/migrations_v2/` on BOTH `main` and
-- `feature/garuda-voa` immediately before merging this file -- renumber
-- rather than let two files claim the same number (cicatrix W40).
--
-- SCOPE (deliberately narrow -- see services/garuda_portal/practice.py's
-- module docstring for the full reasoning): this migration creates ONLY
-- what PR-01 needs (STATE-MACHINE.md line 84: "not_started -> Received,
-- system, OP-02 committed and its outbox event is consumed"). The staff
-- transition engine (PR-02..PR-11: begin review, block, submit, approve,
-- reject, resume, deliver) is NOT built here -- there is no staff UI, no
-- staff auth surface, and no staff endpoint anywhere in this codebase yet
-- to drive it, and building an unreachable write path is exactly the
-- "green mascherava organi morti" shape cicatrix-superscar.md family #2
-- warns against. This table's `state` column therefore accepts the FULL
-- STATE-MACHINE.md enum (so a later PR-02..PR-11 migration only needs to
-- ADD transition logic, never redefine the column) but only `Received` is
-- ever written by the code that ships with this migration.
--
-- RETENTION POLICY (SM-G01): deliberately does NOT introduce a new
-- `policy_scope` value (migration 281 defines exactly VISA_DECISION |
-- GARUDA_CHECK | GARUDA_ORDER -- no GARUDA_PRACTICE). A practice row is
-- created ONLY as a consequence of an order that has already passed the
-- GARUDA_ORDER policy gate at OP-00 (`garuda_orders.
-- active_garuda_order_policy_available`, migration 284), carries ZERO new
-- PII of its own (no email/phone/passport column -- those live only on
-- `garuda_orders`; see the applicant-PII comment on that table), and is
-- gated by a FOREIGN KEY to that same already-authorized order. This
-- mirrors how `garuda_order_journal`/`garuda_order_outbox`/
-- `garuda_payment_inbox` (284) are ALSO downstream artifacts of an
-- authorized order and are NOT independently retention-gated per row --
-- `garuda_practices` follows the identical precedent, not a new one.
-- ============================================================================

-- (1) Practice aggregate --------------------------------------------------

CREATE TABLE public.garuda_practices (
    practice_id             TEXT PRIMARY KEY
                             CHECK (practice_id ~ '^[A-Za-z0-9_-]{16,128}$'),
    order_id                TEXT NOT NULL UNIQUE
                             REFERENCES public.garuda_orders (order_id),
    -- STATE-MACHINE.md's full practice enum, `In_review` spelled with an
    -- underscore for identifier-safety (STATE-MACHINE.md: "`In_review` is
    -- rendered to customers as `In review`" -- the space-containing wire
    -- value is a presentation concern, translated at the API boundary in
    -- services/garuda_portal/practice.py, never stored literally).
    -- `not_started` is deliberately absent: a row only exists once PR-01
    -- has fired, so "not started" is represented by the ABSENCE of a row
    -- (the LEFT JOIN in practice.py), never a state value here.
    state                   TEXT NOT NULL DEFAULT 'Received'
                             CHECK (state IN ('Received', 'In_review', 'Blocked',
                                               'Submitted', 'Approved', 'Rejected',
                                               'Delivered')),
    -- PR-03/05/08 (block) and PR-07 (reject) fields. NULL until a staff
    -- transition (not shipped by this migration) sets them. Pattern-checked
    -- against the SAME closed-vocabulary regexes openapi.yaml's
    -- `BlockPracticeTransition`/`RejectPracticeTransition` schemas use, so
    -- this column can never hold a value the wire contract would reject.
    customer_reason_key     TEXT
                             CHECK (customer_reason_key IS NULL
                                    OR customer_reason_key ~ '^garuda_voa\.practice\.[a-z0-9_]+$'),
    required_action_key     TEXT
                             CHECK (required_action_key IS NULL
                                    OR required_action_key ~ '^garuda_voa\.action\.[a-z0-9_]+$'),
    -- PR-F04: never serialized to a customer surface. Staff-only, per
    -- BlockPracticeTransition/RejectPracticeTransition's own field comment.
    private_staff_note      TEXT,
    -- PR-03/05/08's stored resume target (PR-09 -> In_review, PR-10 ->
    -- Submitted). NULL unless `state = 'Blocked'`.
    resume_target           TEXT
                             CHECK (resume_target IS NULL
                                    OR resume_target IN ('In_review', 'Submitted')),
    -- PR-11 (deliver). NULL until a staff transition (not shipped here)
    -- releases the artifact. `artifact_available` is a separate boolean
    -- (not "artifact_id IS NOT NULL") because the contract's PracticeView
    -- names it as its own required field independent of any internal id
    -- shape ever changing.
    artifact_id             TEXT,
    artifact_digest         TEXT,
    artifact_available      BOOLEAN NOT NULL DEFAULT FALSE,
    -- PR-01's idempotency identity (STATE-MACHINE.md: "Retry idempotent:
    -- Yes -- paid journal event ID"): the `garuda_order_journal.event_id`
    -- of the `payment.paid`/OP-02 event that authorized this practice.
    -- UNIQUE makes "exactly one practice per paid order" structural, not a
    -- caller convention -- a second PR-01 attempt for the same OP-02 event
    -- (retry, redelivered outbox job) hits this constraint and the caller
    -- falls back to reading the existing row instead of inserting a
    -- second one.
    source_paid_journal_event_id TEXT NOT NULL UNIQUE
                             REFERENCES public.garuda_order_journal (event_id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),

    CHECK (
        (state = 'Blocked' AND resume_target IS NOT NULL)
        OR (state <> 'Blocked' AND resume_target IS NULL)
    ),
    CHECK (
        (state = 'Delivered') = (artifact_id IS NOT NULL AND artifact_digest IS NOT NULL)
    )
);

COMMENT ON TABLE public.garuda_practices IS
    'GARUDA VOA practice aggregate (STATE-MACHINE.md practice half). One row per order, created by PR-01 once the order is authoritatively paid. Absence of a row for a paid order means PR-01 has not yet run (lazily materialized in services/garuda_portal/practice.py), never a persisted not_started state.';
COMMENT ON COLUMN public.garuda_practices.private_staff_note IS
    'PR-F04: never serialized to any customer-facing response. Staff-only.';
COMMENT ON COLUMN public.garuda_practices.source_paid_journal_event_id IS
    'PR-01 idempotency key: the OP-02 payment.paid journal event that authorized this practice. UNIQUE enforces exactly-one-practice-per-paid-order at the database, not just in application code.';

CREATE INDEX idx_garuda_practices_order_id
    ON public.garuda_practices (order_id);

-- Defense-in-depth CAS guard (SM-G07), same shape as garuda_orders' own
-- trigger (284): the app layer's INSERT is the only write this migration's
-- shipped code performs, but a future staff-transition UPDATE must not be
-- able to skip the forbidden-transition matrix by writing directly. Only
-- the two edges PR-01's own code can ever produce are relevant today
-- (INSERT establishing `Received`, and no UPDATE at all) -- this trigger
-- is written against STATE-MACHINE.md's FULL forbidden-practice-transition
-- table now so a later PR-02..PR-11 migration does not have to touch it.
CREATE OR REPLACE FUNCTION public.guard_garuda_practice_state_transition()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $func$
DECLARE
    forbidden BOOLEAN;
BEGIN
    IF OLD.state = NEW.state THEN
        RETURN NEW; -- PR-12 no-op / non-state-changing update
    END IF;
    forbidden := CASE
        WHEN OLD.state = 'Received' AND NEW.state IN ('Submitted', 'Approved', 'Delivered', 'Rejected') THEN TRUE
        WHEN OLD.state = 'In_review' AND NEW.state IN ('Received', 'Approved', 'Delivered', 'Rejected') THEN TRUE
        WHEN OLD.state = 'Submitted' AND NEW.state IN ('Received', 'In_review', 'Delivered') THEN TRUE
        WHEN OLD.state = 'Approved' AND NEW.state IN ('Received', 'In_review', 'Submitted', 'Blocked', 'Rejected') THEN TRUE
        WHEN OLD.state = 'Delivered' THEN TRUE
        WHEN OLD.state = 'Blocked' AND NEW.state IN ('Received', 'Approved', 'Delivered', 'Rejected') THEN TRUE
        WHEN OLD.state = 'Blocked' AND NEW.state IN ('In_review', 'Submitted') AND NEW.state <> OLD.resume_target THEN TRUE
        WHEN OLD.state = 'Rejected' THEN TRUE
        ELSE FALSE
    END;
    IF forbidden THEN
        RAISE EXCEPTION 'garuda_practices: forbidden transition % -> %', OLD.state, NEW.state
            USING ERRCODE = '23514';
    END IF;
    NEW.updated_at := statement_timestamp();
    RETURN NEW;
END;
$func$;

CREATE TRIGGER trg_guard_garuda_practice_state_transition
BEFORE UPDATE ON public.garuda_practices
FOR EACH ROW EXECUTE FUNCTION public.guard_garuda_practice_state_transition();

-- === ROLLBACK ===

-- This section deliberately runs the destructive teardown for local/CI
-- rollback only; it is never applied to a live database by the migration
-- runner's forward path.
DROP TRIGGER IF EXISTS trg_guard_garuda_practice_state_transition ON public.garuda_practices;
DROP FUNCTION IF EXISTS public.guard_garuda_practice_state_transition();
DROP TABLE IF EXISTS public.garuda_practices;
