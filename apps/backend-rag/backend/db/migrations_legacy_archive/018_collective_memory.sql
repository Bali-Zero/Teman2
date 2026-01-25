-- Migration 018: Collective Memory System
-- Shared knowledge learned from multiple users
-- Created: 2025-12-16

BEGIN;

-- ============================================
-- COLLECTIVE MEMORIES TABLE
-- Stores facts confirmed by multiple users
-- ============================================

CREATE TABLE IF NOT EXISTS collective_memories (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,  -- SHA256 for deduplication
    category VARCHAR(100) DEFAULT 'general',  -- process, location, provider, regulation, tip
    confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    source_count INTEGER DEFAULT 1,
    is_promoted BOOLEAN DEFAULT FALSE,  -- TRUE when source_count >= 3
    first_learned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_confirmed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(content_hash)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_collective_memories_category ON collective_memories(category);
CREATE INDEX IF NOT EXISTS idx_collective_memories_confidence ON collective_memories(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_collective_memories_promoted ON collective_memories(is_promoted) WHERE is_promoted = TRUE;
CREATE INDEX IF NOT EXISTS idx_collective_memories_content_hash ON collective_memories(content_hash);

-- ============================================
-- COLLECTIVE MEMORY SOURCES TABLE
-- Tracks who contributed each fact (audit trail)
-- ============================================

CREATE TABLE IF NOT EXISTS collective_memory_sources (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER REFERENCES collective_memories(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,  -- email completa per audit
    conversation_id INTEGER,
    action VARCHAR(20) DEFAULT 'contribute',  -- contribute, confirm, refute
    contributed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(memory_id, user_id, action)  -- one action per user per memory
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_collective_sources_memory ON collective_memory_sources(memory_id);
CREATE INDEX IF NOT EXISTS idx_collective_sources_user ON collective_memory_sources(user_id);

-- ============================================
-- HELPER FUNCTION: Update source count and confidence
-- ============================================

CREATE OR REPLACE FUNCTION update_collective_memory_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update source count
    UPDATE collective_memories
    SET
        source_count = (
            SELECT COUNT(DISTINCT user_id)
            FROM collective_memory_sources
            WHERE memory_id = NEW.memory_id AND action IN ('contribute', 'confirm')
        ),
        last_confirmed_at = NOW(),
        -- Auto-promote when 3+ sources
        is_promoted = (
            SELECT COUNT(DISTINCT user_id) >= 3
            FROM collective_memory_sources
            WHERE memory_id = NEW.memory_id AND action IN ('contribute', 'confirm')
        ),
        -- Adjust confidence based on confirmations vs refutations
        confidence = LEAST(1.0, GREATEST(0.0,
            0.5 + (
                (SELECT COUNT(*) FROM collective_memory_sources WHERE memory_id = NEW.memory_id AND action IN ('contribute', 'confirm')) * 0.1
            ) - (
                (SELECT COUNT(*) FROM collective_memory_sources WHERE memory_id = NEW.memory_id AND action = 'refute') * 0.15
            )
        ))
    WHERE id = NEW.memory_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update stats on source changes
DROP TRIGGER IF EXISTS trigger_update_collective_stats ON collective_memory_sources;
CREATE TRIGGER trigger_update_collective_stats
    AFTER INSERT OR UPDATE ON collective_memory_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_collective_memory_stats();

-- ============================================
-- CATEGORIES REFERENCE
-- ============================================
COMMENT ON COLUMN collective_memories.category IS 'Categories: process, location, provider, regulation, tip, pricing, timeline, general';

COMMIT;
