"""
Nuzantara RAG - Cross-Encoder Reranker
Implements local cross-encoder reranking for high-precision retrieval.

This module provides a CrossEncoderReranker class that uses local transformer models
to re-rank search results based on query-document relevance. It runs entirely locally
without external API calls, making it suitable for deployments where data privacy
is critical or external API latency is a concern.

Recommended models:
- cross-encoder/ms-marco-MiniLM-L-6-v2 (fast, good quality, default)
- BAAI/bge-reranker-v2-m3 (better for multilingual)
- cross-encoder/ms-marco-MiniLM-L-12-v2 (slightly better quality, slower)

Usage:
    reranker = CrossEncoderReranker()
    reranked_docs = await reranker.rerank(query, documents, top_k=5)
"""

import asyncio
import logging
import time
from typing import Any

from backend.app.core.config import settings

# Tracing utilities (with fallback for standalone usage)
try:
    from backend.app.utils.tracing import set_span_attribute, set_span_status, trace_span
except ImportError:
    from contextlib import contextmanager

    @contextmanager
    def trace_span(name: Any, attrs: Any = None) -> Any:
        """Trace span."""
        yield

    def set_span_attribute(key: Any, value: Any) -> Any:
        """Set span attribute."""
        pass

    def set_span_status(status: Any, msg: Any = None) -> Any:
        """Set span status."""
        pass


logger = logging.getLogger(__name__)

# Model cache to avoid reloading models
_model_cache: dict[str, Any] = {}


