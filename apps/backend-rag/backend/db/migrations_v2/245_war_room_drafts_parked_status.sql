-- Migration 245: war_room_drafts status CHECK -- add 'parked' (WR2 B2 backstop)
--
-- Purpose:
--   scripts/wr2_draft_generator.py (2026-07-17, B2 "refuse-to-guess" backstop)
--   now sets status='parked' on a news-shaped draft that has NO usable source
--   content anywhere (empty article_summary AND an enrichment object whose only
--   "facts" came from wr2_grounding.py's citation-only injection). Without this
--   migration the UPDATE in _mark_parked() is rejected outright by
--   war_room_drafts_status_check (verified live on prod, 2026-07-17: the
--   constraint's current ARRAY does not include 'parked') -- the code fix alone
--   is inert without this.
--
-- 'parked' is terminal + human-attended, same shape as the existing 'rejected'
-- value (also registered in wr2_supervisor.TRANSITIONS and
-- wr2_supervisor_watchdog.TERMINAL_STATUSES in the same PR, cicatrix #9 --
-- a status introduced on one side of an inter-service contract without
-- updating every participant is exactly the schema-drift disease that family
-- catalogs).
--
-- Mirrors migration 222/163 exact shape: DROP CONSTRAINT IF EXISTS -> ADD
-- CONSTRAINT ... CHECK (status = ANY (ARRAY[...]::text)) NOT VALID -> separate
-- VALIDATE CONSTRAINT. NOTE (2026-07-17 red-team finding #5, corrected): this
-- two-step shape is inherited convention from 222/163, not a genuine
-- lock-avoidance mechanism here -- backend/db/migration_base.py wraps a
-- migration's forward SQL in a SINGLE transaction, so both ALTER TABLE
-- statements commit together and the constraint-validation lock is held
-- until that one transaction commits regardless of the NOT VALID split (the
-- usual NOT VALID benefit -- letting VALIDATE run in ITS OWN later
-- transaction with a lighter lock -- requires the two statements to be
-- separate transactions, which this runner does not do). Kept as-is because
-- lock duration is trivial on this table's current row count, not because
-- it avoids ACCESS EXCLUSIVE.

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
        'drafts_imaged_facted'::text,
        'drafts_imaged_checked'::text,
        'fact_check_failed'::text,
        'image_failed'::text,
        'rendering'::text,
        'rendered'::text,
        'render_failed'::text,
        'rendered_shadow'::text,
        'pending_review'::text,
        'approved'::text,
        'rejected'::text,
        'published'::text,
        'missed'::text,
        'parked'::text
    ]))
    NOT VALID;

ALTER TABLE war_room_drafts
    VALIDATE CONSTRAINT war_room_drafts_status_check;

-- === ROLLBACK ===
-- Revert rows parked by the B2 backstop to 'rejected' (closest existing
-- terminal/human-attended state) BEFORE shrinking the constraint, else
-- VALIDATE fails on existing 'parked' rows.
UPDATE war_room_drafts SET status = 'rejected'
 WHERE status = 'parked';

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
        'drafts_imaged_facted'::text,
        'drafts_imaged_checked'::text,
        'fact_check_failed'::text,
        'image_failed'::text,
        'rendering'::text,
        'rendered'::text,
        'render_failed'::text,
        'rendered_shadow'::text,
        'pending_review'::text,
        'approved'::text,
        'rejected'::text,
        'published'::text,
        'missed'::text
    ]))
    NOT VALID;

ALTER TABLE war_room_drafts
    VALIDATE CONSTRAINT war_room_drafts_status_check;
