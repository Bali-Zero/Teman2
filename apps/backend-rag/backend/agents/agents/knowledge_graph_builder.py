"""
🕸️ KNOWLEDGE GRAPH AUTO-BUILDER
Automatically builds and maintains a knowledge graph from all data sources

Refactored to use modular services:
- KnowledgeGraphSchema: Manage database schema
- EntityExtractor: Extract entities from text using AI
- RelationshipExtractor: Extract relationships between entities using AI
- KnowledgeGraphRepository: Database operations for entities and relationships
"""

import json
import logging
from typing import Any

import asyncpg
from ..services.kg_extractors import EntityExtractor, RelationshipExtractor
from ..services.kg_repository import KnowledgeGraphRepository
from ..services.kg_schema import KnowledgeGraphSchema

try:
    from llm.zantara_ai_client import ZantaraAIClient

    ZANTARA_AVAILABLE = True
except ImportError:
    ZantaraAIClient = None
    ZANTARA_AVAILABLE = False

logger = logging.getLogger(__name__)


class KnowledgeGraphBuilder:
    """
    Autonomous agent that orchestrates knowledge graph building.

    Uses modular services for:
    - Schema management
    - Entity extraction
    - Relationship extraction
    - Database operations
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool | None = None,
        ai_client: ZantaraAIClient | None = None,
    ):
        """
        Initialize KnowledgeGraphBuilder with dependencies.

        Args:
            db_pool: AsyncPG connection pool (if None, will try to get from app.state)
            ai_client: ZantaraAIClient instance (if None, will create new)
        """
        # Get db_pool
        self.db_pool = db_pool
        if not self.db_pool:
            try:
                from app.main_cloud import app

                self.db_pool = getattr(app.state, "db_pool", None)
            except Exception:
                pass

        if not self.db_pool:
            raise RuntimeError(
                "Database pool not available. Provide db_pool in __init__ or ensure app.state.db_pool is set."
            )

        # Initialize services
        self.schema_service = KnowledgeGraphSchema(self.db_pool)
        self.entity_extractor = EntityExtractor(ai_client)
        self.relationship_extractor = RelationshipExtractor(ai_client)
        self.repository = KnowledgeGraphRepository(self.db_pool)

    async def _get_db_pool(self) -> asyncpg.Pool:
        """Get database pool"""
        return self.db_pool

    async def init_graph_schema(self):
        """Create knowledge graph tables"""
        await self.schema_service.init_schema()

    async def extract_entities_from_text(
        self, text: str, timeout: float = 30.0
    ) -> list[dict[str, Any]]:
        """
        Extract entities from text using AI.

        Args:
            text: Text to extract entities from
            timeout: Maximum time to wait for extraction

        Returns:
            List of entity dictionaries
        """
        return await self.entity_extractor.extract_entities(text, timeout)

    async def extract_relationships(
        self, entities: list[dict[str, Any]], text: str, timeout: float = 30.0
    ) -> list[dict[str, Any]]:
        """
        Extract relationships between entities.

        Args:
            entities: List of entity dictionaries
            text: Source text context
            timeout: Maximum time to wait for extraction

        Returns:
            List of relationship dictionaries
        """
        return await self.relationship_extractor.extract_relationships(entities, text, timeout)

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
            entity_type: Type of entity
            name: Entity name as mentioned
            canonical_name: Normalized entity name
            metadata: Additional metadata
            conn: Database connection (must be in transaction)

        Returns:
            Entity ID
        """
        return await self.repository.upsert_entity(
            entity_type, name, canonical_name, metadata, conn
        )

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
            strength: Relationship strength
            evidence: Evidence text
            source_ref: Source reference metadata
            conn: Database connection (must be in transaction)
        """
        await self.repository.upsert_relationship(
            source_id, target_id, rel_type, strength, evidence, source_ref, conn
        )

    async def process_conversation(self, conversation_id: str):
        """Extract entities and relationships from a conversation"""
        if not conversation_id:
            logger.warning("process_conversation called with empty conversation_id")
            return

        try:
            async with self.db_pool.acquire() as conn, conn.transaction():
                # Get conversation
                row = await conn.fetchrow(
                    """
                    SELECT messages, client_id, created_at
                    FROM conversations
                    WHERE conversation_id = $1
                    """,
                    conversation_id,
                )

                if not row:
                    logger.debug(f"Conversation {conversation_id} not found")
                    return

                messages_json = row["messages"]

                # Combine all messages into text
                try:
                    messages = (
                        json.loads(messages_json)
                        if isinstance(messages_json, str)
                        else messages_json
                    )
                    if isinstance(messages, list):
                        full_text = "\n".join(
                            [
                                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                                for msg in messages
                            ]
                        )
                    else:
                        full_text = str(messages_json)
                except (TypeError, ValueError, KeyError) as e:
                    logger.warning(f"Failed to parse messages JSON for {conversation_id}: {e}")
                    full_text = str(messages_json)

                # 1. Extract entities
                entities = await self.extract_entities_from_text(full_text)
                entity_map: dict[str, int] = {}  # canonical_name -> entity_id

                for entity in entities:
                    entity_id = await self.upsert_entity(
                        entity_type=entity["type"],
                        name=entity["name"],
                        canonical_name=entity["canonical_name"],
                        metadata={"context": entity.get("context", "")},
                        conn=conn,
                    )

                    entity_map[entity["canonical_name"]] = entity_id

                    # Add mention
                    await self.repository.add_entity_mention(
                        entity_id=entity_id,
                        source_type="conversation",
                        source_id=conversation_id,
                        context=entity.get("context", "") or "",
                        conn=conn,
                    )

                # 2. Extract relationships
                relationships_count = 0
                if len(entities) >= 2:
                    relationships = await self.extract_relationships(entities, full_text)

                    for rel in relationships:
                        source_canonical = next(
                            (e["canonical_name"] for e in entities if e["name"] == rel["source"]),
                            None,
                        )
                        target_canonical = next(
                            (e["canonical_name"] for e in entities if e["name"] == rel["target"]),
                            None,
                        )

                        if source_canonical and target_canonical:
                            source_id = entity_map.get(source_canonical)
                            target_id = entity_map.get(target_canonical)

                            if source_id and target_id:
                                await self.upsert_relationship(
                                    source_id=source_id,
                                    target_id=target_id,
                                    rel_type=rel["relationship"],
                                    strength=rel.get("strength", 0.7),
                                    evidence=rel.get("evidence", ""),
                                    source_ref={"type": "conversation", "id": conversation_id},
                                    conn=conn,
                                )
                                relationships_count += 1

                logger.info(
                    f"✅ Processed conversation {conversation_id}: {len(entities)} entities, {relationships_count} relationships"
                )

        except asyncpg.PostgresError as e:
            logger.error(
                f"Database error processing conversation {conversation_id}: {e}", exc_info=True
            )
        except Exception as e:
            logger.error(
                f"Unexpected error processing conversation {conversation_id}: {e}", exc_info=True
            )

    async def build_graph_from_all_conversations(self, days_back: int = 30):
        """Process all recent conversations"""
        if days_back < 1 or days_back > 365:
            logger.warning(f"Invalid days_back value: {days_back}, using default 30")
            days_back = 30

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT conversation_id
                    FROM conversations
                    WHERE created_at >= NOW() - INTERVAL $1
                    ORDER BY created_at DESC
                    """,
                    f"{days_back} days",
                )

                conversation_ids = [row["conversation_id"] for row in rows]

            logger.info(f"Processing {len(conversation_ids)} conversations...")

            for conv_id in conversation_ids:
                try:
                    await self.process_conversation(conv_id)
                except Exception as e:
                    logger.error(f"Error processing conversation {conv_id}: {e}", exc_info=True)

            logger.info(f"✅ Knowledge graph built from {len(conversation_ids)} conversations")

        except asyncpg.PostgresError as e:
            logger.error(f"Database error building graph: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error building graph: {e}", exc_info=True)
            raise

    async def get_entity_insights(self, top_n: int = 20) -> dict[str, Any]:
        """
        Get insights from knowledge graph.

        Args:
            top_n: Number of top entities to return

        Returns:
            Dictionary with insights
        """
        return await self.repository.get_entity_insights(top_n)

    async def semantic_search_entities(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """
        Search entities semantically.

        Args:
            query: Search query text
            top_k: Number of results to return

        Returns:
            List of matching entities
        """
        return await self.repository.semantic_search_entities(query, top_k)
