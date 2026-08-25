"""BackendClient tests — every case goes through httpx.MockTransport, never
a real socket (B6 law)."""

from __future__ import annotations

import httpx
import pytest

from team_bot.executor.http_client import (
    BACKEND_BASE_URL_ENV_VAR,
    BackendClient,
    BackendClientConfig,
)

from ._fakes import fake_transport, json_response, network_error, timeout


@pytest.mark.asyncio
async def test_get_returns_parsed_json_body_on_200() -> None:
    transport = fake_transport(json_response(200, {"a": 1}))
    client = BackendClient(BackendClientConfig(base_url="http://backend.example"), transport=transport)
    result = await client.get("/x")
    assert result.status_code == 200
    assert result.json_body == {"a": 1}
    assert result.network_error is None
    await client.aclose()


@pytest.mark.asyncio
async def test_get_returns_status_code_with_none_body_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"")

    client = BackendClient(
        BackendClientConfig(base_url="http://backend.example"), transport=fake_transport(handler)
    )
    result = await client.get("/x")
    assert result.status_code == 404
    assert result.json_body is None
    assert result.network_error is None
    await client.aclose()


@pytest.mark.asyncio
async def test_get_returns_none_body_on_non_json_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json at all")

    client = BackendClient(
        BackendClientConfig(base_url="http://backend.example"), transport=fake_transport(handler)
    )
    result = await client.get("/x")
    assert result.status_code == 200
    assert result.json_body is None
    await client.aclose()


@pytest.mark.asyncio
async def test_get_maps_a_read_timeout_to_timeout_network_error() -> None:
    client = BackendClient(
        BackendClientConfig(base_url="http://backend.example"), transport=fake_transport(timeout())
    )
    result = await client.get("/x")
    assert result.status_code is None
    assert result.json_body is None
    assert result.network_error == "timeout"
    await client.aclose()


@pytest.mark.asyncio
async def test_get_maps_a_connect_error_to_network_error() -> None:
    client = BackendClient(
        BackendClientConfig(base_url="http://backend.example"), transport=fake_transport(network_error())
    )
    result = await client.get("/x")
    assert result.status_code is None
    assert result.json_body is None
    assert result.network_error == "network_error"
    await client.aclose()


@pytest.mark.asyncio
async def test_headers_are_forwarded_to_the_request() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"ok": True})

    client = BackendClient(
        BackendClientConfig(base_url="http://backend.example"), transport=fake_transport(handler)
    )
    await client.get("/x", headers={"Authorization": "Bearer secret"})
    assert seen["authorization"] == "Bearer secret"
    await client.aclose()


@pytest.mark.asyncio
async def test_async_context_manager_closes_the_client() -> None:
    async with BackendClient(
        BackendClientConfig(base_url="http://backend.example"),
        transport=fake_transport(json_response(200, {})),
    ) as client:
        result = await client.get("/x")
        assert result.status_code == 200
    # aclose() was called on exit; a second explicit call must not raise.
    await client.aclose()


def test_config_from_env_requires_the_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(BACKEND_BASE_URL_ENV_VAR, raising=False)
    with pytest.raises(RuntimeError, match=BACKEND_BASE_URL_ENV_VAR):
        BackendClientConfig.from_env()


def test_config_from_env_reads_the_configured_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(BACKEND_BASE_URL_ENV_VAR, "https://nuzantara-rag.example")
    config = BackendClientConfig.from_env()
    assert config.base_url == "https://nuzantara-rag.example"