class CrossEncoderReranker:
    """
    Cross-Encoder Reranker using local transformer models.

    Re-scores (query, document) pairs to determine true relevance using
    a cross-encoder model running locally. This provides better accuracy
    than bi-encoders (embedding similarity) at the cost of more computation.

    The model is loaded once and cached for subsequent requests to minimize
    latency. All inference is done in a thread pool to avoid blocking the
    async event loop.

    Attributes:
        model_name: Name of the cross-encoder model from HuggingFace
        model: The loaded cross-encoder model (cached)
        max_length: Maximum sequence length for the model
        batch_size: Batch size for inference
        enabled: Whether reranking is enabled
    """

    def __init__(
        self,
        model_name: str | None = None,
        max_length: int = 512,
        batch_size: int = 32,
        enabled: bool | None = None,
    ) -> None:
        """
        Initialize the Cross-Encoder Reranker.

        Args:
            model_name: HuggingFace model name. Defaults to config or
                "cross-encoder/ms-marco-MiniLM-L-6-v2"
            max_length: Maximum sequence length for tokenization
            batch_size: Batch size for model inference
            enabled: Whether to enable reranking. Defaults to config setting.
        """
        self.model_name = model_name or getattr(
            settings, "reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        self.max_length = max_length
        self.batch_size = batch_size
        self._model: Any = None
        self._model_loading: bool = False

        # Determine if enabled from settings or parameter
        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = getattr(settings, "enable_reranker", True)

        if not self.enabled:
            logger.warning(
                "⚠️ CrossEncoderReranker is disabled. Reranking will return documents unchanged."
            )
        else:
            logger.info(f"🔧 CrossEncoderReranker initialized (model: {self.model_name})")

    def _load_model(self) -> Any:
        """
        Load the cross-encoder model from HuggingFace.

        Uses model caching to avoid reloading for each instance.
        Falls back gracefully if model loading fails.

        Returns:
            The loaded cross-encoder model or None if loading failed
        """
        global _model_cache

        # Check cache first
        if self.model_name in _model_cache:
            logger.debug(f"Using cached model: {self.model_name}")
            return _model_cache[self.model_name]

        if self._model_loading:
            logger.warning("Model is already being loaded, waiting...")
            return None

        self._model_loading = True

        try:
            # Import here to avoid loading transformers at module import time
            from sentence_transformers import CrossEncoder

            logger.info(f"📥 Loading cross-encoder model: {self.model_name}")
            start_time = time.perf_counter()

            model = CrossEncoder(
                self.model_name,
                max_length=self.max_length,
                device="cpu",  # Can be changed to "cuda" if GPU is available
            )

            load_time = (time.perf_counter() - start_time) * 1000
            logger.info(f"✅ Model loaded in {load_time:.0f}ms")

            # Cache the model
            _model_cache[self.model_name] = model

            return model

        except ImportError as e:
            logger.error(
                f"❌ Failed to import sentence-transformers: {e}. "
                "Install with: pip install sentence-transformers"
            )
            self.enabled = False
            return None

        except Exception as e:
            logger.error(f"❌ Failed to load model {self.model_name}: {e}")
            self.enabled = False
            return None

        finally:
            self._model_loading = False

    @property
    def model(self) -> Any:
        """Lazy load and return the model."""
        if self._model is None and self.enabled:
            self._model = self._load_model()
        return self._model

    def compute_scores(
        self,
        query: str,
        documents: list[str],
    ) -> list[float]:
        """
        Compute relevance scores for query-document pairs.

        This is a synchronous method that runs the model inference.
        For async contexts, use compute_scores_async or rerank.

        Args:
            query: The search query
            documents: List of document texts to score

        Returns:
            List of relevance scores (0-1 range, higher = more relevant)

        Example:
            >>> reranker = CrossEncoderReranker()
            >>> scores = reranker.compute_scores("What is AI?", ["AI is...", "The weather is..."])
            >>> logger.info(scores)  # [0.95, 0.12]
        """
        if not self.enabled or not documents:
            return [0.0] * len(documents)

        model = self.model
        if model is None:
            logger.warning("Model not available, returning zero scores")
            return [0.0] * len(documents)

        try:
            # Prepare query-document pairs
            pairs = [(query, doc) for doc in documents]

            # Run inference
            start_time = time.perf_counter()
            scores = model.predict(
                pairs,
                batch_size=self.batch_size,
                show_progress_bar=False,
            )
            inference_time = (time.perf_counter() - start_time) * 1000

            logger.debug(
                f"Computed scores for {len(documents)} documents in {inference_time:.1f}ms"
            )

            # Convert to list of floats and normalize to 0-1 if needed
            # MS MARCO models output raw logits, apply sigmoid for probability
            if "ms-marco" in self.model_name.lower():
                import numpy as np

                scores = 1 / (1 + np.exp(-scores))  # Sigmoid

            return scores.tolist() if hasattr(scores, "tolist") else list(scores)

        except Exception as e:
            logger.error(f"❌ Score computation failed: {e}")
            return [0.0] * len(documents)

    async def compute_scores_async(
        self,
        query: str,
        documents: list[str],
    ) -> list[float]:
        """
        Async wrapper for compute_scores.

        Runs the CPU-bound model inference in a thread pool to avoid
        blocking the async event loop.

        Args:
            query: The search query
            documents: List of document texts to score

        Returns:
            List of relevance scores (0-1 range)
        """
        if not self.enabled or not documents:
            return [0.0] * len(documents)

        # Run in thread pool to avoid blocking
        return await asyncio.to_thread(self.compute_scores, query, documents)

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Re-rank documents based on relevance to the query.

        Takes a list of documents (typically from vector search), scores each
        document's relevance to the query using the cross-encoder, and returns
        the top_k most relevant documents sorted by score.

        Documents are expected to have either 'text' or 'content' keys.
        The original score is preserved as 'vector_score', and the rerank score
        is stored in 'score' and 'rerank_score'.

        Args:
            query: The search query
            documents: List of document dictionaries from vector search
            top_k: Number of top results to return after reranking

        Returns:
            List of re-ranked document dictionaries, sorted by relevance

        Example:
            >>> docs = [
            ...     {"text": "AI is artificial intelligence", "score": 0.8},
            ...     {"text": "Weather today is sunny", "score": 0.9},
            ... ]
            >>> reranked = await reranker.rerank("What is AI?", docs, top_k=2)
            >>> # AI document will be first despite lower vector score
        """
        with trace_span(
            "rerank.cross_encoder",
            {
                "documents_count": len(documents),
                "top_k": top_k,
                "model": self.model_name,
                "enabled": self.enabled,
            },
        ):
            # Handle disabled or empty cases
            if not self.enabled:
                set_span_attribute("skipped", True)
                set_span_attribute("skip_reason", "disabled")
                set_span_status("ok")
                return documents[:top_k]

            if not documents:
                set_span_attribute("skipped", True)
                set_span_attribute("skip_reason", "no_documents")
                set_span_status("ok")
                return []

            # Extract text content from documents
            doc_texts = []
            valid_docs = []

            for doc in documents:
                text = doc.get("text") or doc.get("content") or ""
                if text:
                    doc_texts.append(text)
                    valid_docs.append(doc)

            if not doc_texts:
                set_span_attribute("skipped", True)
                set_span_attribute("skip_reason", "no_valid_text")
                set_span_status("ok")
                return documents[:top_k]

            set_span_attribute("valid_documents_count", len(valid_docs))

            try:
                # Compute scores asynchronously
                start_time = time.perf_counter()
                scores = await self.compute_scores_async(query, doc_texts)
                compute_time = (time.perf_counter() - start_time) * 1000
                set_span_attribute("compute_time_ms", round(compute_time, 2))

                # Attach scores to documents
                reranked_docs = []
                for doc, score in zip(valid_docs, scores, strict=False):
                    # Create a copy to avoid mutating original
                    doc_copy = doc.copy()

                    # Store rerank score
                    doc_copy["rerank_score"] = float(score)

                    # Preserve original score
                    if "score" in doc_copy and "vector_score" not in doc_copy:
                        doc_copy["vector_score"] = doc_copy["score"]

                    # Update main score to rerank score
                    doc_copy["score"] = float(score)
                    reranked_docs.append(doc_copy)

                # Sort by rerank score (descending)
                reranked_docs.sort(key=lambda x: x["score"], reverse=True)

                set_span_attribute("results_count", len(reranked_docs))
                if reranked_docs:
                    set_span_attribute("top_score", round(reranked_docs[0]["score"], 4))
                set_span_attribute("latency_ms", round(compute_time, 2))
                set_span_status("ok")

                logger.info(
                    f"✅ Reranked {len(reranked_docs)} documents in {compute_time:.1f}ms "
                    f"(model: {self.model_name})"
                )

                return reranked_docs[:top_k]

            except Exception as e:
                logger.error(f"❌ Re-ranking failed: {e}")
                set_span_status("error", str(e))
                # Fallback to original order
                return documents[:top_k]

    async def batch_rerank(
        self,
        queries: list[str],
        documents_list: list[list[dict[str, Any]]],
        top_k: int = 5,
    ) -> list[list[dict[str, Any]]]:
        """
        Re-rank multiple query-document sets in parallel.

        Efficiently reranks multiple queries with their respective documents
        by running them concurrently. Useful for batch processing or when
        handling multiple search results simultaneously.

        Args:
            queries: List of search queries (one per document set)
            documents_list: List of document lists, one per query
            top_k: Number of top results to return for each query

        Returns:
            List of re-ranked document lists, in the same order as input

        Example:
            >>> queries = ["What is AI?", "Weather in Bali"]
            >>> docs_list = [
            ...     [{"text": "AI is..."}, {"text": "The capital is..."}],
            ...     [{"text": "Bali is sunny..."}, {"text": "AI stands for..."}],
            ... ]
            >>> results = await reranker.batch_rerank(queries, docs_list, top_k=2)
        """
        if not self.enabled:
            return [docs[:top_k] for docs in documents_list]

        if len(queries) != len(documents_list):
            raise ValueError(
                f"Queries count ({len(queries)}) must match documents list count ({len(documents_list)})"
            )

        # Run all reranks concurrently
        tasks = [
            self.rerank(query, docs, top_k)
            for query, docs in zip(queries, documents_list, strict=False)
        ]

        return await asyncio.gather(*tasks)


def get_reranker(
    model_name: str | None = None,
    force_local: bool = False,
) -> CrossEncoderReranker | Any:
    """
    Factory function to get the appropriate reranker.

    Returns a CrossEncoderReranker by default, or falls back to the
    existing ReRanker if configured to use external API.

    Args:
        model_name: Optional model name override
        force_local: If True, always return CrossEncoderReranker

    Returns:
        A reranker instance (CrossEncoderReranker or legacy ReRanker)
    """
    # Check if we should use external API (legacy behavior)
    use_external = getattr(settings, "zerank_api_key", None) and not force_local

    if use_external:
        # Import here to avoid circular imports
        from backend.core.reranker import ReRanker

        logger.info("Using external Ze-Rank 2 API reranker")
        return ReRanker(model_name=model_name)

    logger.info("Using local CrossEncoderReranker")
    return CrossEncoderReranker(model_name=model_name)


# Convenience function for direct usage
async def rerank_documents(
    query: str,
    documents: list[dict[str, Any]],
    top_k: int = 5,
    model_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    Convenience function to rerank documents without creating a reranker instance.

    Creates a singleton reranker instance and uses it to rerank documents.
    The instance is cached for subsequent calls.

    Args:
        query: The search query
        documents: List of documents to rerank
        top_k: Number of top results to return
        model_name: Optional model name override

    Returns:
        Re-ranked list of documents

    Example:
        >>> docs = [{"text": "Document 1"}, {"text": "Document 2"}]
        >>> results = await rerank_documents("query", docs, top_k=5)
    """
    reranker = get_reranker(model_name=model_name)
    return await reranker.rerank(query, documents, top_k=top_k)
