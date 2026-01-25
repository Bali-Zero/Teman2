-- Migration 014: Knowledge Graph Tables
-- Creates tables for Knowledge Graph (Entities and Relationships)

CREATE TABLE IF NOT EXISTS kg_entities (
    id VARCHAR(64) PRIMARY KEY,
    type VARCHAR(32) NOT NULL,
    name TEXT NOT NULL,
    canonical_name TEXT,
    description TEXT,
    mention_count INTEGER DEFAULT 0,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kg_entity_name ON kg_entities(name);
CREATE INDEX IF NOT EXISTS idx_kg_entity_type ON kg_entities(type);
CREATE INDEX IF NOT EXISTS idx_kg_canonical ON kg_entities(canonical_name);

CREATE TABLE IF NOT EXISTS kg_relationships (
    id SERIAL PRIMARY KEY,
    source_entity_id VARCHAR(64) REFERENCES kg_entities(id),
    target_entity_id VARCHAR(64) REFERENCES kg_entities(id),
    relationship_type VARCHAR(32) NOT NULL,
    strength FLOAT DEFAULT 1.0,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_entity_id, target_entity_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_kg_rel_source ON kg_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_target ON kg_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_type ON kg_relationships(relationship_type);
