-- Migration 018: Collective Memory System

CREATE TABLE IF NOT EXISTS collective_memories (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    category VARCHAR(100) DEFAULT 'general',
    confidence FLOAT DEFAULT 0.5,
    source_count INTEGER DEFAULT 1,
    is_promoted BOOLEAN DEFAULT FALSE,
    first_learned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_confirmed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    embedding_synced BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS collective_memory_sources (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER REFERENCES collective_memories(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    contributed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    context TEXT,
    UNIQUE(memory_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_collective_memories_category ON collective_memories(category);
CREATE INDEX IF NOT EXISTS idx_collective_memories_promoted ON collective_memories(is_promoted);
CREATE INDEX IF NOT EXISTS idx_collective_memories_confidence ON collective_memories(confidence);
CREATE INDEX IF NOT EXISTS idx_collective_memory_sources_memory ON collective_memory_sources(memory_id);
CREATE INDEX IF NOT EXISTS idx_collective_memory_sources_user ON collective_memory_sources(user_id);
