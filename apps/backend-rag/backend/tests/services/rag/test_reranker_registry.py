"""Tests for Reranker Registry — swappable reranker backends.

# Organo: backend-rag/rag → produce reranked docs → consuma da ReAct loop
"""

from __future__ import annotations

import pytest

from backend.services.rag.reranker_registry import (
    NoOpReranker,
    RerankerRegistry,
    get_reranker,
)


class TestRerankerRegistry:
    """Registry pattern for swappable reranker models."""

    def test_get_ms_marco_default(self) -> None:
        """Default reranker is ms-marco CrossEncoder."""
        reranker = get_reranker()
        assert reranker is not None
        assert hasattr(reranker, "rerank")

    def test_get_none_returns_noop(self) -> None:
        """model_name='none' returns NoOpReranker (passthrough)."""
        reranker = get_reranker("none")
        assert isinstance(reranker, NoOpReranker)

    @pytest.mark.asyncio
    async def test_noop_reranker_passthrough(self) -> None:
        """NoOpReranker returns documents unchanged."""
        docs = [
            {"content": "doc1", "score": 0.5},
            {"content": "doc2", "score": 0.8},
            {"content": "doc3", "score": 0.3},
        ]
        reranker = NoOpReranker()
        result = await reranker.rerank("test query", docs, top_k=3)
        assert len(result) == 3
        assert result == docs

    @pytest.mark.asyncio
    async def test_noop_reranker_top_k(self) -> None:
        """NoOpReranker respects top_k."""
        docs = [
            {"content": f"doc{i}", "score": 0.5} for i in range(10)
        ]
        reranker = NoOpReranker()
        result = await reranker.rerank("test", docs, top_k=3)
        assert len(result) == 3

    def test_registry_list_models(self) -> None:
        """Registry exposes available model names."""
        registry = RerankerRegistry()
        models = registry.available_models()
        assert "ms-marco" in models
        assert "none" in models

    def test_unknown_model_raises(self) -> None:
        """Unknown model name raises KeyError."""
        with pytest.raises(KeyError):
            get_reranker("nonexistent-model")

    def test_get_bge_m3(self) -> None:
        """BGE-M3 reranker is registered."""
        reranker = get_reranker("bge-m3")
        assert reranker is not None
        assert hasattr(reranker, "rerank")

    @pytest.mark.asyncio
    async def test_noop_reranker_empty_docs(self) -> None:
        """NoOpReranker handles empty doc list gracefully."""
        reranker = NoOpReranker()
        result = await reranker.rerank("query", [], top_k=5)
        assert result == []
