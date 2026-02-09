-- ================================================
-- OMNICHANNEL WORKFLOW MIGRATION
-- Adds status, assignment, and internal notes
-- ================================================

-- 1. Add workflow columns to conversations
ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'open',
ADD COLUMN IF NOT EXISTS priority VARCHAR(50) DEFAULT 'medium',
ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(255),
ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS unread_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- 2. Create index for performance
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_conversations_assigned_to ON conversations(assigned_to);

-- 3. Create Internal Notes table
CREATE TABLE IF NOT EXISTS conversation_notes (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    author_id VARCHAR(255), -- Team member identifier
    author_name VARCHAR(255),
    content TEXT NOT NULL,
    is_system_note BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversation_notes_conv_id ON conversation_notes(conversation_id);
