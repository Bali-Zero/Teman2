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
-- Shape mirrors migration 245: normalizing UPDATE of stragglers FIRST (else
-- VALIDATE fails on existing rows), then DROP CONSTRAINT IF EXISTS → ADD
-- CONSTRAINT ... NOT VALID → VALIDATE CONSTRAINT. Stray/typo statuses normalize
-- to 'pending' — re-queued through validation, never silently promoted or lost.
-- NOTE (same caveat as 245): backend/db/migration_base.py wraps the forward SQL
-- in a SINGLE transaction, so NOT VALID + VALIDATE commit together; kept as the
-- inherited convention, lock duration is trivial on these small tables.

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

ALTER TABLE kg_nodes_staging
    DROP CONSTRAINT IF EXISTS kg_nodes_staging_promotion_status_check;

ALTER TABLE kg_nodes_staging
    DROP COLUMN IF EXISTS updated_at;

ALTER TABLE kg_edges_staging
    DROP CONSTRAINT IF EXISTS kg_edges_staging_promotion_status_check;

ALTER TABLE kg_edges_staging
    DROP COLUMN IF EXISTS updated_at;
