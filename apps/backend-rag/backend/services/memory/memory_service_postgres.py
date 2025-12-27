"""
ZANTARA Memory Service - PostgreSQL Backend (Fly.io)

Manages user memory (profile facts, conversation summary, counters) with PostgreSQL persistence.
Replaces Firestore with PostgreSQL for Fly.io deployment.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from app.core.constants import MemoryConstants

logger = logging.getLogger(__name__)


@dataclass
class UserMemory:
    """User memory structure"""

    user_id: str
    profile_facts: list[str]  # Max 10 facts
    summary: str  # Max 500 characters
    counters: dict[str, int]  # conversations, searches, tasks
    updated_at: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for database"""
        return {
            "user_id": self.user_id,
            "profile_facts": self.profile_facts,
            "summary": self.summary,
            "counters": self.counters,
            "updated_at": (
                self.updated_at.isoformat()
                if isinstance(self.updated_at, datetime)
                else self.updated_at
            ),
        }


class MemoryServicePostgres:
    """
    Service for managing persistent user memory with PostgreSQL.

    Features:
    - Profile facts (max 10, auto-deduplicated)
    - Conversation summary (max 500 chars)
    - Activity counters
    - PostgreSQL persistence with in-memory fallback
    """

    MAX_FACTS = MemoryConstants.MAX_FACTS
    MAX_SUMMARY_LENGTH = MemoryConstants.MAX_SUMMARY_LENGTH

    def __init__(self, database_url: str | None = None):
        """
        Initialize MemoryService with PostgreSQL.

        Args:
            database_url: PostgreSQL connection string (from Fly.io DATABASE_URL)
        """
        from app.core.config import settings

        self.database_url = database_url or settings.database_url
        self.pool: asyncpg.Pool | None = None
        self.memory_cache: dict[str, UserMemory] = {}  # In-memory fallback
        self.use_postgres = bool(self.database_url)

        logger.info("✅ MemoryServicePostgres initialized")

    async def connect(self):
        """Initialize PostgreSQL connection pool"""
        if not self.use_postgres:
            logger.warning("⚠️ No DATABASE_URL found, using in-memory only")
            return

        try:
            self.pool = await asyncpg.create_pool(
                self.database_url, min_size=5, max_size=50, command_timeout=60
            )
            logger.info("✅ PostgreSQL connection pool created")
        except (asyncpg.PostgresError, asyncpg.InterfaceError, ValueError, OSError) as e:
            logger.error(f"❌ PostgreSQL connection failed: {e}", exc_info=True)
            self.use_postgres = False

    async def close(self):
        """Close PostgreSQL connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")

    async def get_memory(self, user_id: str, force_refresh: bool = False) -> UserMemory:
        """
        Retrieve user memory.

        Lookup order:
        1. Cache (in-memory) - skipped if force_refresh=True
        2. PostgreSQL memory_facts table
        3. Create new empty memory

        Args:
            user_id: User/collaborator ID
            force_refresh: If True, skip cache and query PostgreSQL directly.
                          Use this when you need the latest data (e.g., after adding facts).

        Returns:
            UserMemory with facts, summary, counters
        """
        # 1. Check cache (skip if force_refresh)
        if not force_refresh and user_id in self.memory_cache:
            logger.debug(f"💾 Memory cache hit for {user_id}")
            return self.memory_cache[user_id]

        # 2. Check PostgreSQL
        if self.use_postgres and self.pool:
            try:
                async with self.pool.acquire() as conn:
                    # Get all memory facts for user
                    rows = await conn.fetch(
                        """
                        SELECT content, confidence, source, metadata, created_at
                        FROM memory_facts
                        WHERE user_id = $1
                        ORDER BY created_at DESC
                        LIMIT $2
                        """,
                        user_id,
                        self.MAX_FACTS,
                    )

                    # Get user stats
                    stats_row = await conn.fetchrow(
                        """
                        SELECT conversations_count, searches_count, summary, updated_at
                        FROM user_stats
                        WHERE user_id = $1
                        """,
                        user_id,
                    )

                    # Build UserMemory
                    profile_facts = [row["content"] for row in rows if row["content"]]

                    counters = {
                        "conversations": stats_row["conversations_count"] if stats_row else 0,
                        "searches": stats_row["searches_count"] if stats_row else 0,
                        "tasks": 0,  # Not tracked in user_stats yet
                    }

                    summary = stats_row["summary"] if stats_row else ""
                    updated_at = stats_row["updated_at"] if stats_row else datetime.now()

                    memory = UserMemory(
                        user_id=user_id,
                        profile_facts=profile_facts,
                        summary=summary,
                        counters=counters,
                        updated_at=updated_at,
                    )

                    self.memory_cache[user_id] = memory
                    logger.info(f"✅ Loaded memory from PostgreSQL for {user_id}")
                    return memory

            except (
                asyncpg.PostgresError,
                asyncpg.InterfaceError,
                json.JSONDecodeError,
                KeyError,
            ) as e:
                logger.error(f"❌ PostgreSQL load failed for {user_id}: {e}", exc_info=True)

        # 3. Create new memory
        memory = UserMemory(
            user_id=user_id,
            profile_facts=[],
            summary="",
            counters={"conversations": 0, "searches": 0, "tasks": 0},
            updated_at=datetime.now(),
        )
        self.memory_cache[user_id] = memory
        logger.info(f"📝 Created new memory for {user_id}")
        return memory

    async def save_memory(self, memory: UserMemory) -> bool:
        """
        Save user memory to PostgreSQL and cache.

        Args:
            memory: UserMemory object

        Returns:
            True if saved successfully
        """
        memory.updated_at = datetime.now()

        # Save to cache
        self.memory_cache[memory.user_id] = memory

        # Save to PostgreSQL
        if self.use_postgres and self.pool:
            try:
                async with self.pool.acquire() as conn:
                    # Upsert user_stats
                    await conn.execute(
                        """
                        INSERT INTO user_stats (user_id, conversations_count, searches_count, summary, updated_at, last_activity)
                        VALUES ($1, $2, $3, $4, $5, $5)
                        ON CONFLICT (user_id) DO UPDATE SET
                            conversations_count = EXCLUDED.conversations_count,
                            searches_count = EXCLUDED.searches_count,
                            summary = EXCLUDED.summary,
                            updated_at = EXCLUDED.updated_at,
                            last_activity = EXCLUDED.last_activity
                        """,
                        memory.user_id,
                        memory.counters.get("conversations", 0),
                        memory.counters.get("searches", 0),
                        memory.summary,
                        memory.updated_at,
                    )

                    logger.info(f"✅ Memory saved to PostgreSQL for {memory.user_id}")
                    return True

            except (asyncpg.PostgresError, asyncpg.InterfaceError, ValueError) as e:
                logger.error(f"❌ PostgreSQL save failed for {memory.user_id}: {e}", exc_info=True)
                return False

        logger.debug(f"💾 Memory saved to cache only for {memory.user_id}")
        return True

    async def add_fact(self, user_id: str, fact: str, fact_type: str = "profile_fact") -> bool:
        """
        Add a profile fact (auto-deduplicated, max 10).

        Args:
            user_id: User/collaborator ID
            fact: New fact to add
            fact_type: Type of fact (default: "profile_fact")

        Returns:
            True if added successfully
        """
        memory = await self.get_memory(user_id)

        # Deduplicate (case-insensitive)
        fact = fact.strip()
        if not fact:
            return False

        # Check if already exists
        existing_lower = [f.lower() for f in memory.profile_facts]
        if fact.lower() in existing_lower:
            logger.debug(f"Fact already exists for {user_id}: {fact}")
            return False

        # Save to PostgreSQL memory_facts table
        if self.use_postgres and self.pool:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO memory_facts (user_id, content, fact_type, confidence, source, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        user_id,
                        fact,
                        fact_type,
                        1.0,
                        "system",
                        datetime.now(),
                    )

                    logger.info(f"✅ Added fact to PostgreSQL for {user_id}: {fact}")

            except (asyncpg.PostgresError, asyncpg.InterfaceError, ValueError) as e:
                logger.error(f"❌ Failed to add fact for {user_id}: {e}", exc_info=True)
                return False

        # Add to memory and trim
        memory.profile_facts.append(fact)
        if len(memory.profile_facts) > self.MAX_FACTS:
            memory.profile_facts = memory.profile_facts[-self.MAX_FACTS :]
            logger.info(f"⚠️ Trimmed facts to {self.MAX_FACTS} for {user_id}")

        # Update cache
        self.memory_cache[user_id] = memory

        logger.info(f"✅ Added fact for {user_id}: {fact}")
        return True

    async def update_summary(self, user_id: str, summary: str) -> bool:
        """
        Update conversation summary (max 500 chars).

        Args:
            user_id: User/collaborator ID
            summary: New summary text

        Returns:
            True if updated successfully
        """
        memory = await self.get_memory(user_id)

        # Truncate if needed
        if len(summary) > self.MAX_SUMMARY_LENGTH:
            summary = summary[: self.MAX_SUMMARY_LENGTH - 3] + "..."
            logger.warning(f"⚠️ Summary truncated to {self.MAX_SUMMARY_LENGTH} chars for {user_id}")

        memory.summary = summary

        # Save
        success = await self.save_memory(memory)
        if success:
            logger.info(f"✅ Updated summary for {user_id}")
        return success

    async def increment_counter(self, user_id: str, counter_name: str) -> bool:
        """
        Increment activity counter.

        Args:
            user_id: User/collaborator ID
            counter_name: Counter name (conversations, searches, tasks)

        Returns:
            True if incremented successfully
        """
        memory = await self.get_memory(user_id)

        if counter_name not in memory.counters:
            memory.counters[counter_name] = 0

        memory.counters[counter_name] += 1

        # Save
        success = await self.save_memory(memory)
        if success:
            logger.debug(
                f"✅ Incremented {counter_name} for {user_id}: {memory.counters[counter_name]}"
            )
        return success

    async def save_fact(self, user_id: str, content: str, fact_type: str = "general") -> bool:
        """
        Save a fact to memory_facts table (alias for add_fact).

        Args:
            user_id: User ID
            content: Fact content
            fact_type: Type of fact

        Returns:
            True if saved successfully
        """
        return await self.add_fact(user_id, content, fact_type=fact_type)

    async def retrieve(self, user_id: str, category: str | None = None) -> dict[str, Any]:
        """
        Retrieve user memory in format expected by ZantaraTools.

        This method is called by ZantaraTools when ZANTARA AI uses the
        retrieve_user_memory tool. It provides a structured format
        with all user memory data, optionally filtered by category.

        Args:
            user_id: User ID or email address
            category: Optional category filter (e.g., 'visa_preferences', 'business_setup')
                     Filters facts by keyword matching (case-insensitive)

        Returns:
            Dict containing:
                - user_id: The user identifier
                - profile_facts: List of facts (all or filtered by category)
                - summary: User's conversation summary
                - counters: Activity counters (conversations, searches, tasks)
                - has_data: Boolean indicating if user has any stored data
                - category_filter: The category used for filtering (if any)
                - error: Error message if retrieval failed (optional)
        """
        try:
            # Get user memory using existing method (force refresh for API calls)
            memory = await self.get_memory(user_id, force_refresh=True)

            # Filter facts by category if specified
            facts = memory.profile_facts
            if category and facts:
                # Simple keyword matching (case-insensitive)
                category_lower = category.lower()
                facts = [f for f in facts if category_lower in f.lower()]
                logger.info(
                    f"Filtered {len(memory.profile_facts)} facts to {len(facts)} for category '{category}'"
                )

            # Determine if user has any data
            has_data = (
                bool(facts) or bool(memory.summary) or any(v > 0 for v in memory.counters.values())
            )

            result = {
                "user_id": user_id,
                "profile_facts": facts,
                "summary": memory.summary or "",
                "counters": memory.counters,
                "has_data": has_data,
                "category_filter": category,
            }

            logger.info(
                f"✅ Retrieved memory for {user_id}: {len(facts)} facts, has_data={has_data}"
            )
            return result

        except (
            asyncpg.PostgresError,
            asyncpg.InterfaceError,
            json.JSONDecodeError,
            KeyError,
            ValueError,
        ) as e:
            logger.error(f"❌ Memory retrieve failed for {user_id}: {e}", exc_info=True)
            # Return empty structure on error - graceful degradation
            return {
                "user_id": user_id,
                "profile_facts": [],
                "summary": "",
                "counters": {"conversations": 0, "searches": 0, "tasks": 0},
                "has_data": False,
                "category_filter": category,
                "error": str(e),
            }

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search across all user memories for specific information.

        This method searches through memory facts in PostgreSQL using
        case-insensitive pattern matching. Falls back to in-memory cache
        if PostgreSQL is unavailable.

        Args:
            query: Search query string (will be matched case-insensitively)
            limit: Maximum number of results to return (default: 5)

        Returns:
            List of matching memory entries, each containing:
                - user_id: The user who owns this memory
                - fact: The matching fact content
                - confidence: Confidence score (0.0 to 1.0)
                - created_at: ISO format timestamp when fact was created

            Returns empty list if search fails or no matches found.
        """
        if not query:
            logger.warning("Search called with empty query")
            return []

        # Try PostgreSQL first if available
        if self.use_postgres and self.pool:
            try:
                async with self.pool.acquire(timeout=10) as conn:
                    # Search memory_facts table with ILIKE for case-insensitive matching
                    # Pattern is parameterized ($1), not interpolated - safe from SQL injection
                    pattern = "%" + query + "%"
                    # nosemgrep: asyncpg-sqli
                    rows = await conn.fetch(
                        """
                        SELECT user_id, content, confidence, created_at
                        FROM memory_facts
                        WHERE content ILIKE $1
                        ORDER BY confidence DESC, created_at DESC
                        LIMIT $2
                        """,
                        pattern,
                        limit,
                    )  # nosemgrep

                    results = []
                    for row in rows:
                        results.append(
                            {
                                "user_id": row["user_id"],
                                "fact": row["content"],
                                "confidence": (
                                    float(row["confidence"]) if row["confidence"] else 1.0
                                ),
                                "created_at": (
                                    row["created_at"].isoformat()
                                    if row["created_at"]
                                    else datetime.now().isoformat()
                                ),
                            }
                        )

                    logger.info(f"✅ PostgreSQL search for '{query}' found {len(results)} results")
                    return results

            except asyncpg.exceptions.PostgresConnectionError as e:
                logger.error(f"❌ PostgreSQL connection error during search: {e}", exc_info=True)
            except asyncpg.exceptions.QueryCanceledError as e:
                logger.error(f"❌ PostgreSQL query timeout during search: {e}", exc_info=True)
            except (asyncpg.PostgresError, asyncpg.InterfaceError, ValueError) as e:
                logger.error(f"❌ PostgreSQL search failed: {e}", exc_info=True)

        # Fallback to in-memory cache search
        logger.info(f"Falling back to in-memory cache search for '{query}'")
        results = []
        query_lower = query.lower()

        try:
            for user_id, memory in self.memory_cache.items():
                # Search in profile facts
                for fact in memory.profile_facts:
                    if query_lower in fact.lower():
                        results.append(
                            {
                                "user_id": user_id,
                                "fact": fact,
                                "confidence": 1.0,  # Cache results have default confidence
                                "created_at": (
                                    memory.updated_at.isoformat()
                                    if isinstance(memory.updated_at, datetime)
                                    else memory.updated_at
                                ),
                            }
                        )
                        if len(results) >= limit:
                            break

                # Also search in summary if not enough results
                if (
                    len(results) < limit
                    and memory.summary
                    and query_lower in memory.summary.lower()
                ):
                    results.append(
                        {
                            "user_id": user_id,
                            "fact": f"[Summary] {memory.summary[:100]}...",
                            "confidence": 0.8,  # Lower confidence for summary matches
                            "created_at": (
                                memory.updated_at.isoformat()
                                if isinstance(memory.updated_at, datetime)
                                else memory.updated_at
                            ),
                        }
                    )

                if len(results) >= limit:
                    break

            logger.info(f"✅ Cache search for '{query}' found {len(results)} results")
            return results[:limit]

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"❌ Cache search failed: {e}", exc_info=True)
            return []

    async def get_relevant_facts(self, user_id: str, query: str) -> list[str]:
        """
        Get relevant facts for a user based on query.
        For now, returns all profile facts as the list is short (max 10).
        """
        memory = await self.get_memory(user_id)
        return memory.profile_facts

    async def get_recent_history(self, user_id: str, limit: int = 5) -> list[dict]:
        """
        Get recent conversation history for context.
        """
        if self.use_postgres and self.pool:
            try:
                async with self.pool.acquire() as conn:
                    # Get latest conversation
                    row = await conn.fetchrow(
                        """
                        SELECT messages
                        FROM conversations
                        WHERE user_id = $1
                        ORDER BY created_at DESC
                        LIMIT 1
                    """,
                        user_id,
                    )

                    if row and row["messages"]:
                        # Parse JSONB messages
                        msgs = (
                            row["messages"]
                            if isinstance(row["messages"], list)
                            else json.loads(row["messages"])
                        )
                        return msgs[-limit:]
            except (
                asyncpg.PostgresError,
                asyncpg.InterfaceError,
                json.JSONDecodeError,
                KeyError,
            ) as e:
                logger.error(f"Error fetching history: {e}", exc_info=True)

        return []

    async def get_stats(self) -> dict:
        """Get memory system statistics"""
        postgres_stats = {}

        if self.use_postgres and self.pool:
            try:
                async with self.pool.acquire() as conn:
                    # Count total users, facts, conversations
                    stats = await conn.fetchrow(
                        """
                        SELECT
                            (SELECT COUNT(*) FROM users) as total_users,
                            (SELECT COUNT(*) FROM memory_facts) as total_facts,
                            (SELECT COUNT(*) FROM conversations) as total_conversations,
                            (SELECT SUM(conversations_count) FROM user_stats) as total_conv_count
                        """
                    )

                    postgres_stats = {
                        "total_users": stats["total_users"],
                        "total_facts": stats["total_facts"],
                        "total_conversations": stats["total_conversations"],
                        "total_conv_count": stats["total_conv_count"] or 0,
                    }

            except (asyncpg.PostgresError, asyncpg.InterfaceError, KeyError) as e:
                logger.error(f"Error getting PostgreSQL stats: {e}", exc_info=True)

        return {
            "cached_users": len(self.memory_cache),
            "postgres_enabled": self.use_postgres,
            "max_facts": self.MAX_FACTS,
            "max_summary_length": self.MAX_SUMMARY_LENGTH,
            **postgres_stats,
        }
