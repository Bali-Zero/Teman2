-- ============================================================
-- 109_garuda_curator.sql
-- Curator Agent Sprint 5.1 — GARUDA indexer foundation
-- Date: 2026-04-14
-- Spec: docs/superpowers/specs/2026-04-14-curator-agent-garuda-design-v2.md
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- garuda_index — Master index of all files under GARUDA/
-- ============================================================
CREATE TABLE IF NOT EXISTS garuda_index (
    file_id          VARCHAR(128) PRIMARY KEY,
    name             VARCHAR(512) NOT NULL,
    path             TEXT NOT NULL,
    parent_folder    VARCHAR(128) NOT NULL,
    category         VARCHAR(32) NOT NULL CHECK (category IN (
        'photos','videos','audio','intelligence','drafts','research','published'
    )),
    mime_type        VARCHAR(128) NOT NULL,
    size_bytes       BIGINT NOT NULL,
    modified_at      TIMESTAMPTZ NOT NULL,
    indexed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drive_version    BIGINT,
    extracted_text   TEXT,
    description      TEXT,
    tags             JSONB DEFAULT '[]'::jsonb,
    content_hash     VARCHAR(64),
    archived         BOOLEAN DEFAULT FALSE,
    trashed          BOOLEAN DEFAULT FALSE,
    quarantined      BOOLEAN DEFAULT FALSE,
    quarantine_reason JSONB,
    metadata         JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_garuda_index_active_by_cat
    ON garuda_index(category, modified_at DESC)
    WHERE archived = FALSE AND trashed = FALSE AND quarantined = FALSE;

CREATE INDEX IF NOT EXISTS idx_garuda_index_content_hash
    ON garuda_index(content_hash)
    WHERE content_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_garuda_index_quarantined
    ON garuda_index(quarantined)
    WHERE quarantined = TRUE;

-- ============================================================
-- publication_history — Cross-channel publication log
-- ============================================================
CREATE TABLE IF NOT EXISTS publication_history (
    publication_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel           VARCHAR(32) NOT NULL CHECK (channel IN (
        'tg_zero','tg_channel','ig_carousel','ig_video','ig_story',
        'newsletter','blog','x_thread','linkedin','whatsapp_broadcast'
    )),
    topic             VARCHAR(512) NOT NULL,
    title             TEXT,
    published_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    external_id       VARCHAR(256),
    external_url      TEXT,
    language          VARCHAR(8) DEFAULT 'en',
    engagement_metrics JSONB DEFAULT '{}'::jsonb,
    curator_agent     VARCHAR(64) NOT NULL,
    autonomy_level    VARCHAR(4) NOT NULL CHECK (autonomy_level IN ('L1','L2','L3','L4')),
    approved_by       VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_pubhist_channel_time
    ON publication_history(channel, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_pubhist_topic
    ON publication_history(topic);

-- ============================================================
-- publication_assets — Bridge: which assets used in publication
-- (Replaces JSONB array for queryability)
-- ============================================================
CREATE TABLE IF NOT EXISTS publication_assets (
    publication_id    UUID NOT NULL REFERENCES publication_history(publication_id) ON DELETE CASCADE,
    file_id           VARCHAR(128) NOT NULL REFERENCES garuda_index(file_id) ON DELETE CASCADE,
    role              VARCHAR(32),
    position          INT,
    PRIMARY KEY (publication_id, file_id)
);

CREATE INDEX IF NOT EXISTS idx_pubassets_file
    ON publication_assets(file_id);

-- ============================================================
-- garuda_indexer_state — Per-worker cursor and state
-- Keyed by worker_name to support multiple parallel workers
-- ============================================================
CREATE TABLE IF NOT EXISTS garuda_indexer_state (
    worker_name              TEXT PRIMARY KEY,
    last_change_page_token   TEXT,
    last_run_started_at      TIMESTAMPTZ,
    last_run_completed_at    TIMESTAMPTZ,
    lease_expires_at         TIMESTAMPTZ,
    files_indexed_total      BIGINT DEFAULT 0,
    files_indexed_last_run   INT DEFAULT 0,
    consecutive_failures     INT DEFAULT 0,
    mode                     VARCHAR(16) DEFAULT 'daily',
    last_error               JSONB,
    config                   JSONB DEFAULT '{}'::jsonb
);

INSERT INTO garuda_indexer_state (worker_name, mode)
VALUES ('default', 'daily')
ON CONFLICT (worker_name) DO NOTHING;

-- ============================================================
-- Comments
-- ============================================================
COMMENT ON TABLE garuda_index IS
    'Mata Garuda Layer 4.5 — Curator Agent. Master index of all files under GARUDA/ Drive folder. Read-only scope: NEVER includes CRM, PERATURAN, CLIENTI.';

COMMENT ON TABLE publication_history IS
    'Per-channel publication log used by Curator for gap coverage and dedup.';

COMMENT ON TABLE publication_assets IS
    'Bridge table linking publications to GARUDA assets used (better than JSONB for analytics).';

COMMENT ON TABLE garuda_indexer_state IS
    'Worker state for incremental Drive crawler. Uses Drive changes.list page tokens.';
