-- Migration 162: war_room fact-check columns
--
-- Sprint B B-bis (2026-05-08): re-enable the fact-extractor + fact-checker
-- pipeline stages between image-generator and canva-apply.
--
-- Background: PR #299 (26 Apr) cut over the old 5-cron WR2 chain to the
-- supervisor-driven event bus. fact-extractor + fact-checker plists
-- moved to ~/Library/LaunchAgents/.disabled/ as a stop-gap because the
-- TRANSITIONS dict still routed through them while their executable
-- scripts (`scripts/wr2_fact_extractor.py`, `scripts/wr2_fact_checker.py`)
-- did NOT exist on disk → silent kickstart failure → drafts stuck.
--
-- This migration adds the columns the new (NET-NEW, B-bis) executables
-- need: a JSONB blob for extracted claims + verification details, a
-- TEXT status (NULL until ran, then pass/fail/degraded), and a
-- TIMESTAMPTZ for the fact-check event.
--
-- Decisions:
--   * fact_check_json JSONB — unstructured because the claim shape will
--     evolve (add per-claim sources, NB-INTEL doc IDs, confidence). A
--     dedicated table per claim was rejected: 1 draft × 5-15 claims is
--     small; querying a JSONB array via fact_check_json->'claims' is
--     fine for the daily volume.
--   * fact_check_status TEXT (CHECK NULL/pass/fail/degraded) — explicit
--     over enum so adding states later (e.g. 'manual_review') is a
--     CHECK-constraint diff instead of an ALTER TYPE migration.
--   * fact_check_at TIMESTAMPTZ — wall-clock when fact-checker finished
--     (NOT when extractor ran; extractor result lives in fact_check_json
--     timestamps if needed).
--
-- Squawk: ADD COLUMN nullable on a populated table is safe (no rewrite,
-- no ACCESS EXCLUSIVE upgrade). The CHECK constraint is added with
-- NOT VALID + VALIDATE in two steps so the initial ADD doesn't scan the
-- table; new rows are checked from inception, the validation pass scans
-- without blocking writes.
--
-- ROLLBACK: drop the three columns. Any populated fact_check_json data
-- is lost — by design, fact-check artifacts are reproducible from the
-- source draft. Status downgrade ('drafts_imaged_checked' → 'drafts_imaged')
-- is handled by the supervisor TRANSITIONS revert in this same PR, NOT
-- here.

-- =====================================================================
-- 1. Add columns
-- =====================================================================

ALTER TABLE war_room_drafts
    ADD COLUMN IF NOT EXISTS fact_check_json JSONB DEFAULT NULL;

ALTER TABLE war_room_drafts
    ADD COLUMN IF NOT EXISTS fact_check_status TEXT DEFAULT NULL;

ALTER TABLE war_room_drafts
    ADD COLUMN IF NOT EXISTS fact_check_at TIMESTAMPTZ DEFAULT NULL;

-- =====================================================================
-- 2. CHECK constraint on fact_check_status
-- =====================================================================
-- NOT VALID first → cheap; we know existing rows are NULL (just added).
-- VALIDATE second → cheap because CHECK is on a fresh column.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'war_room_drafts_fact_check_status_chk'
    ) THEN
        ALTER TABLE war_room_drafts
            ADD CONSTRAINT war_room_drafts_fact_check_status_chk
            CHECK (fact_check_status IS NULL
                   OR fact_check_status IN ('pass', 'fail', 'degraded'))
            NOT VALID;
        ALTER TABLE war_room_drafts
            VALIDATE CONSTRAINT war_room_drafts_fact_check_status_chk;
    END IF;
END $$;

-- =====================================================================
-- 3. Index for fact-checker reads (status='drafts_imaged_facted' lookups)
-- =====================================================================
-- The fact-checker SELECTs WHERE status='drafts_imaged_facted'; the
-- existing partial index on (status, created_at) covers it. No new
-- index required.

COMMENT ON COLUMN war_room_drafts.fact_check_json IS
  'Extracted claims + per-claim verification (Sprint B B-bis, mig 162). '
  'Shape: {claims: [{claim, slide_index, type, verdict?, note?, ...}]}';
COMMENT ON COLUMN war_room_drafts.fact_check_status IS
  'pass=all claims verified; degraded=some unverifiable; fail=discrepancies. '
  'NULL until fact-checker runs.';
COMMENT ON COLUMN war_room_drafts.fact_check_at IS
  'When the fact-checker completed; NULL until then.';

-- === ROLLBACK ===
-- Soft rollback: drop the three columns. Any populated fact_check_json
-- payloads are lost. Existing drafts in status='drafts_imaged_facted'
-- or 'drafts_imaged_checked' must first be reset to 'drafts_imaged' by
-- the operator (this script intentionally does NOT touch status, so a
-- partial rollback doesn't corrupt the state machine).

ALTER TABLE war_room_drafts
    DROP CONSTRAINT IF EXISTS war_room_drafts_fact_check_status_chk;

ALTER TABLE war_room_drafts
    DROP COLUMN IF EXISTS fact_check_at;
ALTER TABLE war_room_drafts
    DROP COLUMN IF EXISTS fact_check_status;
ALTER TABLE war_room_drafts
    DROP COLUMN IF EXISTS fact_check_json;
