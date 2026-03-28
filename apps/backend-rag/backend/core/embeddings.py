"""
ZANTARA RAG - Embeddings Generation
Supports both OpenAI and Sentence Transformers

OPTIMIZED: Added LRU caching for embeddings to reduce API calls and latency
"""

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from typing import Any

logger = logging.getLogger(__name__)

# Tracing utilities (with fallback for standalone usage)
try:
    from backend.app.utils.tracing import set_span_attribute, set_span_status, trace_span
except ImportError:
    from contextlib import contextmanager

    @contextmanager
    def trace_span(name: Any, attrs: Any = None) -> Any:
        yield

    def set_span_attribute(key: Any, value: Any) -> Any:
        pass

    def set_span_status(status: Any, msg: Any = None) -> Any:
        pass


# Import settings
try:
    from backend.app.core.config import settings as _default_settings
except ImportError:
    _default_settings = None


class EmbeddingCache:
    """
    LRU Cache for embeddings to avoid repeated API calls.

    Caches embeddings based on text content hash.
    Thread-safe for async usage.
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._cache = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()

    def _get_key(self, texts: list[str]) -> str:
        """Generate cache key from texts using MD5 hash."""
        content = json.dumps(texts, sort_keys=True)
        return md5(content.encode()).hexdigest()

    async def get(self, texts: list[str]) -> list[list[float]] | None:
        """Get cached embeddings if available."""
        key = self._get_key(texts)
        async with self._lock:
            if key in self._cache:
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    async def set(self, texts: list[str], embeddings: list[list[float]]):
        """Store embeddings in cache."""
        async with self._lock:
            if len(self._cache) >= self._max_size:
                # Simple LRU: remove oldest item
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            key = self._get_key(texts)
            self._cache[key] = embeddings

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "size": len(self._cache),
            "max_size": self._max_size,
        }

    async def clear(self):
        """Clear all cached embeddings."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0


# Global cache instance (shared across all generators)
_global_embedding_cache = EmbeddingCache(max_size=1000)


