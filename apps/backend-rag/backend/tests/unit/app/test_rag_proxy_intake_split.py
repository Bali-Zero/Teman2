"""Unit tests for the intake-review proxy split (Fix #1, Part B).

These exercise `backend.app.rag_proxy`:
  1. /api/intake/review/queue routes to the intake target (NOT the RAG client).
  2. /api/intake/review-metrics does NOT (exact-boundary, Codex P0#3).
  3. /api/intake/gate does NOT route to the intake target (stays on the api/rag path).
  4. intake target unreachable → explicit 503 JSONResponse (NOT 200/raw upstream error,
     NOT a 300s hang) — Codex P0#4 / Gemini P0.
  5. INTAKE_REVIEW_WORKER_URL unset → falls back to RAG_WORKER_URL (inert change).

No real network: the intake client is monkeypatched with an httpx.MockTransport, and the
RAG fallback path is monkeypatched to a sentinel so we can assert *which* target was used.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from backend.app import rag_proxy

pytestmark = pytest.mark.asyncio


def _make_request(path: str, *, method: str = "GET", query: str = "") -> Request:
    """Build a minimal Starlette Request for the given path."""
    raw_headers = [(b"host", b"kita.balizero.com"), (b"authorization", b"Bearer fake.jwt.token")]
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "headers": raw_headers,
        "client": ("203.0.113.5", 1234),
        "scheme": "https",
        "server": ("kita.balizero.com", 443),
    }

    async def _receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive=_receive)


# --------------------------------------------------------------------------- #
# 1/2/3 — routing predicate (exact boundary)
# --------------------------------------------------------------------------- #


def test_intake_review_exact_boundary():
    assert rag_proxy.is_intake_review_route("/api/intake/review") is True
    assert rag_proxy.is_intake_review_route("/api/intake/review/queue") is True
    assert rag_proxy.is_intake_review_route("/api/intake/review/42/claim") is True
    # P0#3: a sibling prefix must NOT be captured.
    assert rag_proxy.is_intake_review_route("/api/intake/review-metrics") is False
    assert rag_proxy.is_intake_review_route("/api/intake/reviewer") is False
    # /api/intake/gate is not an intake-review route (and not heavy at all).
    assert rag_proxy.is_intake_review_route("/api/intake/gate") is False
    assert rag_proxy.is_heavy_route("/api/intake/gate") is False


async def test_queue_routes_to_intake_target(monkeypatch):
    """/api/intake/review/queue → intake client; RAG fallback NOT used."""
    monkeypatch.setenv("INTAKE_REVIEW_WORKER_URL", "https://intake-review.balizero.com")

    captured: dict[str, str] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"total": 12, "items": []})

    intake_client = httpx.AsyncClient(
        base_url="https://intake-review.balizero.com",
        transport=httpx.MockTransport(_handler),
    )
    monkeypatch.setattr(rag_proxy, "_intake_client", intake_client)

    async def _boom_rag(_request):  # RAG path must NOT be taken
        raise AssertionError("RAG fallback was used for an intake-review route")

    monkeypatch.setattr(rag_proxy, "proxy_request", _boom_rag)

    resp = await rag_proxy.proxy_intake_review_request(_make_request("/api/intake/review/queue"))
    await intake_client.aclose()

    assert isinstance(resp, Response)
    assert resp.status_code == 200
    assert "/api/intake/review/queue" in captured["url"]
    assert captured["url"].startswith("https://intake-review.balizero.com/")


async def test_metrics_sibling_not_routed_to_intake(monkeypatch):
    """The dispatcher only calls the intake proxy for the exact boundary."""
    monkeypatch.setenv("INTAKE_REVIEW_WORKER_URL", "https://intake-review.balizero.com")

    intake_called = {"v": False}
    rag_called = {"v": False}

    async def _fake_intake(_request):
        intake_called["v"] = True
        return JSONResponse(status_code=200, content={"ok": True})

    async def _fake_rag(_request):
        rag_called["v"] = True
        return Response(status_code=200, content=b"{}", media_type="application/json")

    monkeypatch.setattr(rag_proxy, "proxy_intake_review_request", _fake_intake)
    monkeypatch.setattr(rag_proxy, "proxy_request", _fake_rag)

    router = rag_proxy.create_proxy_router()
    endpoint = router.routes[0].endpoint  # the catch-all

    # review-metrics is a HEAVY route (starts with /api/intake/review) but NOT the exact
    # intake boundary → must go to the RAG path, not the intake tunnel.
    await endpoint(_make_request("/api/intake/review-metrics"), full_path="api/intake/review-metrics")
    assert intake_called["v"] is False
    assert rag_called["v"] is True


async def test_gate_not_routed_to_intake(monkeypatch):
    """/api/intake/gate is not heavy → 404 from proxy, never the intake tunnel."""
    monkeypatch.setenv("INTAKE_REVIEW_WORKER_URL", "https://intake-review.balizero.com")

    async def _boom_intake(_request):
        raise AssertionError("intake tunnel used for /api/intake/gate")

    async def _boom_rag(_request):
        raise AssertionError("RAG used for /api/intake/gate")

    monkeypatch.setattr(rag_proxy, "proxy_intake_review_request", _boom_intake)
    monkeypatch.setattr(rag_proxy, "proxy_request", _boom_rag)

    router = rag_proxy.create_proxy_router()
    endpoint = router.routes[0].endpoint
    resp = await endpoint(_make_request("/api/intake/gate"), full_path="api/intake/gate")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# 4 — unreachable → 503 (not 200, not raw error, not a hang)
# --------------------------------------------------------------------------- #


async def test_intake_unreachable_returns_503(monkeypatch):
    monkeypatch.setenv("INTAKE_REVIEW_WORKER_URL", "https://intake-review.balizero.com")

    def _refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    intake_client = httpx.AsyncClient(
        base_url="https://intake-review.balizero.com",
        transport=httpx.MockTransport(_refuse),
    )
    monkeypatch.setattr(rag_proxy, "_intake_client", intake_client)

    resp = await rag_proxy.proxy_intake_review_request(_make_request("/api/intake/review/queue"))
    await intake_client.aclose()

    assert resp.status_code == 503
    assert b"intake review reader offline" in bytes(resp.body)


async def test_intake_upstream_5xx_mapped_to_503(monkeypatch):
    """A Cloudflare/tunnel-level 502/503/504 is normalised to our 503 'offline'."""
    monkeypatch.setenv("INTAKE_REVIEW_WORKER_URL", "https://intake-review.balizero.com")

    def _bad_gateway(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="cloudflare bad gateway")

    intake_client = httpx.AsyncClient(
        base_url="https://intake-review.balizero.com",
        transport=httpx.MockTransport(_bad_gateway),
    )
    monkeypatch.setattr(rag_proxy, "_intake_client", intake_client)

    resp = await rag_proxy.proxy_intake_review_request(_make_request("/api/intake/review/queue"))
    await intake_client.aclose()

    assert resp.status_code == 503
    assert b"intake review reader offline" in bytes(resp.body)


async def test_intake_tight_timeout_configured(monkeypatch):
    """The intake client fail-fasts on CONNECT (<=3s, the Pro-offline guard) and bounds READ
    well under the 300s RAG timeout. Read is 30s — enough for the detail/blob round-trip over
    the Pro's mobile tunnel (a 5s read budget mapped every detail open to a spurious 503)."""
    monkeypatch.setenv("INTAKE_REVIEW_WORKER_URL", "https://intake-review.balizero.com")
    # Force a fresh client to pick up the env-derived base_url.
    monkeypatch.setattr(rag_proxy, "_intake_client", None)
    client = await rag_proxy.get_intake_client()
    try:
        assert client.timeout.connect is not None and client.timeout.connect <= 3.0
        assert client.timeout.read is not None and client.timeout.read <= 30.0
    finally:
        await client.aclose()
        rag_proxy._intake_client = None


