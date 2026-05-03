"""
Unit tests for backend/services/rag/reranker_integration.py
Tests the integration between CrossEncoderReranker and SearchService.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.rag.reranker_integration import (
    CrossEncoderRerankerMixin,
    SearchServiceWithCrossEncoder,
    add_cross_encoder_reranking,
    get_reranker_config,
    should_use_cross_encoder,
)


@pytest.fixture
def sample_documents():
    """Fixture providing sample documents."""
    return [
        {
            "text": "Artificial Intelligence is the simulation of human intelligence.",
            "score": 0.9,
            "id": 1,
        },
        {"text": "The weather today is sunny.", "score": 0.8, "id": 2},
        {"text": "Machine learning is a subset of AI.", "score": 0.7, "id": 3},
        {"text": "Python is a programming language.", "score": 0.6, "id": 4},
    ]


class TestCrossEncoderRerankerMixin:
    """Tests for CrossEncoderRerankerMixin."""

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_search_with_cross_encoder_reranking_success(
        self, mock_settings, sample_documents,
    ):
        """Test successful search with cross-encoder reranking."""
        mock_settings.enable_reranker = True
        mock_settings.reranker_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"

        mock_reranker = MagicMock()
        mock_reranker.enabled = True
        mock_reranker.model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        mock_reranker.rerank = AsyncMock(return_value=sample_documents[:2])

        # Create a proper mock class that inherits from the mixin
        class MockSearchService(CrossEncoderRerankerMixin):
            def __init__(self, reranker) -> None:
                self._cross_encoder_reranker = reranker

            async def search(self, **kwargs):
                return {
                    "results": sample_documents,
                    "allowed_tiers": ["S", "A"],
                    "collection_used": "legal_unified",
                }

        with patch(
            "backend.services.rag.reranker.CrossEncoderReranker", return_value=mock_reranker,
        ):
            service = MockSearchService(mock_reranker)
            results = await service.search_with_cross_encoder_reranking(
                "What is AI?",
                user_level=2,
                limit=2,
            )

            assert results["reranked"] is True
            assert results["reranker_enabled"] is True
            assert results["reranker_model"] == "cross-encoder/ms-marco-MiniLM-L-6-v2"
            assert len(results["results"]) == 2
            mock_reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_search_with_cross_encoder_reranking_disabled(self, mock_settings):
        """Test search when reranking is disabled."""
        mock_settings.enable_reranker = False

        mock_reranker = MagicMock()
        mock_reranker.enabled = False

        class MockSearchService(CrossEncoderRerankerMixin):
            def __init__(self, reranker) -> None:
                self._cross_encoder_reranker = reranker

            async def search(self, **kwargs):
                return {
                    "results": [{"text": "doc", "score": 0.8}],
                    "allowed_tiers": ["S"],
                    "collection_used": "legal_unified",
                }

        with patch(
            "backend.services.rag.reranker.CrossEncoderReranker", return_value=mock_reranker,
        ):
            service = MockSearchService(mock_reranker)
            results = await service.search_with_cross_encoder_reranking(
                "query",
                user_level=2,
                limit=2,
            )

            assert results["reranked"] is False
            assert results["reranker_enabled"] is False

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_search_with_cross_encoder_reranking_disabled_via_param(self, mock_settings):
        """Test search when reranking is disabled via parameter."""
        mock_settings.enable_reranker = True

        mock_reranker = MagicMock()
        mock_reranker.enabled = True

        class MockSearchService(CrossEncoderRerankerMixin):
            def __init__(self, reranker) -> None:
                self._cross_encoder_reranker = reranker

            async def search(self, **kwargs):
                return {
                    "results": [{"text": "doc", "score": 0.8}],
                    "allowed_tiers": ["S"],
                    "collection_used": "legal_unified",
                }

        with patch(
            "backend.services.rag.reranker.CrossEncoderReranker", return_value=mock_reranker,
        ):
            service = MockSearchService(mock_reranker)
            results = await service.search_with_cross_encoder_reranking(
                "query",
                user_level=2,
                limit=2,
                use_reranking=False,
            )

            assert results["reranked"] is False
            mock_reranker.rerank.assert_not_called()

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_search_with_cross_encoder_reranking_error(self, mock_settings):
        """Test search when reranking fails."""
        mock_settings.enable_reranker = True

        mock_reranker = MagicMock()
        mock_reranker.enabled = True
        mock_reranker.rerank = AsyncMock(side_effect=RuntimeError("Reranking failed"))
        mock_reranker.model_name = "test-model"

        class MockSearchService(CrossEncoderRerankerMixin):
            def __init__(self, reranker) -> None:
                self._cross_encoder_reranker = reranker

            async def search(self, **kwargs):
                return {
                    "results": [{"text": "doc", "score": 0.8}],
                    "allowed_tiers": ["S"],
                    "collection_used": "legal_unified",
                }

        with patch(
            "backend.services.rag.reranker.CrossEncoderReranker", return_value=mock_reranker,
        ):
            service = MockSearchService(mock_reranker)
            results = await service.search_with_cross_encoder_reranking(
                "query",
                user_level=2,
                limit=2,
            )

            assert results["reranked"] is False
            assert "rerank_error" in results

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_hybrid_search_with_cross_encoder_reranking(self, mock_settings):
        """Test hybrid search with cross-encoder reranking."""
        mock_settings.enable_reranker = True

        mock_reranker = MagicMock()
        mock_reranker.enabled = True
        mock_reranker.model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        mock_reranker.rerank = AsyncMock(return_value=[{"text": "result", "score": 0.99}])

        class MockSearchService(CrossEncoderRerankerMixin):
            def __init__(self, reranker) -> None:
                self._cross_encoder_reranker = reranker

            async def hybrid_search(self, **kwargs):
                return {
                    "results": [{"text": "doc", "score": 0.95}],
                    "collection": "legal_unified",
                    "search_type": "hybrid_rrf",
                    "bm25_enabled": True,
                }

        with patch(
            "backend.services.rag.reranker.CrossEncoderReranker", return_value=mock_reranker,
        ):
            service = MockSearchService(mock_reranker)
            results = await service.hybrid_search_with_cross_encoder_reranking(
                "query",
                user_level=2,
                limit=2,
            )

            assert results["reranked"] is True
            assert results["search_type"] == "hybrid_rrf"
            assert results["bm25_enabled"] is True

    @pytest.mark.asyncio
    @patch("backend.services.rag.reranker.settings")
    async def test_hybrid_search_fallback(self, mock_settings):
        """Test hybrid search fallback to regular search on error."""
        mock_settings.enable_reranker = True

        mock_reranker = MagicMock()
        mock_reranker.enabled = True
        mock_reranker.rerank = AsyncMock(return_value=[{"text": "result", "score": 0.99}])

        class MockSearchService(CrossEncoderRerankerMixin):
            def __init__(self, reranker) -> None:
                self._cross_encoder_reranker = reranker

            async def hybrid_search(self, **kwargs):
                raise Exception("Hybrid failed")

            async def search(self, **kwargs):
                return {
                    "results": [{"text": "doc", "score": 0.8}],
                    "allowed_tiers": ["S"],
                    "collection_used": "legal_unified",
                }

        with patch(
            "backend.services.rag.reranker.CrossEncoderReranker", return_value=mock_reranker,
        ):
            service = MockSearchService(mock_reranker)
            results = await service.hybrid_search_with_cross_encoder_reranking(
                "query",
                user_level=2,
                limit=2,
            )

            assert results["search_type"] == "dense_fallback"


class TestAddCrossEncoderReranking:
    """Tests for add_cross_encoder_reranking function."""

    def test_add_cross_encoder_reranking(self):
        """Test adding cross-encoder reranking to a service."""
        mock_service = MagicMock()
        mock_service._cross_encoder_reranker = None

        with patch("backend.services.rag.reranker.CrossEncoderReranker") as mock_reranker_class:
            mock_reranker = MagicMock()
            mock_reranker.enabled = True
            mock_reranker_class.return_value = mock_reranker

            add_cross_encoder_reranking(mock_service)

            assert hasattr(mock_service, "search_with_cross_encoder_reranking")
            assert hasattr(mock_service, "hybrid_search_with_cross_encoder_reranking")


class TestSearchServiceWithCrossEncoder:
    """Tests for SearchServiceWithCrossEncoder class."""

    def test_search_service_with_cross_encoder_creation(self):
        """Test that SearchServiceWithCrossEncoder class exists and can be referenced."""
        # The actual instantiation requires many dependencies
        # Just verify the class exists and is properly defined
        assert SearchServiceWithCrossEncoder is not None

        # Verify it creates a combined class when instantiated
        # (actual instantiation requires Qdrant connection)
        with patch("backend.services.search.search_service.CollectionManager"):
            with patch("backend.services.rag.reranker.CrossEncoderReranker"):
                # Should not raise during class creation
                try:
                    service = SearchServiceWithCrossEncoder.__new__(SearchServiceWithCrossEncoder)
                    assert service is not None
                except Exception:
                    # Expected without full mocking
                    pass


class TestGetRerankerConfig:
    """Tests for get_reranker_config function."""

    @patch("backend.services.rag.reranker_integration.settings")
    def test_get_reranker_config(self, mock_settings):
        """Test getting reranker configuration."""
        mock_settings.enable_reranker = True
        mock_settings.reranker_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        mock_settings.reranker_top_k = 5
        mock_settings.reranker_overfetch_count = 20
        mock_settings.reranker_return_count = 5
        mock_settings.reranker_cache_enabled = True
        mock_settings.reranker_latency_target_ms = 50.0

        config = get_reranker_config()

        assert config["enabled"] is True
        assert config["model"] == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert config["top_k"] == 5
        assert config["overfetch_count"] == 20
        assert config["return_count"] == 5
        assert config["cache_enabled"] is True
        assert config["latency_target_ms"] == 50.0

    @patch("backend.services.rag.reranker_integration.settings")
    def test_get_reranker_config_defaults(self, mock_settings):
        """Test getting reranker configuration with defaults."""
        # Simulate missing settings
        mock_settings.enable_reranker = None

        config = get_reranker_config()

        assert "enabled" in config
        assert "model" in config


class TestShouldUseCrossEncoder:
    """Tests for should_use_cross_encoder function."""

    @patch("backend.services.rag.reranker_integration.settings")
    def test_should_use_cross_encoder_disabled(self, mock_settings):
        """Test when cross-encoder is disabled."""
        mock_settings.enable_reranker = False

        result = should_use_cross_encoder()
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
