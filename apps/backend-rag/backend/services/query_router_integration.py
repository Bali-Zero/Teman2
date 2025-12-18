"""
Query Router Integration Service
Handles query routing and collection selection logic

Extracted from SearchService to follow Single Responsibility Principle.
"""

import logging
from typing import Any

from services.query_router import QueryRouter

logger = logging.getLogger(__name__)


class QueryRouterIntegration:
    """
    Integrates QueryRouter with SearchService for intelligent collection routing.

    REFACTORED: Extracted from SearchService to reduce complexity.

    Responsibilities:
    - Detect pricing queries
    - Route queries to appropriate collections
    - Handle collection overrides
    - Provide routing metadata

    Does NOT handle:
    - Actual document search (use SearchService)
    - Collection management (use CollectionManager)
    """

    def __init__(self, query_router: QueryRouter | None = None):
        """
        Initialize query router integration.

        Args:
            query_router: Optional QueryRouter instance (creates new if None)
        """
        self.router = query_router or QueryRouter()

        # Pricing query keywords
        self.pricing_keywords = [
            # English
            "price",
            "cost",
            "charge",
            "fee",
            "how much",
            "pricing",
            "rate",
            "expensive",
            "cheap",
            "payment",
            "pay",
            # Indonesian
            "harga",
            "biaya",
            "tarif",
            "berapa",
            # Italian
            "costa",
            "quanto",
            "prezzo",
            "costo",
            "tariffa",
            "pagamento",
        ]

        logger.info("✅ QueryRouterIntegration initialized")

    def is_pricing_query(self, query: str) -> bool:
        """
        Detect if query is about pricing.

        Args:
            query: User query text

        Returns:
            True if query contains pricing keywords
        """
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.pricing_keywords)

    def route_query(
        self,
        query: str,
        collection_override: str | None = None,
        enable_fallbacks: bool = False,
    ) -> dict[str, Any]:
        """
        Route query to appropriate collection(s).

        Args:
            query: User query text
            collection_override: Force specific collection (for testing)
            enable_fallbacks: Whether to return fallback collections

        Returns:
            Dict with:
            - collection_name: Primary collection name
            - collections: List of collections to search (if enable_fallbacks)
            - confidence: Routing confidence (if enable_fallbacks)
            - is_pricing: Whether this is a pricing query
        """
        # Check for override first
        if collection_override:
            logger.info(f"🔧 Using override collection: {collection_override}")
            return {
                "collection_name": collection_override,
                "collections": [collection_override],
                "confidence": 1.0,
                "is_pricing": False,
            }

        # Detect pricing query
        is_pricing = self.is_pricing_query(query)
        if is_pricing:
            collection_name = "bali_zero_pricing"
            logger.info("💰 PRICING QUERY DETECTED → Using bali_zero_pricing collection")
            return {
                "collection_name": collection_name,
                "collections": [collection_name],
                "confidence": 1.0,
                "is_pricing": True,
            }

        # Use QueryRouter for intelligent routing
        if enable_fallbacks:
            primary_collection, confidence, collections = self.router.route_with_confidence(
                query, return_fallbacks=True
            )
            logger.info(
                f"🎯 [Routing] Primary: {primary_collection} "
                f"(confidence={confidence:.2f}), "
                f"Total collections: {len(collections)}"
            )
            return {
                "collection_name": primary_collection,
                "collections": collections,
                "confidence": confidence,
                "is_pricing": False,
            }
        else:
            collection_name = self.router.route(query)
            logger.info(f"🧭 [Routing] Collection: {collection_name}")
            return {
                "collection_name": collection_name,
                "collections": [collection_name],
                "confidence": 1.0,
                "is_pricing": False,
            }










