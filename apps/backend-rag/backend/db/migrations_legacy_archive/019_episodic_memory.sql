-- Migration 019: Episodic Memory System
-- Stores timeline of events/experiences for each user
-- Enables "when did X happen?" and "what happened last week?" queries

-- ============================================================================
-- EPISODIC MEMORIES TABLE
-- ============================================================================
-- Stores individual events with temporal context
-- Each event has: who, what, when, emotion, related entities

CREATE TABLE IF NOT EXISTS episodic_memories (
    id SERIAL PRIMARY KEY,

    -- User identification
    user_id VARCHAR(255) NOT NULL,

    -- Event classification
    event_type VARCHAR(100) NOT NULL DEFAULT 'general',
    -- Types: milestone, problem, resolution, decision, meeting, deadline, discovery

    -- Event content
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Emotional context (helps AI respond appropriately)
    emotion VARCHAR(50) DEFAULT 'neutral',
    -- Values: positive, negative, neutral, urgent, frustrated, excited, worried

    -- Temporal data
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Links to Knowledge Graph entities (KBLI codes, visa types, etc.)
    related_entities JSONB DEFAULT '[]',
    -- Format: [{"entity_id": 123, "entity_type": "kbli", "name": "62011"}]

    -- Flexible metadata
    metadata JSONB DEFAULT '{}',
    -- Can include: source_message, ai_extracted, confidence, conversation_id

    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Primary query pattern: user timeline (most recent first)
CREATE INDEX IF NOT EXISTS idx_episodic_user_time
ON episodic_memories(user_id, occurred_at DESC);

-- Filter by event type
CREATE INDEX IF NOT EXISTS idx_episodic_user_type
ON episodic_memories(user_id, event_type);

-- Search by emotion (for sentiment analysis)
CREATE INDEX IF NOT EXISTS idx_episodic_user_emotion
ON episodic_memories(user_id, emotion);

-- Full-text search on title and description
CREATE INDEX IF NOT EXISTS idx_episodic_title_search
ON episodic_memories USING gin(to_tsvector('english', title || ' ' || COALESCE(description, '')));

-- JSONB index for related entities queries
CREATE INDEX IF NOT EXISTS idx_episodic_entities
ON episodic_memories USING gin(related_entities);

-- ============================================================================
-- TRIGGER: Auto-update updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_episodic_memories_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_episodic_memories_updated_at ON episodic_memories;
CREATE TRIGGER trigger_episodic_memories_updated_at
    BEFORE UPDATE ON episodic_memories
    FOR EACH ROW
    EXECUTE FUNCTION update_episodic_memories_updated_at();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE episodic_memories IS 'Timeline of user events and experiences for temporal memory';
COMMENT ON COLUMN episodic_memories.event_type IS 'Type: milestone, problem, resolution, decision, meeting, deadline, discovery';
COMMENT ON COLUMN episodic_memories.emotion IS 'Emotional context: positive, negative, neutral, urgent, frustrated, excited, worried';
COMMENT ON COLUMN episodic_memories.related_entities IS 'Links to kg_entities: [{"entity_id": 123, "entity_type": "kbli"}]';
COMMENT ON COLUMN episodic_memories.occurred_at IS 'When the event happened (user-specified or AI-extracted)';
