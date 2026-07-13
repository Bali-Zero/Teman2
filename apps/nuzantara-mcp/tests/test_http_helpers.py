"""Unit tests for server HTTP helper functions (_call, _call_safe)."""

from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest


def test_headers_scope_debug_key_to_admin_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """X-Debug-Key is only sent on explicit admin calls."""
    from nuzantara_mcp import server

    monkeypatch.setattr(server, "API_KEY", "service-key")
    monkeypatch.setattr(server, "ADMIN_API_KEY", "admin-key")

    standard_headers = server._headers()
    admin_headers = server._headers(admin=True)

    assert standard_headers["X-API-Key"] == "service-key"
    assert "X-Debug-Key" not in standard_headers
    assert admin_headers["X-API-Key"] == "service-key"
    assert admin_headers["X-Debug-Key"] == "admin-key"


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


def test_secret_from_env_file_reads_named_var(tmp_path) -> None:
    """Fallback reads the exact var from a secrets env file (export-prefixed too)."""
    from nuzantara_mcp.server import _secret_from_env_file

    env_file = tmp_path / "secrets.env"
    env_file.write_text(
        "# comment\n"
        "export OTHER_KEY=zzz\n"
        'NUZANTARA_API_KEY="file-key"\n'
    )

    assert _secret_from_env_file("NUZANTARA_API_KEY", env_file) == "file-key"


def test_secret_from_env_file_name_is_anchored(tmp_path) -> None:
    """A var whose name merely prefixes the requested one must not match (family #3)."""
    from nuzantara_mcp.server import _secret_from_env_file

    env_file = tmp_path / "secrets.env"
    env_file.write_text("NUZANTARA_API_KEY_OLD=stale\n")

    assert _secret_from_env_file("NUZANTARA_API_KEY", env_file) == ""


def test_secret_from_env_file_missing_file_is_empty(tmp_path) -> None:
    """Absent/unreadable file -> '' (fail-safe: identical to no fallback)."""
    from nuzantara_mcp.server import _secret_from_env_file

    assert _secret_from_env_file("NUZANTARA_API_KEY", tmp_path / "absent.env") == ""
