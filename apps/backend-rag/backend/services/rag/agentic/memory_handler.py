"""
Memory Handler for Agentic RAG Orchestrator

Manages conversation memory persistence with:
- Race condition protection (per-user locks)
- Async memory saving
- Fact extraction from conversations
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING

import asyncpg

if TYPE_CHECKING:
    from services.memory import MemoryOrchestrator

logger = logging.getLogger(__name__)


class MemoryHandler:
    """
    Handles conversation memory persistence for the RAG orchestrator.

    Features:
    - Lazy initialization of MemoryOrchestrator
    - Per-user locks to prevent race conditions
    - Async background saving to avoid blocking
    - Metrics recording for lock contention
    """

    def __init__(self, db_pool: asyncpg.Pool | None = None, lock_timeout: float = 5.0):
        """
        Initialize the MemoryHandler.

        Args:
            db_pool: PostgreSQL connection pool for database operations
            lock_timeout: Timeout in seconds for acquiring per-user locks
        """
        self.db_pool = db_pool
        self._memory_orchestrator: "MemoryOrchestrator | None" = None
        self._memory_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._lock_timeout = lock_timeout

    async def get_memory_orchestrator(self) -> "MemoryOrchestrator | None":
        """
        Lazy load and initialize memory orchestrator for fact extraction.

        Creates MemoryOrchestrator instance on first use to avoid initialization
        overhead when memory features are not needed.

        Returns:
            MemoryOrchestrator instance or None if initialization fails

        Note:
            - Non-fatal errors: returns None and logs warning
            - Used for extracting and persisting conversation facts
            - Requires database pool to be configured
        """
        if self._memory_orchestrator is None:
            try:
                from services.memory import MemoryOrchestrator

                self._memory_orchestrator = MemoryOrchestrator(db_pool=self.db_pool)
                await self._memory_orchestrator.initialize()
                logger.info("MemoryOrchestrator initialized for AgenticRAG")
            except (asyncpg.PostgresError, asyncpg.InterfaceError, ValueError, RuntimeError) as e:
                logger.warning(f"Failed to initialize MemoryOrchestrator: {e}", exc_info=True)
                return None
        return self._memory_orchestrator

    async def save_conversation_memory(
        self,
        user_id: str,
        query: str,
        answer: str,
        metrics_collector: "MetricsCollector | None" = None,
    ) -> None:
        """
        Save memory facts from conversation for future personalization.

        Extracts facts from user messages and AI responses, then persists them
        to the database for future context enrichment. Called asynchronously
        after response generation to avoid blocking.

        RACE CONDITION PROTECTION: Uses per-user lock to prevent concurrent
        memory saves for the same user from corrupting data.

        Args:
            user_id: User identifier (email or UUID)
            query: User's original query
            answer: AI's generated response
            metrics_collector: Optional metrics collector for recording lock contention

        Note:
            - Skips anonymous users (user_id == "anonymous")
            - Non-blocking: uses asyncio.create_task() in caller
            - Logs success metrics (facts extracted/saved, processing time)
            - Gracefully handles errors without failing the main flow
            - Lock timeout: configurable (default 5 seconds)
        """
        if not user_id or user_id == "anonymous":
            return

        lock = self._memory_locks[user_id]
        lock_start_time = time.time()

        try:
            # Acquire lock with timeout to prevent deadlocks
            await asyncio.wait_for(lock.acquire(), timeout=self._lock_timeout)
            try:
                orchestrator = await self.get_memory_orchestrator()
                if not orchestrator:
                    return

                result = await orchestrator.process_conversation(
                    user_email=user_id,
                    user_message=query,
                    ai_response=answer,
                )

                if result.success and result.facts_saved > 0:
                    logger.info(
                        f"Saved {result.facts_saved}/{result.facts_extracted} "
                        f"facts for {user_id} ({result.processing_time_ms:.1f}ms)"
                    )

                # Record lock contention metric
                lock_wait_time = time.time() - lock_start_time
                if lock_wait_time > 0.01 and metrics_collector:  # Only record if waited > 10ms
                    metrics_collector.record_memory_lock_contention(
                        operation="save_memory", wait_time_seconds=lock_wait_time
                    )

            finally:
                lock.release()

        except asyncio.TimeoutError:
            logger.warning(
                f"Memory save lock timeout for user {user_id} (timeout: {self._lock_timeout}s)"
            )
            if metrics_collector:
                metrics_collector.record_memory_lock_timeout(user_id=user_id)
        except (asyncpg.PostgresError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to save memory: {e}", exc_info=True)

    def create_save_task(
        self,
        user_id: str,
        query: str,
        answer: str,
        metrics_collector: "MetricsCollector | None" = None,
    ) -> asyncio.Task | None:
        """
        Create a background task to save conversation memory.

        This is a convenience method that wraps save_conversation_memory
        in an asyncio.Task with proper error handling.

        Args:
            user_id: User identifier
            query: User's query
            answer: AI's response
            metrics_collector: Optional metrics collector

        Returns:
            The created task, or None if user_id is invalid
        """
        if not user_id or user_id == "anonymous" or not answer:
            return None

        task = asyncio.create_task(
            self.save_conversation_memory(user_id, query, answer, metrics_collector)
        )
        task.add_done_callback(
            lambda t: logger.error(f"Memory save failed: {t.exception()}")
            if t.exception()
            else None
        )
        return task
