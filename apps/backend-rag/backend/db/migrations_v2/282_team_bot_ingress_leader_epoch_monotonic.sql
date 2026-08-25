-- Migration 282: team_bot_ingress_leader_epoch_monotonic
-- (I DUE BOT, lane B5 -- cross-family refutation finding #7,
-- F9-CALLBACK-WRITE-FENCE-SPEC.md)
--
-- INTEGER BOUND PROVISIONALLY -- same LOCAL-FIRST renumbering convention as
-- 281's own header (LEGACY_PROMOTION_README.md). 282 is the correct next
-- integer against `feature/due-bot` at the time this file was written.
-- Renumber at final PR-train landing if another lane has since claimed 282.
--
-- Purpose
-- -------
-- Migration 281's own COMMENT ON TABLE claims "Written ONLY via
-- compare-and-swap (UPDATE ... WHERE leader_epoch = $expected) -- never a
-- bare UPDATE" -- a cross-family refuter (gpt-5.6-sol,
-- F9-REFUTATION-2026-08-25.md finding #7) correctly named this as a
-- COMMENT, not a CONSTRAINT: nothing in the schema stopped a bare UPDATE
-- from setting leader_epoch BACKWARDS. Application code
-- (ingress_leader.py, ingress_state_repo.py) only ever increments the
-- epoch or leaves it unchanged -- this migration makes that a schema-level
-- guarantee independent of the application ever staying correct.
--
-- A BEFORE UPDATE row-level trigger, not a CHECK constraint: a CHECK
-- constraint only ever sees the NEW row, never OLD -- comparing
-- NEW.leader_epoch against the PREVIOUS value requires a trigger. Rejects
-- ONLY a strict DECREASE (NEW.leader_epoch < OLD.leader_epoch) -- renew()
-- legitimately writes an UPDATE that leaves leader_epoch UNCHANGED (only
-- lease_expires_at moves), so the guard allows "same or greater", never
-- "strictly greater only".
--
-- Rollback marker convention: mandatory for migrations > 111 per
-- backend/db/migration_base.py:29.

CREATE OR REPLACE FUNCTION public.team_bot_ingress_leader_forbid_epoch_rollback()
RETURNS trigger AS $$
BEGIN
    IF NEW.leader_epoch < OLD.leader_epoch THEN
        RAISE EXCEPTION
            'team_bot_ingress_leader: leader_epoch may never decrease (record_id=%, old_epoch=%, attempted_new_epoch=%)',
            OLD.record_id, OLD.leader_epoch, NEW.leader_epoch;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER team_bot_ingress_leader_forbid_epoch_rollback_trg
    BEFORE UPDATE ON public.team_bot_ingress_leader
    FOR EACH ROW
    EXECUTE FUNCTION public.team_bot_ingress_leader_forbid_epoch_rollback();

COMMENT ON TRIGGER team_bot_ingress_leader_forbid_epoch_rollback_trg
    ON public.team_bot_ingress_leader IS
    'F9 refutation finding #7 -- DB-level backstop independent of application '
    'code: rejects any UPDATE that decreases leader_epoch. Allows unchanged '
    '(renew()) and increased (try_promote()) -- never allows a rollback.';

-- === ROLLBACK ===

DROP TRIGGER IF EXISTS team_bot_ingress_leader_forbid_epoch_rollback_trg ON public.team_bot_ingress_leader;
DROP FUNCTION IF EXISTS public.team_bot_ingress_leader_forbid_epoch_rollback();
