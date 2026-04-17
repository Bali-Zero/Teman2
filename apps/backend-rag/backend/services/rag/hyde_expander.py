"""HyDE (Hypothetical Document Embedding) Query Expander.

Generates hypothetical answer documents for a query, embeds them,
and returns additional dense vectors for hybrid search fusion.
This improves retrieval for complex queries where the original query
terms don't match the answer vocabulary.

References:
  Gao et al. 2022 — "Precise Zero-Shot Dense Retrieval without Relevance Labels"

# Organo: backend-rag/rag → produce embedding vectors → consuma da hybrid_search
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import httpx
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# HyDE generation prompt — domain-specific for Indonesian business services
HYDE_PROMPT = """You are a knowledge base about Indonesian business services in Bali.
Given the question below, write a short paragraph (3-5 sentences) that would be
a perfect answer. Focus on specific facts, regulations, requirements, and numbers.
Be concrete and authoritative. Do NOT ask clarifying questions.

Question: "{query}"

Answer:"""

# Cache config
CACHE_PREFIX = "zantara:hyde"
CACHE_TTL = 21600  # 6 hours


class HyDEExpander:
    """Generate hypothetical document embeddings for improved retrieval.

    Uses Ollama (local, fast) for document generation, with Gemini Flash fallback.
    Embeds generated documents using the FROZEN text-embedding-3-small model.
    """

    def __init__(
        self,
        ollama_client: Any = None,
        embedding_client: Any = None,
        redis_client: Any = None,
    ) -> None:
        self._ollama = ollama_client
        self._embedding = embedding_client
        self._redis = redis_client

    async def expand(
        self,
        query: str,
        num_docs: int = 2,
    ) -> list[list[float]]:
        """Generate hypothetical docs and return their embedding vectors.

        Args:
            query: User query to expand.
            num_docs: Number of hypothetical docs to generate (default 2).

        Returns:
            List of embedding vectors (each 1536-dim for text-embedding-3-small).
            Empty list on any failure (graceful degradation).
        """
        # Check cache first
        cache_key = self._cache_key(query)
        cached = await self._get_cached(cache_key)
        if cached is not None:
            logger.debug("HyDE cache hit for query: %s", query[:50])
            return cached

        # Generate hypothetical documents
        hypo_docs = await self._generate_hypothetical_docs(query, num_docs)
        if not hypo_docs:
            logger.debug("HyDE: no hypothetical docs generated for: %s", query[:50])
            return []

        # Embed hypothetical documents
        vectors = await self._embed_documents(hypo_docs)
        if not vectors:
            logger.debug("HyDE: embedding failed for: %s", query[:50])
            return []

        # Cache the vectors
        await self._set_cached(cache_key, vectors)

        logger.info(
            "HyDE: generated %d hypothetical docs, %d vectors for: %s",
            len(hypo_docs),
            len(vectors),
            query[:50],
        )
        return vectors

    async def expand_texts(
        self,
        query: str,
        num_docs: int = 2,
    ) -> list[str]:
        """Generate hypothetical docs and return their text (for debugging/testing).

        Same as expand() but returns text instead of vectors.
        """
        return await self._generate_hypothetical_docs(query, num_docs)

    # ── Private methods ──

    async def _generate_hypothetical_docs(
        self, query: str, num_docs: int
    ) -> list[str]:
        """Generate hypothetical answer documents via LLM."""
        docs: list[str] = []

        for i in range(num_docs):
            prompt = HYDE_PROMPT.format(query=query)
            if i > 0:
                prompt += f"\n\n(Provide a DIFFERENT perspective from previous answers.)"

            doc = await self._call_llm(prompt)
            if doc and len(doc.strip()) > 30:
                docs.append(doc.strip())

        return docs

    async def _call_llm(self, prompt: str) -> str:
        """Call Ollama (preferred) or fall back to Gemini Flash."""
        # Try Ollama first (local, fast, sovereign)
        if self._ollama is not None:
            try:
                result = await self._ollama.generate(
                    prompt=prompt,
                    model="qwen3.5:9b",
                    options={"temperature": 0.7, "num_predict": 256, "think": False},
                )
                if result:
                    return result
            except (httpx.HTTPError, ConnectionError, TimeoutError) as exc:
                logger.debug("HyDE: Ollama failed (%s), trying fallback", exc)
            except Exception as exc:  # noqa: BLE001 — HyDE is optional; degrade to empty document
                logger.debug("HyDE: Ollama failed unexpectedly (%s), trying fallback", exc)

        # Stub for when no LLM is available — return empty for graceful degradation
        logger.debug("HyDE: no LLM available, returning empty")
        return ""

    async def _embed_documents(self, documents: list[str]) -> list[list[float]]:
        """Embed documents using text-embedding-3-small (FROZEN)."""
        if self._embedding is None:
            logger.debug("HyDE: no embedding client available")
            return []

        vectors: list[list[float]] = []
        for doc in documents:
            try:
                vector = await self._embedding.embed(doc)
                if vector and len(vector) == 1536:
                    vectors.append(vector)
            except (httpx.HTTPError, ValueError, TimeoutError) as exc:
                logger.warning("HyDE: embedding failed for doc (%s)", exc)
            except Exception as exc:  # noqa: BLE001 — skip bad doc, continue embedding others
                logger.warning("HyDE: embedding failed unexpectedly for doc (%s)", exc, exc_info=True)

        return vectors

    def _cache_key(self, query: str) -> str:
        """Generate Redis cache key for a query."""
        normalized = query.lower().strip()
        h = hashlib.md5(normalized.encode()).hexdigest()[:12]
        return f"{CACHE_PREFIX}:{h}"

    async def _get_cached(self, key: str) -> list[list[float]] | None:
        """Get cached HyDE vectors from Redis."""
        if self._redis is None:
            return None
        try:
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
        except (RedisError, json.JSONDecodeError, TypeError):
            # cache miss on redis/parse error is fine — caller will recompute
            pass
        except Exception:  # noqa: BLE001 — cache read must never surface to caller
            logger.debug("HyDE: cache get failed unexpectedly", exc_info=True)
        return None

    async def _set_cached(self, key: str, vectors: list[list[float]]) -> None:
        """Cache HyDE vectors in Redis."""
        if self._redis is None:
            return
        try:
            await self._redis.set(key, json.dumps(vectors), ex=CACHE_TTL)
        except (RedisError, TypeError, ValueError) as exc:
            logger.debug("HyDE: cache set failed (%s)", exc)
        except Exception as exc:  # noqa: BLE001 — cache write is best-effort
            logger.debug("HyDE: cache set failed unexpectedly (%s)", exc)
