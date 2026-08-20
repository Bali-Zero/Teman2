-- Migration 275: war_room_drafts vision-quota circuit-breaker columns.
--
-- Purpose (WR2 vision-quota-burn fix, 2026-08-20):
--   The HTML render apply-worker (scripts/wr2_html_render_apply.py) releases a
--   draft WITHOUT burning html_render_attempts whenever the vision critic/
--   verifier chain hits a TRANSIENT infra failure (rate-limit / endpoint
--   timeout — VisionTransient in claude_vision.py). That "no attempt burned"
--   contract is correct (a quota window is not a defect of the draft) but had
--   NO ceiling: a draft landing on a dead quota window bounced
--   status='drafts_imaged_checked' -> 'rendering' -> released, forever, every
--   launchd tick. Measured: ~1,262 `claude --print` vision sessions/day,
--   ~690M cache-write tokens/7d, while every OAuth seat in the chain was
--   rate-limited for hours.
--
--   Two additive columns give the worker a per-draft cap independent of (and
--   a backstop for) the process-wide vision cooldown added in the same
--   change (claude_vision.py's on-disk circuit breaker):
--     html_vision_transient_streak — consecutive VisionTransient releases on
--       this draft; reset to 0 the moment a non-transient outcome (success OR
--       a real render failure) breaks the streak.
--     html_vision_parked_until — set, once the streak reaches
--       WR2_VISION_MAX_TRANSIENT (default 3), to NOW() + WR2_VISION_COOLDOWN_S;
--       NULL means not parked. The HTML-lane fetch
--       (_pg.fetch_pending_html_draft_ids) excludes a draft while
--       parked_until is in the future, so a draft that keeps landing on a
--       dead quota window stops being re-picked every tick WITHOUT ever
--       reaching the existing, terminal 'parked' STATUS value (that value
--       means "no usable source content, needs a human" — a vision-quota
--       window recovers on its own, so this draft must resume automatically
--       once parked_until passes, never wait for a manual re-queue).
--
-- Pure additive nullable/defaulted columns — same shape as migration 228
-- (html_render_attempts). No backfill: existing rows read streak=0,
-- parked_until=NULL (not parked), which is the correct historical value (the
-- circuit breaker did not exist before this migration).

ALTER TABLE war_room_drafts
    ADD COLUMN IF NOT EXISTS html_vision_transient_streak INTEGER NOT NULL DEFAULT 0;

ALTER TABLE war_room_drafts
    ADD COLUMN IF NOT EXISTS html_vision_parked_until TIMESTAMPTZ;

-- === ROLLBACK ===
ALTER TABLE war_room_drafts DROP COLUMN IF EXISTS html_vision_parked_until;
ALTER TABLE war_room_drafts DROP COLUMN IF EXISTS html_vision_transient_streak;
