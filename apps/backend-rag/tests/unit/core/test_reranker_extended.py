"""
Extended unit tests for core.reranker module to improve coverage
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from core.reranker import ReRanker


@pytest.fixture
def mock_settings():
    """Mock settings with API key"""
    with patch("core.reranker.settings") as mock_settings:
        mock_settings.zerank_api_key = "test_api_key"
        mock_settings.zerank_api_url = "https://api.zerank.com/rerank"
        yield mock_settings


@pytest.fixture
def reranker_enabled(mock_settings):
    """Create ReRanker instance with API key enabled"""
    return ReRanker(model_name="zerank-2")


@pytest.fixture
def reranker_disabled():
    """Create ReRanker instance without API key"""
    with patch("core.reranker.settings") as mock_settings:
        mock_settings.zerank_api_key = None
        mock_settings.zerank_api_url = "https://api.zerank.com/rerank"
        return ReRanker()


class TestReRankerInit:
    """Tests for ReRanker initialization"""

    def test_init_with_api_key(self, mock_settings):
        """Test initialization with API key"""
        reranker = ReRanker()
        assert reranker.enabled is True
        assert reranker.api_key == "test_api_key"
        assert reranker.api_url == "https://api.zerank.com/rerank"

    def test_init_without_api_key(self):
        """Test initialization without API key"""
        with patch("core.reranker.settings") as mock_settings:
            mock_settings.zerank_api_key = None
            mock_settings.zerank_api_url = "https://api.zerank.com/rerank"
            reranker = ReRanker()
            assert reranker.enabled is False

    def test_init_with_custom_model_name(self, mock_settings):
        """Test initialization with custom model name"""
        reranker = ReRanker(model_name="custom-model")
        assert reranker.model_name == "custom-model"

    def test_init_default_model_name(self, mock_settings):
        """Test initialization with default model name"""
        reranker = ReRanker()
        assert reranker.model_name == "zerank-2"


class TestReRankerDisabled:
    """Tests for ReRanker when disabled"""

    @pytest.mark.asyncio
    async def test_rerank_disabled_returns_original(self, reranker_disabled):
        """Test rerank returns original documents when disabled"""
        documents = [
            {"text": "Doc 1", "score": 0.5},
            {"text": "Doc 2", "score": 0.3},
        ]
        result = await reranker_disabled.rerank("test query", documents, top_k=2)
        assert result == documents
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_rerank_disabled_empty_documents(self, reranker_disabled):
        """Test rerank with empty documents when disabled"""
        result = await reranker_disabled.rerank("test query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_disabled_respects_top_k(self, reranker_disabled):
        """Test rerank respects top_k when disabled"""
        documents = [
            {"text": "Doc 1", "score": 0.5},
            {"text": "Doc 2", "score": 0.3},
            {"text": "Doc 3", "score": 0.2},
        ]
        result = await reranker_disabled.rerank("test query", documents, top_k=2)
        assert len(result) == 2


class TestReRankerEnabled:
    """Tests for ReRanker when enabled"""

    @pytest.mark.asyncio
    async def test_rerank_success(self, reranker_enabled):
        """Test successful reranking"""
        documents = [
            {"text": "Doc 1", "score": 0.5},
            {"text": "Doc 2", "score": 0.3},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"index": 1, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.85},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await reranker_enabled.rerank("test query", documents, top_k=2)

            assert len(result) == 2
            assert result[0]["score"] == 0.95
            assert result[0]["rerank_score"] == 0.95
            assert result[1]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self, reranker_enabled):
        """Test rerank with empty documents"""
        result = await reranker_enabled.rerank("test query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_no_valid_text(self, reranker_enabled):
        """Test rerank with documents without text or content"""
        documents = [
            {"metadata": "some data", "score": 0.5},
            {"id": "doc2", "score": 0.3},
        ]
        result = await reranker_enabled.rerank("test query", documents, top_k=2)
        assert result == documents[:2]

    @pytest.mark.asyncio
    async def test_rerank_uses_content_key(self, reranker_enabled):
        """Test rerank uses 'content' key when 'text' is missing"""
        documents = [
            {"content": "Doc 1", "score": 0.5},
            {"content": "Doc 2", "score": 0.3},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.9},
                {"index": 1, "relevance_score": 0.8},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await reranker_enabled.rerank("test query", documents, top_k=2)
            assert len(result) == 2
            assert result[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_rerank_api_error_status(self, reranker_enabled):
        """Test rerank handles API error status"""
        documents = [
            {"text": "Doc 1", "score": 0.5},
            {"text": "Doc 2", "score": 0.3},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await reranker_enabled.rerank("test query", documents, top_k=2)
            # Should return original documents on error
            assert result == documents[:2]

    @pytest.mark.asyncio
    async def test_rerank_api_no_results(self, reranker_enabled):
        """Test rerank handles API returning no results"""
        documents = [
            {"text": "Doc 1", "score": 0.5},
            {"text": "Doc 2", "score": 0.3},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await reranker_enabled.rerank("test query", documents, top_k=2)
            # Should return original documents when no results
            assert result == documents[:2]

    @pytest.mark.asyncio
    async def test_rerank_preserves_vector_score(self, reranker_enabled):
        """Test rerank preserves original score as vector_score"""
        documents = [
            {"text": "Doc 1", "score": 0.5},
            {"text": "Doc 2", "score": 0.3},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.9},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await reranker_enabled.rerank("test query", documents, top_k=1)
            assert result[0]["vector_score"] == 0.5
            assert result[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_rerank_sorts_by_score(self, reranker_enabled):
        """Test rerank sorts results by score descending"""
        documents = [
            {"text": "Doc 1", "score": 0.5},
            {"text": "Doc 2", "score": 0.3},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"index": 1, "relevance_score": 0.8},  # Lower index but higher score
                {"index": 0, "relevance_score": 0.9},  # Higher index but lower score
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await reranker_enabled.rerank("test query", documents, top_k=2)
            # Should be sorted by score descending
            assert result[0]["score"] == 0.9
            assert result[1]["score"] == 0.8

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(self, reranker_enabled):
        """Test rerank respects top_k parameter"""
        documents = [
            {"text": "Doc 1", "score": 0.5},
            {"text": "Doc 2", "score": 0.3},
            {"text": "Doc 3", "score": 0.2},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.9},
                {"index": 1, "relevance_score": 0.8},
                {"index": 2, "relevance_score": 0.7},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await reranker_enabled.rerank("test query", documents, top_k=2)
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_rerank_handles_exception(self, reranker_enabled):
        """Test rerank handles exceptions gracefully"""
        documents = [
            {"text": "Doc 1", "score": 0.5},
        ]

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Network error")
            )

            result = await reranker_enabled.rerank("test query", documents, top_k=1)
            # Should return original documents on exception
            assert result == documents[:1]

    @pytest.mark.asyncio
    async def test_rerank_invalid_index(self, reranker_enabled):
        """Test rerank handles invalid index in API response"""
        documents = [
            {"text": "Doc 1", "score": 0.5},
            {"text": "Doc 2", "score": 0.3},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"index": 0, "relevance_score": 0.9},
                {"index": 10, "relevance_score": 0.8},  # Invalid index
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await reranker_enabled.rerank("test query", documents, top_k=2)
            # Should only include valid index
            assert len(result) == 1
            assert result[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_rerank_missing_relevance_score(self, reranker_enabled):
        """Test rerank handles missing relevance_score in API response"""
        documents = [
            {"text": "Doc 1", "score": 0.5},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"index": 0},  # Missing relevance_score
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await reranker_enabled.rerank("test query", documents, top_k=1)
            # Should use default score of 0.0
            assert result[0]["score"] == 0.0
