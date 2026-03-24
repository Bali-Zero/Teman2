"""
Migration 064: Add reverse traversal index on kg_edges

Adds composite index on (target_entity_id, relationship_type) to support
efficient reverse graph traversal queries like "what REQUIRES entity X?".
Forward traversal index (source_entity_id, relationship_type) already exists
from migration 055.
"""

import logging

logger = logging.getLogger(__name__)


async def upgrade(conn) -> None:
    """Add reverse traversal composite index."""
    await conn.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_kg_edges_target_reltype
        ON kg_edges (target_entity_id, relationship_type);
    """)
    logger.info("Created index idx_kg_edges_target_reltype on kg_edges")


async def downgrade(conn) -> None:
    """Remove reverse traversal index."""
    await conn.execute("DROP INDEX IF EXISTS idx_kg_edges_target_reltype;")
    logger.info("Dropped index idx_kg_edges_target_reltype")
