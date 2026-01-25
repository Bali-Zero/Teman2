-- Memory System Tables for ZANTARA
-- Created: 2025-10-20
-- Purpose: Persistent user memory storage (facts, stats, preferences)

-- ========================================
-- MEMORY FACTS TABLE
-- ========================================
-- Stores individual facts about users/collaborators
-- Used for personalized context in conversations

CREATE TABLE IF NOT EXISTS memory_facts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    fact_type VARCHAR(100) DEFAULT 'general',
    confidence FLOAT DEFAULT 1.0,
    source VARCHAR(50) DEFAULT 'user',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast user lookup
CREATE INDEX IF NOT EXISTS idx_memory_facts_user_id ON memory_facts(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_facts_created_at ON memory_facts(created_at DESC);

-- ========================================
-- USER STATS TABLE
-- ========================================
-- Stores user activity counters and conversation summaries

CREATE TABLE IF NOT EXISTS user_stats (
    user_id VARCHAR(255) PRIMARY KEY,
    conversations_count INTEGER DEFAULT 0,
    searches_count INTEGER DEFAULT 0,
    tasks_count INTEGER DEFAULT 0,
    summary TEXT DEFAULT '',
    preferences JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for activity tracking
CREATE INDEX IF NOT EXISTS idx_user_stats_last_activity ON user_stats(last_activity DESC);

-- ========================================
-- CONVERSATIONS TABLE
-- ========================================
-- Stores full conversation history

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255),
    messages JSONB NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for user conversations lookup
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);

-- ========================================
-- USERS TABLE (if not exists from other migrations)
-- ========================================
-- Basic user tracking

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(255) PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- COMMENTS
-- ========================================

COMMENT ON TABLE memory_facts IS 'Stores individual facts extracted from conversations for persistent memory';
COMMENT ON TABLE user_stats IS 'Tracks user activity counters and conversation summaries';
COMMENT ON TABLE conversations IS 'Full conversation history for context retrieval';
COMMENT ON TABLE users IS 'Basic user information and metadata';

-- ========================================
-- END OF MIGRATION
-- ========================================
