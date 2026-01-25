-- Migration 026: Review Queue System
-- Adds review_queue table for feedback correction logic
-- 
-- This migration creates:
-- 1. review_queue table - stores feedback items that need manual review
--    (low ratings <= 2 or items with correction_text)

-- ================================================
-- 1. REVIEW_QUEUE TABLE
-- ================================================

CREATE TABLE IF NOT EXISTS review_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_feedback_id UUID NOT NULL REFERENCES conversation_ratings(id) ON DELETE CASCADE,
    
    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'resolved', 'ignored')),
    
    -- Priority (optional, for manual prioritization)
    priority VARCHAR(20), -- 'low', 'medium', 'high', 'urgent'
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    
    -- Optional resolution notes
    resolution_notes TEXT
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue(status);
CREATE INDEX IF NOT EXISTS idx_review_queue_created ON review_queue(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_queue_feedback_id ON review_queue(source_feedback_id);
CREATE INDEX IF NOT EXISTS idx_review_queue_pending ON review_queue(status, created_at DESC) WHERE status = 'pending';

COMMENT ON TABLE review_queue IS 'Queue for feedback items requiring manual review (low ratings or corrections)';
COMMENT ON COLUMN review_queue.source_feedback_id IS 'Foreign key to conversation_ratings table';
COMMENT ON COLUMN review_queue.status IS 'Status: pending (needs review), resolved (reviewed and handled), ignored (dismissed)';
COMMENT ON COLUMN review_queue.priority IS 'Optional priority level for manual prioritization';


