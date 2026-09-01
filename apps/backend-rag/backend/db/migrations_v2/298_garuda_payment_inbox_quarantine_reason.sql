-- 298_garuda_payment_inbox_quarantine_reason.sql
--
-- THE DEFECT (measured 2026-08-29 on origin/main @ 22dabc1166).
-- `garuda_payment_inbox.outcome = 'quarantined'` is a WRITE-ONLY state.
-- Five call sites in `services/garuda_orders/repository.py` SET it (lines
-- 389, 406, 540, 580, 649) and `git grep -n "FROM garuda_payment_inbox"`
-- returns exactly ONE line in the whole tree — a test
-- (`test_funnel_end_to_end_http.py:655`). Five writers, one reader, and
-- the reader is a test.
--
-- WHAT THAT MEANS IN MONEY. A quarantined row is an authentic,
-- signature-valid provider callback that we DELIBERATELY REFUSED TO ACT
-- ON: it could not be tied to exactly one order, or it claimed a PAID
-- event for the wrong amount. The router answers 204 either way
-- (`garuda_orders_router.py::receive_payment_webhook` is declared
-- `status_code=204` and discards the handler's return value), so Xendit
-- records a successful delivery and stops retrying. Somebody's money
-- moved, we declined to reconcile it, and nothing pages anyone.
--
-- WHY A COLUMN AND NOT JUST A READER. The three quarantine causes in
-- `handle_paid_event` alone are genuinely different incidents with
-- different cures — an unknown checkout session, a wrong-amount charge,
-- and an order that never reached `awaiting_payment` — and they all
-- collapse into one indistinguishable `outcome` value. An alarm built on
-- today's schema could only say "3 events quarantined, cause unknown",
-- which is the half-cure this subsystem keeps producing. The reason is
-- recorded at the moment the decision is made, where it is known for
-- certain, rather than re-derived later by a reader that would have to
-- guess.
--
-- NO PII, BY CONSTRUCTION. A closed four-value vocabulary, enforced by
-- CHECK. The observed-vs-expected amounts are deliberately NOT stored
-- here: `amount_mismatch` plus the row's existing `provider_event_id`
-- and `order_id` is enough for a human to open the charge in the Xendit
-- console, and an unbounded suffix would break the closed vocabulary a
-- CHECK constraint exists to enforce (migration 297's own reasoning for
-- storing `secret_egress:<pattern>` as a bare code).
--
-- NULLABLE, DELIBERATELY. Any row quarantined before this migration has
-- no recorded reason and never will — inventing one would be a
-- fabrication. The reader renders NULL as `unrecorded` and the alarm
-- still pages on it; a cause-less page is worse than a caused one and
-- far better than silence.
--
-- SCOPE: this migration adds one nullable column, its CHECK, and the
-- partial index the alarm's windowed query needs. It changes no existing
-- column, no constraint on `outcome`, and no behaviour. The reader and
-- the alarm that consume it ship in the same PR; the two smaller
-- findings from the same measurement (`outcome='received'` is
-- unreachable as a persisted state; "received but never processed" is
-- undetectable BY DESIGN because the inbox INSERT shares the handler's
-- transaction) are ledgered in PENDING-ARMS, not fixed here — the second
-- one is a documented tradeoff that buys a clean provider retry, and
-- "fixing" it would be a regression.

ALTER TABLE public.garuda_payment_inbox
    ADD COLUMN IF NOT EXISTS quarantine_reason TEXT;

ALTER TABLE public.garuda_payment_inbox
    DROP CONSTRAINT IF EXISTS garuda_payment_inbox_quarantine_reason_check;
ALTER TABLE public.garuda_payment_inbox
    ADD CONSTRAINT garuda_payment_inbox_quarantine_reason_check
    CHECK (quarantine_reason IS NULL OR quarantine_reason IN (
        -- No `garuda_orders` row carries this event's provider_session_id.
        'unmatched_session',
        -- Authentic PAID event whose amount or currency is not the order's
        -- frozen `price_idr` / IDR. A signed webhook is authentic about WHO
        -- paid, never about HOW MUCH (SM-G09/OP-F03).
        'amount_mismatch',
        -- The order exists but is still `created`: its checkout session was
        -- never bound, so a payment against it is unreconcilable.
        'session_not_bound',
        -- The order exists and its state does not admit this event kind
        -- (e.g. a failure event for an order that is not awaiting payment).
        'unexpected_state'
    ));

COMMENT ON COLUMN public.garuda_payment_inbox.quarantine_reason IS
    'Why an authentic provider callback was refused. NULL for rows quarantined before migration 298, and for every non-quarantined row. Read by services/garuda_orders/payment_inbox_watch.py.';

-- Supports the alarm's windowed query, which runs every 300s forever from
-- the GARUDA outbox scheduler. Partial: quarantined rows are the rare case
-- and the only ones this index ever has to answer for.
CREATE INDEX IF NOT EXISTS idx_garuda_payment_inbox_quarantined
    ON public.garuda_payment_inbox (processed_at)
    WHERE outcome = 'quarantined';

-- === ROLLBACK ===

-- This section deliberately runs the destructive teardown for local/CI
-- rollback only; it is never applied to a live database by the migration
-- runner's forward path.
DROP INDEX IF EXISTS public.idx_garuda_payment_inbox_quarantined;
ALTER TABLE public.garuda_payment_inbox
    DROP CONSTRAINT IF EXISTS garuda_payment_inbox_quarantine_reason_check;
ALTER TABLE public.garuda_payment_inbox
    DROP COLUMN IF EXISTS quarantine_reason;
