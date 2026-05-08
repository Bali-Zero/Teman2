-- Migration 163: war_room_drafts.status — extend CHECK constraint
-- to accept fact-stages values used by the B-bis chain (mig 162 + PR #533).
--
-- Sprint B B-bis (PR #533) restored the fact-extractor / fact-checker
-- pipeline. The supervisor TRANSITIONS now route:
--   drafts_imaged → drafts_imaged_facted (fact-extractor)
--   drafts_imaged_facted → drafts_imaged_checked (fact-checker)
-- but the existing `war_room_drafts_status_check` from mig 112 only
-- accepted values up to 'drafts_imaged' / 'fact_check_failed'.
--
-- Live failure 2026-05-08 09:28 WITA after Pro restart of the
-- supervisor with the new TRANSITIONS:
--   asyncpg.exceptions.CheckViolationError: new row for relation
--   "war_room_drafts" violates check constraint
--   "war_room_drafts_status_check"
--   DETAIL: ... drafts_imaged_facted ...
--
-- DB on Pro hotfixed manually 09:30 WITA so the pipeline could resume.
-- This migration is the durable fix that lands on Fly Postgres at the
-- next deploy via `run-sql-v2-migrations-post-deploy`.
--
-- Squawk: DROP CONSTRAINT + ADD CONSTRAINT NOT VALID + VALIDATE in
-- two steps so we never hold ACCESS EXCLUSIVE while scanning the
-- table (low-risk on this small table but safe-by-default).

-- =====================================================================
-- 1. Drop the old constraint (idempotent via IF EXISTS)
-- =====================================================================

ALTER TABLE war_room_drafts
    DROP CONSTRAINT IF EXISTS war_room_drafts_status_check;

-- =====================================================================
-- 2. Add the extended constraint (NOT VALID first, then VALIDATE)
-- =====================================================================

ALTER TABLE war_room_drafts
    ADD CONSTRAINT war_room_drafts_status_check
    CHECK (status = ANY (ARRAY[
        'briefed'::text,
        'briefed_facted'::text,
        'researched'::text,
        'concept'::text,
        'drafts'::text,
        'drafts_checked'::text,
        'drafts_imaged'::text,
        'drafts_imaged_facted'::text,
        'drafts_imaged_checked'::text,
        'fact_check_failed'::text,
        'image_failed'::text,
        'rendered'::text,
        'pending_review'::text,
        'approved'::text,
        'rejected'::text,
        'published'::text,
        'missed'::text
    ]))
    NOT VALID;

ALTER TABLE war_room_drafts
    VALIDATE CONSTRAINT war_room_drafts_status_check;

-- === ROLLBACK ===
-- Restore the pre-163 constraint (status set without the two new
-- fact-stage values). Any drafts already in the new states would
-- violate the rollback constraint VALIDATE pass, so the rollback
-- script preemptively reverts them to 'drafts_imaged' (the parent
-- state that produced them). This is a soft rollback — the work
-- product (claims in fact_check_json) is preserved; only the status
-- gauge resets.

UPDATE war_room_drafts
   SET status = 'drafts_imaged'
 WHERE status IN ('drafts_imaged_facted', 'drafts_imaged_checked');

ALTER TABLE war_room_drafts
    DROP CONSTRAINT IF EXISTS war_room_drafts_status_check;

ALTER TABLE war_room_drafts
    ADD CONSTRAINT war_room_drafts_status_check
    CHECK (status = ANY (ARRAY[
        'briefed'::text,
        'briefed_facted'::text,
        'researched'::text,
        'concept'::text,
        'drafts'::text,
        'drafts_checked'::text,
        'drafts_imaged'::text,
        'fact_check_failed'::text,
        'image_failed'::text,
        'rendered'::text,
        'pending_review'::text,
        'approved'::text,
        'rejected'::text,
        'published'::text,
        'missed'::text
    ]))
    NOT VALID;

ALTER TABLE war_room_drafts
    VALIDATE CONSTRAINT war_room_drafts_status_check;
