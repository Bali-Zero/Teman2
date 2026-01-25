-- Migration 022: Deduplication Constraints
-- Prevents duplicate BAB and adds content fingerprinting for OCR dedup

-- ============================================
-- CONTENT FINGERPRINTING: Detect OCR duplicates
-- ============================================
-- Note: id is already PRIMARY KEY, no additional UNIQUE constraint needed
-- For dedup, we use text_fingerprint to detect identical content from different sources
ALTER TABLE parent_documents
ADD COLUMN IF NOT EXISTS text_fingerprint VARCHAR(64);

-- Index for fast fingerprint lookup
CREATE INDEX IF NOT EXISTS idx_parent_docs_fingerprint
ON parent_documents(document_id, text_fingerprint);

-- ============================================
-- OCR QUALITY TRACKING
-- ============================================
ALTER TABLE parent_documents
ADD COLUMN IF NOT EXISTS is_incomplete BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS ocr_quality_score FLOAT DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS needs_reextract BOOLEAN DEFAULT FALSE;

-- Index for filtering incomplete documents
CREATE INDEX IF NOT EXISTS idx_parent_docs_incomplete
ON parent_documents(is_incomplete) WHERE is_incomplete = TRUE;

-- ============================================
-- SOURCE VERSION TRACKING
-- ============================================
ALTER TABLE parent_documents
ADD COLUMN IF NOT EXISTS source_id TEXT,
ADD COLUMN IF NOT EXISTS source_version VARCHAR(32),
ADD COLUMN IF NOT EXISTS ingestion_run_id VARCHAR(64),
ADD COLUMN IF NOT EXISTS is_canonical BOOLEAN DEFAULT TRUE;

-- Index for canonical lookups
CREATE INDEX IF NOT EXISTS idx_parent_docs_canonical
ON parent_documents(document_id, is_canonical) WHERE is_canonical = TRUE;

-- ============================================
-- COMMENT DOCUMENTATION
-- ============================================
COMMENT ON COLUMN parent_documents.text_fingerprint IS
'SHA256 hash of normalized text (lowercase, no spaces) for OCR duplicate detection';

COMMENT ON COLUMN parent_documents.is_incomplete IS
'True if text contains placeholders (". . .") or missing ayat';

COMMENT ON COLUMN parent_documents.ocr_quality_score IS
'Quality score 0.0-1.0: 1.0=perfect, <0.7=needs review';

COMMENT ON COLUMN parent_documents.needs_reextract IS
'Flag for documents requiring re-extraction from better source';

COMMENT ON COLUMN parent_documents.source_id IS
'Original source identifier (file path, URL, Drive ID)';

COMMENT ON COLUMN parent_documents.source_version IS
'Version identifier for document (e.g., "v1", "2023-12-19", "OCR_tesseract")';

COMMENT ON COLUMN parent_documents.ingestion_run_id IS
'Batch ingestion run ID for tracking and rollback';

COMMENT ON COLUMN parent_documents.is_canonical IS
'True if this is the canonical version (used in production queries)';
