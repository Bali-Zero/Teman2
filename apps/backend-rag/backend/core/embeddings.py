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

from backend.services.observability import llm_cost_tracked, set_usage

logger = logging.getLogger(__name__)

# Token-aware sub-batching (cicatrix scar 2026-05-10):
# OpenAI text-embedding-3-small has TWO hard limits:
#   1. 300k tokens per request (sum across all inputs)
#   2. 8192 tokens per single input string
# Large legal PDFs hit (1) (e.g. Permenkumham 22/2023 7MB → 460k tokens), and
# the chunker may also emit single chunks >8192 tokens triggering (2). Both
# previously caused silent partial-embeddings → upsert length-mismatch error.
# We use tiktoken to enforce both limits before sending to API.
_OPENAI_EMBED_MAX_TOKENS_PER_REQUEST = 300_000
_OPENAI_EMBED_TOKEN_BUDGET = 200_000  # safety margin for limit (1)
_OPENAI_EMBED_MAX_TOKENS_PER_INPUT = 8192  # OpenAI hard limit (2)
_OPENAI_EMBED_INPUT_TOKEN_BUDGET = 7500  # safety margin for limit (2)
try:
    import tiktoken

    _TIKTOKEN_AVAILABLE = True
    _TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
except ImportError:
    _TIKTOKEN_AVAILABLE = False
    _TIKTOKEN_ENCODER = None
    logger.warning(
        "tiktoken not available — embedding sub-batching falls back to "
        "char-count heuristic (1 token ≈ 4 chars). Recommended: pip install tiktoken",
    )


