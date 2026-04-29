-- 143_legacy_conversations.sql
--
-- (Renumbered from 130_legacy_conversations.sql by P0-7 audit fix
-- 2026-04-29 — original 130 was duplicated by
-- 130_crm_guardian_summary_queue.sql. The DDL below is idempotent —
-- no-op on prod where conversations already exists.)
--
--
-- Promote `conversations` from a CI-bootstrap-only table to a
-- migrations_v2 entry. Mirrors `ci_bootstrap_schema.py` exactly.
--
-- Idempotent: `CREATE TABLE IF NOT EXISTS` — no-op on prod (table
-- predates the v2 runner, was created by hand).
--
-- This table is also the FK target for `interactions.conversation_id`
-- (see backend/app/modules/crm/models.py — Interaction.conversation_id
-- references conversations(id)). Keep the column types in sync with
-- that model when promoting follow-up changes.

CREATE TABLE IF NOT EXISTS conversations (
    id          SERIAL PRIMARY KEY,
    user_id     VARCHAR(255) NOT NULL,
    messages    TEXT NOT NULL DEFAULT '[]',
    session_id  VARCHAR(255),
    rating      INTEGER,
    feedback    TEXT,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- === ROLLBACK ===
DROP TABLE IF EXISTS conversations;
