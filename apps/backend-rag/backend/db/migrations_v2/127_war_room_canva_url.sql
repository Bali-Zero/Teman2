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
--
-- Note on bootstrap: war_room_drafts was originally created by the Python
-- migration backend/migrations/migration_112_war_room_tables.py (applied
-- in prod). The CI "Apply database migrations" step only walks v2 SQL
-- files, so we re-declare the minimum table shape with IF NOT EXISTS here
-- to keep the migration self-contained. In prod this is a no-op; in CI it
-- bootstraps the table so the ALTER below has something to touch.
-- ============================================================

CREATE TABLE IF NOT EXISTS war_room_drafts (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic                 TEXT NOT NULL,
    tone_register         TEXT,
    status                TEXT NOT NULL DEFAULT 'briefed',
    brief_json            JSONB,
    research_json         JSONB,
    council_debate_json   JSONB,
    slides_json           JSONB,
    drafts_json           JSONB,
    rejection_reason      TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by           TEXT,
    approved_at           TIMESTAMPTZ
);

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
-- NOTE: rollback drops only the canva_* columns + index added by this
-- migration. The CREATE TABLE above uses IF NOT EXISTS so dropping the
-- whole table here would be destructive in prod (where it predates us).
DROP INDEX IF EXISTS ix_war_room_drafts_ready_for_canva;
ALTER TABLE war_room_drafts
    DROP COLUMN IF EXISTS canva_applied_at,
    DROP COLUMN IF EXISTS canva_view_url,
    DROP COLUMN IF EXISTS canva_edit_url,
    DROP COLUMN IF EXISTS canva_design_id;
