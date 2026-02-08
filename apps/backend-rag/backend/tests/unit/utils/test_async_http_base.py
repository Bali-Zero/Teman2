"""
Comprehensive pytest suite for AsyncHttpService base class.
Tests: _get_client, close, _post_json, _get_json, _auth_header

Target: 90%+ coverage
"""

import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

from backend.utils.async_http_base import AsyncHttpService


class ConcreteHttpService(AsyncHttpService):
    """Concrete implementation for testing."""

    @property
    def service_name(self) -> str:
        return "TestService"


@pytest.fixture
def service():
    """Fresh ConcreteHttpService instance."""
    return ConcreteHttpService()


@pytest.fixture
def mock_success_response():
    """Mock 200 response."""
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"result": "ok"}
    return r


@pytest.fixture
def mock_error_response():
    """Mock error response."""
    r = MagicMock()
    r.status_code = 400
    r.json.return_value = {"error": {"message": "Bad request", "code": 400}}
    return r


class TestClientLifecycle:
    """Tests for HTTP client creation and cleanup."""

    @pytest.mark.asyncio
    async def test_get_client_creates(self, service) -> None:
        client = await service._get_client()
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        await service.close()

    @pytest.mark.asyncio
    async def test_get_client_reuses(self, service) -> None:
        c1 = await service._get_client()
        c2 = await service._get_client()
        assert c1 is c2
        await service.close()

    @pytest.mark.asyncio
    async def test_close(self, service) -> None:
        await service._get_client()
        await service.close()
        assert service._client is None

    @pytest.mark.asyncio
    async def test_close_when_none(self, service) -> None:
        await service.close()  # Should not raise

    def test_service_name(self, service) -> None:
        assert service.service_name == "TestService"


class TestPostJson:
    """Tests for _post_json method."""

    @pytest.mark.asyncio
    async def test_success(self, service, mock_success_response) -> None:
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = mock_success_response
        service._client = mock_client

        result = await service._post_json(
            "https://api.example.com/send",
            {"key": "value"},
        )

        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_with_headers(self, service, mock_success_response) -> None:
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = mock_success_response
        service._client = mock_client

        await service._post_json(
            "https://api.example.com/send",
            {"key": "value"},
            headers={"Authorization": "Bearer token"},
        )

        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer token"

    @pytest.mark.asyncio
    async def test_api_error(self, service, mock_error_response) -> None:
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.return_value = mock_error_response
        service._client = mock_client

        with pytest.raises(ValueError, match="TestService API error"):
            await service._post_json("https://api.example.com/send", {})

    @pytest.mark.asyncio
    async def test_http_error(self, service) -> None:
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.side_effect = httpx.ConnectError("refused")
        service._client = mock_client

        with pytest.raises(httpx.HTTPError):
            await service._post_json("https://api.example.com/send", {})


class TestGetJson:
    """Tests for _get_json method."""

    @pytest.mark.asyncio
    async def test_success(self, service, mock_success_response) -> None:
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = mock_success_response
        service._client = mock_client

        result = await service._get_json("https://api.example.com/data")
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_with_params(self, service, mock_success_response) -> None:
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = mock_success_response
        service._client = mock_client

        await service._get_json(
            "https://api.example.com/data",
            params={"fields": "id,name"},
        )

        call_kwargs = mock_client.get.call_args
        assert call_kwargs.kwargs["params"]["fields"] == "id,name"

    @pytest.mark.asyncio
    async def test_api_error(self, service, mock_error_response) -> None:
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get.return_value = mock_error_response
        service._client = mock_client

        with pytest.raises(ValueError, match="TestService API error"):
            await service._get_json("https://api.example.com/data")


class TestAuthHeader:
    """Tests for _auth_header helper."""

    def test_bearer_token(self, service) -> None:
        headers = service._auth_header("my_token_123")
        assert headers["Authorization"] == "Bearer my_token_123"
        assert headers["Content-Type"] == "application/json"
