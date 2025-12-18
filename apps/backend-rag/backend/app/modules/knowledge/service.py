"""
NUZANTARA PRIME - Knowledge Service
Business logic for RAG, Search, and Vector Database operations

DEPRECATED: This service is deprecated in favor of SearchService (canonical retriever).
It is kept only as a fallback for test/local boot scenarios where SearchService may not be initialized.

Migration path:
- Use SearchService from app.state.search_service (injected in main_cloud.py)
- For /api/search endpoint, use get_search_service(request) helper in router.py
"""

import logging
from typing import Any

from core.cache import cached
from core.qdrant_db import QdrantClient

from app.core.config import settings
from app.models import TierLevel
from services.query_router import QueryRouter

logger = logging.getLogger(__name__)


class KnowledgeService:
    """
    Knowledge Service - RAG search with access control and multi-collection support

    This service encapsulates all RAG/search logic, separated from HTTP interface.
    """

    # Access level to allowed tiers mapping
    LEVEL_TO_TIERS = {
        0: [TierLevel.S],
        1: [TierLevel.S, TierLevel.A],
        2: [TierLevel.S, TierLevel.A, TierLevel.B, TierLevel.C],
        3: [TierLevel.S, TierLevel.A, TierLevel.B, TierLevel.C, TierLevel.D],
    }

    def __init__(self):
        """
        Initialize Knowledge Service with Qdrant and embeddings.

        DEPRECATED: This service creates duplicate Qdrant connections and cache collisions.
        Use SearchService from app.state.search_service instead.
        """
        logger.warning(
            "⚠️ KnowledgeService is deprecated. Use SearchService from app.state.search_service instead."
        )
        logger.info("🔄 KnowledgeService initialization starting...")

        # Initialize embeddings generator using factory function
        logger.info("🔄 Loading EmbeddingsGenerator...")
        from core.embeddings import create_embeddings_generator

        self.embedder = create_embeddings_generator()
        logger.info(
            f"✅ EmbeddingsGenerator ready: {self.embedder.provider} ({self.embedder.dimensions} dims)"
        )

        # Get Qdrant URL from centralized config
        qdrant_url = settings.qdrant_url
        logger.info(f"🔄 Connecting to Qdrant: {qdrant_url}")

        # Initialize collections pointing to Qdrant
        logger.info("🔄 Initializing Qdrant collection clients...")
        self.collections = {
            "bali_zero_pricing": QdrantClient(
                qdrant_url=qdrant_url, collection_name="bali_zero_pricing"
            ),
            "visa_oracle": QdrantClient(qdrant_url=qdrant_url, collection_name="visa_oracle"),
            "kbli_eye": QdrantClient(qdrant_url=qdrant_url, collection_name="kbli_unified"),
            "tax_genius": QdrantClient(qdrant_url=qdrant_url, collection_name="tax_genius"),
            "legal_architect": QdrantClient(qdrant_url=qdrant_url, collection_name="legal_unified"),
            "legal_unified": QdrantClient(qdrant_url=qdrant_url, collection_name="legal_unified"),
            "kb_indonesian": QdrantClient(qdrant_url=qdrant_url, collection_name="knowledge_base"),
            "kbli_comprehensive": QdrantClient(
                qdrant_url=qdrant_url, collection_name="kbli_unified"
            ),
            "kbli_unified": QdrantClient(qdrant_url=qdrant_url, collection_name="kbli_unified"),
            "zantara_books": QdrantClient(qdrant_url=qdrant_url, collection_name="knowledge_base"),
            "cultural_insights": QdrantClient(
                qdrant_url=qdrant_url, collection_name="knowledge_base"
            ),
            "tax_updates": QdrantClient(qdrant_url=qdrant_url, collection_name="tax_genius"),
            "tax_knowledge": QdrantClient(qdrant_url=qdrant_url, collection_name="tax_genius"),
            "property_listings": QdrantClient(
                qdrant_url=qdrant_url, collection_name="property_unified"
            ),
            "property_knowledge": QdrantClient(
                qdrant_url=qdrant_url, collection_name="property_unified"
            ),
            "legal_updates": QdrantClient(qdrant_url=qdrant_url, collection_name="legal_unified"),
            "legal_intelligence": QdrantClient(
                qdrant_url=qdrant_url, collection_name="legal_unified"
            ),
        }
        logger.info("✅ All Qdrant collection clients initialized")

        # Initialize query router
        logger.info("🔄 Initializing QueryRouter...")
        self.router = QueryRouter()
        logger.info("✅ QueryRouter initialized")

        # Pricing query keywords
        self.pricing_keywords = [
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
            "harga",
            "biaya",
            "tarif",
            "berapa",
        ]

        logger.info(f"KnowledgeService initialized with Qdrant URL: {qdrant_url}")

    @cached(ttl=300, prefix="rag_search_deprecated")
    async def search(
        self,
        query: str,
        user_level: int,
        limit: int = 5,
        tier_filter: list[TierLevel] | None = None,
        collection_override: str | None = None,
        **_kwargs,  # Accept additional kwargs for backward compatibility (e.g., apply_filters)
    ) -> dict[str, Any]:
        """
        Semantic search with tier-based access control and intelligent collection routing.

        Args:
            query: Search query
            user_level: User access level (0-3)
            limit: Max results
            tier_filter: Optional specific tier filter
            collection_override: Force specific collection (for testing)

        Returns:
            Search results with metadata
        """
        try:
            # Generate query embedding
            query_embedding = self.embedder.generate_query_embedding(query)

            logger.debug(
                f"Query: '{query[:50]}...', embedding_dim={len(query_embedding)}, provider={self.embedder.provider}"
            )
            logger.debug(
                f"Parameters: collection_override={collection_override}, user_level={user_level}, limit={limit}"
            )

            # Detect if pricing query
            is_pricing_query = any(kw in query.lower() for kw in self.pricing_keywords)

            # Route to appropriate collection
            if collection_override:
                collection_name = collection_override
                logger.debug(f"Using override collection: {collection_name}")
            elif is_pricing_query:
                collection_name = "bali_zero_pricing"
                logger.debug("PRICING QUERY DETECTED → Using bali_zero_pricing collection")
            else:
                collection_name = self.router.route(query)

            # Select the appropriate vector DB client
            vector_db = self.collections.get(collection_name)
            if not vector_db:
                logger.error(f"Unknown collection: {collection_name}, defaulting to visa_oracle")
                vector_db = self.collections["visa_oracle"]
                collection_name = "visa_oracle"

            # Determine allowed tiers (only apply to zantara_books collection)
            allowed_tiers = self.LEVEL_TO_TIERS.get(user_level, [])

            # Apply tier filter if provided
            if tier_filter:
                allowed_tiers = [t for t in allowed_tiers if t in tier_filter]

            # Build filter (only for zantara_books)
            if collection_name == "zantara_books" and allowed_tiers:
                tier_values = [t.value for t in allowed_tiers]
                chroma_filter = {"tier": {"$in": tier_values}}
            else:
                chroma_filter = None
                tier_values = []

            logger.debug(f"Final collection: {collection_name}")

            # Search (async)
            raw_results = await vector_db.search(
                query_embedding=query_embedding, filter=chroma_filter, limit=limit
            )

            # Format results consistently
            formatted_results = []
            for i in range(len(raw_results.get("documents", []))):
                distance = (
                    raw_results["distances"][i]
                    if i < len(raw_results.get("distances", []))
                    else 1.0
                )
                score = 1 / (1 + distance)

                if collection_name == "bali_zero_pricing":
                    score = min(1.0, score + 0.15)  # Bias towards official pricing docs

                metadata = (
                    raw_results["metadatas"][i] if i < len(raw_results.get("metadatas", [])) else {}
                )
                if collection_name == "bali_zero_pricing":
                    metadata = {**metadata, "pricing_priority": "high"}

                formatted_results.append(
                    {
                        "id": (
                            raw_results["ids"][i] if i < len(raw_results.get("ids", [])) else None
                        ),
                        "text": (
                            raw_results["documents"][i]
                            if i < len(raw_results.get("documents", []))
                            else ""
                        ),
                        "metadata": metadata,
                        "score": round(score, 4),
                    }
                )

            return {
                "query": query,
                "results": formatted_results,
                "user_level": user_level,
                "allowed_tiers": tier_values,
                "collection_used": collection_name,
            }

        except Exception as e:
            logger.error(f"Search error: {e}")
            raise

    def _init_reranker(self):
        """Lazy load the re-ranker"""
        if not hasattr(self, "reranker"):
            from core.reranker import ReRanker

            self.reranker = ReRanker()

    async def search_with_reranking(
        self,
        query: str,
        user_level: int,
        limit: int = 5,
        tier_filter: list[TierLevel] | None = None,
        collection_override: str | None = None,
    ) -> dict[str, Any]:
        """
        Enhanced search with Semantic Re-ranking.
        Retrieves 3x candidates and re-ranks them for higher precision.
        """
        # 1. Retrieve more candidates (Wide Funnel)
        initial_limit = limit * 3

        results = await self.search(
            query=query,
            user_level=user_level,
            limit=initial_limit,
            tier_filter=tier_filter,
            collection_override=collection_override,
        )

        # 2. Re-rank
        self._init_reranker()
        if self.reranker.enabled:
            logger.info(f"🔍 Re-ranking {len(results['results'])} candidates for query: '{query}'")
            reranked_docs = await self.reranker.rerank(query, results["results"], top_k=limit)
            results["results"] = reranked_docs
            results["reranked"] = True
        else:
            results["reranked"] = False
            results["results"] = results["results"][:limit]

        return results
