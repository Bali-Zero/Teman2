-- Migration 020: Collective Memory Vector Search Setup
-- Enables semantic search for collective memories via Qdrant
-- Created: 2025-12-17

BEGIN;

-- ============================================
-- NOTE: Vectors are stored in Qdrant, not PostgreSQL
-- This migration just tracks that setup was done
-- ============================================

-- Add tracking column for embedding sync status
ALTER TABLE collective_memories
ADD COLUMN IF NOT EXISTS embedding_synced BOOLEAN DEFAULT FALSE;

-- Index for finding unsynced memories (for backfill)
CREATE INDEX IF NOT EXISTS idx_collective_unsynced
ON collective_memories(embedding_synced) WHERE embedding_synced = FALSE;

-- Comment documenting the Qdrant integration
COMMENT ON COLUMN collective_memories.embedding_synced IS 'TRUE when embedding has been synced to Qdrant collective_memories collection';

COMMIT;
