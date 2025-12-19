"""
ZANTARA RAG - Search Service
Core search functionality with tier-based access control

REFACTORED: Split into focused services following Single Responsibility Principle.
- Collection management → CollectionManager
- Conflict resolution → ConflictResolver
- Cultural insights → CulturalInsightsService
- Query routing → QueryRouterIntegration
- Health monitoring → CollectionHealthService
- Collection warmup → CollectionWarmupService

This service now handles ONLY core search logic with proper delegation.
"""

import asyncio
import logging
import time
from typing import Any

import httpx
from qdrant_client.http import exceptions as qdrant_exceptions

logger = logging.getLogger(__name__)

# Performance metrics (Phase 1 fixes)
try:
    from app.metrics import (
        rag_embedding_duration,
        rag_vector_search_duration,
        rag_reranking_duration,
        rag_pipeline_duration,
        rag_early_exit_total,
        rag_parallel_searches,
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("Performance metrics not available")

from core.cache import cached

from app.core.config import settings
from app.models import TierLevel
from services.collection_manager import CollectionManager
from .collection_warmup_service import CollectionWarmupService
from .conflict_resolver import ConflictResolver
from .cultural_insights_service import CulturalInsightsService
from .result_formatter import format_search_results
from .search_filters import build_search_filter

# from services.query_router_integration import QueryRouterIntegration


class SearchService:
    """
    Core search service for document retrieval.

    REFACTORED: Now handles ONLY core search functionality with proper delegation.
    Uses dependency injection for all other responsibilities.

    Responsibilities:
    - Search documents in collections
    - Apply tier-based access control
    - Format search results
    - Coordinate search operations

    Properly delegates to:
    - CollectionManager: Collection access and management
    - ConflictResolver: Multi-collection conflict detection and resolution
    - CollectionHealthService: Query metrics and health monitoring
    - CulturalInsightsService: Cultural context enrichment
    - QueryRouterIntegration: Collection routing decisions
    - CollectionWarmupService: Collection pre-loading and warmup
    """

    # Access level to allowed tiers mapping
    LEVEL_TO_TIERS = {
        0: [TierLevel.S],
        1: [TierLevel.S, TierLevel.A],
        2: [TierLevel.S, TierLevel.A, TierLevel.B, TierLevel.C],
        3: [TierLevel.S, TierLevel.A, TierLevel.B, TierLevel.C, TierLevel.D],
    }

    def __init__(
        self,
        collection_manager: CollectionManager | None = None,
        conflict_resolver: ConflictResolver | None = None,
        cultural_insights: CulturalInsightsService | None = None,
        query_router: Any | None = None,
    ):
        """Initialize SearchService with dependency injection.

        Sets up the core search service with modular, composable dependencies
        following the Single Responsibility Principle. Each dependency handles
        a specific concern (collection access, conflict resolution, etc.).

        Dependencies (all optional, auto-created if None):
        - CollectionManager: Vector database collection access and lifecycle
        - ConflictResolver: Multi-collection conflict detection and resolution
        - CulturalInsightsService: Cultural context enrichment for responses
        - QueryRouterIntegration: Intelligent collection routing decisions
        - CollectionHealthService: Query metrics and health monitoring
        - CollectionWarmupService: Pre-loading for reduced cold-start latency

        Args:
            collection_manager: Collection access manager (auto-created if None)
            conflict_resolver: Conflict detection/resolution (auto-created if None)
            cultural_insights: Cultural context service (auto-created if None)
            query_router: Collection routing service (auto-created if None)

        Note:
            - Embeddings: Auto-detects provider (Vertex AI, OpenAI, etc.)
            - Qdrant URL: Uses centralized config (settings.qdrant_url)
            - Health monitor: Tracks query metrics for analytics
            - Warmup service: Initializes priority collections on startup
        """
        logger.info("🔄 SearchService initialization starting...")

        # Initialize embeddings generator using factory function
        logger.info("🔄 Loading EmbeddingsGenerator...")
        from core.embeddings import create_embeddings_generator

        self.embedder = create_embeddings_generator()
        logger.info(
            f"✅ EmbeddingsGenerator ready: {self.embedder.provider} ({self.embedder.dimensions} dims)"
        )

        # Initialize BM25 vectorizer for hybrid search
        self._bm25_vectorizer = None
        if settings.enable_bm25:
            try:
                from core.bm25_vectorizer import BM25Vectorizer
                self._bm25_vectorizer = BM25Vectorizer(
                    vocab_size=settings.bm25_vocab_size,
                    k1=settings.bm25_k1,
                    b=settings.bm25_b,
                )
                logger.info("✅ BM25Vectorizer ready for hybrid search")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize BM25Vectorizer: {e}")

        # Get Qdrant URL from centralized config
        qdrant_url = settings.qdrant_url
        logger.info(f"🔄 Connecting to Qdrant: {qdrant_url}")

        # Initialize dependencies (use provided or create new)
        self.collection_manager = collection_manager or CollectionManager(qdrant_url=qdrant_url)
        self.conflict_resolver = conflict_resolver or ConflictResolver()
        if query_router:
            self.query_router = query_router
        else:
            from services.query_router_integration import QueryRouterIntegration

            self.query_router = QueryRouterIntegration()

        # Initialize cultural insights service (requires embedder)
        self._cultural_insights = cultural_insights or CulturalInsightsService(
            collection_manager=self.collection_manager, embedder=self.embedder
        )

        # Initialize collection health monitor
        from services.collection_health_service import CollectionHealthService

        self.health_monitor = CollectionHealthService(search_service=self)

        # Initialize collection warmup service
        self.warmup_service = CollectionWarmupService(
            collection_manager=self.collection_manager, embedder=self.embedder
        )

        # Conflict resolution tracking (delegated to ConflictResolver)
        # Initialize with all fields for backward compatibility with tests
        self.conflict_stats = {
            "total_multi_collection_searches": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "timestamp_resolutions": 0,
        }

        logger.info(f"✅ SearchService initialized with Qdrant URL: {qdrant_url}")
        logger.info("✅ Using dependency injection for modular services")

    @property
    def cultural_insights(self):
        """Access to CulturalInsightsService (public API)."""
        return self._cultural_insights

    def _prepare_search_context(
        self,
        query: str,
        user_level: int,
        tier_filter: list[TierLevel] | None,
        collection_override: str | None,
        apply_filters: bool | None,
    ) -> tuple[list[float], str, Any, dict[str, Any] | None, list[str]]:
        """Prepare common context for search operations (DRY helper).

        Extracts shared logic from search() and search_with_reranking():
        - Generate query embedding
        - Route to collection
        - Get vector DB client
        - Build tier/repealed filters
        - Determine allowed tier values

        Args:
            query: Search query
            user_level: User access level (0-3)
            tier_filter: Optional tier restriction
            collection_override: Force specific collection
            apply_filters: Whether to apply filters (None = default behavior)

        Returns:
            Tuple of (query_embedding, collection_name, vector_db, chroma_filter, tier_values)

        Raises:
            ValueError: If query is empty or user_level is out of range
        """
        # Validate input
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        if user_level < 0 or user_level > 3:
            raise ValueError(f"User level must be between 0 and 3, got {user_level}")

        # Generate query embedding
        query_embedding = self.embedder.generate_query_embedding(query)
        
        # Validate embedding was generated
        if not query_embedding or len(query_embedding) == 0:
            raise ValueError("Failed to generate query embedding")

        # Route to appropriate collection
        routing_info = self.query_router.route_query(
            query=query, collection_override=collection_override, enable_fallbacks=False
        )
        collection_name = routing_info["collection_name"]

        # Get vector DB client
        vector_db = self.collection_manager.get_collection(collection_name)
        if not vector_db:
            logger.error(f"❌ Unknown collection: {collection_name}, defaulting to legal_unified")
            vector_db = self.collection_manager.get_collection("legal_unified")
            collection_name = "legal_unified"
            if not vector_db:
                raise ValueError("Failed to initialize default collection")

        # Determine allowed tiers
        allowed_tiers = self.LEVEL_TO_TIERS.get(user_level, [])
        if tier_filter:
            allowed_tiers = [t for t in allowed_tiers if t in tier_filter]

        # Build filter (only for zantara_books)
        tier_filter_dict = None
        if collection_name == "zantara_books" and allowed_tiers:
            tier_values = [t.value for t in allowed_tiers]
            tier_filter_dict = {"tier": {"$in": tier_values}}
        else:
            tier_values = []

        # Build combined filter
        chroma_filter = build_search_filter(
            tier_filter=tier_filter_dict, exclude_repealed=True
        )

        # Control filter application
        if apply_filters is False:
            chroma_filter = None

        return query_embedding, collection_name, vector_db, chroma_filter, tier_values

    @cached(ttl=300, prefix="rag_search")
    async def search(
        self,
        query: str,
        user_level: int,
        limit: int = 5,
        tier_filter: list[TierLevel] = None,
        collection_override: str | None = None,
        apply_filters: bool | None = None,
    ) -> dict[str, Any]:
        """
        Semantic search with tier-based access control and intelligent collection routing.

        Args:
            query: Search query
            user_level: User access level (0-3)
            limit: Max results
            tier_filter: Optional specific tier filter
            collection_override: Force specific collection (for testing)
            apply_filters: If True, apply tier/exclude_repealed filters. If None, uses default
                          behavior (filters disabled for backward compatibility with chat path).

        Returns:
            Search results with metadata
        """
        try:
            # Prepare search context (DRY: shared logic with search_with_reranking)
            embedding_start = time.time() if METRICS_AVAILABLE else None
            query_embedding, collection_name, vector_db, chroma_filter, tier_values = (
                self._prepare_search_context(
                    query, user_level, tier_filter, collection_override, apply_filters
                )
            )
            if METRICS_AVAILABLE and embedding_start:
                rag_embedding_duration.observe(time.time() - embedding_start)

            # Debug logging (only in debug mode)
            logger.debug(
                f"Query: '{query[:50]}...', embedding_dim={len(query_embedding)}, provider={self.embedder.provider}"
            )
            logger.debug(
                f"Parameters: collection_override={collection_override}, user_level={user_level}, limit={limit}"
            )
            logger.debug(f"Final collection: {collection_name}")
            if chroma_filter:
                logger.debug(f"Filter applied: {chroma_filter}")

            # Search (async)
            raw_results = await vector_db.search(
                query_embedding=query_embedding, filter=chroma_filter, limit=limit
            )

            # Format results using helper method
            formatted_results = format_search_results(
                raw_results, collection_name, primary_collection=None
            )

            # Record query for health monitoring
            avg_score = (
                sum(r["score"] for r in formatted_results) / len(formatted_results)
                if formatted_results
                else 0.0
            )
            self.health_monitor.record_query(
                collection_name=collection_name,
                had_results=len(formatted_results) > 0,
                result_count=len(formatted_results),
                avg_score=avg_score,
            )

            return {
                "query": query,
                "results": formatted_results,
                "user_level": user_level,
                "allowed_tiers": tier_values,
                "collection_used": collection_name,  # NEW: tracking which collection was searched
            }

        except (qdrant_exceptions.UnexpectedResponse, httpx.HTTPError, ValueError, KeyError) as e:
            logger.error(f"Search error: {e}", exc_info=True)
            raise

    def _init_reranker(self):
        """Lazy load the re-ranker"""
        if not hasattr(self, "_reranker"):
            from core.reranker import ReRanker

            self._reranker = ReRanker()
            logger.info(f"🔧 ReRanker initialized: enabled={self._reranker.enabled}, url={self._reranker.api_url}")
        return self._reranker

    async def search_with_reranking(
        self,
        query: str,
        user_level: int,
        limit: int = 5,
        tier_filter: list[TierLevel] = None,
        collection_override: str | None = None,
    ) -> dict[str, Any]:
        """
        Enhanced search with Semantic Re-ranking.
        Retrieves 3x candidates and re-ranks them for higher precision.

        Args:
            query: Search query
            user_level: User access level (0-3)
            limit: Max results (final count after reranking)
            tier_filter: Optional specific tier filter
            collection_override: Force specific collection (for testing)

        Returns:
            Search results with reranking metadata
        """
        pipeline_start_time = time.time() if METRICS_AVAILABLE else None
        
        # 1. Retrieve more candidates (Wide Funnel)
        initial_limit = limit * 3

        results = await self.search(
            query=query,
            user_level=user_level,
            limit=initial_limit,
            tier_filter=tier_filter,
            collection_override=collection_override,
            apply_filters=True,  # Enable filters for reranked search
        )

        # PERFORMANCE FIX: Early exit for high-confidence results (>0.9 score)
        # See: docs/debug/performance/rag_pipeline_report.md
        # Skip reranking if top result already has high confidence
        if results["results"] and results["results"][0].get("score", 0) > 0.9:
            logger.info(
                f"⚡ Early exit: Top result score {results['results'][0]['score']:.3f} > 0.9, "
                f"skipping reranking for query: '{query}'"
            )
            if METRICS_AVAILABLE:
                rag_early_exit_total.inc()
            results["results"] = results["results"][:limit]
            results["reranked"] = False
            results["early_exit"] = True
            return results

        # 2. Re-rank (track duration)
        reranker = self._init_reranker()
        if reranker.enabled:
            logger.info(f"🔍 Re-ranking {len(results['results'])} candidates for query: '{query}'")
            rerank_start = time.time() if METRICS_AVAILABLE else None
            reranked_docs = await reranker.rerank(query, results["results"], top_k=limit)
            if METRICS_AVAILABLE and rerank_start:
                rag_reranking_duration.observe(time.time() - rerank_start)
            results["results"] = reranked_docs
            results["reranked"] = True
            results["early_exit"] = False
        else:
            logger.warning(f"⚠️ ReRanker disabled - skipping rerank for query: '{query[:50]}'")
            results["reranked"] = False
            results["early_exit"] = False
            results["results"] = results["results"][:limit]

        # Track total pipeline duration
        if METRICS_AVAILABLE and pipeline_start_time:
            rag_pipeline_duration.observe(time.time() - pipeline_start_time)

        return results

    async def hybrid_search(
        self,
        query: str,
        user_level: int,
        limit: int = 5,
        tier_filter: list[TierLevel] = None,
        collection_override: str | None = None,
        apply_filters: bool | None = None,
    ) -> dict[str, Any]:
        """
        Hybrid search combining dense vectors and BM25 sparse vectors.

        Uses Reciprocal Rank Fusion (RRF) to combine results from both
        dense semantic search and BM25 keyword search for optimal retrieval.

        Args:
            query: Search query
            user_level: User access level (0-3)
            limit: Max results
            tier_filter: Optional specific tier filter
            collection_override: Force specific collection
            apply_filters: If True, apply tier/exclude_repealed filters

        Returns:
            Search results with hybrid search metadata
        """
        try:
            # Prepare search context (same as regular search)
            embedding_start = time.time() if METRICS_AVAILABLE else None
            query_embedding, collection_name, vector_db, chroma_filter, tier_values = (
                self._prepare_search_context(
                    query, user_level, tier_filter, collection_override, apply_filters
                )
            )
            if METRICS_AVAILABLE and embedding_start:
                rag_embedding_duration.observe(time.time() - embedding_start)

            # Generate BM25 sparse vector
            query_sparse = None
            if self._bm25_vectorizer:
                query_sparse = self._bm25_vectorizer.generate_query_sparse_vector(query)
                logger.debug(
                    f"Generated BM25 sparse vector: {len(query_sparse.get('indices', []))} tokens"
                )

            # Try hybrid search if available
            search_start = time.time() if METRICS_AVAILABLE else None
            if query_sparse and hasattr(vector_db, 'hybrid_search'):
                raw_results = await vector_db.hybrid_search(
                    query_embedding=query_embedding,
                    query_sparse=query_sparse,
                    filter=chroma_filter,
                    limit=limit,
                    prefetch_limit=limit * 3,  # Get more candidates for fusion
                )
                search_type = raw_results.get("search_type", "hybrid_rrf")
            else:
                # Fallback to dense-only search
                raw_results = await vector_db.search(
                    query_embedding=query_embedding, filter=chroma_filter, limit=limit
                )
                search_type = "dense_only"

            if METRICS_AVAILABLE and search_start:
                rag_vector_search_duration.observe(time.time() - search_start)

            # Format results
            formatted_results = format_search_results(
                raw_results, collection_name, primary_collection=None
            )

            # Record query for health monitoring
            avg_score = (
                sum(r["score"] for r in formatted_results) / len(formatted_results)
                if formatted_results
                else 0.0
            )
            self.health_monitor.record_query(
                collection_name=collection_name,
                had_results=len(formatted_results) > 0,
                result_count=len(formatted_results),
                avg_score=avg_score,
            )

            return {
                "query": query,
                "results": formatted_results,
                "collection": collection_name,
                "total_results": len(formatted_results),
                "search_type": search_type,
                "bm25_enabled": query_sparse is not None,
            }

        except Exception as e:
            logger.error(f"Hybrid search error: {e}", exc_info=True)
            # Fallback to regular search on error
            return await self.search(
                query=query,
                user_level=user_level,
                limit=limit,
                tier_filter=tier_filter,
                collection_override=collection_override,
                apply_filters=apply_filters,
            )

    async def hybrid_search_with_reranking(
        self,
        query: str,
        user_level: int,
        limit: int = 5,
        tier_filter: list[TierLevel] = None,
        collection_override: str | None = None,
    ) -> dict[str, Any]:
        """
        Full hybrid search pipeline: BM25 + Dense + RRF + Ze-Rank 2 reranking.

        This is the most comprehensive search method combining:
        1. Dense vector search (semantic)
        2. BM25 sparse vector search (keyword)
        3. Reciprocal Rank Fusion (combining both)
        4. Ze-Rank 2 semantic reranking (final precision)

        Args:
            query: Search query
            user_level: User access level (0-3)
            limit: Max results (final count after all stages)
            tier_filter: Optional specific tier filter
            collection_override: Force specific collection

        Returns:
            Search results with full pipeline metadata
        """
        pipeline_start_time = time.time() if METRICS_AVAILABLE else None

        # 1. Hybrid search with overfetch for reranking
        initial_limit = limit * 3
        results = await self.hybrid_search(
            query=query,
            user_level=user_level,
            limit=initial_limit,
            tier_filter=tier_filter,
            collection_override=collection_override,
            apply_filters=True,
        )

        # 2. Early exit for high-confidence results
        if results["results"] and results["results"][0].get("score", 0) > 0.9:
            logger.info(
                f"⚡ Early exit: Top result score {results['results'][0]['score']:.3f} > 0.9"
            )
            if METRICS_AVAILABLE:
                rag_early_exit_total.inc()
            results["results"] = results["results"][:limit]
            results["reranked"] = False
            results["early_exit"] = True
            return results

        # 3. Re-rank with Ze-Rank 2
        reranker = self._init_reranker()
        if reranker.enabled:
            logger.info(
                f"🔍 Re-ranking {len(results['results'])} hybrid candidates for: '{query[:50]}'"
            )
            rerank_start = time.time() if METRICS_AVAILABLE else None
            reranked_docs = await reranker.rerank(query, results["results"], top_k=limit)
            if METRICS_AVAILABLE and rerank_start:
                rag_reranking_duration.observe(time.time() - rerank_start)
            results["results"] = reranked_docs
            results["reranked"] = True
            results["early_exit"] = False
        else:
            results["results"] = results["results"][:limit]
            results["reranked"] = False
            results["early_exit"] = False

        # Track total pipeline duration
        if METRICS_AVAILABLE and pipeline_start_time:
            rag_pipeline_duration.observe(time.time() - pipeline_start_time)

        results["pipeline"] = "hybrid_bm25_rrf_zerank2"
        return results

    @cached(ttl=300, prefix="rag_multi_search")
    async def search_with_conflict_resolution(
        self,
        query: str,
        user_level: int,
        limit: int = 5,
        tier_filter: list[TierLevel] = None,
        enable_fallbacks: bool = True,
    ) -> dict[str, Any]:
        """Enhanced multi-collection search with conflict detection and resolution.

        Implements the Supreme Knowledge Architecture's conflict resolution pipeline:
        1. Intelligent routing: Classify query and determine primary collection
        2. Fallback chains: Add secondary collections based on confidence
        3. Parallel search: Query all relevant collections concurrently
        4. Conflict detection: Identify contradicting or outdated information
        5. Resolution: Apply timestamp-based and semantic deduplication
        6. Merge & rank: Combine results with score-based ordering

        Conflict Detection Algorithm:
        - Temporal conflicts: Same regulation with different timestamps
        - Semantic conflicts: Contradicting facts on same topic
        - Resolution: Prefer newer timestamps, higher scores, primary collection

        Args:
            query: Natural language search query
            user_level: User access level (0=S-tier only, 3=all tiers)
            limit: Max results PER collection (final may be 2x limit)
            tier_filter: Optional tier restriction (subset of allowed tiers)
            enable_fallbacks: If True, search fallback collections (default: True)

        Returns:
            Dict containing:
                - query (str): Original query
                - results (list[dict]): Merged, deduped results (up to 2x limit)
                - user_level (int): Access level used
                - primary_collection (str): Main collection searched
                - collections_searched (list[str]): All collections queried
                - confidence (float): Router confidence in primary selection
                - conflicts_detected (int): Number of conflicts found
                - conflicts (list[dict]): Detailed conflict reports
                - fallbacks_used (bool): Whether fallback collections were used

        Note:
            - Caching: 5-minute TTL for query deduplication
            - Pricing queries: Single collection (bali_zero_pricing), no fallbacks
            - Health tracking: Records metrics for all collections searched
            - Error handling: Falls back to simple search on failure
            - Performance: ~200-500ms for 3 collections (parallel execution)

        Example:
            >>> results = await search_service.search_with_conflict_resolution(
            ...     query="What is the latest E33G visa requirement?",
            ...     user_level=2,
            ...     limit=5
            ... )
            >>> print(f"Primary: {results['primary_collection']}")
            >>> print(f"Searched: {results['collections_searched']}")
            >>> print(f"Conflicts: {results['conflicts_detected']}")
            >>> for conflict in results['conflicts']:
            ...     print(f"  - {conflict['type']}: {conflict['reason']}")
        """
        try:
            self.conflict_stats["total_multi_collection_searches"] += 1

            # Generate query embedding once (reuse for all collections)
            query_embedding = self.embedder.generate_query_embedding(query)

            # Route query with fallbacks (using QueryRouterIntegration)
            routing_info = self.query_router.route_query(
                query=query, collection_override=None, enable_fallbacks=enable_fallbacks
            )
            primary_collection = routing_info["collection_name"]
            collections_to_search = routing_info["collections"]
            confidence = routing_info["confidence"]

            if routing_info["is_pricing"]:
                logger.info("💰 PRICING QUERY → Single collection: bali_zero_pricing")
            else:
                logger.info(
                    f"🎯 [Conflict Resolution] Primary: {primary_collection} "
                    f"(confidence={confidence:.2f}), "
                    f"Total collections: {len(collections_to_search)}"
                )

            # Search all collections in parallel using asyncio.gather
            async def search_single_collection(collection_name: str) -> tuple[str, list]:
                """
                Search a single collection and format results.

                Applies tier filters, searches collection, and formats results.
                """
                vector_db = self.collection_manager.get_collection(collection_name)
                if not vector_db:
                    logger.warning(f"⚠️ Collection not found: {collection_name}, skipping")
                    return collection_name, []

                # Determine allowed tiers (only for zantara_books)
                allowed_tiers = self.LEVEL_TO_TIERS.get(user_level, [])
                if tier_filter:
                    allowed_tiers = [t for t in allowed_tiers if t in tier_filter]

                # Build filter (only for zantara_books)
                tier_filter_dict = None
                if collection_name == "zantara_books" and allowed_tiers:
                    tier_values = [t.value for t in allowed_tiers]
                    tier_filter_dict = {"tier": {"$in": tier_values}}

                # Build combined filter with default exclusion of repealed laws
                chroma_filter = build_search_filter(
                    tier_filter=tier_filter_dict, exclude_repealed=True
                )

                # Search this collection (async) - track duration
                search_start = time.time() if METRICS_AVAILABLE else None
                raw_results = await vector_db.search(
                    query_embedding=query_embedding, filter=chroma_filter, limit=limit
                )
                if METRICS_AVAILABLE and search_start:
                    rag_vector_search_duration.observe(time.time() - search_start)

                # Format results using helper method
                formatted_results = format_search_results(
                    raw_results, collection_name, primary_collection=primary_collection
                )

                return collection_name, formatted_results

            # Execute all searches in parallel (track parallel execution)
            if METRICS_AVAILABLE:
                rag_parallel_searches.inc(len(collections_to_search))
            search_tasks = [search_single_collection(coll) for coll in collections_to_search]
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

            # Process results and collect health metrics for batch recording
            results_by_collection = {}
            health_metrics = []

            for result in search_results:
                if isinstance(result, Exception):
                    logger.error(f"Search task failed: {result}")
                    continue
                collection_name, formatted_results = result

                if formatted_results:
                    results_by_collection[collection_name] = formatted_results
                    logger.info(
                        f"   ✓ {collection_name}: {len(formatted_results)} results (top score: {formatted_results[0]['score']:.2f})"
                    )

                    # Collect health metrics for batch recording
                    avg_score = sum(r["score"] for r in formatted_results) / len(formatted_results)
                    health_metrics.append(
                        {
                            "collection_name": collection_name,
                            "had_results": True,
                            "result_count": len(formatted_results),
                            "avg_score": avg_score,
                        }
                    )
                else:
                    # Collect zero-result query metrics
                    health_metrics.append(
                        {
                            "collection_name": collection_name,
                            "had_results": False,
                            "result_count": 0,
                            "avg_score": 0.0,
                        }
                    )

            # Batch record health metrics (performance optimization)
            if health_metrics:
                self.health_monitor.record_queries_batch(health_metrics)

            # Detect conflicts (delegate to ConflictResolver)
            conflicts = self.conflict_resolver.detect_conflicts(results_by_collection)

            # Resolve conflicts if any
            conflict_reports = []
            if conflicts:
                resolved_results, conflict_reports = self.conflict_resolver.resolve_conflicts(
                    results_by_collection, conflicts
                )
            else:
                # No conflicts - just merge all results
                resolved_results = []
                for coll_results in results_by_collection.values():
                    resolved_results.extend(coll_results)

            # Sort by score (descending)
            resolved_results.sort(key=lambda x: x["score"], reverse=True)

            # Limit final results
            final_results = resolved_results[: limit * 2]  # Return up to 2x limit to show conflicts

            return {
                "query": query,
                "results": final_results,
                "user_level": user_level,
                "primary_collection": primary_collection,
                "collections_searched": list(results_by_collection.keys()),
                "confidence": confidence,
                "conflicts_detected": len(conflicts),
                "conflicts": conflict_reports,
                "fallbacks_used": len(collections_to_search) > 1,
            }

        except (
            qdrant_exceptions.UnexpectedResponse,
            httpx.HTTPError,
            ValueError,
            KeyError,
            RuntimeError,
        ) as e:
            logger.error(f"Search with conflict resolution error: {e}", exc_info=True)
            # Fallback to simple search
            return await self.search(query, user_level, limit, tier_filter)

    def get_conflict_stats(self) -> dict:
        """Get comprehensive conflict resolution statistics.

        Aggregates metrics from ConflictResolver and SearchService to provide
        insights into multi-collection search behavior and conflict patterns.

        REFACTORED: Delegates to ConflictResolver for core metrics.

        Returns:
            Dict with conflict resolution metrics:
                - total_multi_collection_searches (int): Total multi-collection queries
                - conflicts_detected (int): Number of conflicts found
                - conflicts_resolved (int): Number successfully resolved
                - timestamp_resolutions (int): Conflicts resolved by timestamp
                - conflict_rate (str): Percentage of searches with conflicts
                - resolution_rate (str): Percentage of conflicts successfully resolved

        Note:
            - Includes both detection and resolution metrics
            - Rates calculated as percentages with 1 decimal place
            - Useful for monitoring data quality and consistency

        Example:
            >>> stats = search_service.get_conflict_stats()
            >>> print(f"Conflict rate: {stats['conflict_rate']}")
            >>> print(f"Resolution rate: {stats['resolution_rate']}")
        """
        resolver_stats = self.conflict_resolver.get_stats()
        total_searches = self.conflict_stats["total_multi_collection_searches"]
        conflict_rate = (
            (resolver_stats["conflicts_detected"] / total_searches * 100)
            if total_searches > 0
            else 0.0
        )

        return {
            **self.conflict_stats,
            **resolver_stats,
            "conflict_rate": f"{conflict_rate:.1f}%",
            "resolution_rate": f"{(resolver_stats['conflicts_resolved'] / resolver_stats['conflicts_detected'] * 100) if resolver_stats['conflicts_detected'] > 0 else 0:.1f}%",
        }



    async def search_collection(
        self,
        query: str,
        collection_name: str,
        limit: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Direct search on a specific collection (e.g., for few-shot examples).

        Args:
            query: Search query
            collection_name: Target collection
            limit: Max results
            filter: Optional filter

        Returns:
            Search results
        """
        try:
            # Generate embedding
            query_embedding = self.embedder.generate_query_embedding(query)

            # Get client (lazy loading)
            client = self.collection_manager.get_collection(collection_name)
            if not client:
                # Create ad-hoc client for new collections like conversation_examples
                from core.qdrant_db import QdrantClient

                client = QdrantClient(
                    qdrant_url=settings.qdrant_url, collection_name=collection_name
                )

            # Search (async)
            raw_results = await client.search(
                query_embedding=query_embedding, filter=filter, limit=limit
            )

            # Format results using helper method
            formatted_results = format_search_results(
                raw_results, collection_name, primary_collection=None
            )

            return {"query": query, "results": formatted_results, "collection": collection_name}

        except (qdrant_exceptions.UnexpectedResponse, httpx.HTTPError, ValueError, KeyError) as e:
            logger.error(f"Collection search failed: {e}", exc_info=True)
            return {"results": [], "error": str(e)}

