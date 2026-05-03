"""
Integration module for Cross-Encoder Reranker with SearchService.

This module provides seamless integration between the CrossEncoderReranker
and the existing SearchService, allowing for easy adoption of local
reranking without disrupting existing code.

Usage:
    # Option 1: Direct usage in SearchService
    search_service = SearchServiceWithCrossEncoder()
    results = await search_service.search_with_reranking("What is AI?", user_level=2)

    # Option 2: Add to existing SearchService
    from backend.services.rag.reranker_integration import add_cross_encoder_reranking

    search_service = SearchService()
    add_cross_encoder_reranking(search_service)
    results = await search_service.search_with_cross_encoder_reranking(
        "What is AI?", user_level=2
    )
"""

import logging
import time
from typing import Any

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class CrossEncoderRerankerMixin:
    """
    Mixin to add CrossEncoder reranking capabilities to SearchService.

    This mixin adds a `search_with_cross_encoder_reranking` method to any
    SearchService instance, providing a drop-in replacement for the existing
    `search_with_reranking` method that uses local cross-encoder models
    instead of external API calls.

    The mixin preserves all existing behavior including:
    - Tier-based access control
    - Collection routing
    - Conflict resolution
    - Metrics collection
    - Early exit for high-confidence results

    Example:
        class SearchServiceWithReranking(SearchService, CrossEncoderRerankerMixin):
            pass

        service = SearchServiceWithReranking()
        results = await service.search_with_cross_encoder_reranking("query", user_level=2)
    """

    def _init_cross_encoder_reranker(self) -> Any:
        """Lazy initialization of cross-encoder reranker."""
        if not hasattr(self, "_cross_encoder_reranker"):
            from backend.services.rag.reranker import CrossEncoderReranker

            self._cross_encoder_reranker = CrossEncoderReranker()
            logger.info(
                f"🔧 CrossEncoderReranker integrated: enabled={self._cross_encoder_reranker.enabled}",
            )
        return self._cross_encoder_reranker

    @property
    def cross_encoder_reranker(self) -> Any:
        """Access to CrossEncoderReranker instance."""
        return self._init_cross_encoder_reranker()

    async def search_with_cross_encoder_reranking(
        self,
        query: str,
        user_level: int,
        limit: int = 5,
        tier_filter: list | None = None,
        collection_override: str | None = None,
        use_reranking: bool = True,
        overfetch_factor: int = 4,
    ) -> dict[str, Any]:
        """
        Enhanced search with Cross-Encoder reranking.

        This method performs semantic search and then re-ranks the results
        using a local cross-encoder model for improved relevance.

        The pipeline:
        1. Retrieve overfetch_factor * limit candidates using vector search
        2. Re-rank candidates using cross-encoder model
        3. Return top 'limit' results

        Args:
            query: Search query
            user_level: User access level (0-3)
            limit: Number of final results to return
            tier_filter: Optional tier restriction
            collection_override: Force specific collection
            use_reranking: Whether to apply cross-encoder reranking
            overfetch_factor: How many candidates to retrieve before reranking

        Returns:
            Search results with reranking metadata:
            {
                "query": str,
                "results": list[dict],  # Re-ranked documents
                "user_level": int,
                "collection_used": str,
                "reranked": bool,       # Whether reranking was applied
                "candidates_count": int, # Number of candidates before rerank
                "reranker_enabled": bool,
                "reranker_model": str,
            }

        Example:
            >>> results = await service.search_with_cross_encoder_reranking(
            ...     "What is AI?",
            ...     user_level=2,
            ...     limit=5,
            ... )
            >>> print(f"Found {len(results['results'])} results")
            >>> print(f"Reranked: {results['reranked']}")
        """
        # Import metrics if available
        try:
            from backend.app.metrics import (
                rag_pipeline_duration,
                rag_reranking_duration,
            )

            metrics_available = True
        except ImportError:
            metrics_available = False

        pipeline_start = time.time() if metrics_available else None

        # 1. Retrieve candidates (overfetch for reranking)
        initial_limit = limit * overfetch_factor

        candidates = await self.search(
            query=query,
            user_level=user_level,
            limit=initial_limit,
            tier_filter=tier_filter,
            collection_override=collection_override,
            apply_filters=True,
        )

        results = {
            "query": query,
            "results": candidates["results"][:limit],
            "user_level": user_level,
            "allowed_tiers": candidates.get("allowed_tiers", []),
            "collection_used": candidates.get("collection_used", "unknown"),
            "reranked": False,
            "candidates_count": len(candidates["results"]),
            "reranker_enabled": False,
            "reranker_model": None,
        }

        # 2. Apply reranking if enabled
        if use_reranking and self.cross_encoder_reranker.enabled:
            reranker = self.cross_encoder_reranker

            if len(candidates["results"]) > 0:
                rerank_start = time.time() if metrics_available else None

                try:
                    reranked_docs = await reranker.rerank(
                        query=query,
                        documents=candidates["results"],
                        top_k=limit,
                    )

                    if metrics_available and rerank_start:
                        rag_reranking_duration.observe(time.time() - rerank_start)

                    results["results"] = reranked_docs
                    results["reranked"] = True
                    results["reranker_enabled"] = True
                    results["reranker_model"] = reranker.model_name

                    logger.info(
                        f"✅ Cross-encoder reranking applied: {len(candidates['results'])} candidates "
                        f"→ {len(reranked_docs)} results using {reranker.model_name}",
                    )

                except Exception as e:
                    logger.error(f"❌ Cross-encoder reranking failed: {e}")
                    # Fallback to vector search results (already set)
                    results["rerank_error"] = str(e)
            else:
                logger.debug("No candidates to rerank")
        else:
            if not use_reranking:
                logger.debug("Reranking disabled by parameter")
            elif not self.cross_encoder_reranker.enabled:
                logger.debug("CrossEncoderReranker is disabled")

        # Track total pipeline duration
        if metrics_available and pipeline_start:
            rag_pipeline_duration.observe(time.time() - pipeline_start)

        return results

    async def hybrid_search_with_cross_encoder_reranking(
        self,
        query: str,
        user_level: int,
        limit: int = 5,
        tier_filter: list | None = None,
        collection_override: str | None = None,
        use_reranking: bool = True,
        overfetch_factor: int = 4,
    ) -> dict[str, Any]:
        """
        Full hybrid search pipeline with Cross-Encoder reranking.

        Combines BM25 + Dense + Cross-Encoder reranking for optimal results:
        1. Hybrid search (BM25 + Dense vectors with RRF)
        2. Re-rank with cross-encoder

        This is the most comprehensive search method, providing:
        - Keyword matching via BM25
        - Semantic matching via dense vectors
        - Precise relevance scoring via cross-encoder

        Args:
            query: Search query
            user_level: User access level (0-3)
            limit: Number of final results
            tier_filter: Optional tier restriction
            collection_override: Force specific collection
            use_reranking: Whether to apply reranking
            overfetch_factor: Candidate multiplier before reranking

        Returns:
            Search results with full pipeline metadata
        """
        try:
            from backend.app.metrics import (
                rag_pipeline_duration,
                rag_reranking_duration,
            )

            metrics_available = True
        except ImportError:
            metrics_available = False

        pipeline_start = time.time() if metrics_available else None

        # 1. Hybrid search with overfetch
        initial_limit = limit * overfetch_factor

        try:
            candidates = await self.hybrid_search(
                query=query,
                user_level=user_level,
                limit=initial_limit,
                tier_filter=tier_filter,
                collection_override=collection_override,
                apply_filters=True,
            )
        except Exception as e:
            logger.warning(f"Hybrid search failed, falling back to regular search: {e}")
            candidates = await self.search(
                query=query,
                user_level=user_level,
                limit=initial_limit,
                tier_filter=tier_filter,
                collection_override=collection_override,
                apply_filters=True,
            )
            candidates["search_type"] = "dense_fallback"

        results = {
            "query": query,
            "results": candidates["results"][:limit],
            "user_level": user_level,
            "collection": candidates.get("collection", "unknown"),
            "search_type": candidates.get("search_type", "hybrid"),
            "bm25_enabled": candidates.get("bm25_enabled", False),
            "reranked": False,
            "candidates_count": len(candidates["results"]),
            "reranker_enabled": False,
            "reranker_model": None,
        }

        # 2. Re-rank with cross-encoder
        if use_reranking and self.cross_encoder_reranker.enabled:
            if len(candidates["results"]) > 0:
                rerank_start = time.time() if metrics_available else None

                try:
                    reranked_docs = await self.cross_encoder_reranker.rerank(
                        query=query,
                        documents=candidates["results"],
                        top_k=limit,
                    )

                    if metrics_available and rerank_start:
                        rag_reranking_duration.observe(time.time() - rerank_start)

                    results["results"] = reranked_docs
                    results["reranked"] = True
                    results["reranker_enabled"] = True
                    results["reranker_model"] = self.cross_encoder_reranker.model_name

                    logger.info(
                        f"✅ Hybrid + Cross-encoder pipeline complete: "
                        f"{len(candidates['results'])} candidates → {len(reranked_docs)} results",
                    )

                except Exception as e:
                    logger.error(f"❌ Cross-encoder reranking failed: {e}")
                    results["rerank_error"] = str(e)

        if metrics_available and pipeline_start:
            rag_pipeline_duration.observe(time.time() - pipeline_start)

        return results


