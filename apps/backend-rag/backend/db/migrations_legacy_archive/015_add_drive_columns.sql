-- Migration 015: Add Drive Columns
-- Adds Google Drive metadata to parent_documents

ALTER TABLE parent_documents
ADD COLUMN IF NOT EXISTS drive_file_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS drive_web_view_link TEXT,
ADD COLUMN IF NOT EXISTS mime_type VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_parent_docs_drive_id ON parent_documents(drive_file_id);
