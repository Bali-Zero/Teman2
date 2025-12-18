"""
Knowledge Graph Schema Service

Responsibility: Manage knowledge graph database schema.
"""

import logging

import asyncpg

logger = logging.getLogger(__name__)


class KnowledgeGraphSchema:
    """Service for managing knowledge graph database schema"""

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize KnowledgeGraphSchema.

        Args:
            db_pool: AsyncPG connection pool
        """
        self.db_pool = db_pool

    async def init_schema(self):
        """Create knowledge graph tables if they don't exist"""
        try:
            async with self.db_pool.acquire() as conn, conn.transaction():
                # Entities table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kg_entities (
                        id SERIAL PRIMARY KEY,
                        type VARCHAR(50) NOT NULL,
                        name TEXT NOT NULL,
                        canonical_name TEXT,
                        metadata JSONB DEFAULT '{}',
                        mention_count INTEGER DEFAULT 1,
                        first_seen_at TIMESTAMP DEFAULT NOW(),
                        last_seen_at TIMESTAMP DEFAULT NOW(),
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(type, canonical_name)
                    );

                    CREATE INDEX IF NOT EXISTS idx_kg_entities_type ON kg_entities(type);
                    CREATE INDEX IF NOT EXISTS idx_kg_entities_canonical ON kg_entities(canonical_name);
                    """
                )

                # Relationships table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kg_relationships (
                        id SERIAL PRIMARY KEY,
                        source_entity_id INTEGER REFERENCES kg_entities(id),
                        target_entity_id INTEGER REFERENCES kg_entities(id),
                        relationship_type VARCHAR(50) NOT NULL,
                        strength FLOAT DEFAULT 1.0,
                        evidence TEXT[],
                        source_references JSONB DEFAULT '[]',
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(source_entity_id, target_entity_id, relationship_type)
                    );

                    CREATE INDEX IF NOT EXISTS idx_kg_rel_source ON kg_relationships(source_entity_id);
                    CREATE INDEX IF NOT EXISTS idx_kg_rel_target ON kg_relationships(target_entity_id);
                    """
                )

                # Entity mentions table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kg_entity_mentions (
                        id SERIAL PRIMARY KEY,
                        entity_id INTEGER REFERENCES kg_entities(id),
                        source_type VARCHAR(50) NOT NULL,
                        source_id TEXT NOT NULL,
                        context TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    );

                    CREATE INDEX IF NOT EXISTS idx_kg_mentions_entity ON kg_entity_mentions(entity_id);
                    CREATE INDEX IF NOT EXISTS idx_kg_mentions_source ON kg_entity_mentions(source_type, source_id);
                    """
                )

            logger.info("✅ Knowledge graph schema initialized")
        except asyncpg.PostgresError as e:
            logger.error(f"Database error initializing schema: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing schema: {e}", exc_info=True)
            raise




