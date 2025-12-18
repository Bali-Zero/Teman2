"""
Memory Orchestrator - Centralized Memory Management for ZANTARA

This is the main entry point for all memory operations. It coordinates:
- MemoryServicePostgres: PostgreSQL persistence for facts and stats
- MemoryFactExtractor: Pattern-based fact extraction from conversations
- (Future) MemoryVectorService: Qdrant semantic search

Usage:
    orchestrator = MemoryOrchestrator(db_pool)
    await orchestrator.initialize()

    # Get user context before generating response
    context = await orchestrator.get_user_context(user_email)

    # Save facts after response is generated
    result = await orchestrator.process_conversation(
        user_email=user_email,
        user_message=query,
        ai_response=response,
    )
"""

import logging
import time
from datetime import datetime
from typing import Any

import asyncpg
from agents.services.kg_repository import KnowledgeGraphRepository

from services.collective_memory_service import CollectiveMemoryService
from services.episodic_memory_service import EpisodicMemoryService
from services.memory.models import (
    FactType,
    MemoryContext,
    MemoryFact,
    MemoryProcessResult,
    MemoryStats,
)
from services.memory_fact_extractor import MemoryFactExtractor
from services.memory_service_postgres import MemoryServicePostgres

logger = logging.getLogger(__name__)


