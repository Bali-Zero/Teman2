"""Regression tests for streaming through the API-to-RAG proxy."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import Request

from backend.app import rag_proxy


def _request(path: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"last_event_id=cursor-1",
        "headers": [
            (b"authorization", b"Bearer test-token"),
            (b"last-event-id", b"cursor-1"),
        ],
        "client": ("203.0.113.5", 1234),
        "scheme": "https",
        "server": ("kita.balizero.com", 443),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive=receive)


class PausedEventStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.closed = False

    async def __aiter__(self):
        yield b"event: goal\ndata: first\n\n"
        await self.release.wait()
        yield b"event: goal\ndata: second\n\n"

    async def aclose(self) -> None:
        self.closed = True


class JsonStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = False

    async def __aiter__(self):
        yield b'{"ok":true}'

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_champion_sse_yields_before_upstream_closes(monkeypatch):
    upstream = PausedEventStream()
    captured: dict[str, str] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["query"] = request.url.query.decode()
        captured["authorization"] = request.headers["authorization"]
        captured["last-event-id"] = request.headers["last-event-id"]
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream", "x-rag-test": "forwarded"},
            stream=upstream,
        )

    client = httpx.AsyncClient(
        base_url="http://rag.internal:8080", transport=httpx.MockTransport(handle)
    )

    async def get_client() -> httpx.AsyncClient:
        return client

    monkeypatch.setattr(rag_proxy, "get_proxy_client", get_client)
    try:
        response = await asyncio.wait_for(
            rag_proxy.proxy_request(_request("/api/dashboard/portal-challenge/events")),
            timeout=1.0,
        )
        assert response.status_code == 200
        assert response.headers["x-rag-test"] == "forwarded"
        iterator = response.body_iterator
        assert (
            await asyncio.wait_for(anext(iterator), timeout=1.0) == b"event: goal\ndata: first\n\n"
        )
        assert upstream.closed is False
        assert captured == {
            "path": "/api/dashboard/portal-challenge/events",
            "query": "last_event_id=cursor-1",
            "authorization": "Bearer test-token",
            "last-event-id": "cursor-1",
        }
        upstream.release.set()
        assert (
            await asyncio.wait_for(anext(iterator), timeout=1.0) == b"event: goal\ndata: second\n\n"
        )
        with pytest.raises(StopAsyncIteration):
            await anext(iterator)
        assert upstream.closed is True
    finally:
        upstream.release.set()
        await client.aclose()


@pytest.mark.asyncio
async def test_champion_sse_disconnect_closes_upstream(monkeypatch):
    upstream = PausedEventStream()

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=upstream)

    client = httpx.AsyncClient(
        base_url="http://rag.internal:8080", transport=httpx.MockTransport(handle)
    )

    async def get_client() -> httpx.AsyncClient:
        return client

    monkeypatch.setattr(rag_proxy, "get_proxy_client", get_client)
    try:
        response = await rag_proxy.proxy_request(_request("/api/dashboard/portal-challenge/events"))
        iterator = response.body_iterator
        assert await anext(iterator) == b"event: goal\ndata: first\n\n"
        await iterator.aclose()
        assert upstream.closed is True
    finally:
        upstream.release.set()
        await client.aclose()


@pytest.mark.asyncio
async def test_champion_sse_disconnect_before_first_chunk_closes_upstream(monkeypatch):
    upstream = PausedEventStream()

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=upstream)

    client = httpx.AsyncClient(
        base_url="http://rag.internal:8080", transport=httpx.MockTransport(handle)
    )

    async def get_client() -> httpx.AsyncClient:
        return client

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message):
        pass

    monkeypatch.setattr(rag_proxy, "get_proxy_client", get_client)
    try:
        request = _request("/api/dashboard/portal-challenge/events")
        response = await rag_proxy.proxy_request(request)
        await asyncio.wait_for(response(request.scope, receive, send), timeout=1.0)
        assert upstream.closed is True
    finally:
        upstream.release.set()
        await client.aclose()


@pytest.mark.asyncio
async def test_json_proxy_keeps_status_headers_and_body(monkeypatch):
    upstream = JsonStream()

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            headers={"content-type": "application/json", "x-rag-test": "forwarded"},
            stream=upstream,
        )

    client = httpx.AsyncClient(
        base_url="http://rag.internal:8080", transport=httpx.MockTransport(handle)
    )

    async def get_client() -> httpx.AsyncClient:
        return client

    monkeypatch.setattr(rag_proxy, "get_proxy_client", get_client)
    try:
        response = await rag_proxy.proxy_request(_request("/api/dashboard/summary"))
        assert response.status_code == 201
        assert response.headers["x-rag-test"] == "forwarded"
        assert response.body == b'{"ok":true}'
        assert upstream.closed is True
    finally:
        await client.aclose()
