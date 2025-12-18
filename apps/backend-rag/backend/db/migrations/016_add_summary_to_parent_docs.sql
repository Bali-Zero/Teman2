-- Migration 016: Add Summary to Parent Documents
-- Adds a text column to store the AI-generated summary of the chapter/document

ALTER TABLE parent_documents
ADD COLUMN IF NOT EXISTS summary TEXT;

-- Create index for full text search on summary (optional but good for retrieval)
-- CREATE INDEX IF NOT EXISTS idx_parent_docs_summary ON parent_documents USING GIN (to_tsvector('english', summary));