class MemoryOrchestrator:
    """
    Centralized facade for all memory operations.

    This class provides a unified interface for:
    1. Retrieving user context from persistent storage
    2. Extracting and saving facts from conversations
    3. Managing the memory system lifecycle

    Thread-safe and designed for concurrent access.
    """

    def __init__(self, db_pool: asyncpg.Pool | None = None, database_url: str | None = None):
        """
        Initialize MemoryOrchestrator.

        Args:
            db_pool: Optional existing asyncpg connection pool
            database_url: Optional database URL (uses settings if not provided)
        """
        self._db_pool = db_pool
        self._database_url = database_url
        self._memory_service: MemoryServicePostgres | None = None
        self._fact_extractor: MemoryFactExtractor | None = None
        self._collective_memory: CollectiveMemoryService | None = None
        self._episodic_memory: EpisodicMemoryService | None = None
        self._kg_repository: KnowledgeGraphRepository | None = None
        self._is_initialized = False

        logger.info("📝 MemoryOrchestrator created")

    @property
    def is_initialized(self) -> bool:
        """Check if orchestrator is initialized and ready"""
        return self._is_initialized

    @property
    def db_pool(self) -> asyncpg.Pool | None:
        """Get the database connection pool"""
        return self._db_pool

    async def initialize(self) -> None:
        """
        Initialize the memory system.

        Creates connection pool if not provided, and initializes all services.
        Safe to call multiple times (idempotent).
        """
        if self._is_initialized:
            logger.debug("MemoryOrchestrator already initialized")
            return

        try:
            # Create memory service
            self._memory_service = MemoryServicePostgres(database_url=self._database_url)

            # If pool provided, use it directly
            if self._db_pool:
                self._memory_service.pool = self._db_pool
                self._memory_service.use_postgres = True
            else:
                # Connect to create pool
                await self._memory_service.connect()
                self._db_pool = self._memory_service.pool

            # Create fact extractor
            self._fact_extractor = MemoryFactExtractor()

            # Create collective memory service
            self._collective_memory = CollectiveMemoryService(pool=self._db_pool)

            # Create episodic memory service
            self._episodic_memory = EpisodicMemoryService(pool=self._db_pool)

            # Create knowledge graph repository
            self._kg_repository = KnowledgeGraphRepository(db_pool=self._db_pool)

            self._is_initialized = True
            logger.info("✅ MemoryOrchestrator initialized successfully")

        except Exception as e:
            logger.error(f"❌ MemoryOrchestrator initialization failed: {e}")
            # Allow graceful degradation - still mark as initialized
            # but with limited functionality
            self._is_initialized = True
            logger.warning("⚠️ MemoryOrchestrator running in degraded mode")

    async def close(self) -> None:
        """
        Close the memory system and release resources.

        Safe to call multiple times.
        """
        try:
            if self._memory_service:
                await self._memory_service.close()

            if self._db_pool:
                await self._db_pool.close()

            self._is_initialized = False
            logger.info("✅ MemoryOrchestrator closed")

        except Exception as e:
            logger.error(f"❌ Error closing MemoryOrchestrator: {e}")

    def _ensure_initialized(self) -> None:
        """Raise error if not initialized"""
        if not self._is_initialized:
            raise RuntimeError("MemoryOrchestrator not initialized. Call initialize() first.")

    async def get_user_context(self, user_email: str, query: str | None = None) -> MemoryContext:
        """
        Get user context from memory for use in AI responses.

        This method retrieves all stored facts and context for a user,
        formatted for use as system prompt context.

        Args:
            user_email: User identifier (email address)
            query: Optional query for query-aware collective memory retrieval

        Returns:
            MemoryContext with user's profile facts, summary, counters, and collective facts.
            Returns empty context if user not found or on error.
        """
        self._ensure_initialized()

        if not user_email:
            return MemoryContext(user_id="", has_data=False)

        try:
            if not self._memory_service or not self._memory_service.pool:
                logger.warning("Memory service not available, returning empty context")
                return MemoryContext(user_id=user_email, has_data=False)

            # Get memory from PostgreSQL (force refresh for API calls to avoid stale cache)
            memory = await self._memory_service.get_memory(user_email, force_refresh=True)

            # Get collective memory (query-aware if query provided)
            collective_facts: list[str] = []
            if self._collective_memory:
                try:
                    if query:
                        # Query-aware semantic retrieval
                        collective_facts = await self._collective_memory.get_relevant_context(
                            query=query,
                            limit=10,
                        )
                        logger.debug(
                            f"Retrieved {len(collective_facts)} relevant collective facts for query"
                        )
                    else:
                        # Fallback to confidence-based retrieval
                        collective_facts = await self._collective_memory.get_collective_context(
                            limit=10
                        )
                except Exception as e:
                    logger.warning(f"Failed to get collective memory: {e}")

            # Get episodic memory (timeline of events)
            timeline_summary: str = ""
            if self._episodic_memory:
                try:
                    timeline_summary = await self._episodic_memory.get_context_summary(
                        user_id=user_email,
                        limit=5,
                    )
                    if timeline_summary:
                        logger.debug(f"Retrieved timeline summary for {user_email}")
                except Exception as e:
                    logger.warning(f"Failed to get episodic memory: {e}")

            # Get knowledge graph entities for context
            kg_entities: list[dict] = []
            if self._kg_repository and query:
                try:
                    kg_entities = await self._kg_repository.get_entity_context_for_query(
                        query=query,
                        limit=5,
                    )
                    if kg_entities:
                        logger.debug(f"Retrieved {len(kg_entities)} KG entities for query")
                except Exception as e:
                    logger.warning(f"Failed to get KG entities: {e}")

            # Build context
            has_data = (
                bool(memory.profile_facts)
                or bool(memory.summary)
                or any(v > 0 for v in memory.counters.values())
                or bool(collective_facts)
                or bool(timeline_summary)
                or bool(kg_entities)
            )

            context = MemoryContext(
                user_id=user_email,
                profile_facts=memory.profile_facts,
                collective_facts=collective_facts,
                timeline_summary=timeline_summary,
                kg_entities=kg_entities,
                summary=memory.summary,
                counters=memory.counters,
                has_data=has_data,
                last_activity=memory.updated_at
                if isinstance(memory.updated_at, datetime)
                else None,
            )

            if has_data:
                logger.info(
                    f"✅ Retrieved context for {user_email}: "
                    f"{len(context.profile_facts)} personal facts, {len(collective_facts)} collective facts"
                )
            else:
                logger.debug(f"📝 No existing memory for {user_email}")

            return context

        except Exception as e:
            logger.error(f"❌ Error getting context for {user_email}: {e}")
            # Graceful degradation - return empty context
            return MemoryContext(user_id=user_email, has_data=False)

    async def process_conversation(
        self,
        user_email: str,
        user_message: str,
        ai_response: str,
    ) -> MemoryProcessResult:
        """
        Process a conversation turn for fact extraction and storage.

        This method:
        1. Extracts key facts from the user message and AI response
        2. Deduplicates and ranks facts by confidence
        3. Saves facts to PostgreSQL
        4. Updates user counters

        Should be called AFTER generating the AI response.
        Designed to be run in background (asyncio.create_task).

        Args:
            user_email: User identifier (email address)
            user_message: What the user said
            ai_response: What the AI responded

        Returns:
            MemoryProcessResult with extraction and save statistics
        """
        start_time = time.time()

        # Handle empty/invalid inputs gracefully
        if not user_email:
            return MemoryProcessResult(
                facts_extracted=0,
                facts_saved=0,
                processing_time_ms=0,
            )

        self._ensure_initialized()

        try:
            if not self._fact_extractor:
                logger.warning("Fact extractor not available")
                return MemoryProcessResult(
                    facts_extracted=0,
                    facts_saved=0,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

            # Extract facts from conversation
            raw_facts = self._fact_extractor.extract_facts_from_conversation(
                user_message=user_message,
                ai_response=ai_response,
                user_id=user_email,
            )

            if not raw_facts:
                logger.debug(f"No facts extracted for {user_email}")
                return MemoryProcessResult(
                    facts_extracted=0,
                    facts_saved=0,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

            # Convert to MemoryFact objects
            facts = []
            for raw_fact in raw_facts:
                try:
                    fact_type = FactType(raw_fact.get("type", "general"))
                except ValueError:
                    fact_type = FactType.GENERAL

                facts.append(
                    MemoryFact(
                        content=raw_fact["content"],
                        fact_type=fact_type,
                        confidence=raw_fact.get("confidence", 0.8),
                        source=raw_fact.get("source", "user"),
                    )
                )

            facts_extracted = len(facts)

            # Save facts to storage
            facts_saved = 0
            if self._memory_service and self._memory_service.pool:
                for fact in facts:
                    try:
                        success = await self._memory_service.add_fact(
                            user_id=user_email,
                            fact=fact.content,
                            fact_type=fact.fact_type,
                        )
                        if success:
                            facts_saved += 1
                    except Exception as e:
                        logger.warning(f"Failed to save fact: {e}")

                # Update conversation counter
                try:
                    await self._memory_service.increment_counter(
                        user_id=user_email,
                        counter_name="conversations",
                    )
                except Exception as e:
                    logger.warning(f"Failed to increment counter: {e}")

            # Extract and save episodic events (timeline)
            if self._episodic_memory:
                try:
                    event_result = await self._episodic_memory.extract_and_save_event(
                        user_id=user_email,
                        message=user_message,
                        ai_response=ai_response,
                    )
                    if event_result and event_result.get("status") == "created":
                        logger.info(
                            f"📅 Saved episodic event: {event_result.get('title', '')[:50]}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to extract episodic event: {e}")

            processing_time = (time.time() - start_time) * 1000

            if facts_saved > 0:
                logger.info(
                    f"💾 Saved {facts_saved}/{facts_extracted} facts for {user_email} "
                    f"({processing_time:.1f}ms)"
                )

            return MemoryProcessResult(
                facts_extracted=facts_extracted,
                facts_saved=facts_saved,
                facts=facts,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(f"❌ Error processing conversation for {user_email}: {e}")
            return MemoryProcessResult(
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
            )

    async def get_stats(self) -> MemoryStats:
        """
        Get memory system statistics.

        Returns:
            MemoryStats with system metrics
        """
        self._ensure_initialized()

        try:
            if self._memory_service:
                raw_stats = await self._memory_service.get_stats()
                return MemoryStats(
                    cached_users=raw_stats.get("cached_users", 0),
                    postgres_enabled=raw_stats.get("postgres_enabled", False),
                    total_users=raw_stats.get("total_users", 0),
                    total_facts=raw_stats.get("total_facts", 0),
                    total_conversations=raw_stats.get("total_conversations", 0),
                    max_facts=raw_stats.get("max_facts", 10),
                    max_summary_length=raw_stats.get("max_summary_length", 500),
                )
        except Exception as e:
            logger.error(f"Error getting stats: {e}")

        return MemoryStats()

    async def search_facts(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Search across all user memories for specific information.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching facts with user_id, content, confidence
        """
        self._ensure_initialized()

        try:
            if self._memory_service:
                return await self._memory_service.search(query, limit)
        except Exception as e:
            logger.error(f"Error searching facts: {e}")

        return []

    async def get_relevant_facts_for_query(
        self,
        user_email: str,
        query: str,
    ) -> list[str]:
        """
        Get relevant facts for a specific query.

        For now, returns all profile facts.
        Future: Will use semantic search to find relevant facts.

        Args:
            user_email: User identifier
            query: The user's query

        Returns:
            List of relevant fact strings
        """
        self._ensure_initialized()

        try:
            if self._memory_service:
                return await self._memory_service.get_relevant_facts(user_email, query)
        except Exception as e:
            logger.error(f"Error getting relevant facts: {e}")

        return []
