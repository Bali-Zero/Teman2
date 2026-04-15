"""Tests for HyDE (Hypothetical Document Embedding) Query Expander.

# Organo: backend-rag/rag → produce embedding vectors → consuma da hybrid_search
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.rag.hyde_expander import HYDE_PROMPT, HyDEExpander


class TestHyDEExpander:
    """HyDE generates hypothetical answer docs and embeds them."""

    def setup_method(self) -> None:
        self.mock_ollama = AsyncMock()
        self.mock_embedding = AsyncMock()
        self.mock_redis = AsyncMock()
        self.expander = HyDEExpander(
            ollama_client=self.mock_ollama,
            embedding_client=self.mock_embedding,
            redis_client=self.mock_redis,
        )

    # ── Core flow ──

    @pytest.mark.asyncio
    async def test_expand_returns_vectors(self) -> None:
        """Full flow: generate docs → embed → return vectors."""
        self.mock_redis.get.return_value = None  # cache miss
        self.mock_ollama.generate.return_value = (
            "KITAS work permit requires RPTKA approval and sponsor letter from employer."
        )
        fake_vector = [0.1] * 1536
        self.mock_embedding.embed.return_value = fake_vector

        vectors = await self.expander.expand("What is KITAS?", num_docs=2)

        assert len(vectors) == 2
        assert all(len(v) == 1536 for v in vectors)
        assert self.mock_ollama.generate.call_count == 2
        assert self.mock_embedding.embed.call_count == 2

    @pytest.mark.asyncio
    async def test_expand_cache_hit(self) -> None:
        """Cached vectors returned without LLM/embedding calls."""
        cached_vectors = [[0.5] * 1536, [0.6] * 1536]
        import json
        self.mock_redis.get.return_value = json.dumps(cached_vectors)

        vectors = await self.expander.expand("What is KITAS?")

        assert vectors == cached_vectors
        self.mock_ollama.generate.assert_not_called()
        self.mock_embedding.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_expand_caches_result(self) -> None:
        """Generated vectors are cached in Redis."""
        self.mock_redis.get.return_value = None
        self.mock_ollama.generate.return_value = (
            "Detailed answer about visa requirements for working in Indonesia."
        )
        self.mock_embedding.embed.return_value = [0.1] * 1536

        await self.expander.expand("visa requirements")

        self.mock_redis.set.assert_called_once()
        call_args = self.mock_redis.set.call_args
        assert "zantara:hyde:" in call_args[0][0]

    # ── Graceful degradation ──

    @pytest.mark.asyncio
    async def test_ollama_failure_returns_empty(self) -> None:
        """Ollama failure → graceful degradation to empty list."""
        self.mock_redis.get.return_value = None
        self.mock_ollama.generate.side_effect = Exception("Ollama down")

        vectors = await self.expander.expand("test query")

        assert vectors == []

    @pytest.mark.asyncio
    async def test_embedding_failure_returns_empty(self) -> None:
        """Embedding failure → graceful degradation to empty list."""
        self.mock_redis.get.return_value = None
        self.mock_ollama.generate.return_value = (
            "A detailed answer about Indonesian business setup procedures and requirements."
        )
        self.mock_embedding.embed.side_effect = Exception("Embedding API down")

        vectors = await self.expander.expand("test query")

        assert vectors == []

    @pytest.mark.asyncio
    async def test_no_clients_returns_empty(self) -> None:
        """No LLM or embedding clients → returns empty list."""
        expander = HyDEExpander()  # no clients
        vectors = await expander.expand("test query")
        assert vectors == []

    @pytest.mark.asyncio
    async def test_redis_failure_still_works(self) -> None:
        """Redis failure → still generates and returns vectors."""
        self.mock_redis.get.side_effect = Exception("Redis down")
        self.mock_redis.set.side_effect = Exception("Redis down")
        self.mock_ollama.generate.return_value = (
            "PT PMA company setup requires minimum paid-up capital and NIB from OSS."
        )
        self.mock_embedding.embed.return_value = [0.2] * 1536

        vectors = await self.expander.expand("PT PMA setup", num_docs=1)

        assert len(vectors) == 1

    # ── Text generation ──

    @pytest.mark.asyncio
    async def test_expand_texts_returns_strings(self) -> None:
        """expand_texts() returns text, not vectors (for debugging)."""
        self.mock_ollama.generate.return_value = (
            "Indonesian tax obligations for PT PMA include PPh and PPN reporting."
        )

        texts = await self.expander.expand_texts("tax obligations", num_docs=2)

        assert len(texts) == 2
        assert all(isinstance(t, str) for t in texts)
        assert all(len(t) > 30 for t in texts)

    @pytest.mark.asyncio
    async def test_short_llm_output_filtered(self) -> None:
        """LLM output shorter than 30 chars is filtered out."""
        self.mock_redis.get.return_value = None
        self.mock_ollama.generate.return_value = "Too short"

        vectors = await self.expander.expand("test", num_docs=2)

        assert vectors == []

    # ── Prompt format ──

    def test_prompt_includes_query(self) -> None:
        """HYDE_PROMPT template includes the query placeholder."""
        formatted = HYDE_PROMPT.format(query="What is KITAS?")
        assert "What is KITAS?" in formatted
        assert "knowledge base" in formatted.lower()

    @pytest.mark.asyncio
    async def test_wrong_embedding_dimension_filtered(self) -> None:
        """Embedding with wrong dimension (not 1536) is filtered out."""
        self.mock_redis.get.return_value = None
        self.mock_ollama.generate.return_value = (
            "Detailed explanation of business permit requirements in Indonesia."
        )
        self.mock_embedding.embed.return_value = [0.1] * 768  # wrong dim

        vectors = await self.expander.expand("test", num_docs=1)

        assert vectors == []
