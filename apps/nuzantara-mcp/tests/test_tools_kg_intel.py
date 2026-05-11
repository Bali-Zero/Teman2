"""Tests for kg_intel tool (Bridge A: Pro MCP -> Mini KG)."""
from __future__ import annotations

import os
from typing import Any, Awaitable, Callable

import httpx
import pytest

from nuzantara_mcp.tools import kg_intel


class _FakeMCP:
    """Minimal stand-in for FastMCP capturing decorated tools."""

    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., Awaitable[Any]]] = {}

    def tool(self):  # noqa: D401
        def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            self.tools[func.__name__] = func
            return func
        return decorator


@pytest.fixture
def admin_role(monkeypatch: pytest.MonkeyPatch):
    """Set AGENT_ROLE=admin so the @require_role gate allows calls."""
    monkeypatch.setenv("AGENT_ROLE", "admin")
    yield


@pytest.fixture
def clear_agent_role(monkeypatch: pytest.MonkeyPatch):
    """Ensure AGENT_ROLE is unset so caller is 'unknown'."""
    monkeypatch.delenv("AGENT_ROLE", raising=False)
    yield


@pytest.fixture
def mock_kg_routes(monkeypatch: pytest.MonkeyPatch):
    """Inject httpx.MockTransport into kg_intel; return the routes dict so tests can populate it."""
    routes: dict[str, tuple[int, dict]] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        target = str(request.url.path)
        if request.url.query:
            target += "?" + request.url.query.decode("ascii")
        for key, (status, body) in routes.items():
            if key in target:
                return httpx.Response(status, json=body)
        return httpx.Response(500, json={"error": "no_route", "path": target})

    monkeypatch.setattr(kg_intel, "_TRANSPORT_OVERRIDE", httpx.MockTransport(respond), raising=False)
    monkeypatch.setattr(kg_intel, "_client", None, raising=False)
    yield routes


@pytest.fixture
def registered(mock_kg_routes, admin_role) -> tuple[_FakeMCP, dict[str, tuple[int, dict]]]:
    """Register kg_intel against a fake MCP with admin role + mock transport."""
    fake = _FakeMCP()
    kg_intel.register(fake, _call=None, _call_safe=None)
    return fake, mock_kg_routes


@pytest.mark.asyncio
async def test_p1_kg_intel_search_returns_results(registered) -> None:
    """P1: search returns dict with 'results' list."""
    fake, routes = registered
    routes["/kg/search"] = (200, {
        "query": "imigrasi", "limit": 20,
        "results": [{"name": "Imigrasi", "type": "organizations", "source_count": 17, "last_seen": "2026-04-30T12:14:09+00:00"}],
    })
    out = await fake.tools["kg_intel_search"]("imigrasi")
    assert isinstance(out, dict)
    assert out["results"][0]["name"] == "Imigrasi"


@pytest.mark.asyncio
async def test_p2_kg_intel_entity(registered) -> None:
    """P2: entity returns parsed entity record."""
    fake, routes = registered
    routes["/kg/entity/"] = (200, {
        "name": "Imigrasi", "type": "organizations", "source_count": 17,
        "first_seen": "2026-03-12T08:11:02+00:00", "last_seen": "2026-04-30T12:14:09+00:00",
        "neighbor_names": [], "observation_count": 0, "observations": [],
    })
    out = await fake.tools["kg_intel_entity"]("Imigrasi", "organizations")
    assert out["name"] == "Imigrasi"
    assert out["type"] == "organizations"


@pytest.mark.asyncio
async def test_p3_kg_intel_health(registered) -> None:
    """P3: health returns counts."""
    fake, routes = registered
    routes["/health"] = (200, {"ok": True, "entities_count": 409, "relations_count": 1549, "observations_count": 622, "schema_ok": True, "kg_path": "/x"})
    out = await fake.tools["kg_intel_health"]()
    assert out["ok"] is True
    assert out["entities_count"] == 409


@pytest.mark.asyncio
async def test_p4_connect_error_graceful(monkeypatch: pytest.MonkeyPatch, admin_role) -> None:
    """P4: ConnectError returns kg_unavailable dict, no raise."""
    def fail(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Tailscale flap")

    monkeypatch.setattr(kg_intel, "_TRANSPORT_OVERRIDE", httpx.MockTransport(fail), raising=False)
    monkeypatch.setattr(kg_intel, "_client", None, raising=False)
    fake = _FakeMCP()
    kg_intel.register(fake, _call=None, _call_safe=None)

    out = await fake.tools["kg_intel_search"]("imigrasi")
    assert out["error"] == "kg_unavailable"


@pytest.mark.asyncio
async def test_p5_timeout_graceful(monkeypatch: pytest.MonkeyPatch, admin_role) -> None:
    """P5: TimeoutException returns kg_unavailable dict."""
    def slow(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(kg_intel, "_TRANSPORT_OVERRIDE", httpx.MockTransport(slow), raising=False)
    monkeypatch.setattr(kg_intel, "_client", None, raising=False)
    fake = _FakeMCP()
    kg_intel.register(fake, _call=None, _call_safe=None)

    out = await fake.tools["kg_intel_health"]()
    assert out["error"] == "kg_unavailable"


@pytest.mark.asyncio
async def test_p6_404_entity_not_found(registered) -> None:
    """P6: HTTP 404 returns entity_not_found error dict."""
    fake, routes = registered
    routes["/kg/entity/"] = (404, {"error": "entity_not_found", "detail": "no such entity"})
    out = await fake.tools["kg_intel_entity"]("Zaphod", "persons")
    assert out["error"] == "entity_not_found"


@pytest.mark.asyncio
async def test_p7_register_denies_non_admin(monkeypatch: pytest.MonkeyPatch, clear_agent_role) -> None:
    """P7: each registered tool denies non-admin role via MCPAccessDenied."""
    from nuzantara_mcp.auth import MCPAccessDenied

    monkeypatch.setattr(kg_intel, "_client", None, raising=False)
    fake = _FakeMCP()
    kg_intel.register(fake, _call=None, _call_safe=None)

    # AGENT_ROLE unset -> caller is "unknown" -> all admin-only tools deny.
    with pytest.raises(MCPAccessDenied):
        await fake.tools["kg_intel_health"]()
    with pytest.raises(MCPAccessDenied):
        await fake.tools["kg_intel_search"]("x")
    with pytest.raises(MCPAccessDenied):
        await fake.tools["kg_intel_entity"]("x", "persons")


def test_p8_module_importable() -> None:
    """P8: regression: kg_intel module imports successfully."""
    import importlib

    importlib.import_module("nuzantara_mcp.tools.kg_intel")
