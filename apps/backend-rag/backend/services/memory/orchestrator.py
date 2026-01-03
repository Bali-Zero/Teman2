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

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Any

import asyncpg
from agents.services.kg_repository import KnowledgeGraphRepository

from .collective_memory_service import CollectiveMemoryService
from .episodic_memory_service import EpisodicMemoryService
from .memory_fact_extractor import MemoryFactExtractor
from .memory_service_postgres import MemoryServicePostgres
from .models import (
    FactType,
    MemoryContext,
    MemoryFact,
    MemoryProcessResult,
    MemoryStats,
)

logger = logging.getLogger(__name__)


class MemoryServiceStatus(Enum):
    """Status of memory service."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


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

        # Status tracking for graceful degradation
        self._status = MemoryServiceStatus.UNAVAILABLE
        self._degraded_mode_allowed = False
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5

        # Race condition protection: read-write locks per user
        # Write locks: exclusive access for process_conversation
        # Read semaphores: allow concurrent reads in get_user_context
        self._write_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._read_semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(10)  # Allow 10 concurrent reads per user
        )
        self._lock_timeout = 5.0  # seconds

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
        Initialize the memory system with strict validation.

        Creates connection pool if not provided, and initializes all services.
        Distinguishes between critical and non-critical failures.
        Safe to call multiple times (idempotent).
        """
        if self._is_initialized:
            logger.debug("MemoryOrchestrator already initialized")
            return

        critical_failures = []
        non_critical_failures = []

        try:
            # CRITICAL: Memory service must initialize
            self._memory_service = MemoryServicePostgres(database_url=self._database_url)

            if self._db_pool:
                self._memory_service.pool = self._db_pool
                self._memory_service.use_postgres = True
            else:
                await self._memory_service.connect()
                self._db_pool = self._memory_service.pool

            # Verify connection works
            test_memory = await self._memory_service.get_memory("__test__", force_refresh=False)
            if test_memory is None:
                raise RuntimeError("Memory service connection test failed")

            logger.info("✅ Memory service initialized and verified")

        except Exception as e:
            critical_failures.append(("memory_service", str(e)))
            logger.error(
                f"❌ CRITICAL: Memory service initialization failed: {e}",
                extra={"error_type": type(e).__name__}
            )

        try:
            # NON-CRITICAL: Fact extractor
            self._fact_extractor = MemoryFactExtractor()
        except Exception as e:
            non_critical_failures.append(("fact_extractor", str(e)))
            logger.warning(f"⚠️ Fact extractor initialization failed: {e}")

        try:
            # NON-CRITICAL: Collective memory
            self._collective_memory = CollectiveMemoryService(pool=self._db_pool)
        except Exception as e:
            non_critical_failures.append(("collective_memory", str(e)))
            logger.warning(f"⚠️ Collective memory initialization failed: {e}")

        try:
            # NON-CRITICAL: Episodic memory
            self._episodic_memory = EpisodicMemoryService(pool=self._db_pool)
        except Exception as e:
            non_critical_failures.append(("episodic_memory", str(e)))
            logger.warning(f"⚠️ Episodic memory initialization failed: {e}")

        try:
            # NON-CRITICAL: Knowledge graph repository
            self._kg_repository = KnowledgeGraphRepository(db_pool=self._db_pool)
        except Exception as e:
            non_critical_failures.append(("kg_repository", str(e)))
            logger.warning(f"⚠️ Knowledge graph repository initialization failed: {e}")

        # Determine status
        if critical_failures:
            self._status = MemoryServiceStatus.UNAVAILABLE
            self._is_initialized = False

            # Import metrics
            try:
                from app.metrics import memory_orchestrator_unavailable_total
                memory_orchestrator_unavailable_total.inc()
            except ImportError:
                pass

            # Alert on critical failure
            await self._alert_critical_failure(critical_failures)

            raise RuntimeError(
                f"MemoryOrchestrator initialization failed: {critical_failures}"
            )
        elif non_critical_failures:
            self._status = MemoryServiceStatus.DEGRADED
            self._is_initialized = True
            self._degraded_mode_allowed = True

            logger.warning(
                "⚠️ MemoryOrchestrator running in DEGRADED mode",
                extra={
                    "non_critical_failures": non_critical_failures,
                    "degraded_features": [f[0] for f in non_critical_failures],
                }
            )

            # Import metrics
            try:
                from app.metrics import memory_orchestrator_degraded_total
                memory_orchestrator_degraded_total.inc()
            except ImportError:
                pass

            # Alert on degraded mode
            await self._alert_degraded_mode(non_critical_failures)
        else:
            self._status = MemoryServiceStatus.HEALTHY
            self._is_initialized = True
            logger.info("✅ MemoryOrchestrator initialized successfully (HEALTHY)")

            # Import metrics
            try:
                from app.metrics import memory_orchestrator_healthy_total
                memory_orchestrator_healthy_total.inc()
            except ImportError:
                pass

    async def _alert_critical_failure(self, failures: list[tuple[str, str]]):
        """Alert on critical initialization failure."""
        logger.error(
            "🚨 CRITICAL: MemoryOrchestrator initialization failed completely",
            extra={
                "failures": failures,
                "action": "system_unavailable"
            }
        )
        # TODO: Integrate with alerting system when available

    async def _alert_degraded_mode(self, failures: list[tuple[str, str]]):
        """Alert on degraded mode activation."""
        logger.warning(
            "⚠️ MemoryOrchestrator running in DEGRADED mode",
            extra={
                "failures": failures,
                "degraded_features": [f[0] for f in failures],
                "action": "monitor_degraded_features"
            }
        )
        # TODO: Integrate with alerting system when available

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
        """Raise error if not initialized or unavailable."""
        if not self._is_initialized:
            raise RuntimeError("MemoryOrchestrator not initialized. Call initialize() first.")

        if self._status == MemoryServiceStatus.UNAVAILABLE:
            raise RuntimeError("MemoryOrchestrator is unavailable. Check initialization errors.")

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

        semaphore = self._read_semaphores[user_email]

        if self._status == MemoryServiceStatus.DEGRADED:
            # In degraded mode, return limited context
            logger.debug(f"Returning degraded context for {user_email}")
            try:
                from app.metrics import memory_context_degraded_total
                memory_context_degraded_total.inc()
            except ImportError:
                pass

        try:
            async with semaphore:
                # Read operations can proceed concurrently (up to 10 per user)
                if not self._memory_service or not self._memory_service.pool:
                    logger.warning("Memory service not available, returning empty context")
                    return MemoryContext(user_id=user_email, has_data=False)

                # Get memory from PostgreSQL (force refresh for API calls to avoid stale cache)
                memory = await self._memory_service.get_memory(user_email, force_refresh=True)

                # Get collective memory only if available and not in degraded mode
                collective_facts: list[str] = []
                if self._collective_memory and self._status != MemoryServiceStatus.DEGRADED:
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

        except Exception:
            logger.exception(
                "Failed to get user context",
                extra={"user_email": user_email}
            )
            try:
                from app.metrics import memory_context_failed_total
                memory_context_failed_total.inc()
            except ImportError:
                pass

            # Return empty context instead of raising
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

        RACE CONDITION PROTECTION: Uses write lock to ensure exclusive access
        during fact extraction and saving. Prevents concurrent writes from
        corrupting user memory data.

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

        lock = self._write_locks[user_email]

        try:
            # Acquire write lock with timeout
            await asyncio.wait_for(lock.acquire(), timeout=self._lock_timeout)
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

            finally:
                lock.release()

        except asyncio.TimeoutError:
            logger.warning(f"Write lock timeout for user {user_email}")
            # Return empty result instead of failing
            return MemoryProcessResult(
                facts_extracted=0,
                facts_saved=0,
                processing_time_ms=(time.time() - start_time) * 1000,
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