def add_cross_encoder_reranking(search_service: Any) -> None:
    """
    Dynamically add cross-encoder reranking methods to a SearchService instance.

    This function monkey-patches the SearchService instance to add cross-encoder
    reranking capabilities without modifying the original class.

    Args:
        search_service: An instance of SearchService to augment

    Example:
        >>> from backend.services.search.search_service import SearchService
        >>> from backend.services.rag.reranker_integration import add_cross_encoder_reranking
        >>>
        >>> service = SearchService()
        >>> add_cross_encoder_reranking(service)
        >>> results = await service.search_with_cross_encoder_reranking("query", user_level=2)
    """
    mixin = CrossEncoderRerankerMixin()

    # Bind mixin methods to the search_service instance
    search_service._cross_encoder_reranker = None
    search_service._init_cross_encoder_reranker = mixin._init_cross_encoder_reranker.__get__(
        search_service, type(search_service),
    )
    search_service.cross_encoder_reranker = property(
        lambda self: self._init_cross_encoder_reranker(),
    )
    search_service.search_with_cross_encoder_reranking = (
        mixin.search_with_cross_encoder_reranking.__get__(search_service, type(search_service))
    )
    search_service.hybrid_search_with_cross_encoder_reranking = (
        mixin.hybrid_search_with_cross_encoder_reranking.__get__(
            search_service, type(search_service),
        )
    )

    logger.info("✅ Cross-encoder reranking added to SearchService instance")


