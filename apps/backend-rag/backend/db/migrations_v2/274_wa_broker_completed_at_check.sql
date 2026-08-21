-- 274_wa_broker_completed_at_check.sql
-- BOT-V4 S2 PR-5 — the follow-up promised in expire_stale_jobs' docstring
-- ("A DB CHECK tying the state to completed_at is the follow-up migration,
-- tracked for PR-5"): a completed_pending_consume row MUST carry
-- completed_at, or a malformed writer could mint a row whose dead-consumer
-- grace anchors on nothing (the reaper already defends with
-- COALESCE(completed_at, created_at); this makes the malformed row
-- unwritable instead of merely reapable — belt at the schema, braces in
-- the reaper). complete_job's success branch always sets completed_at, so
-- no live writer can violate this. The table ships dark (flag-OFF lane):
-- the validation scan is on an empty-or-tiny table.

ALTER TABLE broker_jobs
    ADD CONSTRAINT broker_jobs_completed_requires_completed_at
    CHECK (state <> 'completed_pending_consume' OR completed_at IS NOT NULL);

-- === ROLLBACK ===

ALTER TABLE broker_jobs
    DROP CONSTRAINT IF EXISTS broker_jobs_completed_requires_completed_at;
