-- Migration 061: Add OCR status tracking to documents table
-- Part of Auto-Land: Drive Upload → OCR → CRM Auto-Populate

-- Add OCR tracking columns to documents
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ocr_status VARCHAR(20) DEFAULT NULL;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ocr_completed_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ocr_extracted_data JSONB DEFAULT NULL;

-- Index for polling OCR status
CREATE INDEX IF NOT EXISTS idx_documents_ocr_status ON documents (ocr_status) WHERE ocr_status IS NOT NULL;

COMMENT ON COLUMN documents.ocr_status IS 'OCR processing status: pending, processing, completed, failed';
COMMENT ON COLUMN documents.ocr_completed_at IS 'Timestamp when OCR extraction completed';
COMMENT ON COLUMN documents.ocr_extracted_data IS 'Raw extracted data from OCR (JSON)';
