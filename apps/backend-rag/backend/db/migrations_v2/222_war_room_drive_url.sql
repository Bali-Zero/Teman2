-- Migration 222: WR2 HTML renderer wiring -- drive_url columns + status parity (rendering/render_failed/rendered_shadow)
--
-- Purpose (WR2 wiring v4, condition C2 + C3):
--   1. Add drive_url + drive_url_shadow columns to war_room_drafts. The HTML/CSS
--      renderer (replacing Canva) uploads the finished carousel to Google Drive and
--      persists the share link here. drive_url_shadow holds the link from a
--      WR2_HTML_SHADOW dry-run (terminal, never delivered to WhatsApp).
--   2. Fix a PRE-EXISTING latent constraint violation: the canva_renderer_v2 lease
--      (services/canva_renderer_v2/_pg.py) and migration 170 recovery index already
--      USE status=rendering, but migration 163 CHECK never allowed it. The lease
--      UPDATE ... SET status=rendering would be rejected by war_room_drafts_status_check.
--      This migration adds rendering (legitimizing the existing lease path) plus the
--      two new terminal states the HTML worker introduces: render_failed (circuit
--      breaker) and rendered_shadow (shadow-mode dry run).
--
-- Mirrors migration 163 exact shape: DROP CONSTRAINT IF EXISTS -> ADD CONSTRAINT ...
-- CHECK (status = ANY (ARRAY[...]::text)) NOT VALID -> separate VALIDATE CONSTRAINT.
-- Two-step NOT VALID + VALIDATE avoids ACCESS EXCLUSIVE during scan (Squawk-safe).
-- The runner wraps the forward block in one transaction; VALIDATE works inside it
-- (163 already does this in production). Idempotent: ADD COLUMN IF NOT EXISTS;
-- DROP CONSTRAINT IF EXISTS before re-add.

ALTER TABLE war_room_drafts
    ADD COLUMN IF NOT EXISTS drive_url TEXT;

ALTER TABLE war_room_drafts
    ADD COLUMN IF NOT EXISTS drive_url_shadow TEXT;

-- C4 (heartbeat lease): the HTML worker renews this every ~60s during a long
-- designer loop so reset_stale_leases keys off liveness, not start-time — a live
-- worker keeps its lease no matter how long the render runs; only a dead worker
-- (no heartbeat) is reclaimed. NULL means no heartbeat-based lease in progress.
ALTER TABLE war_room_drafts
    ADD COLUMN IF NOT EXISTS lease_heartbeat_at TIMESTAMPTZ;

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

-- === ROLLBACK ===
-- Revert rows parked in the new states to a safe parent BEFORE shrinking the
-- constraint, else VALIDATE fails on existing rows.
UPDATE war_room_drafts SET status = 'drafts_imaged_checked'
 WHERE status IN ('rendering', 'render_failed');
UPDATE war_room_drafts SET status = 'rendered'
 WHERE status = 'rendered_shadow';

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

-- drive_url / drive_url_shadow left in place on rollback (additive nullable, harmless).
-- Drop manually only for a full revert:
--   ALTER TABLE war_room_drafts DROP COLUMN IF EXISTS drive_url;
--   ALTER TABLE war_room_drafts DROP COLUMN IF EXISTS drive_url_shadow;
--   ALTER TABLE war_room_drafts DROP COLUMN IF EXISTS lease_heartbeat_at;
