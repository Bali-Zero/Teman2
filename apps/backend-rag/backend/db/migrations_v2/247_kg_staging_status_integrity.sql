-- Migration 247: kg_*_staging promotion_status CHECK + updated_at (S5 companion)
--
-- Purpose:
--   backend/scripts/kg_staging_promotion.py (S5, 2026-07-18) arms the quarantine
--   pattern's second half (design: research/operations/2026-07-18-kg-staging-promotion-job-design.md
--   §3.3, after refuter SERIO-2). Two schema gaps in migration_077's staging
--   tables block it:
--     1) promotion_status is free TEXT — typo-prone. The job flips rows among
--        exactly ('pending','promoted','rejected','merged') → pin with a CHECK.
--        'merged' is reserved for the future human-reviewed merge path; the v2
--        job NEVER auto-merges (fuzzy candidates become
--        rejected(fuzzy_ambiguous_review)), so no writer produces 'merged' today.
--     2) no updated_at — the Phase-4 retention prune (rejected rows > 30 days)
--        has no reliable timestamp → add updated_at, backfilled from created_at.
--
-- SELF-SUFFICIENCY (scar 2026-07-18, caught by CI Backend Tests): the v2 chain
--   (092→246) never creates kg_*_staging — they came from LEGACY migration_077,
--   so they exist in prod but NOT in a fresh v2-only schema (CI bootstrap).
--   This migration therefore creates the tables IF NOT EXISTS first (exact
--   migration_077 column shape; a no-op in prod), then alters them. One file,
--   both worlds.
--
-- Shape mirrors migration 245: normalizing UPDATE of stragglers FIRST (else
-- VALIDATE fails on existing rows), then DROP CONSTRAINT IF EXISTS → ADD
-- CONSTRAINT ... NOT VALID → VALIDATE CONSTRAINT. Stray/typo statuses normalize
-- to 'pending' — re-queued through validation, never silently promoted or lost.
-- NOTE (same caveat as 245): backend/db/migration_base.py wraps the forward SQL
-- in a SINGLE transaction, so NOT VALID + VALIDATE commit together; kept as the
-- inherited convention, lock duration is trivial on these small tables.

-- --- 0. Ensure the staging tables exist (legacy-077 shape; no-op where present) ---

CREATE TABLE IF NOT EXISTS kg_nodes_staging (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    properties JSONB DEFAULT '{}'::jsonb,
    confidence FLOAT DEFAULT 0.7,
    source_chunk_ids TEXT[],
    extraction_source TEXT DEFAULT 'auto_heuristic',
    promotion_status TEXT DEFAULT 'pending',
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kg_nodes_staging_status
    ON kg_nodes_staging(promotion_status);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_staging_created
    ON kg_nodes_staging(created_at);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_staging_type
    ON kg_nodes_staging(entity_type);

CREATE TABLE IF NOT EXISTS kg_edges_staging (
    relationship_id TEXT PRIMARY KEY,
    source_entity_id TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    properties JSONB DEFAULT '{}'::jsonb,
    confidence FLOAT DEFAULT 0.7,
    source_chunk_ids TEXT[],
    extraction_source TEXT DEFAULT 'auto_heuristic',
    promotion_status TEXT DEFAULT 'pending',
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kg_edges_staging_status
    ON kg_edges_staging(promotion_status);
CREATE INDEX IF NOT EXISTS idx_kg_edges_staging_source
    ON kg_edges_staging(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_staging_target
    ON kg_edges_staging(target_entity_id);

-- --- kg_nodes_staging ---

UPDATE kg_nodes_staging
   SET promotion_status = 'pending'
 WHERE promotion_status IS NULL
    OR promotion_status NOT IN ('pending', 'promoted', 'rejected', 'merged');

ALTER TABLE kg_nodes_staging
    DROP CONSTRAINT IF EXISTS kg_nodes_staging_promotion_status_check;

ALTER TABLE kg_nodes_staging
    ADD CONSTRAINT kg_nodes_staging_promotion_status_check
    CHECK (promotion_status IN ('pending', 'promoted', 'rejected', 'merged'))
    NOT VALID;

ALTER TABLE kg_nodes_staging
    VALIDATE CONSTRAINT kg_nodes_staging_promotion_status_check;

ALTER TABLE kg_nodes_staging
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE kg_nodes_staging
   SET updated_at = COALESCE(created_at, now())
 WHERE updated_at IS NULL;

ALTER TABLE kg_nodes_staging
    ALTER COLUMN updated_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET NOT NULL;

-- --- kg_edges_staging ---

UPDATE kg_edges_staging
   SET promotion_status = 'pending'
 WHERE promotion_status IS NULL
    OR promotion_status NOT IN ('pending', 'promoted', 'rejected', 'merged');

ALTER TABLE kg_edges_staging
    DROP CONSTRAINT IF EXISTS kg_edges_staging_promotion_status_check;

ALTER TABLE kg_edges_staging
    ADD CONSTRAINT kg_edges_staging_promotion_status_check
    CHECK (promotion_status IN ('pending', 'promoted', 'rejected', 'merged'))
    NOT VALID;

ALTER TABLE kg_edges_staging
    VALIDATE CONSTRAINT kg_edges_staging_promotion_status_check;

ALTER TABLE kg_edges_staging
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE kg_edges_staging
   SET updated_at = COALESCE(created_at, now())
 WHERE updated_at IS NULL;

ALTER TABLE kg_edges_staging
    ALTER COLUMN updated_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET NOT NULL;

-- === ROLLBACK ===
-- Drop the constraints and the updated_at columns. Status values stay as they
-- are (no data rewrite needed — 'pending'/'promoted'/'rejected'/'merged' were
-- all valid free-TEXT values before this migration too).
-- The staging TABLES are intentionally NOT dropped: in prod they pre-date this
-- migration (legacy 077), and CREATE TABLE IF NOT EXISTS made no change there.
-- DROP ... IF EXISTS on tables is safe on a v2-only schema (where this file did
-- create them) and a no-op error-free everywhere... but a rollback in prod must
-- never destroy the live staging area, so tables are left in place by design.

ALTER TABLE kg_nodes_staging
    DROP CONSTRAINT IF EXISTS kg_nodes_staging_promotion_status_check;

ALTER TABLE kg_nodes_staging
    DROP COLUMN IF EXISTS updated_at;

ALTER TABLE kg_edges_staging
    DROP CONSTRAINT IF EXISTS kg_edges_staging_promotion_status_check;

ALTER TABLE kg_edges_staging
    DROP COLUMN IF EXISTS updated_at;
