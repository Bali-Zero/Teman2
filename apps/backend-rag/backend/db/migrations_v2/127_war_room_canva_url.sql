-- ============================================================
-- 127_war_room_canva_url.sql
-- WR2 Canva Renderer — store edit URL on draft after headless apply.
-- Date: 2026-04-22
--
-- WR2 used to render slides to PNG via Playwright. From 2026-04-22, the
-- rendering stage is replaced by headless `claude -p` + MCP Canva: each
-- draft with status='rendered' gets a Canva design (editable by Zero in
-- the Canva UI before Review Gate approval). The edit URL lives on the
-- draft row so Review Gate shows the link in Telegram.
--
-- Ref: backend/services/canva_renderer/ + scripts/wr2_canva_apply.py.
-- ============================================================

ALTER TABLE war_room_drafts
    ADD COLUMN IF NOT EXISTS canva_design_id  TEXT,
    ADD COLUMN IF NOT EXISTS canva_edit_url   TEXT,
    ADD COLUMN IF NOT EXISTS canva_view_url   TEXT,
    ADD COLUMN IF NOT EXISTS canva_applied_at TIMESTAMPTZ;

-- Query path: the apply worker polls for drafts ready to be rendered.
CREATE INDEX IF NOT EXISTS ix_war_room_drafts_ready_for_canva
    ON war_room_drafts (status, created_at)
    WHERE status = 'drafts' AND canva_edit_url IS NULL;

-- === ROLLBACK ===
DROP INDEX IF EXISTS ix_war_room_drafts_ready_for_canva;
ALTER TABLE war_room_drafts
    DROP COLUMN IF EXISTS canva_applied_at,
    DROP COLUMN IF EXISTS canva_view_url,
    DROP COLUMN IF EXISTS canva_edit_url,
    DROP COLUMN IF EXISTS canva_design_id;