class SearchServiceWithCrossEncoder:
    """
    SearchService with integrated Cross-Encoder reranking.

    This is a convenience class that combines SearchService with
    CrossEncoderRerankerMixin for immediate use.

    Example:
        >>> service = SearchServiceWithCrossEncoder()
        >>> results = await service.search_with_cross_encoder_reranking("What is AI?", user_level=2)
        >>> print(f"Top result: {results['results'][0]['text'][:100]}")
    """

    def __new__(cls, *args, **kwargs):
        """Create a combined SearchService with reranking mixin."""
        from backend.services.search.search_service import SearchService

        # Create a combined class dynamically
        class CombinedService(SearchService, CrossEncoderRerankerMixin):
            pass

        return CombinedService(*args, **kwargs)


# Configuration helpers
def get_reranker_config() -> dict[str, Any]:
    """
    Get current reranker configuration from settings.

    Returns:
        Dictionary with reranker configuration

    Example:
        >>> config = get_reranker_config()
        >>> print(f"Model: {config['model']}, Enabled: {config['enabled']}")
    """
    return {
        "enabled": getattr(settings, "enable_reranker", True),
        "model": getattr(settings, "reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
        "top_k": getattr(settings, "reranker_top_k", 5),
        "overfetch_count": getattr(settings, "reranker_overfetch_count", 20),
        "return_count": getattr(settings, "reranker_return_count", 5),
        "cache_enabled": getattr(settings, "reranker_cache_enabled", True),
        "latency_target_ms": getattr(settings, "reranker_latency_target_ms", 50.0),
    }


def should_use_cross_encoder() -> bool:
    """
    Determine if cross-encoder reranking should be used.

    Checks configuration and environment to decide whether to use
    cross-encoder reranking or fall back to other methods.

    Returns:
        True if cross-encoder should be used, False otherwise
    """
    # Check if explicitly disabled
    if not getattr(settings, "enable_reranker", True):
        return False

    # Check if sentence-transformers is available
    try:
        import importlib.util

        if importlib.util.find_spec("sentence_transformers") is not None:
            return True
        raise ImportError("sentence_transformers not found")
    except ImportError:
        logger.warning(
            "sentence-transformers not installed. Cross-encoder reranking will be disabled.",
        )
        return False
