"""
NUZANTARA RAG - Hybrid Search Service (BM25 + Vector)

Implements hybrid search combining BM25 keyword search with dense vector similarity
to improve retrieval accuracy by 15-25% over pure vector search.

Uses Qdrant's native sparse vector support and Reciprocal Rank Fusion (RRF) for
combining results from both search methods.

Features:
- BM25 sparse vector computation for keyword matching
- Dense vector search using text-embedding-3-small
- Reciprocal Rank Fusion (RRF) with configurable alpha
- Support for Indonesian and English queries
- Graceful degradation when BM25 is unavailable
"""

import logging
import time
from typing import Any

from backend.app.core.config import settings
from backend.core.bm25_vectorizer import BM25Vectorizer, get_bm25_vectorizer
from backend.core.cache import cached
from backend.core.qdrant_db import QdrantClient
from backend.services.ingestion.collection_manager import CollectionManager

logger = logging.getLogger(__name__)

# RRF constant (typical value is 60)
RRF_K = 60


class HybridSearchService:
    """
    Hybrid Search Service combining BM25 and dense vector search.

    This service provides advanced hybrid search capabilities that combine:
    1. BM25 sparse vector search for keyword matching
    2. Dense vector search for semantic similarity
    3. Reciprocal Rank Fusion (RRF) for optimal result combination

    The hybrid approach improves retrieval accuracy by 15-25% compared to
    pure vector search, especially for keyword-heavy queries.

    Attributes:
        bm25_vectorizer: BM25Vectorizer instance for sparse vector generation
        collection_manager: CollectionManager for accessing Qdrant collections
        _bm25_enabled: Whether BM25 is available and initialized

    Example:
        >>> service = HybridSearchService()
        >>> results = await service.search_hybrid(
        ...     query="visa requirements for KITAS",
        ...     collection="legal_unified_hybrid",
        ...     limit=10,
        ...     alpha=0.5
        ... )
    """

    def __init__(
        self,
        collection_manager: CollectionManager | None = None,
        bm25_vectorizer: BM25Vectorizer | None = None,
        embedder: Any | None = None,
    ) -> None:
        """
        Initialize HybridSearchService.

        Args:
            collection_manager: CollectionManager instance (auto-created if None)
            bm25_vectorizer: BM25Vectorizer instance (auto-created if None)
            embedder: EmbeddingsGenerator instance (auto-created if None).
                      Reused across searches to avoid creating new HTTP clients per request.
        """
        logger.info("Initializing HybridSearchService...")

        # Initialize embedder (reuse across all search calls)
        if embedder is not None:
            self._embedder = embedder
        else:
            from backend.core.embeddings import create_embeddings_generator
            self._embedder = create_embeddings_generator()

        # Initialize collection manager
        qdrant_url = settings.qdrant_url
        self.collection_manager = collection_manager or CollectionManager(qdrant_url=qdrant_url)

        # Initialize BM25 vectorizer
        self._bm25_enabled = False
        self._bm25_vectorizer = None

        if settings.enable_bm25:
            try:
                self._bm25_vectorizer = bm25_vectorizer or get_bm25_vectorizer()
                self._bm25_enabled = True
                logger.info("BM25 vectorizer initialized for hybrid search")
            except Exception as e:
                logger.warning(f"Failed to initialize BM25 vectorizer: {e}")
                self._bm25_enabled = False
        else:
            logger.info("BM25 disabled via settings")

        logger.info("HybridSearchService initialized")

    @property
    def bm25_enabled(self) -> bool:
        """Check if BM25 is enabled and available."""
        return self._bm25_enabled and self._bm25_vectorizer is not None

    def compute_bm25_vectors(self, texts: list[str]) -> list[dict[str, Any]]:
        """
        Compute BM25 sparse vectors for a list of texts.

        Generates sparse vectors in Qdrant format with indices and values
        for BM25-based keyword search.

        Args:
            texts: List of text strings to vectorize

        Returns:
            List of sparse vector dictionaries with 'indices' and 'values' keys

        Example:
            >>> texts = ["visa application process", "KITAS requirements"]
            >>> vectors = service.compute_bm25_vectors(texts)
            >>> print(vectors[0])
            {'indices': [1234, 5678], 'values': [0.85, 0.72]}
        """
        if not self._bm25_enabled or not self._bm25_vectorizer:
            logger.warning("BM25 not enabled, returning empty sparse vectors")
            return [{"indices": [], "values": []} for _ in texts]

        try:
            sparse_vectors = self._bm25_vectorizer.generate_batch_sparse_vectors(texts)
            logger.debug(f"Generated BM25 vectors for {len(texts)} texts")
            return sparse_vectors
        except Exception as e:
            logger.error(f"Failed to compute BM25 vectors: {e}")
            return [{"indices": [], "values": []} for _ in texts]

    def compute_bm25_query_vector(self, query: str) -> dict[str, Any]:
        """
        Compute BM25 sparse vector for a search query.

        Queries use a simplified TF scoring without length normalization
        since they are typically short.

        Args:
            query: Search query string

        Returns:
            Sparse vector dictionary with 'indices' and 'values' keys

        Example:
            >>> query_vector = service.compute_bm25_query_vector("KITAS visa")
            >>> print(query_vector)
            {'indices': [1234, 5678], 'values': [0.69, 0.53]}
        """
        if not self._bm25_enabled or not self._bm25_vectorizer:
            logger.warning("BM25 not enabled, returning empty query vector")
            return {"indices": [], "values": []}

        try:
            sparse_vector = self._bm25_vectorizer.generate_query_sparse_vector(query)
            logger.debug(
                f"Generated BM25 query vector with {len(sparse_vector.get('indices', []))} tokens",
            )
            return sparse_vector
        except Exception as e:
            logger.error(f"Failed to compute BM25 query vector: {e}")
            return {"indices": [], "values": []}

    def reciprocal_rank_fusion(
        self,
        dense_results: list[dict[str, Any]],
        sparse_results: list[dict[str, Any]],
        alpha: float = 0.5,
        k: int = RRF_K,
    ) -> list[dict[str, Any]]:
        """
        Combine dense and sparse search results using Reciprocal Rank Fusion.

        RRF formula: score = sum(1/(k + rank)) for each result list

        Args:
            dense_results: Results from dense vector search, each with 'id' and 'score'
            sparse_results: Results from sparse/BM25 search, each with 'id' and 'score'
            alpha: Weight for balancing dense vs sparse (0.0 = all sparse, 1.0 = all dense)
            k: RRF constant (default 60), higher values reduce the impact of ranking position

        Returns:
            Combined and re-ranked list of results

        Example:
            >>> dense = [{"id": "1", "score": 0.9, "text": "..."}]
            >>> sparse = [{"id": "1", "score": 0.8, "text": "..."}]
            >>> fused = service.reciprocal_rank_fusion(dense, sparse, alpha=0.5)
        """
        if not dense_results and not sparse_results:
            return []

        # Handle edge cases where one result set is empty
        if not sparse_results:
            logger.debug("No sparse results, returning dense results only")
            return [{**r, "fusion_score": r.get("score", 0) * alpha} for r in dense_results]

        if not dense_results:
            logger.debug("No dense results, returning sparse results only")
            return [{**r, "fusion_score": r.get("score", 0) * (1 - alpha)} for r in sparse_results]

        # Build score dictionary: id -> {"dense_rank": rank or None, "sparse_rank": rank or None}
        ranks: dict[str, dict[str, Any]] = {}

        # Add dense ranks
        for rank, result in enumerate(dense_results, start=1):
            doc_id = str(result.get("id", result.get("_id", "")))
            if doc_id:
                if doc_id not in ranks:
                    ranks[doc_id] = {"result": result}
                ranks[doc_id]["dense_rank"] = rank

        # Add sparse ranks
        for rank, result in enumerate(sparse_results, start=1):
            doc_id = str(result.get("id", result.get("_id", "")))
            if doc_id:
                if doc_id not in ranks:
                    ranks[doc_id] = {"result": result}
                ranks[doc_id]["sparse_rank"] = rank

        # Calculate RRF scores
        fused_results = []
        for doc_id, data in ranks.items():
            dense_rank = data.get("dense_rank")
            sparse_rank = data.get("sparse_rank")
            result = data["result"]

            # RRF formula with alpha weighting
            rrf_score = 0.0

            if dense_rank is not None:
                rrf_score += alpha * (1.0 / (k + dense_rank))

            if sparse_rank is not None:
                rrf_score += (1 - alpha) * (1.0 / (k + sparse_rank))

            fused_results.append(
                {
                    **result,
                    "id": doc_id,
                    "fusion_score": round(rrf_score, 6),
                    "dense_rank": dense_rank,
                    "sparse_rank": sparse_rank,
                },
            )

        # Sort by fusion score (descending)
        fused_results.sort(key=lambda x: x["fusion_score"], reverse=True)

        logger.debug(
            f"RRF fusion: {len(dense_results)} dense + {len(sparse_results)} sparse "
            f"= {len(fused_results)} fused results",
        )

        return fused_results

    @cached(ttl=300, prefix="hybrid_search")
    async def search_hybrid(
        self,
        query: str,
        collection: str,
        limit: int = 10,
        alpha: float = 0.5,
        prefetch_limit: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform hybrid search combining BM25 and dense vector search.

        Uses Qdrant's native hybrid search with RRF when available,
        otherwise falls back to manual fusion.

        Args:
            query: Search query string (supports Indonesian and English)
            collection: Name of the Qdrant collection to search
            limit: Maximum number of results to return
            alpha: Weight between BM25 and dense search (0.0=all BM25, 1.0=all dense, 0.5=balanced)
            prefetch_limit: Number of candidates to prefetch (default: limit * 3)
            filters: Optional metadata filters

        Returns:
            Dictionary containing:
                - results: List of search results
                - query: Original query
                - collection: Collection name
                - total_results: Number of results
                - search_type: Type of search performed
                - bm25_enabled: Whether BM25 was used
                - alpha: Fusion weight used

        Example:
            >>> results = await service.search_hybrid(
            ...     query="peraturan visa KITAS",
            ...     collection="legal_unified_hybrid",
            ...     limit=5,
            ...     alpha=0.5
            ... )
            >>> print(results["results"][0]["text"])
        """
        start_time = time.time()
        prefetch_limit = prefetch_limit or limit * 3

        try:
            # Get collection client
            vector_db = self.collection_manager.get_collection(collection)
            if not vector_db:
                # Try creating ad-hoc client
                vector_db = QdrantClient(
                    qdrant_url=settings.qdrant_url,
                    collection_name=collection,
                )

            # Generate BM25 sparse vector
            query_sparse = None
            if self.bm25_enabled:
                query_sparse = self.compute_bm25_query_vector(query)
                if query_sparse.get("indices"):
                    logger.debug(f"BM25 query vector: {len(query_sparse['indices'])} tokens")
                else:
                    logger.warning("BM25 query vector is empty, falling back to dense-only")
                    query_sparse = None

            # Check if collection supports native hybrid search
            has_native_hybrid = hasattr(vector_db, "hybrid_search") and (
                collection.endswith("_hybrid") or "_hybrid" in collection
            )

            if has_native_hybrid and query_sparse and query_sparse.get("indices"):
                # Use Qdrant's native hybrid search with RRF
                try:
                    # Generate dense embedding (reuse init-time embedder)
                    query_embedding = await self._embedder.generate_query_embedding(query)

                    raw_results = await vector_db.hybrid_search(
                        query_embedding=query_embedding,
                        query_sparse=query_sparse,
                        filter=filters,
                        limit=limit,
                        prefetch_limit=prefetch_limit,
                    )

                    search_type = raw_results.get("search_type", "hybrid_rrf")
                    bm25_used = True

                    logger.info(
                        f"Native hybrid search completed: {raw_results.get('total_found', 0)} results",
                    )

                except Exception as e:
                    logger.warning(
                        f"Native hybrid search failed: {e}, falling back to manual fusion",
                    )
                    has_native_hybrid = False

            if not has_native_hybrid or not query_sparse:
                # Fallback: Use manual RRF fusion or dense-only
                search_type, raw_results, bm25_used = await self._manual_hybrid_search(
                    query=query,
                    vector_db=vector_db,
                    collection=collection,
                    limit=limit,
                    alpha=alpha,
                    filters=filters,
                    query_sparse=query_sparse,
                )

            # Format results
            formatted_results = self._format_results(raw_results)

            elapsed = time.time() - start_time
            logger.info(
                f"Hybrid search completed in {elapsed * 1000:.1f}ms: "
                f"{len(formatted_results)} results from {collection}",
            )

            return {
                "results": formatted_results,
                "query": query,
                "collection": collection,
                "total_results": len(formatted_results),
                "search_type": search_type,
                "bm25_enabled": bm25_used and self.bm25_enabled,
                "alpha": alpha,
                "duration_ms": round(elapsed * 1000, 2),
            }

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}", exc_info=True)
            # Graceful degradation: return empty results
            return {
                "results": [],
                "query": query,
                "collection": collection,
                "total_results": 0,
                "search_type": "error",
                "bm25_enabled": False,
                "alpha": alpha,
                "error": str(e),
            }

    async def _manual_hybrid_search(
        self,
        query: str,
        vector_db: QdrantClient,
        collection: str,
        limit: int,
        alpha: float,
        filters: dict[str, Any] | None,
        query_sparse: dict[str, Any] | None,
    ) -> tuple[str, dict[str, Any], bool]:
        """
        Perform manual hybrid search by running dense and sparse separately and fusing.

        Args:
            query: Search query
            vector_db: Qdrant client
            collection: Collection name
            limit: Result limit
            alpha: Fusion weight
            filters: Metadata filters
            query_sparse: Pre-computed sparse vector

        Returns:
            Tuple of (search_type, results, bm25_used)
        """
        query_embedding = await self._embedder.generate_query_embedding(query)

        # Determine vector name for collections with named vectors
        from backend.services.search.search_service import _uses_named_vectors

        use_vector_name = "dense" if _uses_named_vectors(collection) else None

        # Run dense search
        dense_results = await vector_db.search(
            query_embedding=query_embedding,
            filter=filters,
            limit=limit * 2,  # Get more for fusion
            vector_name=use_vector_name,
        )

        dense_formatted = self._format_results(dense_results)

        # Run sparse search if available
        sparse_formatted = []
        bm25_used = False

        if query_sparse and query_sparse.get("indices") and hasattr(vector_db, "search_sparse"):
            try:
                sparse_results = await vector_db.search_sparse(
                    query_sparse=query_sparse,
                    filter=filters,
                    limit=limit * 2,
                )
                sparse_formatted = self._format_results(sparse_results)
                bm25_used = True
            except Exception as e:
                logger.warning(f"Sparse search not available: {e}")

        # Fuse results
        if sparse_formatted:
            fused_results = self.reciprocal_rank_fusion(
                dense_formatted,
                sparse_formatted,
                alpha=alpha,
            )
            search_type = "hybrid_manual_rrf"
        else:
            fused_results = dense_formatted
            search_type = "dense_only"

        # Convert back to raw format
        raw_results = {
            "ids": [r.get("id") for r in fused_results[:limit]],
            "documents": [r.get("text", "") for r in fused_results[:limit]],
            "metadatas": [r.get("metadata", {}) for r in fused_results[:limit]],
            "scores": [r.get("fusion_score", r.get("score", 0)) for r in fused_results[:limit]],
            "total_found": len(fused_results[:limit]),
        }

        return search_type, raw_results, bm25_used

    def _format_results(self, raw_results: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Format raw Qdrant results into standardized format.

        Args:
            raw_results: Raw results from Qdrant

        Returns:
            List of formatted result dictionaries
        """
        formatted = []

        ids = raw_results.get("ids", [])
        documents = raw_results.get("documents", [])
        metadatas = raw_results.get("metadatas", [])
        scores = raw_results.get("scores", raw_results.get("distances", []))

        for i in range(len(ids)):
            formatted.append(
                {
                    "id": str(ids[i]) if i < len(ids) else "",
                    "text": documents[i] if i < len(documents) else "",
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "score": float(scores[i]) if i < len(scores) else 0.0,
                },
            )

        return formatted

    async def search_dense_only(
        self,
        query: str,
        collection: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform dense-only vector search (fallback method).

        Args:
            query: Search query
            collection: Collection name
            limit: Maximum results
            filters: Optional metadata filters

        Returns:
            Search results dictionary
        """
        start_time = time.time()

        try:
            # Get embedding (reuse init-time embedder)
            query_embedding = await self._embedder.generate_query_embedding(query)

            # Get collection
            vector_db = self.collection_manager.get_collection(collection)
            if not vector_db:
                vector_db = QdrantClient(
                    qdrant_url=settings.qdrant_url,
                    collection_name=collection,
                )

            # Search
            from backend.services.search.search_service import _uses_named_vectors

            use_vector_name = "dense" if _uses_named_vectors(collection) else None
            raw_results = await vector_db.search(
                query_embedding=query_embedding,
                filter=filters,
                limit=limit,
                vector_name=use_vector_name,
            )

            formatted_results = self._format_results(raw_results)
            elapsed = time.time() - start_time

            return {
                "results": formatted_results,
                "query": query,
                "collection": collection,
                "total_results": len(formatted_results),
                "search_type": "dense_only",
                "bm25_enabled": False,
                "alpha": 1.0,
                "duration_ms": round(elapsed * 1000, 2),
            }

        except Exception as e:
            logger.error(f"Dense search failed: {e}")
            return {
                "results": [],
                "query": query,
                "collection": collection,
                "total_results": 0,
                "search_type": "error",
                "bm25_enabled": False,
                "alpha": 1.0,
                "error": str(e),
            }

    async def compare_search_methods(
        self,
        query: str,
        collection: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """
        Compare hybrid search vs dense-only search for evaluation.

        Args:
            query: Search query
            collection: Collection name
            limit: Number of results

        Returns:
            Comparison results with both methods
        """
        # Run both searches
        hybrid_results = await self.search_hybrid(
            query=query,
            collection=collection,
            limit=limit,
            alpha=0.5,
        )

        dense_results = await self.search_dense_only(
            query=query,
            collection=collection,
            limit=limit,
        )

        # Calculate overlap
        hybrid_ids = {r["id"] for r in hybrid_results.get("results", [])}
        dense_ids = {r["id"] for r in dense_results.get("results", [])}
        overlap = hybrid_ids & dense_ids

        return {
            "query": query,
            "collection": collection,
            "hybrid": hybrid_results,
            "dense": dense_results,
            "comparison": {
                "hybrid_count": len(hybrid_ids),
                "dense_count": len(dense_ids),
                "overlap_count": len(overlap),
                "overlap_percentage": round(len(overlap) / max(len(hybrid_ids), 1) * 100, 1),
                "hybrid_duration_ms": hybrid_results.get("duration_ms", 0),
                "dense_duration_ms": dense_results.get("duration_ms", 0),
            },
        }


# Global singleton instance
_hybrid_search_service: HybridSearchService | None = None


def get_hybrid_search_service() -> HybridSearchService:
    """
    Get or create global HybridSearchService instance.

    Returns:
        HybridSearchService singleton
    """
    global _hybrid_search_service
    if _hybrid_search_service is None:
        _hybrid_search_service = HybridSearchService()
    return _hybrid_search_service
