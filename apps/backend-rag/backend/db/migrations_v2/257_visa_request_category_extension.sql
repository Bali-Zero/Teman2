-- Migration 257: Visa Oracle request_category extension (business + diaspora)
--
-- The v2 interview has 10 purpose tiles; migration 255's request_category
-- CHECK admits only the 8 legacy values (the visa_check.match_tree.Purpose
-- vocabulary).  W1 Fable delta 3 (binding, 2026-07-23, adjudicated in
-- research/visa/2026-07-23-w1-evidence-machinery-brief.md Item 3) rules:
-- extend the enum to 10 -- add 'business' and 'diaspora', keep 'other'.
-- The rejected alternative (map both tiles to 'other') would silently
-- miscount real end-user demand in the G-a evidence report.
--
-- Semantics on the collector side (shadow_evidence.py, same PR): the 7
-- legacy substantive categories stay REQUIRED for the G-a gates;
-- 'business'/'diaspora' rows are REPORTED (counted, honestly labeled) but
-- NOT required, because their behavioral trees do not exist yet -- they are
-- Track B FASE 2 lanes 2 and 6, so no honest evaluation can be demanded of
-- them for gate-green today.
--
-- Mechanics: the 8-value CHECK created inline by migration 255
-- (auto-named visa_decisions_request_category_check by Postgres) is dropped
-- and re-added with the 10-value list.  Same roll-forward pattern as 255/
-- 256: no backfill, no data rewrite -- existing rows keep their already-
-- valid categories (the new value list is a strict superset, so re-
-- validation at ADD CONSTRAINT time cannot fail on pre-257 data).
--
-- This migration does not change VISA_ENGINE_MATCH_MODE /
-- VISA_ENGINE_EVALUATE_MODE and cannot arm ENFORCE.

ALTER TABLE public.visa_decisions
    DROP CONSTRAINT visa_decisions_request_category_check;

ALTER TABLE public.visa_decisions
    ADD CONSTRAINT visa_decisions_request_category_check
        CHECK (
            request_category IS NULL
            OR request_category IN (
                'work_remote',
                'investor',
                'work_employee',
                'family',
                'long_tourism',
                'retirement',
                'student',
                'other',
                'business',
                'diaspora'
            )
        );

-- === ROLLBACK ===
-- Restore migration 255's exact 8-value CHECK.  IF EXISTS throughout so a
-- defensive rollback before this migration ever ran (the test-fixture
-- convention) is a semantic no-op: it drops whatever request_category CHECK
-- is present (10-value if 257 was applied, 8-value if not) and re-adds the
-- 8-value one, provided the table exists at all.  Requires the
-- request_category column to exist (migration 255 applied) -- the fixture
-- chain guarantees ordering (257's rollback always runs BEFORE 255's, which
-- is what drops the column).

ALTER TABLE IF EXISTS public.visa_decisions
    DROP CONSTRAINT IF EXISTS visa_decisions_request_category_check;

ALTER TABLE IF EXISTS public.visa_decisions
    ADD CONSTRAINT visa_decisions_request_category_check
        CHECK (
            request_category IS NULL
            OR request_category IN (
                'work_remote',
                'investor',
                'work_employee',
                'family',
                'long_tourism',
                'retirement',
                'student',
                'other'
            )
        );
