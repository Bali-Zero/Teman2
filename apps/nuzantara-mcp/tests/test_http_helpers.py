"""Unit tests for server HTTP helper functions (_call, _call_safe)."""

from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest


@pytest.mark.asyncio
async def test_call_success() -> None:
    """_call should return parsed JSON on success."""
    from nuzantara_mcp.server import _call

    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ok"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("nuzantara_mcp.server.httpx.AsyncClient", return_value=mock_client):
        result = await _call("/health")

    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_call_raises_on_http_error() -> None:
    """_call should raise httpx.HTTPStatusError on non-2xx."""
    from nuzantara_mcp.server import _call

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error",
        request=MagicMock(),
        response=MagicMock(status_code=500),
    )

    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("nuzantara_mcp.server.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            await _call("/bad-endpoint")


@pytest.mark.asyncio
async def test_call_safe_returns_error_on_http_error() -> None:
    """_call_safe should return error dict instead of raising."""
    from nuzantara_mcp.server import _call_safe

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found",
        request=MagicMock(),
        response=mock_response,
    )

    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("nuzantara_mcp.server.httpx.AsyncClient", return_value=mock_client):
        result = await _call_safe("/missing")

    assert result["error"] is True
    assert result["status"] == 404


@pytest.mark.asyncio
async def test_call_safe_returns_error_on_connection_error() -> None:
    """_call_safe should return error dict on connection failure."""
    from nuzantara_mcp.server import _call_safe

    mock_client = AsyncMock()
    mock_client.request.side_effect = httpx.RequestError("Connection refused")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("nuzantara_mcp.server.httpx.AsyncClient", return_value=mock_client):
        result = await _call_safe("/unreachable")

    assert result["error"] is True
    assert result["status"] == 0
    assert "Connection error" in result["detail"]
