-- Fix missing tables for Migration 013 and downstream dependencies
-- This SQL script ensures parent_documents, golden_routes and query_route_clusters exist.

-- 1. Create parent_documents
CREATE TABLE IF NOT EXISTS parent_documents (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    type TEXT,
    title TEXT,
    full_text TEXT,
    summary TEXT,
    char_count INTEGER,
    pasal_count INTEGER,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Create golden_routes
CREATE TABLE IF NOT EXISTS golden_routes (
    route_id TEXT PRIMARY KEY,
    canonical_query TEXT NOT NULL,
    document_ids TEXT[] DEFAULT '{}',
    chapter_ids TEXT[] DEFAULT '{}',
    collections TEXT[] DEFAULT '{"legal_unified"}',
    routing_hints JSONB DEFAULT '{}',
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Create query_route_clusters
CREATE TABLE IF NOT EXISTS query_route_clusters (
    cluster_id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,
    route_ids TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_parent_docs_doc_id ON parent_documents(document_id);
CREATE INDEX IF NOT EXISTS idx_golden_routes_query ON golden_routes(canonical_query);
