"""
ZANTARA Collective Memory Service

Manages shared knowledge learned from multiple users.
Facts become "collective" when confirmed by 3+ different users.

Key features:
- Contribution tracking with full user audit trail
- Automatic promotion to collective when threshold reached
- Confidence scoring based on confirmations vs refutations
- Category-based organization (process, location, provider, etc.)
- PostgreSQL-based storage and retrieval (Qdrant removed 2026-01-10)
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import asyncpg

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

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
    ):
        self.pool = pool
        logger.info("CollectiveMemoryService initialized (PostgreSQL only)")

    async def set_pool(self, pool: asyncpg.Pool):
        """Set connection pool (for lazy initialization)"""
        self.pool = pool

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
            async with conn.transaction():
                try:
                    # RACE CONDITION PROTECTION: Use SELECT FOR UPDATE to lock row
                    # This prevents concurrent contributions from causing duplicate promotions
                    existing = await conn.fetchrow(
                        """
                        SELECT id, source_count, is_promoted
                        FROM collective_memories
                        WHERE content_hash = $1
                        FOR UPDATE
                        """,
                        content_hash,
                    )

                    if existing:
                        # Fact exists - try to add user as confirmer
                        memory_id = existing["id"]
                        fact_was_promoted = existing["is_promoted"]

                        # Check if user already contributed (within transaction)
                        already_contributed = await conn.fetchrow(
                            """
                            SELECT id FROM collective_memory_sources
                            WHERE memory_id = $1 AND user_id = $2 AND action IN ('contribute', 'confirm')
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

                        # Add confirmation atomically
                        await conn.execute(
                            """
                            INSERT INTO collective_memory_sources (memory_id, user_id, conversation_id, action)
                            VALUES ($1, $2, $3, 'confirm')
                            """,
                            memory_id,
                            user_id,
                            conversation_id,
                        )

                        # Atomic increment with promotion check
                        # The trigger will update source_count, but we need to check promotion atomically
                        updated = await conn.fetchrow(
                            """
                            UPDATE collective_memories
                            SET last_confirmed_at = NOW()
                            WHERE id = $1
                            RETURNING id, source_count, is_promoted, confidence
                            """,
                            memory_id,
                        )

                        # Recalculate source_count manually to ensure accuracy
                        actual_source_count = await conn.fetchval(
                            """
                            SELECT COUNT(DISTINCT user_id)
                            FROM collective_memory_sources
                            WHERE memory_id = $1 AND action IN ('contribute', 'confirm')
                            """,
                            memory_id,
                        )

                        # Check if we just crossed the promotion threshold
                        should_promote = (
                            actual_source_count >= self.PROMOTION_THRESHOLD
                            and not fact_was_promoted
                        )

                        if should_promote:
                            # Atomically promote if threshold crossed
                            await conn.execute(
                                """
                                UPDATE collective_memories
                                SET is_promoted = TRUE,
                                    source_count = $2
                                WHERE id = $1 AND NOT is_promoted
                                """,
                                memory_id,
                                actual_source_count,
                            )
                            # Re-fetch to get updated status
                            updated = await conn.fetchrow(
                                """
                                SELECT id, source_count, is_promoted, confidence
                                FROM collective_memories
                                WHERE id = $1
                                """,
                                memory_id,
                            )
                            logger.info(
                                f"🎉 [Collective] Fact #{memory_id} promoted to collective "
                                f"(sources: {actual_source_count})"
                            )

                        logger.info(
                            f"🧠 [Collective] User {user_id} confirmed fact #{memory_id} "
                            f"(sources: {actual_source_count}, promoted: {updated['is_promoted']})"
                        )

                        return {
                            "status": "confirmed",
                            "memory_id": memory_id,
                            "source_count": actual_source_count,
                            "is_promoted": updated["is_promoted"],
                            "confidence": updated["confidence"],
                        }

                    else:
                        # New fact - create it atomically
                        memory_id = await conn.fetchval(
                            """
                            INSERT INTO collective_memories (content, content_hash, category, metadata, source_count)
                            VALUES ($1, $2, $3, $4, 1)
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

                        # NOTE 2026-01-10: Qdrant sync removed - using PostgreSQL only
                        # Collective memories are stored in PostgreSQL and retrieved via SQL queries
                        # Qdrant collection was empty and not needed for current use case

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
