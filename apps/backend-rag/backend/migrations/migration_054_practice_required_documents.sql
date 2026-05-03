-- Migration: Create practice_required_documents table
-- Description: Stores document requirements for practices/cases
-- Created: 2025-02-19

-- Create the table
CREATE TABLE IF NOT EXISTS practice_required_documents (
    id SERIAL PRIMARY KEY,
    practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,
    document_label VARCHAR(100) NOT NULL,
    description TEXT,
    is_required BOOLEAN DEFAULT TRUE,
    
    -- Upload tracking
    uploaded_by_client BOOLEAN DEFAULT FALSE,
    uploaded_file_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    uploaded_at TIMESTAMP,
    
    -- Notes
    client_notes TEXT,
    team_member_notes TEXT,
    
    -- Status: pending, uploaded, verified, rejected
    status VARCHAR(20) DEFAULT 'pending',
    
    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(practice_id, document_type),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'uploaded', 'verified', 'rejected'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_practice_required_docs_practice_id 
    ON practice_required_documents(practice_id);
CREATE INDEX IF NOT EXISTS idx_practice_required_docs_status 
    ON practice_required_documents(status);
CREATE INDEX IF NOT EXISTS idx_practice_required_docs_uploaded 
    ON practice_required_documents(uploaded_by_client) 
    WHERE uploaded_by_client = TRUE;

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_practice_required_docs_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_practice_required_docs_timestamp 
    ON practice_required_documents;

CREATE TRIGGER trigger_update_practice_required_docs_timestamp
    BEFORE UPDATE ON practice_required_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_practice_required_docs_timestamp();

-- Add client_notification_sent to practices if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'practices' AND column_name = 'client_notification_sent'
    ) THEN
        ALTER TABLE practices ADD COLUMN client_notification_sent BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Comment for documentation
COMMENT ON TABLE practice_required_documents IS 'Stores document requirements for each practice/case';
COMMENT ON COLUMN practice_required_documents.document_type IS 'Type of document: passport, photo, cv, bank_statement, etc.';
COMMENT ON COLUMN practice_required_documents.status IS 'Document status: pending, uploaded, verified, rejected';
