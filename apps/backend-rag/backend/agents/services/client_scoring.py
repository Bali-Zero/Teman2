"""
Client Scoring Service

Responsibility: Calculate client lifetime value (LTV) scores from database data.
"""

import logging
from datetime import datetime
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class ClientScoringService:
    """Service for calculating client LTV scores"""

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize ClientScoringService.

        Args:
            db_pool: AsyncPG connection pool
        """
        self.db_pool = db_pool

    async def calculate_client_score(self, client_id: str) -> dict[str, Any] | None:
        """
        Calculate comprehensive client value score for a single client.

        Args:
            client_id: Client ID to score

        Returns:
            Dictionary with score data or None if client not found
        """
        if not client_id:
            logger.warning("calculate_client_score called with empty client_id")
            return None

        try:
            async with self.db_pool.acquire() as conn:
                # Get client data with single query
                row = await conn.fetchrow(
                    """
                    SELECT
                        c.name,
                        c.email,
                        c.phone,
                        c.created_at,
                        COUNT(DISTINCT i.id) as interaction_count,
                        AVG(CASE WHEN i.sentiment IS NOT NULL THEN i.sentiment ELSE 0 END) as avg_sentiment,
                        COUNT(DISTINCT CASE WHEN i.created_at >= NOW() - INTERVAL '30 days' THEN i.id END) as recent_interactions,
                        MAX(i.created_at) as last_interaction,
                        COUNT(DISTINCT conv.id) as conversation_count,
                        AVG(conv.rating) as avg_rating,
                        ARRAY_AGG(DISTINCT p.status) as practice_statuses,
                        COUNT(DISTINCT p.id) as practice_count
                    FROM crm_clients c
                    LEFT JOIN crm_interactions i ON c.id = i.client_id
                    LEFT JOIN conversations conv ON c.id::text = conv.client_id
                    LEFT JOIN crm_practices p ON c.id = p.client_id
                    WHERE c.id = $1
                    GROUP BY c.id, c.name, c.email, c.phone, c.created_at
                    """,
                    int(client_id),
                )

                if not row:
                    logger.debug(f"No data found for client_id: {client_id}")
                    return None

                return self._calculate_scores_from_row(row, client_id)

        except asyncpg.PostgresError as e:
            logger.error(
                f"Database error calculating score for client {client_id}: {e}", exc_info=True
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error calculating score for client {client_id}: {e}", exc_info=True
            )
            return None

    async def calculate_scores_batch(self, client_ids: list[str]) -> dict[str, dict[str, Any]]:
        """
        Calculate scores for multiple clients in batch (fixes N+1 query problem).

        Args:
            client_ids: List of client IDs to score

        Returns:
            Dictionary mapping client_id -> score data
        """
        if not client_ids:
            return {}

        try:
            async with self.db_pool.acquire() as conn:
                # Batch query for all clients
                rows = await conn.fetch(
                    """
                    SELECT
                        c.id::text as client_id,
                        c.name,
                        c.email,
                        c.phone,
                        c.created_at,
                        COUNT(DISTINCT i.id) as interaction_count,
                        AVG(CASE WHEN i.sentiment IS NOT NULL THEN i.sentiment ELSE 0 END) as avg_sentiment,
                        COUNT(DISTINCT CASE WHEN i.created_at >= NOW() - INTERVAL '30 days' THEN i.id END) as recent_interactions,
                        MAX(i.created_at) as last_interaction,
                        COUNT(DISTINCT conv.id) as conversation_count,
                        AVG(conv.rating) as avg_rating,
                        ARRAY_AGG(DISTINCT p.status) as practice_statuses,
                        COUNT(DISTINCT p.id) as practice_count
                    FROM crm_clients c
                    LEFT JOIN crm_interactions i ON c.id = i.client_id
                    LEFT JOIN conversations conv ON c.id::text = conv.client_id
                    LEFT JOIN crm_practices p ON c.id = p.client_id
                    WHERE c.id = ANY($1::int[])
                    GROUP BY c.id, c.name, c.email, c.phone, c.created_at
                    """,
                    [int(cid) for cid in client_ids],
                )

                results = {}
                for row in rows:
                    client_id = row["client_id"]
                    results[client_id] = self._calculate_scores_from_row(row, client_id)

                return results

        except asyncpg.PostgresError as e:
            logger.error(f"Database error in batch score calculation: {e}", exc_info=True)
            return {}
        except Exception as e:
            logger.error(f"Unexpected error in batch score calculation: {e}", exc_info=True)
            return {}

    def _calculate_scores_from_row(self, row: asyncpg.Record, client_id: str) -> dict[str, Any]:
        """
        Calculate all scores from a database row.

        Args:
            row: Database row with client data
            client_id: Client ID

        Returns:
            Dictionary with calculated scores
        """
        # Extract values
        interaction_count = row["interaction_count"] or 0
        avg_sentiment = row["avg_sentiment"] or 0.0
        recent_interactions = row["recent_interactions"] or 0
        avg_rating = row["avg_rating"] or 0.0
        practice_count = row["practice_count"] or 0
        last_interaction = row["last_interaction"]

        # Calculate component scores (0-100)
        engagement_score = min(100, interaction_count * 5)
        sentiment_score = (avg_sentiment + 1) * 50  # -1 to 1 -> 0 to 100
        recency_score = min(100, recent_interactions * 10)
        quality_score = avg_rating * 20  # 0-5 -> 0-100
        practice_score = min(100, practice_count * 15)

        # Days since last interaction
        days_since_last = (datetime.now() - last_interaction).days if last_interaction else 999

        # Weighted LTV prediction
        ltv_score = (
            engagement_score * 0.3
            + sentiment_score * 0.2
            + recency_score * 0.2
            + quality_score * 0.2
            + practice_score * 0.1
        )

        return {
            "client_id": client_id,
            "name": row["name"],
            "email": row["email"],
            "phone": row["phone"],
            "ltv_score": round(ltv_score, 2),
            "engagement_score": round(engagement_score, 2),
            "sentiment_score": round(sentiment_score, 2),
            "recency_score": round(recency_score, 2),
            "quality_score": round(quality_score, 2),
            "practice_score": round(practice_score, 2),
            "days_since_last_interaction": days_since_last,
            "total_interactions": interaction_count,
            "total_conversations": row["conversation_count"] or 0,
            "practice_statuses": row["practice_statuses"] or [],
        }










