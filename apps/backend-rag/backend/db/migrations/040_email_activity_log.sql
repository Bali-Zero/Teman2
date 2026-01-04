-- Migration 040: Email Activity Log
-- Tracks email operations for weekly reporting
-- Created: 2026-01-05

CREATE TABLE IF NOT EXISTS email_activity_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    operation VARCHAR(50) NOT NULL, -- 'sent', 'received', 'read', 'deleted', 'replied', 'forwarded'
    email_subject TEXT,
    recipient_email TEXT, -- for sent emails
    has_attachments BOOLEAN DEFAULT FALSE,
    attachment_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for efficient weekly reporting
CREATE INDEX IF NOT EXISTS idx_email_activity_user ON email_activity_log(user_id);
CREATE INDEX IF NOT EXISTS idx_email_activity_created ON email_activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_activity_user_created ON email_activity_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_email_activity_operation ON email_activity_log(operation);

-- Comment for documentation
COMMENT ON TABLE email_activity_log IS 'Tracks email operations per user for weekly activity reports';
