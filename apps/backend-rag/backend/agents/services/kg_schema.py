"""
Knowledge Graph Schema Service

Responsibility: Manage knowledge graph database schema.

Updated Dec 2025 to use unified schema (kg_nodes/kg_edges).
Tables are created via migrations (028, 029), this service
just verifies they exist.
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
        """
        Verify knowledge graph tables exist.

        The actual table creation is handled by migrations 028 and 029.
        This method verifies the tables exist and logs their status.
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Check if new schema tables exist
                kg_nodes_exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'kg_nodes'
                    )
                    """
                )

                kg_edges_exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'kg_edges'
                    )
                    """
                )

                if kg_nodes_exists and kg_edges_exists:
                    # Get counts for logging
                    nodes_count = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
                    edges_count = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")
                    logger.info(
                        f"✅ Knowledge graph schema verified: "
                        f"{nodes_count:,} nodes, {edges_count:,} edges"
                    )
                else:
                    missing = []
                    if not kg_nodes_exists:
                        missing.append("kg_nodes")
                    if not kg_edges_exists:
                        missing.append("kg_edges")
                    logger.warning(
                        f"⚠️ Knowledge graph tables missing: {', '.join(missing)}. "
                        f"Run migrations 028 and 029 to create them."
                    )

        except asyncpg.PostgresError as e:
            logger.error(f"Database error verifying schema: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error verifying schema: {e}", exc_info=True)
            raise
