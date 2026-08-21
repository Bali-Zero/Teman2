-- 271_wa_broker_gauge_half_open_at.sql
-- BOT-V4 S2 PR-2 (Codex re-verdict, finding 2): the half_open orphan guard
-- anchored on wa_broker_gauge.updated_at, but every claim_job poll refreshes
-- that same timestamp — a polling broker kept the 120s orphan threshold from
-- ever maturing, so a half_open gauge whose canary result was lost (worker
-- died between consume and record) stayed absorbing forever. The breaker
-- transition needs its OWN clock, untouched by heartbeats:
--   * set to now() by the open->half_open CAS in breaker_admits()
--   * cleared on every transition out of half_open (record_breaker_result,
--     _revert_canary_cas, the orphan demotion itself)
-- NULL means "not in half_open" — the orphan guard only fires on a non-NULL
-- value older than the orphan window.

ALTER TABLE wa_broker_gauge
    ADD COLUMN IF NOT EXISTS breaker_half_open_at TIMESTAMPTZ;

-- === ROLLBACK ===

ALTER TABLE wa_broker_gauge
    DROP COLUMN IF EXISTS breaker_half_open_at;
