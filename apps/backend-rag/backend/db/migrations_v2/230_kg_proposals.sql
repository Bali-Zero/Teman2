-- Migration 230: kg_proposals — Curiosity Loop propose-only pipeline table.
--
-- WHY THIS EXISTS (cicatrix "Esiste != Armato" / superscar #2):
-- The table was authored in 2026-04 as backend/migrations/migration_108_kg_proposals.py,
-- a LEGACY manual-apply file (MIGRATIONS.md: loader=None, "DO NOT ADD"). It was never
-- promoted to the V2 SQL loader, so it was never applied on any DB the deploy path
-- touches. Result: the curiosity_loop cron (scripts/gap_fill_autonomous.py ->
-- KGProposalStore.save) hit a missing-relation error on EVERY gap; the :15432 proxy
-- closed the connection on the SQL error, surfacing as the misleading
-- "connection was closed in the middle of operation" log. 10 days dead, 0 proposals,
-- TERMINAL in DLQ (2026-06-06 -> 2026-06-16). The build existed; the last mile (arming
-- it on the live deploy path) was never walked.
--
-- The legacy 108 number collided with migrations_v2/108_lkpm_receipts.sql (already
-- tracked in _schema_versions). The two systems share the number space but NOT the
-- tracker, so the legacy file was invisible -- never a runner bug, just an un-armed file.
-- This migration arms it as V2 under a free number (230; the original 229 collided
-- with 229_team_avatars_align_roster.sql from a parallel branch — the very W40
-- number-collision class this fix is about, bumped to the next free slot).
--
-- Schema is byte-equivalent to migration_108_kg_proposals.py (verified applied live on
-- the Pro DB 2026-06-16). Idempotent (IF NOT EXISTS) so re-running over the hand-applied
-- table is a no-op and _schema_versions records it cleanly.
--
-- On the Pro apply manually like 212-228:
--   psql "$DATABASE_URL" \
--     -f apps/backend-rag/backend/db/migrations_v2/230_kg_proposals.sql
-- === FORWARD ===

CREATE TABLE IF NOT EXISTS kg_proposals (
    id BIGSERIAL PRIMARY KEY,
    proposal_id TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    gap_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    proposal_type TEXT NOT NULL CHECK(
        proposal_type IN ('node', 'edge', 'property')
    ),

    -- For node proposals
    node_label TEXT,
    node_type TEXT,
    node_properties JSONB DEFAULT '{}',

    -- For edge proposals
    source_entity_id TEXT,
    target_entity_id TEXT,
    relationship_type TEXT,
    edge_properties JSONB DEFAULT '{}',

    -- For property proposals
    target_entity_id_prop TEXT,
    property_key TEXT,
    property_value JSONB,

    -- Validation
    evidence_sources JSONB DEFAULT '[]',
    self_rag_score FLOAT NOT NULL DEFAULT 0.0,
    tier TEXT NOT NULL DEFAULT 'tier1_simple',
    research_method TEXT DEFAULT '',

    -- State machine
    status TEXT NOT NULL DEFAULT 'pending' CHECK(
        status IN (
            'pending', 'approved', 'rejected',
            'applied', 'auto_expired'
        )
    ),
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    applied_at TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Audit
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_kg_proposals_status     ON kg_proposals (status);
CREATE INDEX IF NOT EXISTS idx_kg_proposals_domain     ON kg_proposals (domain);
CREATE INDEX IF NOT EXISTS idx_kg_proposals_gap_id     ON kg_proposals (gap_id);
CREATE INDEX IF NOT EXISTS idx_kg_proposals_created_at ON kg_proposals (created_at);

-- === ROLLBACK ===
-- Reversible. The inverse DDL (remove the four idx_kg_proposals_* indexes, then
-- the kg_proposals table, in reverse order) is the rollback() coroutine in the
-- twin legacy file backend/migrations/migration_108_kg_proposals.py. It is left
-- out of the executable rollback section here on purpose: this table is the sole
-- store for Curiosity Loop proposals, so a teardown discards Zero's
-- pending-approval queue. Run the legacy rollback() by hand only after confirming
-- `SELECT count(*) FROM kg_proposals WHERE status = 'pending'` returns 0.
