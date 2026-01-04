"""
Unit tests for core/reranker.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.reranker import ReRanker


class TestReRanker:
    """Tests for ReRanker class"""

    def test_init_without_api_key(self):
        """Test ReRanker initialization without API key"""
        with patch("core.reranker.settings") as mock_settings:
            mock_settings.zerank_api_key = None
            mock_settings.zerank_api_url = "http://api.example.com"

            reranker = ReRanker()

            assert reranker.enabled is False
            assert reranker.api_key is None

    def test_init_with_api_key(self):
        """Test ReRanker initialization with API key"""
        with patch("core.reranker.settings") as mock_settings:
            mock_settings.zerank_api_key = "test-api-key"
            mock_settings.zerank_api_url = "http://api.example.com"

            reranker = ReRanker()

            assert reranker.enabled is True
            assert reranker.api_key == "test-api-key"
            assert reranker.api_url == "http://api.example.com"

    def test_init_with_custom_model(self):
        """Test ReRanker initialization with custom model"""
        with patch("core.reranker.settings") as mock_settings:
            mock_settings.zerank_api_key = "test-key"
            mock_settings.zerank_api_url = "http://api.example.com"

            reranker = ReRanker(model_name="custom-model")

            assert reranker.model_name == "custom-model"

    @pytest.mark.asyncio
    async def test_rerank_disabled(self):
        """Test rerank when disabled"""
        with patch("core.reranker.settings") as mock_settings:
            mock_settings.zerank_api_key = None
            mock_settings.zerank_api_url = "http://api.example.com"

            reranker = ReRanker()
            documents = [{"text": "doc1", "score": 0.9}, {"text": "doc2", "score": 0.8}]

            result = await reranker.rerank("query", documents, top_k=2)

            assert len(result) == 2
            assert result == documents[:2]

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self):
        """Test rerank with empty documents"""
        with patch("core.reranker.settings") as mock_settings:
            mock_settings.zerank_api_key = "test-key"
            mock_settings.zerank_api_url = "http://api.example.com"

            reranker = ReRanker()

            result = await reranker.rerank("query", [], top_k=5)

            assert result == []

    @pytest.mark.asyncio
    async def test_rerank_success(self):
        """Test successful rerank"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"index": 1, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.85},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with (
            patch("core.reranker.settings") as mock_settings,
            patch("core.reranker.httpx.AsyncClient") as mock_client,
        ):
            mock_settings.zerank_api_key = "test-key"
            mock_settings.zerank_api_url = "http://api.example.com"

            reranker = ReRanker()

            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance

            documents = [{"text": "doc1", "score": 0.8}, {"text": "doc2", "score": 0.9}]

            result = await reranker.rerank("query", documents, top_k=2)

            assert len(result) == 2
            assert "rerank_score" in result[0]

    @pytest.mark.asyncio
    async def test_rerank_with_content_key(self):
        """Test rerank with 'content' key instead of 'text'"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"index": 0, "relevance_score": 0.9}]}
        mock_response.raise_for_status = MagicMock()

        with (
            patch("core.reranker.settings") as mock_settings,
            patch("core.reranker.httpx.AsyncClient") as mock_client,
        ):
            mock_settings.zerank_api_key = "test-key"
            mock_settings.zerank_api_url = "http://api.example.com"

            reranker = ReRanker()

            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance

            documents = [{"content": "doc1", "score": 0.8}]

            result = await reranker.rerank("query", documents, top_k=1)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_rerank_no_valid_text(self):
        """Test rerank with documents without text or content"""
        with patch("core.reranker.settings") as mock_settings:
            mock_settings.zerank_api_key = "test-key"
            mock_settings.zerank_api_url = "http://api.example.com"

            reranker = ReRanker()
            documents = [
                {"score": 0.8},  # No text or content
                {"metadata": "data"},  # No text or content
            ]

            result = await reranker.rerank("query", documents, top_k=2)

            # Should return original documents
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_rerank_http_error(self):
        """Test rerank with HTTP error"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        with (
            patch("core.reranker.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_settings.zerank_api_key = "test-key"
            mock_settings.zerank_api_url = "http://api.example.com"

            reranker = ReRanker()

            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.post = AsyncMock(side_effect=error)
            mock_client.return_value = mock_client_instance

            documents = [{"text": "doc1", "score": 0.8}]

            # Should return original documents on error
            result = await reranker.rerank("query", documents, top_k=1)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_rerank_timeout(self):
        """Test rerank with timeout"""
        timeout_error = httpx.TimeoutException("Request timeout")

        with (
            patch("core.reranker.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_client,
        ):
            mock_settings.zerank_api_key = "test-key"
            mock_settings.zerank_api_url = "http://api.example.com"

            reranker = ReRanker()

            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.post = AsyncMock(side_effect=timeout_error)
            mock_client.return_value = mock_client_instance

            documents = [{"text": "doc1", "score": 0.8}]

            # Should return original documents on timeout
            result = await reranker.rerank("query", documents, top_k=1)

            assert len(result) == 1
