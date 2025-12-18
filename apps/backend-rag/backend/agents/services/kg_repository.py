"""
Knowledge Graph Repository

Responsibility: Database operations for knowledge graph (entities, relationships, queries).
"""

import json
import logging
from datetime import datetime
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Constants
DEFAULT_TOP_N = 20
DEFAULT_TOP_K = 10


class KnowledgeGraphRepository:
    """Service for knowledge graph database operations"""

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize KnowledgeGraphRepository.

        Args:
            db_pool: AsyncPG connection pool
        """
        self.db_pool = db_pool

    async def upsert_entity(
        self,
        entity_type: str,
        name: str,
        canonical_name: str,
        metadata: dict[str, Any],
        conn: asyncpg.Connection,
    ) -> int:
        """
        Insert or update entity, return entity_id.

        Args:
            entity_type: Type of entity (law, topic, company, etc.)
            name: Entity name as mentioned
            canonical_name: Normalized entity name
            metadata: Additional metadata
            conn: Database connection (must be in transaction)

        Returns:
            Entity ID
        """
        row = await conn.fetchrow(
            """
            INSERT INTO kg_entities (type, name, canonical_name, metadata, mention_count, last_seen_at)
            VALUES ($1, $2, $3, $4, 1, NOW())
            ON CONFLICT (type, canonical_name)
            DO UPDATE SET
                mention_count = kg_entities.mention_count + 1,
                last_seen_at = NOW(),
                metadata = kg_entities.metadata || EXCLUDED.metadata
            RETURNING id
            """,
            entity_type,
            name,
            canonical_name,
            json.dumps(metadata),
        )

        return row["id"] if row else 0

    async def upsert_relationship(
        self,
        source_id: int,
        target_id: int,
        rel_type: str,
        strength: float,
        evidence: str,
        source_ref: dict[str, Any],
        conn: asyncpg.Connection,
    ):
        """
        Insert or update relationship.

        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            rel_type: Relationship type
            strength: Relationship strength (0-1)
            evidence: Evidence text
            source_ref: Source reference metadata
            conn: Database connection (must be in transaction)
        """
        await conn.execute(
            """
            INSERT INTO kg_relationships (
                source_entity_id, target_entity_id, relationship_type,
                strength, evidence, source_references
            )
            VALUES ($1, $2, $3, $4, ARRAY[$5], $6::jsonb)
            ON CONFLICT (source_entity_id, target_entity_id, relationship_type)
            DO UPDATE SET
                strength = (kg_relationships.strength + EXCLUDED.strength) / 2,
                evidence = array_append(kg_relationships.evidence, EXCLUDED.evidence[1]),
                source_references = kg_relationships.source_references || EXCLUDED.source_references,
                updated_at = NOW()
            """,
            source_id,
            target_id,
            rel_type,
            strength,
            evidence,
            json.dumps([source_ref]),
        )

    async def add_entity_mention(
        self,
        entity_id: int,
        source_type: str,
        source_id: str,
        context: str,
        conn: asyncpg.Connection,
    ):
        """
        Add entity mention record.

        Args:
            entity_id: Entity ID
            source_type: Type of source (conversation, document, etc.)
            source_id: Source identifier
            context: Context where entity was mentioned
            conn: Database connection (must be in transaction)
        """
        await conn.execute(
            """
            INSERT INTO kg_entity_mentions (entity_id, source_type, source_id, context)
            VALUES ($1, $2, $3, $4)
            """,
            entity_id,
            source_type,
            source_id,
            context[:500] if context else "",
        )

    async def get_entity_insights(self, top_n: int = DEFAULT_TOP_N) -> dict[str, Any]:
        """
        Get insights from knowledge graph.

        Args:
            top_n: Number of top entities to return

        Returns:
            Dictionary with insights
        """
        if top_n < 1 or top_n > 100:
            top_n = DEFAULT_TOP_N

        try:
            async with self.db_pool.acquire() as conn:
                # Top entities by type
                top_entities_rows = await conn.fetch(
                    """
                    SELECT type, name, mention_count
                    FROM kg_entities
                    ORDER BY mention_count DESC
                    LIMIT $1
                    """,
                    top_n,
                )

                top_entities = [
                    {"type": row["type"], "name": row["name"], "mentions": row["mention_count"]}
                    for row in top_entities_rows
                ]

                # Most connected entities (hub analysis)
                hubs_rows = await conn.fetch(
                    """
                    SELECT
                        e.type,
                        e.name,
                        COUNT(DISTINCT r.id) as connection_count
                    FROM kg_entities e
                    JOIN kg_relationships r ON e.id = r.source_entity_id OR e.id = r.target_entity_id
                    GROUP BY e.id, e.type, e.name
                    ORDER BY connection_count DESC
                    LIMIT $1
                    """,
                    top_n,
                )

                hubs = [
                    {
                        "type": row["type"],
                        "name": row["name"],
                        "connections": row["connection_count"],
                    }
                    for row in hubs_rows
                ]

                # Relationship insights
                rel_rows = await conn.fetch(
                    """
                    SELECT relationship_type, COUNT(*) as count
                    FROM kg_relationships
                    GROUP BY relationship_type
                    ORDER BY count DESC
                    """
                )

                rel_types = {row["relationship_type"]: row["count"] for row in rel_rows}

                return {
                    "top_entities": top_entities,
                    "hubs": hubs,
                    "relationship_types": rel_types,
                    "generated_at": datetime.now().isoformat(),
                }

        except asyncpg.PostgresError as e:
            logger.error(f"Database error getting insights: {e}", exc_info=True)
            return {
                "top_entities": [],
                "hubs": [],
                "relationship_types": {},
                "generated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Unexpected error getting insights: {e}", exc_info=True)
            return {
                "top_entities": [],
                "hubs": [],
                "relationship_types": {},
                "generated_at": datetime.now().isoformat(),
            }

    async def get_user_related_entities(
        self, user_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get entities related to a user's memories.

        Args:
            user_id: User identifier
            limit: Maximum entities to return

        Returns:
            List of entities with type, name, and mention count
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Check if the function exists (created by migration 021)
                func_exists = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM information_schema.routines
                        WHERE routine_name = 'get_user_memory_entities'
                    )
                    """
                )

                if func_exists:
                    # Use the optimized function
                    rows = await conn.fetch(
                        "SELECT * FROM get_user_memory_entities($1) LIMIT $2",
                        user_id,
                        limit,
                    )
                    return [
                        {
                            "entity_id": row["entity_id"],
                            "type": row["entity_type"],
                            "name": row["entity_name"],
                            "mentions": row["mention_count"],
                        }
                        for row in rows
                    ]
                else:
                    # Fallback: replicate SQL function logic
                    # Query memory_facts.related_entities and unnest, matching the function's behavior
                    rows = await conn.fetch(
                        """
                        SELECT
                            ke.id as entity_id,
                            ke.type,
                            ke.name,
                            COUNT(*)::BIGINT as mention_count
                        FROM memory_facts mf
                        CROSS JOIN UNNEST(mf.related_entities) AS entity_id_val
                        JOIN kg_entities ke ON ke.id = entity_id_val
                        WHERE mf.user_id = $1
                        GROUP BY ke.id, ke.type, ke.name
                        ORDER BY mention_count DESC
                        LIMIT $2
                        """,
                        user_id,
                        limit,
                    )
                    return [
                        {
                            "entity_id": row["entity_id"],  # VARCHAR(64)
                            "type": row["type"],
                            "name": row["name"],
                            "mentions": row["mention_count"],
                        }
                        for row in rows
                    ]

        except Exception as e:
            logger.warning(f"Error getting user related entities: {e}")
            return []

    async def get_entity_context_for_query(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Get relevant entities for a query to enrich AI context.

        Args:
            query: User's query text
            limit: Maximum entities to return

        Returns:
            List of relevant entities with descriptions
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Text-based search (can be enhanced with embeddings)
                query_pattern = f"%{query}%"
                rows = await conn.fetch(
                    """
                    SELECT
                        e.id,
                        e.type,
                        e.name,
                        e.canonical_name,
                        e.metadata,
                        e.mention_count,
                        array_agg(DISTINCT r.relationship_type) as relationship_types
                    FROM kg_entities e
                    LEFT JOIN kg_relationships r ON e.id = r.source_entity_id OR e.id = r.target_entity_id
                    WHERE
                        e.name ILIKE $1
                        OR e.canonical_name ILIKE $1
                    GROUP BY e.id, e.type, e.name, e.canonical_name, e.metadata, e.mention_count
                    ORDER BY e.mention_count DESC
                    LIMIT $2
                    """,
                    query_pattern,
                    limit,
                )

                return [
                    {
                        "entity_id": row["id"],
                        "type": row["type"],
                        "name": row["name"],
                        "canonical_name": row["canonical_name"],
                        "metadata": row["metadata"],
                        "mentions": row["mention_count"],
                        "relationships": row["relationship_types"] or [],
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.warning(f"Error getting entity context: {e}")
            return []

    async def semantic_search_entities(
        self, query: str, top_k: int = DEFAULT_TOP_K
    ) -> list[dict[str, Any]]:
        """
        Search entities semantically.

        Args:
            query: Search query text
            top_k: Number of results to return

        Returns:
            List of matching entities
        """
        if not query:
            return []

        if top_k < 1 or top_k > 100:
            top_k = DEFAULT_TOP_K

        try:
            async with self.db_pool.acquire() as conn:
                # Simple text search for now (can be enhanced with embeddings)
                query_pattern = f"%{query}%"
                rows = await conn.fetch(
                    """
                    SELECT
                        e.id,
                        e.type,
                        e.name,
                        e.mention_count,
                        e.metadata,
                        COUNT(DISTINCT m.id) as mention_count_in_sources
                    FROM kg_entities e
                    LEFT JOIN kg_entity_mentions m ON e.id = m.entity_id
                    WHERE
                        e.name ILIKE $1
                        OR e.canonical_name ILIKE $2
                        OR e.metadata::text ILIKE $3
                    GROUP BY e.id, e.type, e.name, e.mention_count, e.metadata
                    ORDER BY mention_count_in_sources DESC
                    LIMIT $4
                    """,
                    query_pattern,
                    query_pattern,
                    query_pattern,
                    top_k,
                )

                return [
                    {
                        "entity_id": row["id"],
                        "type": row["type"],
                        "name": row["name"],
                        "mentions": row["mention_count"],
                        "metadata": row["metadata"],
                        "source_mentions": row["mention_count_in_sources"],
                    }
                    for row in rows
                ]

        except asyncpg.PostgresError as e:
            logger.error(f"Database error in semantic search: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error in semantic search: {e}", exc_info=True)
            return []

    async def get_user_related_entities(
        self, user_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get entities related to a user's memories.

        Args:
            user_id: User identifier
            limit: Maximum entities to return

        Returns:
            List of entities with type, name, and mention count
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Check if the function exists (created by migration 021)
                func_exists = await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM information_schema.routines
                        WHERE routine_name = 'get_user_memory_entities'
                    )
                    """
                )

                if func_exists:
                    # Use the optimized function
                    # FIX: Column name is 'mention_count' (matches RETURNS TABLE definition)
                    rows = await conn.fetch(
                        "SELECT * FROM get_user_memory_entities($1) LIMIT $2",
                        user_id,
                        limit,
                    )
                    return [
                        {
                            "entity_id": row["entity_id"],  # VARCHAR(64)
                            "type": row["entity_type"],
                            "name": row["entity_name"],
                            "mentions": row["mention_count"],  # FIX: matches SQL column name
                        }
                        for row in rows
                    ]
                else:
                    # Fallback: direct query (entity_id is VARCHAR(64))
                    rows = await conn.fetch(
                        """
                        SELECT DISTINCT
                            ke.id as entity_id,
                            ke.type,
                            ke.name,
                            ke.mention_count
                        FROM kg_entity_mentions km
                        JOIN kg_entities ke ON ke.id = km.entity_id
                        WHERE km.source_type = 'conversation'
                        AND km.source_id LIKE $1
                        ORDER BY ke.mention_count DESC
                        LIMIT $2
                        """,
                        f"%{user_id}%",
                        limit,
                    )
                    return [
                        {
                            "entity_id": row["entity_id"],  # VARCHAR(64)
                            "type": row["type"],
                            "name": row["name"],
                            "mentions": row["mention_count"],
                        }
                        for row in rows
                    ]

        except Exception as e:
            logger.warning(f"Error getting user related entities: {e}")
            return []

    async def get_entity_context_for_query(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Get relevant entities for a query to enrich AI context.

        Args:
            query: User's query text
            limit: Maximum entities to return

        Returns:
            List of relevant entities with descriptions
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Text-based search (can be enhanced with embeddings)
                query_pattern = f"%{query}%"
                rows = await conn.fetch(
                    """
                    SELECT
                        e.id,
                        e.type,
                        e.name,
                        e.canonical_name,
                        e.metadata,
                        e.mention_count,
                        array_agg(DISTINCT r.relationship_type) FILTER (WHERE r.relationship_type IS NOT NULL) as relationship_types
                    FROM kg_entities e
                    LEFT JOIN kg_relationships r ON e.id = r.source_entity_id OR e.id = r.target_entity_id
                    WHERE
                        e.name ILIKE $1
                        OR e.canonical_name ILIKE $1
                    GROUP BY e.id, e.type, e.name, e.canonical_name, e.metadata, e.mention_count
                    ORDER BY e.mention_count DESC
                    LIMIT $2
                    """,
                    query_pattern,
                    limit,
                )

                return [
                    {
                        "entity_id": row["id"],  # VARCHAR(64)
                        "type": row["type"],
                        "name": row["name"],
                        "canonical_name": row["canonical_name"],
                        "metadata": row["metadata"],
                        "mentions": row["mention_count"],
                        "relationships": row["relationship_types"] or [],
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.warning(f"Error getting entity context: {e}")
            return []
