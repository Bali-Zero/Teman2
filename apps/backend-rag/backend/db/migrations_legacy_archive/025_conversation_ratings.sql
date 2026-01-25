-- Migration 025: Conversation Ratings System
-- Adds conversation ratings table and view for ConversationTrainer agent
-- 
-- This migration creates:
-- 1. conversation_ratings table - stores user ratings and feedback for conversations
-- 2. v_rated_conversations view - aggregates ratings with conversation messages for training

-- ================================================
-- 1. CONVERSATION_RATINGS TABLE
-- ================================================

CREATE TABLE IF NOT EXISTS conversation_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    user_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
    
    -- Rating (1-5 stelle)
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    
    -- Feedback qualitativo
    feedback_type VARCHAR(20), -- 'positive', 'negative', 'issue'
    feedback_text TEXT,
    
    -- Metadata
    turn_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indici per query frequenti
CREATE INDEX IF NOT EXISTS idx_conv_ratings_session ON conversation_ratings(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_ratings_rating ON conversation_ratings(rating) WHERE rating >= 4;
CREATE INDEX IF NOT EXISTS idx_conv_ratings_created ON conversation_ratings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conv_ratings_user ON conversation_ratings(user_id) WHERE user_id IS NOT NULL;

COMMENT ON TABLE conversation_ratings IS 'User ratings and feedback for conversations, used by ConversationTrainer agent';

-- ================================================
-- 2. VIEW: V_RATED_CONVERSATIONS
-- ================================================
-- Aggregates ratings with conversation messages for ConversationTrainer
-- Only includes high-rated conversations (rating >= 4)
-- Note: If conversation_history doesn't exist yet, messages will be NULL
--       The view will be updated automatically when migration 023 is applied

-- Create a function to safely get messages
CREATE OR REPLACE FUNCTION get_conversation_messages(session_uuid UUID)
RETURNS jsonb AS $$
DECLARE
    result jsonb;
    table_exists boolean;
BEGIN
    -- Check if conversation_history table exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public'
        AND table_name = 'conversation_history'
    ) INTO table_exists;
    
    IF table_exists THEN
        BEGIN
            SELECT jsonb_agg(
                jsonb_build_object(
                    'role', ch.role,
                    'content', ch.content
                ) ORDER BY ch.created_at
            ) INTO result
            FROM conversation_history ch 
            WHERE ch.session_id = session_uuid;
        EXCEPTION WHEN OTHERS THEN
            result := NULL;
        END;
    ELSE
        result := NULL;
    END IF;
    
    RETURN COALESCE(result, '[]'::jsonb);
END;
$$ LANGUAGE plpgsql STABLE;

-- Create view using the function
CREATE OR REPLACE VIEW v_rated_conversations AS
SELECT 
    cr.session_id::text as conversation_id,
    cr.rating,
    cr.feedback_text as client_feedback,
    cr.created_at,
    get_conversation_messages(cr.session_id) as messages
FROM conversation_ratings cr
WHERE cr.rating >= 4;

COMMENT ON VIEW v_rated_conversations IS 'High-rated conversations with messages aggregated, used by ConversationTrainer agent';

