"""
Oracle Analytics Service
Responsibility: Query analytics and tracking
"""

import asyncio
import hashlib
import logging

from services.oracle_database import db_manager

logger = logging.getLogger(__name__)


class OracleAnalyticsService:
    """
    Service for Oracle query analytics.

    Responsibility: Track query analytics and store metrics.
    """

    def generate_query_hash(self, query_text: str) -> str:
        """
        Generate hash for query analytics.

        Args:
            query_text: Query text

        Returns:
            MD5 hash string
        """
        return hashlib.md5(query_text.encode()).hexdigest()

    async def store_query_analytics(self, analytics_data: dict) -> None:
        """
        Store query analytics data asynchronously.

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
            asyncio.create_task(db_manager.store_query_analytics(analytics_data))
        except Exception as e:
            logger.error(f"Error storing analytics: {e}")

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
            },
        }