def _count_tokens(text: str) -> int:
    """Count tokens for a string using tiktoken (or char-based fallback)."""
    if _TIKTOKEN_AVAILABLE and _TIKTOKEN_ENCODER is not None:
        try:
            return len(_TIKTOKEN_ENCODER.encode(text, disallowed_special=()))
        except Exception:
            pass
    # Fallback: 1 token ≈ 4 characters (conservative for non-English)
    return max(1, len(text) // 3)  # use /3 not /4 to err on safer side for Bahasa


def _truncate_oversized_input(text: str, max_tokens: int = _OPENAI_EMBED_INPUT_TOKEN_BUDGET) -> str:
    """Truncate a single input string to max_tokens (OpenAI 8192 hard limit).

    Logs WARNING when truncation happens — the upstream chunker should produce
    chunks within the limit; oversized inputs are evidence of a chunker config
    bug or a malformed PDF page.
    """
    if not _TIKTOKEN_AVAILABLE or _TIKTOKEN_ENCODER is None:
        # Char-based fallback: ~4 chars/token → max ~30k chars
        max_chars = max_tokens * 3
        if len(text) > max_chars:
            logger.warning(
                f"Truncating oversized input (char-fallback): {len(text)} chars → {max_chars}",
            )
            return text[:max_chars] + " [TRUNCATED]"
        return text

    tokens = _TIKTOKEN_ENCODER.encode(text, disallowed_special=())
    if len(tokens) <= max_tokens:
        return text
    truncated_tokens = tokens[:max_tokens]
    truncated_text = _TIKTOKEN_ENCODER.decode(truncated_tokens)
    logger.warning(
        f"Truncating oversized input: {len(tokens)} tokens → {max_tokens} "
        f"({len(text)} chars → {len(truncated_text)} chars). "
        f"Upstream chunker should produce smaller chunks (limit: OpenAI 8192/input).",
    )
    return truncated_text + " [TRUNCATED]"


def _split_by_token_budget(
    texts: list[str], budget: int = _OPENAI_EMBED_TOKEN_BUDGET,
) -> list[list[str]]:
    """Split texts into sub-batches each under `budget` tokens.

    Each individual text is assumed to fit within budget (chunker should ensure
    this; if not, it's emitted as its own sub-batch and OpenAI will reject it
    with a clear error rather than silently truncating).
    """
    sub_batches: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for text in texts:
        text_tokens = _count_tokens(text)
        if current_tokens + text_tokens > budget and current:
            sub_batches.append(current)
            current = [text]
            current_tokens = text_tokens
        else:
            current.append(text)
            current_tokens += text_tokens
    if current:
        sub_batches.append(current)
    return sub_batches

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

    async def set(self, texts: list[str], embeddings: list[list[float]]) -> None:
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

    async def clear(self) -> None:
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

    def _init_openai(self, api_key: str | None = None, model: str | None = None) -> None:
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

    def _init_sentence_transformers(self, model: str | None = None) -> None:
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
                # IMPORTANT (cicatrix scar 2026-05-10): do NOT swallow this error
                # by returning []. Downstream code (LegalIngestionService,
                # HierarchicalIndexer) expects len(embeddings) == len(texts) and
                # otherwise produces silent partial-ingest with chunks_created=0.
                # Propagating the error lets the caller fail loudly + log clearly.
                logger.error(f"Error generating embeddings: {e}")
                set_span_status("error", str(e))
                raise

    def get_cache_stats(self) -> dict:
        """Get embedding cache statistics."""
        return _global_embedding_cache.get_stats()

    async def clear_cache(self) -> None:
        """Clear the embedding cache."""
        await _global_embedding_cache.clear()

    @llm_cost_tracked(provider="openai_embeddings", model_attr="model")
    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        """
        Call the OpenAI Embeddings API for a single batch (ASYNC).
        Tracks cost via @llm_cost_tracked; token counts come from response.usage.
        """
        response = await self.client.embeddings.create(model=self.model, input=batch)
        set_usage(
            input_tokens=getattr(response.usage, "prompt_tokens", 0),
            output_tokens=0,
        )
        return [item.embedding for item in response.data]

    async def _generate_embeddings_openai(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings using OpenAI API (ASYNC).

        Two-level batching:
          1. **Item count**: max 2048 texts per request (OpenAI API limit)
          2. **Token count**: max 200k tokens per request (safety margin under
             OpenAI 300k hard limit; cicatrix scar 2026-05-10 — large legal
             PDFs hit this limit silently producing length-mismatch errors)
        """
        logger.info(f"Generating embeddings for {len(texts)} texts using OpenAI (Async)")

        # Pre-flight: truncate any single input >8192 tokens (OpenAI per-input limit).
        # Counts truncations to surface chunker config issues.
        truncated_texts: list[str] = []
        n_truncated = 0
        for t in texts:
            t_safe = _truncate_oversized_input(t)
            if t_safe is not t:
                n_truncated += 1
            truncated_texts.append(t_safe)
        if n_truncated > 0:
            logger.warning(
                f"⚠️  {n_truncated}/{len(texts)} inputs were truncated to fit OpenAI "
                f"8192-token per-input limit. Consider tuning chunker max chunk size.",
            )

        MAX_BATCH_SIZE = 2048  # OpenAI API limit (item count)
        all_embeddings: list[list[float]] = []

        # First level: split by item count
        item_batches = [
            truncated_texts[i : i + MAX_BATCH_SIZE]
            for i in range(0, len(truncated_texts), MAX_BATCH_SIZE)
        ]

        for batch_idx, item_batch in enumerate(item_batches, start=1):
            # Second level: split by token budget
            sub_batches = _split_by_token_budget(item_batch, budget=_OPENAI_EMBED_TOKEN_BUDGET)
            logger.debug(
                f"Item batch {batch_idx}/{len(item_batches)}: {len(item_batch)} texts → "
                f"{len(sub_batches)} token-sub-batches",
            )
            for sub_idx, sub_batch in enumerate(sub_batches, start=1):
                sub_tokens = sum(_count_tokens(t) for t in sub_batch)
                logger.debug(
                    f"  sub-batch {sub_idx}/{len(sub_batches)}: {len(sub_batch)} texts, "
                    f"~{sub_tokens} tokens",
                )
                if sub_tokens > _OPENAI_EMBED_MAX_TOKENS_PER_REQUEST:
                    # A single text exceeds the hard limit — log + let OpenAI reject
                    # with the explicit max_tokens_per_request error.
                    logger.error(
                        f"Sub-batch exceeds OpenAI 300k token limit "
                        f"({sub_tokens} tokens, {len(sub_batch)} texts). "
                        f"Likely a single chunk too large; chunker should produce "
                        f"smaller chunks. Will attempt anyway — expect 400 from API.",
                    )
                sub_embeddings = await self._embed_batch(sub_batch)
                if len(sub_embeddings) != len(sub_batch):
                    raise RuntimeError(
                        f"OpenAI embed batch returned {len(sub_embeddings)} embeddings for "
                        f"{len(sub_batch)} input texts — likely truncation due to API limit. "
                        f"Sub-batch tokens: ~{sub_tokens}. Aborting before downstream "
                        f"length-mismatch error in upsert.",
                    )
                all_embeddings.extend(sub_embeddings)

        # Hard contract: caller MUST receive same number of embeddings as inputs
        if len(all_embeddings) != len(texts):
            raise RuntimeError(
                f"OpenAI embedding generation produced {len(all_embeddings)} vectors for "
                f"{len(texts)} input texts (mismatch). This is a bug in batching logic.",
            )
        logger.info(
            f"✅ Generated {len(all_embeddings)} embeddings (OpenAI, "
            f"{len(all_embeddings[0]) if all_embeddings else 0} dims)",
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
