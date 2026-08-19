-- 273_wa_broker_completion_digest.sql
-- BOT-V4 S2 PR-2 (Codex re-verdict r5, finding 2): complete_job's contract
-- promises CONFLICT (409) when the same completion attempt (same
-- completion_key + fence_token) re-arrives with a DIFFERENT payload — but
-- the replay check compared only key/fence/state, so that branch was
-- unreachable: a corrupted retry (result B, or a typed failure, under the
-- key that accepted result A) answered REPLAY 200 while the worker kept
-- consuming A. And after consume_result NULLs result_text, the conflict
-- was undetectable forever. This column freezes a NON-PII fingerprint of
-- the accepted payload ("ok:<sha256(result_text)>" or "err:<error_class>")
-- at accept time; it survives the payload NULLing (it is not payload
-- content), so replays are compared against it indefinitely. Nullable:
-- rows terminalized by paths that accept no payload (expiry) never set it.

ALTER TABLE broker_jobs
    ADD COLUMN IF NOT EXISTS completion_digest TEXT;

-- === ROLLBACK ===

ALTER TABLE broker_jobs
    DROP COLUMN IF EXISTS completion_digest;
