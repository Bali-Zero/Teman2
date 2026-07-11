"""
Regression tests for backend/app/routers/kg_agentic.py.

Live prod 500 (this session):
  'KGEnhancedRetrieval' object has no attribute '_load_golden_routes'

Both GET /api/kg/routes and GET /api/kg/stats called
`orchestrator.kg_retrieval._load_golden_routes()`, a method that does not
exist on KGEnhancedRetrieval. The real, always-available source of golden
routes is the `GOLDEN_ROUTES` class attribute (dict[str, GoldenRoute]).

These tests call the router handler functions directly (bypassing FastAPI's
dependency injection, which only resolves `Depends(...)` when invoked through
an app) with a minimal fake orchestrator exposing `.kg_retrieval` as a real
`KGEnhancedRetrieval` instance. No live DB/network is required for the
/routes endpoint. The /stats endpoint additionally needs a fake db_pool since
it queries kg_nodes/kg_edges counts.
"""

from __future__ import annotations

import pytest

from backend.app.routers import kg_agentic
from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval


class _FakeOrchestrator:
    """Minimal stand-in exposing only what the /routes handler touches."""

    def __init__(self, db_pool: object | None = None) -> None:
        self.kg_retrieval = KGEnhancedRetrieval(db_pool=object())
        self.db_pool = db_pool


class _Acquire:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self.conn

    async def __aexit__(self, *exc_info) -> None:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self.conn)


class _FakeConn:
    """Serves canned rows for the 3 fetch/fetchrow calls kg_stats() makes."""

    def __init__(self) -> None:
        self.fetch_calls: list[str] = []

    async def fetchrow(self, sql: str, *args):
        return {"total_nodes": 10, "total_edges": 5}

    async def fetch(self, sql: str, *args):
        self.fetch_calls.append(sql)
        if "kg_nodes" in sql:
            return [{"entity_type": "kbli", "count": 7}]
        return [{"relationship_type": "requires", "count": 3}]


class _FakeKGCache:
    async def get_stats(self) -> dict | None:
        return None

    async def set_stats(self, stats: dict) -> None:
        return None


@pytest.mark.asyncio
async def test_list_golden_routes_does_not_raise_attribute_error() -> None:
    """
    Guilt: with the buggy `_load_golden_routes()` call-site this raises
    AttributeError (surfaced by the router as HTTP 500), reproducing the
    live prod error verbatim.
    Innocence: with the fix, it returns a non-empty list of GoldenRouteInfo
    built from the real GOLDEN_ROUTES mapping.
    """
    orchestrator = _FakeOrchestrator()

    result = await kg_agentic.list_golden_routes(orchestrator=orchestrator)

    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(r, kg_agentic.GoldenRouteInfo) for r in result)
    route_ids = {r.route_id for r in result}
    assert "pt_pma_setup" in route_ids


@pytest.mark.asyncio
async def test_kg_stats_does_not_raise_attribute_error(monkeypatch) -> None:
    """
    W89 sibling call-site: GET /api/kg/stats hit the exact same
    AttributeError as /routes ('KGEnhancedRetrieval' object has no attribute
    '_load_golden_routes') while counting golden routes for
    golden_routes_available. Same fix (GOLDEN_ROUTES attribute), same
    verification shape: no live DB/redis required — db_pool and the kg
    stats cache are faked.
    """
    monkeypatch.setattr(kg_agentic, "get_kg_cache", lambda: _FakeKGCache(), raising=False)
    import backend.services.rag.kg_cache as kg_cache_module

    monkeypatch.setattr(kg_cache_module, "get_kg_cache", lambda: _FakeKGCache())

    conn = _FakeConn()
    orchestrator = _FakeOrchestrator(db_pool=_FakePool(conn))

    result = await kg_agentic.kg_stats(orchestrator=orchestrator)

    assert result.total_nodes == 10
    assert result.total_edges == 5
    assert result.golden_routes_available > 0
    assert result.golden_routes_available == len(orchestrator.kg_retrieval.GOLDEN_ROUTES)
