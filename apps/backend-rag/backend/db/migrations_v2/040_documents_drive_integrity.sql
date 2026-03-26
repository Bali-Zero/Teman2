-- Migration 040: Documents Drive Integrity
-- Add drive_verified_at column and partial NOT NULL constraint for Google Drive docs.
-- Safe to run on live DB — no table rewrites, no lock escalation.

-- 1. Add drive_verified_at column (nullable, backfill later via background job)
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS drive_verified_at TIMESTAMPTZ;

-- 2. Add CHECK constraint: if storage_type = 'google_drive', file_id must not be null or empty.
--    Uses a partial expression so existing NULL file_id rows on non-Drive docs are unaffected.
ALTER TABLE documents
    ADD CONSTRAINT chk_documents_drive_file_id
    CHECK (
        storage_type IS DISTINCT FROM 'google_drive'
        OR (file_id IS NOT NULL AND file_id <> '')
    );

-- 3. Index for quick lookup of unverified Drive documents (background verifier job).
CREATE INDEX IF NOT EXISTS idx_documents_drive_unverified
    ON documents (id)
    WHERE storage_type = 'google_drive'
      AND drive_verified_at IS NULL;
