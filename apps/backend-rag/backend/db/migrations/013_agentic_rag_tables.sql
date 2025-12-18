-- Migration 013: Agentic RAG Tables
-- Creates tables for Parent-Child Retrieval and Golden Router

-- ============================================
-- PARENT DOCUMENTS (BAB completi)
-- ============================================
CREATE TABLE IF NOT EXISTS parent_documents (
    id VARCHAR(64) PRIMARY KEY,
    document_id VARCHAR(64) NOT NULL,
    type VARCHAR(32) DEFAULT 'chapter',
    title TEXT,
    full_text TEXT NOT NULL,
    char_count INTEGER,
    pasal_count INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_parent_docs_document ON parent_documents(document_id);

-- ============================================
-- GOLDEN ROUTES (Router, non cache)
-- ============================================
CREATE TABLE IF NOT EXISTS golden_routes (
    route_id VARCHAR(16) PRIMARY KEY,
    canonical_query TEXT NOT NULL,
    document_ids TEXT[] NOT NULL,
    chapter_ids TEXT[] DEFAULT '{}',
    collections TEXT[] NOT NULL,
    routing_hints JSONB DEFAULT '{}',
    usage_count INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS query_route_clusters (
    id SERIAL PRIMARY KEY,
    query_hash VARCHAR(32) UNIQUE,
    route_id VARCHAR(16) REFERENCES golden_routes(route_id),
    example_query TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_golden_routes_usage ON golden_routes(usage_count DESC);
CREATE INDEX IF NOT EXISTS idx_query_route_hash ON query_route_clusters(query_hash);
