-- Migration 167: CRM Knowledge Graph (separate from domain kg_nodes)
--
-- Why separate tables:
--   The existing kg_nodes/kg_edges (m028) hold domain entities (KBLI codes,
--   regulations, visa types) that are shared across all RAG queries. Mixing
--   PII-bearing CRM nodes (passports, NPWP, contracts) into the same table
--   relies on a single discriminator column for RBAC isolation, which is
--   anti-pattern: one missed WHERE clause leaks PII to non-CRM users.
--
--   Separate tables enable:
--     - DB-level grant/revoke per role (Subhi never gets SELECT on crm_kg_*)
--     - Distinct index strategies (partial indexes on entity_type)
--     - Independent vacuum/autoanalyze (CRM rows churn more than domain rows)
--     - Clean delete cascade lifecycle when files are removed from Drive
--
-- Privacy (UU PDP Indonesia):
--   passport_number / npwp / phone numbers are NEVER stored raw in this
--   table. Person/Company nodes use UUIDv5(namespace_balizero, sha256(id+salt))
--   as person_uid/company_uid; the salt lives in env CRM_KG_HASH_SALT.
--   Raw fields stay in documents.ocr_data JSONB (existing CRM table) which
--   already has DLP rules + RLS for client-data access.
--
-- Idempotency:
--   - crm_kg_nodes: UPSERT by (entity_id) → file_id/client_id/practice_id
--     are stable lookup keys; re-OCR updates properties without dup nodes
--   - crm_kg_edges: UNIQUE (source, target, relationship_type) → re-emission
--     is no-op via ON CONFLICT DO UPDATE
--
-- Lifecycle:
--   Soft-delete via deleted_at; nightly garbage collection cron will
--   hard-delete edges older than 90 days where source or target node is
--   deleted_at. (cron added in separate PR.)

-- Dependencies (ensure pgcrypto for gen_random_uuid)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ─── crm_kg_nodes ────────────────────────────────────────────────────────

CREATE TABLE crm_kg_nodes (
    entity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL CHECK (entity_type IN (
        'crm_client',
        'crm_document',
        'crm_practice',
        'crm_person',
        'crm_company',
        'crm_property'
    )),
    name TEXT NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Stable lookup keys for direct entity types. Each is unique per type
    -- because a single client_id maps to exactly one Client node, etc.
    -- These columns are nullable because not every node type uses them.
    file_id TEXT,             -- crm_document only
    client_id INTEGER,        -- crm_client only
    practice_id INTEGER,      -- crm_practice only
    person_uid UUID,          -- crm_person only — UUIDv5 of hash(passport)
    company_uid UUID,         -- crm_company only — UUIDv5 of hash(npwp)

    confidence FLOAT NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),

    -- Soft delete: set deleted_at instead of DELETE so we can recover/audit
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One Document node per Drive file_id (re-OCR updates same row)
CREATE UNIQUE INDEX idx_crm_kg_nodes_file_id ON crm_kg_nodes (file_id)
    WHERE file_id IS NOT NULL;

-- One Client/Practice node per CRM PK
CREATE UNIQUE INDEX idx_crm_kg_nodes_client_id ON crm_kg_nodes (client_id)
    WHERE client_id IS NOT NULL;

CREATE UNIQUE INDEX idx_crm_kg_nodes_practice_id ON crm_kg_nodes (practice_id)
    WHERE practice_id IS NOT NULL;

-- One Person node per UUIDv5(passport_hash). Same person across multiple
-- documents → same node (mediated edges become trivial).
CREATE UNIQUE INDEX idx_crm_kg_nodes_person_uid ON crm_kg_nodes (person_uid)
    WHERE person_uid IS NOT NULL;

CREATE UNIQUE INDEX idx_crm_kg_nodes_company_uid ON crm_kg_nodes (company_uid)
    WHERE company_uid IS NOT NULL;

-- Common filter: live nodes by type
CREATE INDEX idx_crm_kg_nodes_type_live ON crm_kg_nodes (entity_type)
    WHERE deleted_at IS NULL;

-- Properties full-text-ish search (e.g. find by extracted name fragment)
CREATE INDEX idx_crm_kg_nodes_properties ON crm_kg_nodes USING GIN (properties);

-- ─── crm_kg_edges ────────────────────────────────────────────────────────

CREATE TABLE crm_kg_edges (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id UUID NOT NULL REFERENCES crm_kg_nodes(entity_id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES crm_kg_nodes(entity_id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Tier of inference for confidence interpretation:
    --   'direct'    → SQL-deterministic (BELONGS_TO from documents.client_id)
    --   'mediated'  → SQL JOIN on shared property (SAME_PERSON_AS via uid)
    --   'thematic'  → LLM inference (RELATED_PROJECT, REGULATION_AFFECTS)
    edge_tier TEXT NOT NULL CHECK (edge_tier IN ('direct', 'mediated', 'thematic')),

    confidence FLOAT NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Idempotency: at most one edge per (src, tgt, type). Re-emission of
    -- the same fact updates confidence/properties via ON CONFLICT DO UPDATE.
    UNIQUE (source_entity_id, target_entity_id, relationship_type)
);

CREATE INDEX idx_crm_kg_edges_source_tier ON crm_kg_edges (source_entity_id, edge_tier);
CREATE INDEX idx_crm_kg_edges_target ON crm_kg_edges (target_entity_id);
CREATE INDEX idx_crm_kg_edges_type ON crm_kg_edges (relationship_type);

-- === ROLLBACK ===

DROP INDEX IF EXISTS idx_crm_kg_edges_type;
DROP INDEX IF EXISTS idx_crm_kg_edges_target;
DROP INDEX IF EXISTS idx_crm_kg_edges_source_tier;
DROP TABLE IF EXISTS crm_kg_edges;

DROP INDEX IF EXISTS idx_crm_kg_nodes_properties;
DROP INDEX IF EXISTS idx_crm_kg_nodes_type_live;
DROP INDEX IF EXISTS idx_crm_kg_nodes_company_uid;
DROP INDEX IF EXISTS idx_crm_kg_nodes_person_uid;
DROP INDEX IF EXISTS idx_crm_kg_nodes_practice_id;
DROP INDEX IF EXISTS idx_crm_kg_nodes_client_id;
DROP INDEX IF EXISTS idx_crm_kg_nodes_file_id;
DROP TABLE IF EXISTS crm_kg_nodes;
