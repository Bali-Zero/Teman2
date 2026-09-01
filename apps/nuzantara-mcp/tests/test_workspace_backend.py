"""Tests for the minimal, no-admin workspace backend client."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from nuzantara_mcp import workspace_backend


def test_workspace_backend_uses_only_dedicated_route_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("NUZANTARA_API_KEY", "ordinary-private-key")
    monkeypatch.setenv("NUZANTARA_ADMIN_API_KEY", "admin-private-key")
    monkeypatch.setenv("NUZANTARA_WORKSPACE_MARKETING_API_KEY", "workspace-route-key")

    headers = workspace_backend._headers()

    assert headers == {
        "Content-Type": "application/json",
        "X-Workspace-Marketing-Key": "workspace-route-key",
    }
    assert "ordinary-private-key" not in str(headers)
    assert "admin-private-key" not in str(headers)

    monkeypatch.delenv("NUZANTARA_WORKSPACE_MARKETING_API_KEY")
    env_file = tmp_path / "secrets.env"
    env_file.write_text(
        "NUZANTARA_API_KEY=ordinary\n"
        "NUZANTARA_ADMIN_API_KEY=admin\n"
        "NUZANTARA_WORKSPACE_MARKETING_API_KEY=file-workspace-key\n",
        encoding="utf-8",
    )
    assert workspace_backend._workspace_key(env_file) == "file-workspace-key"


@pytest.mark.parametrize(
    "url",
    [
        "http://nuzantara-rag.fly.dev",
        "https://user:pass@nuzantara-rag.fly.dev",
        "https://nuzantara-rag.fly.dev/private",
        "https://nuzantara-rag.fly.dev?token=private",
    ],
)
def test_workspace_backend_requires_plain_https_origin(url: str) -> None:
    with pytest.raises(RuntimeError, match="HTTPS origin"):
        workspace_backend._validated_backend_url(url)

    assert (
        workspace_backend._validated_backend_url("https://nuzantara-rag.fly.dev/")
        == "https://nuzantara-rag.fly.dev"
    )


@pytest.mark.asyncio
async def test_workspace_backend_rejects_non_read_or_non_newsroom_endpoint() -> None:
    with pytest.raises(RuntimeError, match="endpoint is not allowed"):
        await workspace_backend.call(
            "/api/workspace-marketing/news/news_1",
            method="POST",
        )
    with pytest.raises(RuntimeError, match="endpoint is not allowed"):
        await workspace_backend.call(
            "/api/workspace-marketing/news/news_1/publish",
            method="GET",
        )
    with pytest.raises(RuntimeError, match="endpoint is not allowed"):
        await workspace_backend.call("/api/clients", method="GET")
    with pytest.raises(RuntimeError, match="endpoint is not allowed"):
        await workspace_backend.call(
            "/api/workspace-marketing/news/pending",
            method="PUT",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/workspace-marketing/capabilities"),
        ("GET", "/api/workspace-marketing/news/news_1/publication-status"),
        ("PUT", "/api/workspace-marketing/news/news_1/editorial"),
        ("POST", "/api/workspace-marketing/news/news_1/cover"),
        ("POST", "/api/workspace-marketing/news/news_1/confirm-live"),
    ],
)
async def test_workspace_backend_allows_exact_editorial_actions(
    monkeypatch,
    method: str,
    path: str,
) -> None:
    monkeypatch.setenv("NUZANTARA_WORKSPACE_MARKETING_API_KEY", "workspace-route-key")
    request = httpx.Request(method, f"https://nuzantara-rag.fly.dev{path}")
    response = httpx.Response(200, request=request, json={"success": True})

    class FakeClient:
        is_closed = False

        async def request(self, **_kwargs):
            return response

    monkeypatch.setattr(workspace_backend, "_get_client", lambda: FakeClient())

    result = await workspace_backend.call(path, method=method, json={})

    assert result == {"success": True}


@pytest.mark.asyncio
async def test_workspace_backend_allows_only_scoped_publish_post(monkeypatch) -> None:
    monkeypatch.setenv("NUZANTARA_WORKSPACE_MARKETING_API_KEY", "workspace-route-key")
    request = httpx.Request(
        "POST",
        "https://nuzantara-rag.fly.dev/api/workspace-marketing/news/news_1/publish",
    )
    response = httpx.Response(
        200,
        request=request,
        json={"success": True},
    )

    class FakeClient:
        is_closed = False

        def __init__(self) -> None:
            self.request_kwargs = None

        async def request(self, **kwargs):
            self.request_kwargs = kwargs
            return response

    client = FakeClient()
    monkeypatch.setattr(workspace_backend, "_get_client", lambda: client)

    result = await workspace_backend.call(
        "/api/workspace-marketing/news/news_1/publish",
        method="POST",
        json={"confirmation": "DAMAR_CONFIRMED"},
    )

    assert result == {"success": True}
    assert client.request_kwargs["method"] == "POST"
    assert client.request_kwargs["url"].endswith("/news/news_1/publish")
    assert client.request_kwargs["json"] == {"confirmation": "DAMAR_CONFIRMED"}


@pytest.mark.asyncio
async def test_backend_error_never_echoes_response_body(monkeypatch) -> None:
    monkeypatch.setenv("NUZANTARA_WORKSPACE_MARKETING_API_KEY", "workspace-route-key")
    request = httpx.Request("GET", "https://example.invalid/private")
    response = httpx.Response(
        500,
        request=request,
        text="client@example.com passport ABC123456 raw internal body",
    )

    class FakeClient:
        is_closed = False

        async def request(self, **_kwargs):
            return response

    monkeypatch.setattr(workspace_backend, "_get_client", lambda: FakeClient())

    with pytest.raises(RuntimeError) as exc_info:
        await workspace_backend.call("/api/workspace-marketing/news/pending")

    message = str(exc_info.value)
    assert "HTTP 500" in message
    assert "client@example.com" not in message
    assert "ABC123456" not in message


@pytest.mark.asyncio
async def test_backend_invalid_json_is_normalized_without_body_leak(
    monkeypatch,
) -> None:
    monkeypatch.setenv("NUZANTARA_WORKSPACE_MARKETING_API_KEY", "workspace-route-key")
    request = httpx.Request("GET", "https://example.invalid/private")
    response = httpx.Response(
        200,
        request=request,
        text="client@example.com passport ABC123456 invalid payload",
    )

    class FakeClient:
        is_closed = False

        async def request(self, **_kwargs):
            return response

    monkeypatch.setattr(workspace_backend, "_get_client", lambda: FakeClient())

    with pytest.raises(RuntimeError) as exc_info:
        await workspace_backend.call("/api/workspace-marketing/news/pending")

    message = str(exc_info.value)
    assert message == "Nuzantara marketing backend returned invalid JSON"
    assert "client@example.com" not in message
    assert "ABC123456" not in message
