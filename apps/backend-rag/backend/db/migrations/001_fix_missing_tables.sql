-- ================================================
-- Migration 001: Fix missing PostgreSQL tables
-- Created: 2025-10-19
-- Purpose: Create cultural_knowledge, query_clusters tables and fix memory_facts.id
-- Idempotency: YES
-- ================================================

BEGIN;

-- Create cultural_knowledge table
CREATE TABLE IF NOT EXISTS cultural_knowledge (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    category VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cultural_knowledge_language ON cultural_knowledge(language);
CREATE INDEX IF NOT EXISTS idx_cultural_knowledge_category ON cultural_knowledge(category);

-- Create query_clusters table
CREATE TABLE IF NOT EXISTS query_clusters (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    cluster_id INTEGER,
    similarity_score FLOAT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_clusters_cluster_id ON query_clusters(cluster_id);

-- Fix memory_facts table (add id column if missing)
DO $$
BEGIN
    -- Check if memory_facts table exists
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'memory_facts'
    ) THEN
        -- Check if id column exists
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'memory_facts' AND column_name = 'id'
        ) THEN
            ALTER TABLE memory_facts ADD COLUMN id SERIAL PRIMARY KEY;
            RAISE NOTICE 'Added id column to memory_facts table';
        ELSE
            RAISE NOTICE 'memory_facts.id column already exists';
        END IF;
    ELSE
        RAISE NOTICE 'memory_facts table does not exist (will be created by app)';
    END IF;
END $$;

COMMIT;


















