"""
Oracle Analytics Service
Responsibility: Query analytics and tracking
"""

import asyncio
import hashlib
import logging

from backend.services.oracle.oracle_database import db_manager

logger = logging.getLogger(__name__)


class OracleAnalyticsService:
    """
    Service for Oracle query analytics.

    Responsibility: Track query analytics and store metrics.
    """

    # Strong refs to in-flight background tasks. Without this set,
    # `asyncio.create_task(...)` returns a coroutine that the event loop
    # only weakly references — CPython can GC the task before it completes.
    # See https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
    _background_tasks: set[asyncio.Task] = set()

    def generate_query_hash(self, query_text: str) -> str:
        """
        Generate hash for query analytics.

        Args:
            query_text: Query text

        Returns:
            MD5 hash string (non-cryptographic — used only as a bucket key)
        """
        # usedforsecurity=False so Bandit/B303 don't flag this; MD5 is fine
        # here because the hash is used only for analytics grouping.
        return hashlib.md5(query_text.encode(), usedforsecurity=False).hexdigest()

    async def store_query_analytics(self, analytics_data: dict) -> None:
        """
        Store query analytics data asynchronously (fire-and-forget).

        The caller is typically on a request hot path, so we don't await
        the DB write. We DO keep a strong reference to the created task
        in a class-level set so it isn't garbage-collected mid-flight,
        and we attach a done callback that logs any exception so failures
        aren't silently swallowed.

        Args:
            analytics_data: Dictionary with analytics data:
                - user_id: User ID
                - query_hash: Query hash
                - query_text: Query text
                - response_text: Response text
                - language_preference: Language code
                - model_used: Model identifier
                - response_time_ms: Response time
                - document_count: Number of documents
                - session_id: Session ID
                - metadata: Additional metadata
        """
        try:
            task = asyncio.create_task(
                db_manager.store_query_analytics(analytics_data),
                name="oracle-analytics-store",
            )
        except RuntimeError as exc:
            # No running event loop (shouldn't happen from async caller, but be safe)
            logger.error("Could not schedule analytics store: %s", exc)
            return

        self._background_tasks.add(task)
        task.add_done_callback(self._on_analytics_done)

    @classmethod
    def _on_analytics_done(cls, task: asyncio.Task) -> None:
        """Remove finished task from the strong-ref set and log exceptions."""
        cls._background_tasks.discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("Oracle analytics task failed: %s", exc, exc_info=exc)

    def build_analytics_data(
        self,
        query: str,
        answer: str,
        user_profile: dict | None,
        model_used: str,
        execution_time_ms: float,
        document_count: int,
        session_id: str | None,
        collection_used: str,
        routing_stats: dict,
        search_time_ms: float,
        reasoning_time_ms: float,
    ) -> dict:
        """
        Build analytics data dictionary.

        Args:
            query: Query text
            answer: Answer text
            user_profile: User profile dict
            model_used: Model identifier
            execution_time_ms: Total execution time
            document_count: Number of documents
            session_id: Session ID
            collection_used: Collection name
            routing_stats: Routing statistics
            search_time_ms: Search time
            reasoning_time_ms: Reasoning time

        Returns:
            Analytics data dictionary
        """
        query_hash = self.generate_query_hash(query)

        return {
            "user_id": user_profile.get("id") if user_profile else None,
            "query_hash": query_hash,
            "query_text": query,
            "response_text": answer,
            "language_preference": None,  # Will be set by caller
            "model_used": model_used,
            "response_time_ms": execution_time_ms,
            "document_count": document_count,
            "session_id": session_id,
            "metadata": {
                "collection_used": collection_used,
                "routing_stats": routing_stats,
                "search_time_ms": search_time_ms,
                "reasoning_time_ms": reasoning_time_ms,
                "evidence_score": routing_stats.get("evidence_score", 0.0)
                if routing_stats
                else 0.0,
                "verification_status": routing_stats.get("verification_status", "unchecked")
                if routing_stats
                else "unchecked",
                "timings": routing_stats,  # Store full timings dict
            },
        }