class EmbeddingsGenerator:
    """
    Generate embeddings using configured provider (OpenAI or Sentence Transformers).
    Automatically chooses provider based on settings.

    Note: This class no longer uses singleton pattern. Each instance is independent.
    For dependency injection, use create_embeddings_generator() factory function.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        settings: object | None = None,
    ) -> None:
        """
        Initialize embeddings generator.
        Automatically chooses provider based on settings.

        Args:
            api_key: OpenAI API key (only needed if using OpenAI provider)
            model: Embedding model name (default from settings)
            provider: "openai" or "sentence-transformers" (default from settings)
            settings: Optional settings object (for testing). If None, uses module-level settings.
        """
        self._settings = settings if settings is not None else _default_settings
        self._executor = ThreadPoolExecutor(max_workers=2)  # For CPU-bound tasks

        # Determine provider from settings or parameter
        if provider:
            self.provider = provider
        elif self._settings:
            self.provider = getattr(self._settings, "embedding_provider", "sentence-transformers")
        else:
            # Default to sentence-transformers for local deployment
            self.provider = "sentence-transformers"

        # Load appropriate provider
        if self.provider == "openai":
            self._init_openai(api_key, model)
        else:
            # Default to sentence-transformers (local, no API key needed)
            self._init_sentence_transformers(model)

    def _init_openai(self, api_key: str | None = None, model: str | None = None):
        """Initialize OpenAI embeddings provider"""
        from openai import AsyncOpenAI

        self.provider = "openai"  # Ensure provider is set to openai
        self.model = (
            model
            or (getattr(self._settings, "embedding_model", None) if self._settings else None)
            or "text-embedding-3-small"
        )
        self.dimensions = 1536  # OpenAI text-embedding-3-small is always 1536
        self.api_key = api_key or (
            getattr(self._settings, "openai_api_key", None) if self._settings else None
        )

        if not self.api_key:
            if (
                self._settings
                and getattr(self._settings, "environment", "development") == "production"
            ):
                logger.critical("❌ CRITICAL: No OpenAI API key found in PRODUCTION environment")
                raise ValueError("OpenAI API key is required for OpenAI provider in production")

            raise ValueError("OpenAI API key is required for OpenAI provider")

        self.client = AsyncOpenAI(api_key=self.api_key)
        logger.info(
            f"🔌 [EmbeddingsGenerator] Initialized with OpenAI (Async): {self.model} ({self.dimensions} dims)",
        )

    def _init_sentence_transformers(self, model: str | None = None):
        """Initialize Sentence Transformers local embeddings provider"""
        self.model = (
            model
            or (getattr(self._settings, "embedding_model", None) if self._settings else None)
            or "sentence-transformers/all-MiniLM-L6-v2"
        )

        logger.info(
            f"🔌 [EmbeddingsGenerator] Attempting to load Sentence Transformers: {self.model}",
        )

        try:
            from sentence_transformers import SentenceTransformer

            logger.info("   This may take a moment on first run (downloads model)...")
            self.transformer = SentenceTransformer(self.model)
            self.dimensions = self.transformer.get_sentence_embedding_dimension()
            logger.info(
                f"🔌 [EmbeddingsGenerator] Initialized with Sentence Transformers: {self.model} ({self.dimensions} dims)",
            )

        except ImportError:
            # Sentence transformers not available (size constraint on Fly.io)
            # Fallback to OpenAI
            logger.warning(
                "🔌 [EmbeddingsGenerator] Sentence Transformers not available (size constraint)",
            )
            logger.warning("   Falling back to OpenAI (text-embedding-3-small)")
            logger.warning(
                "   ⚠️ NOTE: This may cause dimension mismatch if Qdrant collections expect 384 dims",
            )
            self._init_openai(model=None)

        except Exception as e:
            logger.error(f"🔌 [EmbeddingsGenerator] Failed to load Sentence Transformers: {e}")
            logger.error("   Falling back to OpenAI...")
            try:
                self._init_openai(model=None)
            except Exception as openai_error:
                logger.error(f"🔌 [EmbeddingsGenerator] Both providers failed: {openai_error}")
                raise

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts (ASYNC).

        Uses LRU caching to avoid redundant API calls for repeated queries.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each vector is a list of floats)

        Raises:
            Exception: If API call fails
        """
        with trace_span(
            "embedding.generate",
            {
                "provider": self.provider,
                "model": self.model,
                "texts_count": len(texts),
                "dimensions": self.dimensions,
            },
        ):
            if not texts:
                logger.warning("Empty text list provided for embedding")
                set_span_attribute("skipped", True)
                set_span_attribute("skip_reason", "empty_input")
                set_span_status("ok")
                return []

            # Check cache first
            cached = await _global_embedding_cache.get(texts)
            if cached:
                logger.debug(f"🔥 Embedding cache HIT for {len(texts)} texts")
                set_span_attribute("cache_hit", True)
                set_span_attribute("cached_embeddings", len(cached))
                set_span_status("ok")
                return cached

            try:
                start_time = time.perf_counter()
                if self.provider == "openai":
                    result = await self._generate_embeddings_openai(texts)
                else:
                    result = await self._generate_embeddings_sentence_transformers(texts)

                # Store in cache for future use
                await _global_embedding_cache.set(texts, result)

                latency_ms = (time.perf_counter() - start_time) * 1000
                set_span_attribute("latency_ms", round(latency_ms, 2))
                set_span_attribute("embeddings_generated", len(result))
                set_span_attribute("cache_hit", False)
                set_span_status("ok")
                return result

            except Exception as e:
                logger.error(f"Error generating embeddings: {e}")
                set_span_status("error", str(e))
                raise

    def get_cache_stats(self) -> dict:
        """Get embedding cache statistics."""
        return _global_embedding_cache.get_stats()

    async def clear_cache(self):
        """Clear the embedding cache."""
        await _global_embedding_cache.clear()

    async def _generate_embeddings_openai(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings using OpenAI API (ASYNC).
        Automatically batches large requests (OpenAI max batch size: 2048).
        """
        logger.info(f"Generating embeddings for {len(texts)} texts using OpenAI (Async)")

        MAX_BATCH_SIZE = 2048  # OpenAI API limit
        all_embeddings = []

        # Process in batches if needed
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i : i + MAX_BATCH_SIZE]
            logger.debug(f"Processing batch {i // MAX_BATCH_SIZE + 1}: {len(batch)} texts")

            # Call OpenAI API Async
            response = await self.client.embeddings.create(model=self.model, input=batch)

            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        logger.info(
            f"✅ Generated {len(all_embeddings)} embeddings (OpenAI, {len(all_embeddings[0]) if all_embeddings else 0} dims)",
        )
        return all_embeddings

    async def _generate_embeddings_sentence_transformers(
        self, texts: list[str],
    ) -> list[list[float]]:
        """Generate embeddings using Sentence Transformers (Thread Pool Offload)"""
        logger.info(f"Generating embeddings for {len(texts)} texts using Sentence Transformers")

        try:
            loop = asyncio.get_running_loop()

            # Offload CPU-bound task to executor
            embeddings = await loop.run_in_executor(
                self._executor,
                lambda: self.transformer.encode(
                    texts, convert_to_numpy=True, show_progress_bar=False,
                ),
            )

            # Convert numpy array to list of lists
            embeddings_list = embeddings.tolist()
            logger.info(f"✅ Generated {len(embeddings_list)} embeddings (Sentence Transformers)")
            return embeddings_list

        except Exception as e:
            logger.error(f"Sentence Transformers error: {e}")
            raise

    async def generate_single_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text (ASYNC).

        Args:
            text: Text string to embed

        Returns:
            Embedding vector as list of floats
        """
        embeddings = await self.generate_embeddings([text])
        return embeddings[0] if embeddings else []

    async def generate_query_embedding(self, query: str) -> list[float]:
        """
        Generate embedding optimized for query/search (ASYNC).

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        # For text-embedding-3-small, same process as document embedding
        return await self.generate_single_embedding(query)

    async def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts (ASYNC).

        Alias for generate_embeddings() for backward compatibility.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (each vector is a list of floats)
        """
        return await self.generate_embeddings(texts)

    def get_model_info(self) -> dict:
        """
        Get information about the embedding model.

        Returns:
            Dictionary with model configuration
        """
        cost_info = "Paid (OpenAI API)" if self.provider == "openai" else "FREE (Local)"
        return {
            "model": self.model,
            "dimensions": self.dimensions,
            "provider": self.provider,
            "cost": cost_info,
        }


# Factory function for dependency injection
def create_embeddings_generator(
    api_key: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    settings: object | None = None,
) -> EmbeddingsGenerator:
    """
    Factory function to create EmbeddingsGenerator instance.
    Use this for dependency injection instead of direct instantiation.

    Args:
        api_key: OpenAI API key (only needed if using OpenAI provider)
        model: Embedding model name (default from settings)
        provider: "openai" or "sentence-transformers" (default from settings)
        settings: Optional settings object (for testing)

    Returns:
        EmbeddingsGenerator instance
    """
    return EmbeddingsGenerator(api_key=api_key, model=model, provider=provider, settings=settings)


# Convenience function
async def generate_embeddings(texts: list[str], api_key: str | None = None) -> list[list[float]]:
    """
    Quick function to generate embeddings without instantiating class (ASYNC).

    Args:
        texts: List of texts to embed
        api_key: Optional OpenAI API key

    Returns:
        List of embedding vectors
    """
    generator = EmbeddingsGenerator(api_key=api_key)
    return await generator.generate_embeddings(texts)
