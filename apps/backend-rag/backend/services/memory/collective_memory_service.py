"""
ZANTARA Collective Memory Service

Manages shared knowledge learned from multiple users.
Facts become "collective" when confirmed by 3+ different users.

Key features:
- Contribution tracking with full user audit trail
- Automatic promotion to collective when threshold reached
- Confidence scoring based on confirmations vs refutations
- Category-based organization (process, location, provider, etc.)
- Query-aware semantic retrieval via Qdrant (v1.5+)
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import asyncpg

if TYPE_CHECKING:
    from core.embeddings import EmbeddingsGenerator
    from core.qdrant_db import QdrantClient

logger = logging.getLogger(__name__)


@dataclass
class CollectiveMemory:
    """A shared fact learned from multiple users"""

    id: int
    content: str
    category: str
    confidence: float
    source_count: int
    is_promoted: bool
    first_learned_at: datetime
    last_confirmed_at: datetime
    metadata: dict

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "confidence": self.confidence,
            "source_count": self.source_count,
            "is_promoted": self.is_promoted,
            "first_learned_at": self.first_learned_at.isoformat()
            if self.first_learned_at
            else None,
            "last_confirmed_at": self.last_confirmed_at.isoformat()
            if self.last_confirmed_at
            else None,
        }


class CollectiveMemoryService:
    """
    Service for managing collective memory - shared knowledge across users.

    Workflow:
    1. User contributes a fact → stored with source tracking
    2. Other users confirm same fact → source_count increases
    3. When source_count >= 3 → fact becomes "promoted" (collective)
    4. Promoted facts are included in AI context for all users
    """

    PROMOTION_THRESHOLD = 3  # Min sources to become collective
    MAX_COLLECTIVE_CONTEXT = 10  # Max facts to include in context
    QDRANT_COLLECTION = "collective_memories"  # Qdrant collection name

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        embedder: "EmbeddingsGenerator | None" = None,
        qdrant_client: "QdrantClient | None" = None,
    ):
        self.pool = pool
        self._embedder = embedder
        self._qdrant = qdrant_client
        self._qdrant_initialized = False
        logger.info("CollectiveMemoryService initialized")

    async def set_pool(self, pool: asyncpg.Pool):
        """Set connection pool (for lazy initialization)"""
        self.pool = pool

    def _get_embedder(self) -> "EmbeddingsGenerator":
        """Get or create embeddings generator (lazy initialization)"""
        if self._embedder is None:
            from core.embeddings import create_embeddings_generator

            self._embedder = create_embeddings_generator()
        return self._embedder

    async def _get_qdrant(self) -> "QdrantClient":
        """Get or create Qdrant client (lazy initialization)"""
        if self._qdrant is None:
            from core.qdrant_db import QdrantClient

            from app.core.config import settings

            self._qdrant = QdrantClient(
                qdrant_url=settings.qdrant_url,
                collection_name=self.QDRANT_COLLECTION,
            )
        # Ensure collection exists on first use
        if not self._qdrant_initialized:
            try:
                await self._qdrant.create_collection(vector_size=1536, distance="Cosine")
                self._qdrant_initialized = True
            except Exception as e:
                # Collection may already exist
                logger.debug(f"Qdrant collection setup: {e}")
                self._qdrant_initialized = True
        return self._qdrant

    @staticmethod
    def _hash_content(content: str) -> str:
        """Generate SHA256 hash for content deduplication"""
        normalized = content.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

    async def add_contribution(
        self,
        user_id: str,
        content: str,
        category: str = "general",
        conversation_id: int | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """
        Add a new contribution or confirm existing fact.

        Args:
            user_id: Email of contributor
            content: The fact content
            category: process, location, provider, regulation, tip, pricing, timeline
            conversation_id: Optional link to conversation
            metadata: Additional metadata

        Returns:
            dict with status and memory_id
        """
        if not self.pool:
            logger.warning("No database pool, skipping collective memory")
            return {"status": "skipped", "reason": "no_database"}

        content_hash = self._hash_content(content)

        async with self.pool.acquire() as conn:
            try:
                # Check if fact already exists
                existing = await conn.fetchrow(
                    "SELECT id, source_count, is_promoted FROM collective_memories WHERE content_hash = $1",
                    content_hash,
                )

                if existing:
                    # Fact exists - try to add user as confirmer
                    memory_id = existing["id"]

                    # Check if user already contributed
                    already_contributed = await conn.fetchval(
                        """
                        SELECT EXISTS(
                            SELECT 1 FROM collective_memory_sources
                            WHERE memory_id = $1 AND user_id = $2 AND action IN ('contribute', 'confirm')
                        )
                        """,
                        memory_id,
                        user_id,
                    )

                    if already_contributed:
                        return {
                            "status": "already_contributed",
                            "memory_id": memory_id,
                            "is_promoted": existing["is_promoted"],
                        }

                    # Add confirmation
                    await conn.execute(
                        """
                        INSERT INTO collective_memory_sources (memory_id, user_id, conversation_id, action)
                        VALUES ($1, $2, $3, 'confirm')
                        """,
                        memory_id,
                        user_id,
                        conversation_id,
                    )

                    # Get updated stats (trigger updates them)
                    updated = await conn.fetchrow(
                        "SELECT source_count, is_promoted, confidence FROM collective_memories WHERE id = $1",
                        memory_id,
                    )

                    logger.info(
                        f"🧠 [Collective] User {user_id} confirmed fact #{memory_id} "
                        f"(sources: {updated['source_count']}, promoted: {updated['is_promoted']})"
                    )

                    return {
                        "status": "confirmed",
                        "memory_id": memory_id,
                        "source_count": updated["source_count"],
                        "is_promoted": updated["is_promoted"],
                        "confidence": updated["confidence"],
                    }

                else:
                    # New fact - create it
                    memory_id = await conn.fetchval(
                        """
                        INSERT INTO collective_memories (content, content_hash, category, metadata)
                        VALUES ($1, $2, $3, $4)
                        RETURNING id
                        """,
                        content,
                        content_hash,
                        category,
                        json.dumps(metadata or {}),
                    )

                    # Add contributor
                    await conn.execute(
                        """
                        INSERT INTO collective_memory_sources (memory_id, user_id, conversation_id, action)
                        VALUES ($1, $2, $3, 'contribute')
                        """,
                        memory_id,
                        user_id,
                        conversation_id,
                    )

                    # Sync to Qdrant for semantic search
                    await self._sync_to_qdrant(memory_id, content, category, metadata)

                    logger.info(
                        f"🧠 [Collective] New fact #{memory_id} from {user_id}: {content[:50]}..."
                    )

                    return {
                        "status": "created",
                        "memory_id": memory_id,
                        "source_count": 1,
                        "is_promoted": False,
                    }

            except Exception as e:
                logger.error(f"Failed to add collective contribution: {e}")
                return {"status": "error", "error": str(e)}

    async def refute_fact(
        self,
        user_id: str,
        memory_id: int,
        reason: str | None = None,
    ) -> dict:
        """
        Refute a collective fact (decreases confidence).

        Args:
            user_id: Email of refuter
            memory_id: ID of the fact to refute
            reason: Optional reason for refutation

        Returns:
            dict with status
        """
        if not self.pool:
            return {"status": "skipped", "reason": "no_database"}

        async with self.pool.acquire() as conn:
            try:
                # Check if fact exists
                exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM collective_memories WHERE id = $1)",
                    memory_id,
                )

                if not exists:
                    return {"status": "not_found"}

                # Add refutation (or update if already refuted)
                await conn.execute(
                    """
                    INSERT INTO collective_memory_sources (memory_id, user_id, action)
                    VALUES ($1, $2, 'refute')
                    ON CONFLICT (memory_id, user_id, action) DO NOTHING
                    """,
                    memory_id,
                    user_id,
                )

                # Get updated confidence
                updated = await conn.fetchrow(
                    "SELECT confidence, is_promoted FROM collective_memories WHERE id = $1",
                    memory_id,
                )

                logger.info(
                    f"⚠️ [Collective] Fact #{memory_id} refuted by {user_id} (conf: {updated['confidence']:.2f})"
                )

                # Auto-remove if confidence too low
                if updated["confidence"] < 0.2:
                    await conn.execute("DELETE FROM collective_memories WHERE id = $1", memory_id)
                    logger.info(f"🗑️ [Collective] Fact #{memory_id} removed due to low confidence")
                    return {"status": "removed", "reason": "low_confidence"}

                return {
                    "status": "refuted",
                    "confidence": updated["confidence"],
                    "is_promoted": updated["is_promoted"],
                }

            except Exception as e:
                logger.error(f"Failed to refute fact: {e}")
                return {"status": "error", "error": str(e)}

    async def get_collective_context(
        self,
        category: str | None = None,
        limit: int | None = None,
    ) -> list[str]:
        """
        Get promoted collective facts for AI context.

        Args:
            category: Optional filter by category
            limit: Max facts to return (default: MAX_COLLECTIVE_CONTEXT)

        Returns:
            List of fact strings for system prompt
        """
        if not self.pool:
            return []

        limit = limit or self.MAX_COLLECTIVE_CONTEXT

        async with self.pool.acquire() as conn:
            try:
                if category:
                    rows = await conn.fetch(
                        """
                        SELECT content, confidence, source_count
                        FROM collective_memories
                        WHERE is_promoted = TRUE AND category = $1
                        ORDER BY confidence DESC, source_count DESC
                        LIMIT $2
                        """,
                        category,
                        limit,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT content, confidence, source_count
                        FROM collective_memories
                        WHERE is_promoted = TRUE
                        ORDER BY confidence DESC, source_count DESC
                        LIMIT $1
                        """,
                        limit,
                    )

                return [row["content"] for row in rows]

            except Exception as e:
                logger.error(f"Failed to get collective context: {e}")
                return []

    async def _sync_to_qdrant(
        self,
        memory_id: int,
        content: str,
        category: str,
        metadata: dict | None = None,
    ) -> bool:
        """
        Sync a memory to Qdrant for semantic search.

        Args:
            memory_id: Database ID of the memory
            content: The fact content
            category: Category of the fact
            metadata: Additional metadata

        Returns:
            True if successful
        """
        try:
            # Generate embedding
            embedder = self._get_embedder()
            embedding = embedder.generate_single_embedding(content)

            # Upsert to Qdrant
            qdrant = await self._get_qdrant()
            result = await qdrant.upsert_documents(
                chunks=[content],
                embeddings=[embedding],
                metadatas=[
                    {
                        "id": memory_id,
                        "category": category,
                        "is_promoted": False,  # New facts start unpromoted
                        "confidence": 0.5,
                        "source_count": 1,
                        **(metadata or {}),
                    }
                ],
                ids=[f"cm_{memory_id}"],
            )

            # Mark as synced in PostgreSQL
            if result.get("success") and self.pool:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE collective_memories SET embedding_synced = TRUE WHERE id = $1",
                        memory_id,
                    )

            logger.debug(f"Synced memory #{memory_id} to Qdrant")
            return result.get("success", False)

        except Exception as e:
            logger.warning(f"Failed to sync memory #{memory_id} to Qdrant: {e}")
            return False

    async def get_relevant_context(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
        min_confidence: float = 0.5,
    ) -> list[str]:
        """
        Get collective facts relevant to the query using semantic search.

        This is the query-aware alternative to get_collective_context().
        Uses Qdrant vector search to find semantically similar facts.

        Args:
            query: User query to find relevant facts for
            category: Optional filter by category
            limit: Max facts to return
            min_confidence: Minimum confidence threshold

        Returns:
            List of fact strings ordered by relevance
        """
        try:
            # Generate query embedding
            embedder = self._get_embedder()
            query_embedding = embedder.generate_query_embedding(query)

            # Build filter
            qdrant_filter = {"is_promoted": True}
            if category:
                qdrant_filter["category"] = category

            # Search Qdrant
            qdrant = await self._get_qdrant()
            results = await qdrant.search(
                query_embedding=query_embedding,
                filter=qdrant_filter,
                limit=limit * 2,  # Get extra for filtering
            )

            # Extract and filter results
            facts = []
            for i, doc in enumerate(results.get("documents", [])):
                if not doc:
                    continue
                # Get metadata
                metadata = (
                    results.get("metadatas", [{}])[i]
                    if i < len(results.get("metadatas", []))
                    else {}
                )
                confidence = metadata.get("confidence", 0.5)

                # Filter by confidence
                if confidence >= min_confidence:
                    facts.append(doc)

                if len(facts) >= limit:
                    break

            logger.debug(f"Found {len(facts)} relevant collective facts for query: {query[:50]}...")
            return facts

        except Exception as e:
            logger.warning(f"Semantic search failed, falling back to confidence-based: {e}")
            # Fallback to confidence-based retrieval
            return await self.get_collective_context(category=category, limit=limit)

    async def get_all_memories(
        self,
        include_unpromoted: bool = False,
        limit: int = 50,
    ) -> list[CollectiveMemory]:
        """
        Get all collective memories (for admin/debugging).

        Args:
            include_unpromoted: Include facts not yet promoted
            limit: Max records to return

        Returns:
            List of CollectiveMemory objects
        """
        if not self.pool:
            return []

        async with self.pool.acquire() as conn:
            try:
                if include_unpromoted:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM collective_memories
                        ORDER BY is_promoted DESC, confidence DESC
                        LIMIT $1
                        """,
                        limit,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM collective_memories
                        WHERE is_promoted = TRUE
                        ORDER BY confidence DESC
                        LIMIT $1
                        """,
                        limit,
                    )

                return [
                    CollectiveMemory(
                        id=row["id"],
                        content=row["content"],
                        category=row["category"],
                        confidence=row["confidence"],
                        source_count=row["source_count"],
                        is_promoted=row["is_promoted"],
                        first_learned_at=row["first_learned_at"],
                        last_confirmed_at=row["last_confirmed_at"],
                        metadata=row["metadata"] or {},
                    )
                    for row in rows
                ]

            except Exception as e:
                logger.error(f"Failed to get all memories: {e}")
                return []

    async def get_memory_sources(self, memory_id: int) -> list[dict]:
        """Get all sources/contributors for a memory (audit trail)"""
        if not self.pool:
            return []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, action, contributed_at
                FROM collective_memory_sources
                WHERE memory_id = $1
                ORDER BY contributed_at
                """,
                memory_id,
            )

            return [dict(row) for row in rows]

    async def search_similar(self, query: str, limit: int = 5) -> list[CollectiveMemory]:
        """
        Search for similar facts (simple text matching).
        For semantic search, would need vector embeddings.
        """
        if not self.pool:
            return []

        async with self.pool.acquire() as conn:
            # Simple ILIKE search for now
            rows = await conn.fetch(
                """
                SELECT * FROM collective_memories
                WHERE content ILIKE $1 AND is_promoted = TRUE
                ORDER BY confidence DESC
                LIMIT $2
                """,
                f"%{query}%",
                limit,
            )

            return [
                CollectiveMemory(
                    id=row["id"],
                    content=row["content"],
                    category=row["category"],
                    confidence=row["confidence"],
                    source_count=row["source_count"],
                    is_promoted=row["is_promoted"],
                    first_learned_at=row["first_learned_at"],
                    last_confirmed_at=row["last_confirmed_at"],
                    metadata=row["metadata"] or {},
                )
                for row in rows
            ]

    async def get_stats(self) -> dict:
        """Get collective memory statistics"""
        if not self.pool:
            return {"status": "no_database"}

        async with self.pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM collective_memories")
            promoted = await conn.fetchval(
                "SELECT COUNT(*) FROM collective_memories WHERE is_promoted = TRUE"
            )
            by_category = await conn.fetch(
                """
                SELECT category, COUNT(*) as count
                FROM collective_memories
                WHERE is_promoted = TRUE
                GROUP BY category
                ORDER BY count DESC
                """
            )

            return {
                "total_facts": total,
                "promoted_facts": promoted,
                "pending_facts": total - promoted,
                "by_category": {row["category"]: row["count"] for row in by_category},
            }
