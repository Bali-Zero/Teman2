-- Migration 228: war_room_drafts.html_render_attempts — dedicated INTEGER circuit-breaker counter.
--
-- Purpose (WR2 HTML renderer bug-fix, 2026-06-13 SCAR):
--   The HTML render apply-worker (scripts/wr2_html_render_apply.py, _apply_one)
--   tracked its render-retry counter by abusing the JSONB `slides_json` column:
--     READ  : SELECT COALESCE((slides_json->>'_html_attempts')::int, 0)
--     WRITE : jsonb_set(slides_json, '{_html_attempts}', to_jsonb($3::int))
--   But slides_json is a JSONB **ARRAY** (the list of slide objects), not an
--   object. On an array:
--     * the READ (`->>'_html_attempts'`) silently returns NULL → COALESCE → 0,
--       so the counter NEVER accumulated;
--     * the WRITE (`jsonb_set(array, '{_html_attempts}', ...)`) RAISES
--       `InvalidTextRepresentationError: path element at position 1 is not an
--       integer: "_html_attempts"`, crashing the retry-release path BEFORE the
--       draft could be parked in its retry state.
--   Live impact: a draft that fails the designer-loop convergence gate never had
--   its attempt counter incremented, never reached max-attempts, never
--   transitioned to render_failed — its lease just expired and reconciliation
--   re-kicked it forever (two drafts looped ~8h, 2026-06-13).
--
-- Fix: store the counter in a dedicated, type-correct INTEGER column instead of
-- abusing the slides_json array. The apply-worker now reads/writes
-- html_render_attempts; the slides_json array is never touched for this purpose.
--
-- Pure additive nullable column. DEFAULT 0 so existing rows + future drafts read
-- as 0 (= no failed attempt yet). No backfill needed (the old `_html_attempts`
-- inside slides_json never actually persisted a value — the write always crashed
-- on the array — so there is no legacy counter to migrate).

ALTER TABLE war_room_drafts
    ADD COLUMN IF NOT EXISTS html_render_attempts INTEGER NOT NULL DEFAULT 0;

-- === ROLLBACK ===
ALTER TABLE war_room_drafts DROP COLUMN IF EXISTS html_render_attempts;
