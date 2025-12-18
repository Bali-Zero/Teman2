"""
Unit tests for Semantic Re-ranker (Ze-Rank 2 API)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.reranker import ReRanker


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient"""
    mock = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_reranker_init_success():
    """Test ReRanker initialization"""
    # Mock settings
    with patch("core.reranker.settings") as mock_settings:
        mock_settings.zerank_api_key = "test_key"
        mock_settings.zerank_api_url = "https://api.test.com"

        reranker = ReRanker()
        assert reranker.enabled is True
        assert reranker.api_key == "test_key"
        assert reranker.api_url == "https://api.test.com"


@pytest.mark.asyncio
async def test_reranker_disabled_without_key():
    """Test ReRanker disabled if key missing"""
    with patch("core.reranker.settings") as mock_settings:
        mock_settings.zerank_api_key = None

        reranker = ReRanker()
        assert reranker.enabled is False


@pytest.mark.asyncio
async def test_rerank_logic():
    """Test re-ranking logic with mocked API response"""
    with patch("core.reranker.settings") as mock_settings:
        mock_settings.zerank_api_key = "test_key"
        mock_settings.zerank_api_url = "https://api.test.com"

        reranker = ReRanker()

        query = "test query"
        docs = [
            {"text": "This is irrelevant garbage", "id": 1, "score": 0.5},
            {"text": "This is highly relevant content", "id": 2, "score": 0.5},
            {"text": "This is somewhat related", "id": 3, "score": 0.5},
        ]

        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"index": 1, "relevance_score": 0.9},  # id 2
                {"index": 2, "relevance_score": 0.5},  # id 3
                {"index": 0, "relevance_score": 0.1},  # id 1
            ]
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            # Support async context manager
            MockClient.return_value.__aenter__.return_value = mock_client_instance

            reranked = await reranker.rerank(query, docs, top_k=3)

            assert len(reranked) == 3
            assert reranked[0]["id"] == 2
            assert reranked[0]["score"] == 0.9
            assert reranked[0]["rerank_score"] == 0.9

            assert reranked[1]["id"] == 3
            assert reranked[1]["score"] == 0.5

            assert reranked[2]["id"] == 1
            assert reranked[2]["score"] == 0.1


@pytest.mark.asyncio
async def test_rerank_api_error():
    """Test fallback when API fails"""
    with patch("core.reranker.settings") as mock_settings:
        mock_settings.zerank_api_key = "test_key"

        reranker = ReRanker()
        docs = [{"text": "doc1", "score": 0.5}, {"text": "doc2", "score": 0.4}]

        # Mock API error
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client_instance

            # Should return original docs
            result = await reranker.rerank("query", docs)
            assert len(result) == 2
            assert result == docs


@pytest.mark.asyncio
async def test_rerank_empty_results():
    """Test handling of empty API results"""
    with patch("core.reranker.settings") as mock_settings:
        mock_settings.zerank_api_key = "test_key"

        reranker = ReRanker()
        docs = [{"text": "doc1", "score": 0.5}]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client_instance

            result = await reranker.rerank("query", docs)
            assert result == docs
