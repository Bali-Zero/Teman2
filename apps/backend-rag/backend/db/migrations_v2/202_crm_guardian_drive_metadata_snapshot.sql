-- migration 202_crm_guardian_drive_metadata_snapshot
-- CRM Guardian read-only Drive evidence graph.
--
-- Adds staging tables for validating existing CRM Drive IDs through direct
-- files.get metadata lookups, resolving shortcuts, and queueing owner/stale
-- link review. This migration is additive and does not alter existing Drive,
-- document, client, company, or invoice tables.
--
-- Phase 1/2 evidence:
-- /tmp/nuzantara-gws-phase1/reports/direct_drive_validation_summary.md
-- /tmp/nuzantara-gws-phase1/reports/phase2_crm_guardian_backlog.md

BEGIN;

CREATE TABLE IF NOT EXISTS crm_guardian_drive_metadata_snapshot (
    drive_id TEXT PRIMARY KEY,
    name TEXT,
    mime_type TEXT,
    owner_email TEXT,
    owner_domain TEXT,
    parent_ids TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    shared_drive_id TEXT,
    trashed BOOLEAN NOT NULL DEFAULT false,
    web_view_link TEXT,
    shortcut_target_id TEXT,
    shortcut_target_mime_type TEXT,
    can_copy BOOLEAN,
    can_download BOOLEAN,
    can_edit BOOLEAN,
    can_move_item_into_team_drive BOOLEAN,
    can_move_item_out_of_drive BOOLEAN,
    can_move_item_within_drive BOOLEAN,
    validation_status TEXT NOT NULL,
    error_status TEXT,
    error_message TEXT,
    source_mix TEXT,
    raw_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    validated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_drive_metadata_owner_domain
    ON crm_guardian_drive_metadata_snapshot (owner_domain);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_drive_metadata_mime_type
    ON crm_guardian_drive_metadata_snapshot (mime_type);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_drive_metadata_shared_drive
    ON crm_guardian_drive_metadata_snapshot (shared_drive_id);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_drive_metadata_validation
    ON crm_guardian_drive_metadata_snapshot (validation_status, validated_at DESC);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_drive_metadata_shortcut
    ON crm_guardian_drive_metadata_snapshot (shortcut_target_id)
    WHERE shortcut_target_id IS NOT NULL;

COMMENT ON TABLE crm_guardian_drive_metadata_snapshot IS
    'Read-only CRM Guardian snapshot of Google Drive metadata for Drive IDs already referenced by CRM tables.';
COMMENT ON COLUMN crm_guardian_drive_metadata_snapshot.validation_status IS
    'ok, error_404, error_403, etc. Not an instruction to delete existing CRM links.';
COMMENT ON COLUMN crm_guardian_drive_metadata_snapshot.owner_domain IS
    'Owner domain used for Canonical migration risk scoring; gmail.com usually means external-owner review.';

CREATE TABLE IF NOT EXISTS crm_guardian_drive_db_link_snapshot (
    id BIGSERIAL PRIMARY KEY,
    source_table TEXT NOT NULL,
    link_kind TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    parent_entity_id TEXT,
    entity_label TEXT,
    document_type TEXT,
    file_name TEXT,
    drive_id TEXT,
    raw_url TEXT,
    crm_status TEXT,
    crm_updated_at TIMESTAMPTZ,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_drive_db_link_drive_id
    ON crm_guardian_drive_db_link_snapshot (drive_id);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_drive_db_link_entity
    ON crm_guardian_drive_db_link_snapshot (entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_drive_db_link_source
    ON crm_guardian_drive_db_link_snapshot (source_table, link_kind);

COMMENT ON TABLE crm_guardian_drive_db_link_snapshot IS
    'Appendable read-only capture of which CRM rows reference which Drive IDs.';

CREATE TABLE IF NOT EXISTS crm_guardian_shortcut_edges (
    shortcut_id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    target_mime_type TEXT,
    source_path TEXT,
    source_cluster TEXT,
    owner_email TEXT,
    owner_domain TEXT,
    resolution_status TEXT NOT NULL DEFAULT 'pending',
    resolved_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_shortcut_edges_target
    ON crm_guardian_shortcut_edges (target_id);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_shortcut_edges_status
    ON crm_guardian_shortcut_edges (resolution_status, created_at DESC);

COMMENT ON TABLE crm_guardian_shortcut_edges IS
    'Shortcut relationship graph. Shortcuts are evidence edges, not duplicated content.';

CREATE TABLE IF NOT EXISTS crm_guardian_migration_backlog (
    id BIGSERIAL PRIMARY KEY,
    drive_id TEXT NOT NULL,
    backlog_type TEXT NOT NULL,
    priority TEXT NOT NULL,
    owner_email TEXT,
    owner_domain TEXT,
    source_mix TEXT,
    recommended_action TEXT NOT NULL,
    confidence NUMERIC(5, 4),
    status TEXT NOT NULL DEFAULT 'open',
    evidence JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    CONSTRAINT ck_crm_guardian_migration_backlog_confidence CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
    )
);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_migration_backlog_status
    ON crm_guardian_migration_backlog (status, priority);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_migration_backlog_drive_id
    ON crm_guardian_migration_backlog (drive_id);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_migration_backlog_type_owner
    ON crm_guardian_migration_backlog (backlog_type, owner_domain);

COMMENT ON TABLE crm_guardian_migration_backlog IS
    'Review queue for external ownership, stale-link candidates, shortcut blockers, and Canonical readiness.';

CREATE TABLE IF NOT EXISTS crm_guardian_entity_match_candidates (
    id BIGSERIAL PRIMARY KEY,
    drive_id TEXT NOT NULL,
    candidate_entity_type TEXT NOT NULL,
    candidate_entity_id TEXT NOT NULL,
    candidate_relation TEXT NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL,
    match_reasons JSONB NOT NULL DEFAULT '[]'::JSONB,
    source_trace JSONB NOT NULL DEFAULT '{}'::JSONB,
    status TEXT NOT NULL DEFAULT 'pending_review',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at TIMESTAMPTZ,
    approved_by TEXT,
    CONSTRAINT ck_crm_guardian_entity_match_confidence CHECK (
        confidence >= 0 AND confidence <= 1
    )
);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_entity_match_candidates_drive
    ON crm_guardian_entity_match_candidates (drive_id);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_entity_match_candidates_entity
    ON crm_guardian_entity_match_candidates (candidate_entity_type, candidate_entity_id);

CREATE INDEX IF NOT EXISTS idx_crm_guardian_entity_match_candidates_status
    ON crm_guardian_entity_match_candidates (status, confidence DESC);

COMMENT ON TABLE crm_guardian_entity_match_candidates IS
    'Pending person/company/practice/document match suggestions for unlinked Drive evidence.';

COMMIT;

-- === ROLLBACK ===
-- Inline rollback per W42 lint. This migration is additive, so rollback drops
-- only the CRM Guardian evidence/backlog tables introduced above.
-- BEGIN;
--
-- DROP INDEX IF EXISTS idx_crm_guardian_entity_match_candidates_status;
-- DROP INDEX IF EXISTS idx_crm_guardian_entity_match_candidates_entity;
-- DROP INDEX IF EXISTS idx_crm_guardian_entity_match_candidates_drive;
-- DROP TABLE IF EXISTS crm_guardian_entity_match_candidates;
--
-- DROP INDEX IF EXISTS idx_crm_guardian_migration_backlog_type_owner;
-- DROP INDEX IF EXISTS idx_crm_guardian_migration_backlog_drive_id;
-- DROP INDEX IF EXISTS idx_crm_guardian_migration_backlog_status;
-- DROP TABLE IF EXISTS crm_guardian_migration_backlog;
--
-- DROP INDEX IF EXISTS idx_crm_guardian_shortcut_edges_status;
-- DROP INDEX IF EXISTS idx_crm_guardian_shortcut_edges_target;
-- DROP TABLE IF EXISTS crm_guardian_shortcut_edges;
--
-- DROP INDEX IF EXISTS idx_crm_guardian_drive_db_link_source;
-- DROP INDEX IF EXISTS idx_crm_guardian_drive_db_link_entity;
-- DROP INDEX IF EXISTS idx_crm_guardian_drive_db_link_drive_id;
-- DROP TABLE IF EXISTS crm_guardian_drive_db_link_snapshot;
--
-- DROP INDEX IF EXISTS idx_crm_guardian_drive_metadata_shortcut;
-- DROP INDEX IF EXISTS idx_crm_guardian_drive_metadata_validation;
-- DROP INDEX IF EXISTS idx_crm_guardian_drive_metadata_shared_drive;
-- DROP INDEX IF EXISTS idx_crm_guardian_drive_metadata_mime_type;
-- DROP INDEX IF EXISTS idx_crm_guardian_drive_metadata_owner_domain;
-- DROP TABLE IF EXISTS crm_guardian_drive_metadata_snapshot;
--
-- COMMIT;
