"""
Migration 097: KG Entity Mentions — Cross-source entity resolution for GraphRAG 2.0

Links Qdrant vector document chunks to KG entities via entity mentions.
Enables graph-aware retrieval: when a document mentions a KG entity,
the graph neighborhood of that entity enriches the retrieval signal.

Table:
  - kg_entity_mentions: entity_id → (collection, point_id) linkage
"""

MIGRATION_ID = "097_entity_mentions"

UP_SQL = """
CREATE TABLE IF NOT EXISTS kg_entity_mentions (
    mention_id      TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES kg_nodes(entity_id) ON DELETE CASCADE,
    collection_name TEXT NOT NULL,
    point_id        TEXT NOT NULL,
    mention_text    TEXT NOT NULL,
    confidence      FLOAT NOT NULL DEFAULT 0.7,
    match_type      TEXT NOT NULL DEFAULT 'fuzzy',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Entity lookup: "which documents mention this entity?"
CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity ON kg_entity_mentions(entity_id);

-- Document lookup: "which entities are in this document?"
CREATE INDEX IF NOT EXISTS idx_entity_mentions_point ON kg_entity_mentions(collection_name, point_id);

-- High-confidence filtering
CREATE INDEX IF NOT EXISTS idx_entity_mentions_conf ON kg_entity_mentions(confidence)
    WHERE confidence >= 0.7;

-- Prevent duplicate mentions
CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_mentions_dedup
    ON kg_entity_mentions(entity_id, collection_name, point_id);
"""

DOWN_SQL = """
DROP TABLE IF EXISTS kg_entity_mentions;
"""


async def up(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(UP_SQL)


async def down(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(DOWN_SQL)
