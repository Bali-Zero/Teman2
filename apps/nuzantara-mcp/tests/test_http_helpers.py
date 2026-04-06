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
    mock_client.is_closed = False

    with patch("nuzantara_mcp.server._http_client", mock_client):
        result = await _call("/health")

    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_call_raises_runtime_error_on_http_error() -> None:
    """_call should raise RuntimeError with status code on non-2xx."""
    from nuzantara_mcp.server import _call

    mock_error_response = MagicMock()
    mock_error_response.status_code = 500
    mock_error_response.text = "Internal Server Error"

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error",
        request=MagicMock(),
        response=mock_error_response,
    )

    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response
    mock_client.is_closed = False

    with patch("nuzantara_mcp.server._http_client", mock_client):
        with pytest.raises(RuntimeError, match="HTTP 500"):
            await _call("/bad-endpoint")


@pytest.mark.asyncio
async def test_call_safe_returns_error_on_http_error() -> None:
    """_call_safe should return error dict with status code."""
    from nuzantara_mcp.server import _call_safe

    mock_error_response = MagicMock()
    mock_error_response.status_code = 500
    mock_error_response.text = "Internal Server Error"

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error",
        request=MagicMock(),
        response=mock_error_response,
    )

    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response
    mock_client.is_closed = False

    with patch("nuzantara_mcp.server._http_client", mock_client):
        result = await _call_safe("/missing")

    # _call_safe catches RuntimeError from _call and also httpx errors
    assert result.get("error") is True


@pytest.mark.asyncio
async def test_call_safe_returns_error_on_connection_error() -> None:
    """_call_safe should return error dict on connection failure."""
    from nuzantara_mcp.server import _call_safe

    mock_client = AsyncMock()
    mock_client.request.side_effect = httpx.RequestError("Connection refused")
    mock_client.is_closed = False

    with patch("nuzantara_mcp.server._http_client", mock_client):
        result = await _call_safe("/unreachable")

    assert result["error"] is True
    assert result["status"] == 0
    assert "Connection error" in result["detail"]
