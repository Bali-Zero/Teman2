-- Migration 037: Add practice required documents table
-- This table stores documents required for each practice/process
-- and tracks their upload status by clients

CREATE TABLE IF NOT EXISTS practice_required_documents (
    id SERIAL PRIMARY KEY,
    practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
    document_type VARCHAR(100) NOT NULL,
    document_label VARCHAR(200) NOT NULL,
    description TEXT,
    is_required BOOLEAN DEFAULT TRUE,
    uploaded_by_client BOOLEAN DEFAULT FALSE,
    uploaded_file_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    uploaded_at TIMESTAMP,
    client_notes TEXT,
    team_member_notes TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- pending, uploaded, verified, rejected
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255) NOT NULL,
    UNIQUE(practice_id, document_type)
);

-- Index for faster lookups
CREATE INDEX idx_practice_required_docs_practice_id ON practice_required_documents(practice_id);
CREATE INDEX idx_practice_required_docs_status ON practice_required_documents(status);
CREATE INDEX idx_practice_required_docs_uploaded ON practice_required_documents(uploaded_by_client);

-- Add notification column to practices table
ALTER TABLE practices ADD COLUMN IF NOT EXISTS client_notification_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE practices ADD COLUMN IF NOT EXISTS client_notification_sent_at TIMESTAMP;

-- Migration log
INSERT INTO migration_log (version, description, applied_at)
VALUES ('037', 'Add practice required documents table', NOW());
