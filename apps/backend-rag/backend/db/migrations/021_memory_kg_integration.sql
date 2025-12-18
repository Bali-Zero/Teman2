-- ========================================
-- Migration 021: Memory-Knowledge Graph Integration
-- Links memory_facts to kg_entities for richer context
-- ========================================

-- Add related_entities column to memory_facts
-- Stores array of kg_entity IDs related to this fact
-- FIX: Using VARCHAR(64)[] to match kg_entities.id type (not INTEGER[])
ALTER TABLE memory_facts
ADD COLUMN IF NOT EXISTS related_entities VARCHAR(64)[] DEFAULT '{}';

-- Create GIN index for efficient array lookups
CREATE INDEX IF NOT EXISTS idx_memory_facts_entities
ON memory_facts USING GIN(related_entities);

-- Add kg_entity_ids to episodic_memories as well
-- For linking timeline events to KG entities
-- FIX: Using VARCHAR(64)[] to match kg_entities.id type (not INTEGER[])
ALTER TABLE episodic_memories
ADD COLUMN IF NOT EXISTS kg_entity_ids VARCHAR(64)[] DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_episodic_kg_entities
ON episodic_memories USING GIN(kg_entity_ids);

-- Create view for easy fact-entity joins
CREATE OR REPLACE VIEW memory_facts_with_entities AS
SELECT
    mf.id,
    mf.user_id,
    mf.content,
    mf.fact_type,
    mf.confidence,
    mf.source,
    mf.metadata,
    mf.created_at,
    mf.related_entities,
    COALESCE(
        json_agg(
            json_build_object(
                'id', ke.id,
                'type', ke.type,
                'name', ke.name,
                'canonical_name', ke.canonical_name
            )
        ) FILTER (WHERE ke.id IS NOT NULL),
        '[]'::json
    ) as entities
FROM memory_facts mf
LEFT JOIN kg_entities ke ON ke.id = ANY(mf.related_entities)
GROUP BY mf.id, mf.user_id, mf.content, mf.fact_type, mf.confidence,
         mf.source, mf.metadata, mf.created_at, mf.related_entities;

-- Function to get entities for a user's memories
-- FIX: entity_id is VARCHAR(64) to match kg_entities.id type
-- FIX: SELECT uses 'mention_count' alias to match RETURNS TABLE definition
CREATE OR REPLACE FUNCTION get_user_memory_entities(p_user_id VARCHAR(255))
RETURNS TABLE (
    entity_id VARCHAR(64),
    entity_type VARCHAR(50),
    entity_name TEXT,
    mention_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ke.id,
        ke.type,
        ke.name,
        COUNT(*)::BIGINT as mention_count
    FROM memory_facts mf
    CROSS JOIN UNNEST(mf.related_entities) AS entity_id_val
    JOIN kg_entities ke ON ke.id = entity_id_val
    WHERE mf.user_id = p_user_id
    GROUP BY ke.id, ke.type, ke.name
    ORDER BY mention_count DESC;
END;
$$ LANGUAGE plpgsql;