# --------------------------------------------------------------------------- #
# 5 — unset → fall back to RAG
# --------------------------------------------------------------------------- #


async def test_unset_falls_back_to_rag(monkeypatch):
    monkeypatch.delenv("INTAKE_REVIEW_WORKER_URL", raising=False)
    assert rag_proxy.get_intake_review_worker_url() is None

    rag_called = {"v": False}

    async def _fake_rag(_request):
        rag_called["v"] = True
        return Response(status_code=200, content=b'{"via":"rag"}', media_type="application/json")

    monkeypatch.setattr(rag_proxy, "proxy_request", _fake_rag)

    # Direct call to the intake proxy with no URL configured → defers to RAG.
    resp = await rag_proxy.proxy_intake_review_request(_make_request("/api/intake/review/queue"))
    assert rag_called["v"] is True
    assert resp.status_code == 200

    # And the dispatcher itself does not even enter the intake branch when unset.
    rag_called["v"] = False
    monkeypatch.setattr(rag_proxy, "is_heavy_route", lambda _p: True)
    router = rag_proxy.create_proxy_router()
    endpoint = router.routes[0].endpoint
    await endpoint(_make_request("/api/intake/review/queue"), full_path="api/intake/review/queue")
    assert rag_called["v"] is True


async def test_empty_env_treated_as_unset(monkeypatch):
    monkeypatch.setenv("INTAKE_REVIEW_WORKER_URL", "   ")
    assert rag_proxy.get_intake_review_worker_url() is None
