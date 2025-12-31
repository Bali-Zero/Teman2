"""
Knowledge Graph Repository

Responsibility: Database operations for knowledge graph (entities, relationships, queries).

UPDATED 2025-12-31: Migrated from legacy kg_entities/kg_relationships to kg_nodes/kg_edges schema.
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
    """Service for knowledge graph database operations using kg_nodes/kg_edges schema"""

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize KnowledgeGraphRepository.

        Args:
            db_pool: AsyncPG connection pool
        """
        self.db_pool = db_pool

    def _generate_entity_id(self, entity_type: str, canonical_name: str) -> str:
        """
        Generate a canonical entity_id from type and name.

        Args:
            entity_type: Type of entity (law, topic, company, etc.)
            canonical_name: Normalized entity name

        Returns:
            Canonical entity ID like "law_pp_number_32_2023"
        """
        name_normalized = canonical_name.upper().strip().replace(" ", "_").lower()
        return f"{entity_type.lower()}_{name_normalized}"

    async def upsert_entity(
        self,
        entity_type: str,
        name: str,
        canonical_name: str,
        metadata: dict[str, Any],
        conn: asyncpg.Connection,
        source_chunk_id: str | None = None,
    ) -> str:
        """
        Insert or update entity, return entity_id.

        Args:
            entity_type: Type of entity (law, topic, company, etc.)
            name: Entity name as mentioned
            canonical_name: Normalized entity name
            metadata: Additional metadata
            conn: Database connection (must be in transaction)
            source_chunk_id: Optional source chunk ID for provenance

        Returns:
            Entity ID (TEXT)
        """
        entity_id = self._generate_entity_id(entity_type, canonical_name)
        chunk_ids = [source_chunk_id] if source_chunk_id else []

        await conn.execute(
            """
            INSERT INTO kg_nodes (
                entity_id, entity_type, name, properties,
                confidence, source_chunk_ids, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, 1.0, $5, NOW(), NOW())
            ON CONFLICT (entity_id) DO UPDATE SET
                properties = kg_nodes.properties || $4,
                source_chunk_ids = (
                    SELECT array_agg(DISTINCT elem)
                    FROM unnest(
                        COALESCE(kg_nodes.source_chunk_ids, ARRAY[]::text[]) || $5
                    ) elem
                ),
                updated_at = NOW()
            """,
            entity_id,
            entity_type,
            name,
            json.dumps(metadata),
            chunk_ids,
        )

        return entity_id

    async def upsert_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        strength: float,
        evidence: str,
        source_ref: dict[str, Any],
        conn: asyncpg.Connection,
        source_chunk_id: str | None = None,
    ):
        """
        Insert or update relationship.

        Args:
            source_id: Source entity ID (TEXT)
            target_id: Target entity ID (TEXT)
            rel_type: Relationship type
            strength: Relationship strength (0-1), maps to confidence
            evidence: Evidence text
            source_ref: Source reference metadata
            conn: Database connection (must be in transaction)
            source_chunk_id: Optional source chunk ID for provenance
        """
        relationship_id = f"{source_id}_{rel_type}_{target_id}"
        chunk_ids = [source_chunk_id] if source_chunk_id else []

        properties = {
            "evidence": [evidence] if evidence else [],
            "source_references": [source_ref] if source_ref else [],
        }

        await conn.execute(
            """
            INSERT INTO kg_edges (
                relationship_id, source_entity_id, target_entity_id,
                relationship_type, properties, confidence,
                source_chunk_ids, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT (relationship_id) DO UPDATE SET
                confidence = (kg_edges.confidence + EXCLUDED.confidence) / 2,
                properties = jsonb_set(
                    kg_edges.properties,
                    '{evidence}',
                    COALESCE(kg_edges.properties->'evidence', '[]'::jsonb) ||
                    COALESCE(EXCLUDED.properties->'evidence', '[]'::jsonb)
                ),
                source_chunk_ids = (
                    SELECT array_agg(DISTINCT elem)
                    FROM unnest(
                        COALESCE(kg_edges.source_chunk_ids, ARRAY[]::text[]) || $7
                    ) elem
                )
            """,
            relationship_id,
            source_id,
            target_id,
            rel_type,
            json.dumps(properties),
            strength,
            chunk_ids,
        )

    async def add_entity_mention(
        self,
        entity_id: str,
        source_type: str,
        source_id: str,
        context: str,
        conn: asyncpg.Connection,
    ):
        """
        Add entity mention by updating source_chunk_ids on kg_nodes.

        Note: The legacy kg_entity_mentions table is deprecated.
        Mentions are now tracked via source_chunk_ids array in kg_nodes.

        Args:
            entity_id: Entity ID (TEXT)
            source_type: Type of source (conversation, document, etc.)
            source_id: Source identifier
            context: Context where entity was mentioned (stored in properties)
            conn: Database connection (must be in transaction)
        """
        # Update the entity's source_chunk_ids and add mention context to properties
        mention_ref = f"{source_type}:{source_id}"

        await conn.execute(
            """
            UPDATE kg_nodes
            SET
                source_chunk_ids = (
                    SELECT array_agg(DISTINCT elem)
                    FROM unnest(
                        COALESCE(source_chunk_ids, ARRAY[]::text[]) || ARRAY[$2]
                    ) elem
                ),
                properties = jsonb_set(
                    COALESCE(properties, '{}'::jsonb),
                    '{mentions}',
                    COALESCE(properties->'mentions', '[]'::jsonb) ||
                    jsonb_build_array(jsonb_build_object(
                        'source_type', $3,
                        'source_id', $4,
                        'context', $5
                    ))
                ),
                updated_at = NOW()
            WHERE entity_id = $1
            """,
            entity_id,
            mention_ref,
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
                # Top entities by mention count (approximated by source_chunk_ids length)
                top_entities_rows = await conn.fetch(
                    """
                    SELECT
                        entity_type as type,
                        name,
                        COALESCE(array_length(source_chunk_ids, 1), 0) as mention_count
                    FROM kg_nodes
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
                        n.entity_type as type,
                        n.name,
                        COUNT(DISTINCT e.relationship_id) as connection_count
                    FROM kg_nodes n
                    JOIN kg_edges e ON n.entity_id = e.source_entity_id
                                    OR n.entity_id = e.target_entity_id
                    GROUP BY n.entity_id, n.entity_type, n.name
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
                    FROM kg_edges
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
                # Search kg_nodes by checking source_chunk_ids for user references
                # or by checking properties for user-related mentions
                rows = await conn.fetch(
                    """
                    SELECT
                        n.entity_id,
                        n.entity_type as type,
                        n.name,
                        COALESCE(array_length(n.source_chunk_ids, 1), 0) as mention_count
                    FROM kg_nodes n
                    WHERE EXISTS (
                        SELECT 1 FROM unnest(n.source_chunk_ids) chunk
                        WHERE chunk LIKE $1
                    )
                    OR n.properties::text LIKE $1
                    ORDER BY mention_count DESC
                    LIMIT $2
                    """,
                    f"%{user_id}%",
                    limit,
                )

                return [
                    {
                        "entity_id": row["entity_id"],
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
                # Text-based search
                query_pattern = f"%{query}%"
                rows = await conn.fetch(
                    """
                    SELECT
                        n.entity_id,
                        n.entity_type as type,
                        n.name,
                        n.description,
                        n.properties,
                        COALESCE(array_length(n.source_chunk_ids, 1), 0) as mention_count,
                        array_agg(DISTINCT e.relationship_type)
                            FILTER (WHERE e.relationship_type IS NOT NULL) as relationship_types
                    FROM kg_nodes n
                    LEFT JOIN kg_edges e ON n.entity_id = e.source_entity_id
                                         OR n.entity_id = e.target_entity_id
                    WHERE
                        n.name ILIKE $1
                        OR n.entity_id ILIKE $1
                        OR n.description ILIKE $1
                    GROUP BY n.entity_id, n.entity_type, n.name, n.description,
                             n.properties, n.source_chunk_ids
                    ORDER BY mention_count DESC
                    LIMIT $2
                    """,
                    query_pattern,
                    limit,
                )

                return [
                    {
                        "entity_id": row["entity_id"],
                        "type": row["type"],
                        "name": row["name"],
                        "description": row["description"],
                        "properties": row["properties"],
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
                # Text search (can be enhanced with embeddings in future)
                query_pattern = f"%{query}%"
                rows = await conn.fetch(
                    """
                    SELECT
                        n.entity_id,
                        n.entity_type as type,
                        n.name,
                        COALESCE(array_length(n.source_chunk_ids, 1), 0) as mention_count,
                        n.properties,
                        n.confidence
                    FROM kg_nodes n
                    WHERE
                        n.name ILIKE $1
                        OR n.entity_id ILIKE $2
                        OR n.properties::text ILIKE $3
                        OR n.description ILIKE $4
                    ORDER BY mention_count DESC, confidence DESC
                    LIMIT $5
                    """,
                    query_pattern,
                    query_pattern,
                    query_pattern,
                    query_pattern,
                    top_k,
                )

                return [
                    {
                        "entity_id": row["entity_id"],
                        "type": row["type"],
                        "name": row["name"],
                        "mentions": row["mention_count"],
                        "properties": row["properties"],
                        "confidence": row["confidence"],
                    }
                    for row in rows
                ]

        except asyncpg.PostgresError as e:
            logger.error(f"Database error in semantic search: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error in semantic search: {e}", exc_info=True)
            return []

    async def get_entity_by_id(self, entity_id: str) -> dict[str, Any] | None:
        """
        Get a single entity by its ID.

        Args:
            entity_id: Entity ID (TEXT)

        Returns:
            Entity dict or None if not found
        """
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        entity_id, entity_type, name, description,
                        properties, confidence, source_collection,
                        source_chunk_ids, created_at, updated_at
                    FROM kg_nodes
                    WHERE entity_id = $1
                    """,
                    entity_id,
                )

                if not row:
                    return None

                return {
                    "entity_id": row["entity_id"],
                    "type": row["entity_type"],
                    "name": row["name"],
                    "description": row["description"],
                    "properties": row["properties"],
                    "confidence": row["confidence"],
                    "source_collection": row["source_collection"],
                    "source_chunk_ids": row["source_chunk_ids"] or [],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }

        except Exception as e:
            logger.error(f"Error getting entity by ID: {e}")
            return None

    async def get_entity_relationships(
        self, entity_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """
        Get relationships for an entity.

        Args:
            entity_id: Entity ID (TEXT)
            limit: Maximum relationships to return

        Returns:
            List of relationships with connected entities
        """
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        e.relationship_id,
                        e.relationship_type,
                        e.confidence,
                        e.properties,
                        e.source_chunk_ids,
                        CASE
                            WHEN e.source_entity_id = $1 THEN 'outgoing'
                            ELSE 'incoming'
                        END as direction,
                        CASE
                            WHEN e.source_entity_id = $1 THEN n.entity_id
                            ELSE n2.entity_id
                        END as connected_entity_id,
                        CASE
                            WHEN e.source_entity_id = $1 THEN n.name
                            ELSE n2.name
                        END as connected_entity_name,
                        CASE
                            WHEN e.source_entity_id = $1 THEN n.entity_type
                            ELSE n2.entity_type
                        END as connected_entity_type
                    FROM kg_edges e
                    LEFT JOIN kg_nodes n ON e.target_entity_id = n.entity_id
                    LEFT JOIN kg_nodes n2 ON e.source_entity_id = n2.entity_id
                    WHERE e.source_entity_id = $1 OR e.target_entity_id = $1
                    ORDER BY e.confidence DESC
                    LIMIT $2
                    """,
                    entity_id,
                    limit,
                )

                return [
                    {
                        "relationship_id": row["relationship_id"],
                        "type": row["relationship_type"],
                        "direction": row["direction"],
                        "confidence": row["confidence"],
                        "properties": row["properties"],
                        "connected_entity": {
                            "id": row["connected_entity_id"],
                            "name": row["connected_entity_name"],
                            "type": row["connected_entity_type"],
                        },
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Error getting entity relationships: {e}")
            return []

    async def get_graph_stats(self) -> dict[str, Any]:
        """
        Get overall knowledge graph statistics.

        Returns:
            Dictionary with node and edge counts, type distributions
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Node stats
                node_count = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
                edge_count = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")

                # Type distributions
                node_types = await conn.fetch(
                    """
                    SELECT entity_type, COUNT(*) as count
                    FROM kg_nodes
                    GROUP BY entity_type
                    ORDER BY count DESC
                    """
                )

                edge_types = await conn.fetch(
                    """
                    SELECT relationship_type, COUNT(*) as count
                    FROM kg_edges
                    GROUP BY relationship_type
                    ORDER BY count DESC
                    """
                )

                return {
                    "total_nodes": node_count,
                    "total_edges": edge_count,
                    "node_types": {row["entity_type"]: row["count"] for row in node_types},
                    "edge_types": {row["relationship_type"]: row["count"] for row in edge_types},
                    "generated_at": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"Error getting graph stats: {e}")
            return {
                "total_nodes": 0,
                "total_edges": 0,
                "node_types": {},
                "edge_types": {},
                "generated_at": datetime.now().isoformat(),
            }
