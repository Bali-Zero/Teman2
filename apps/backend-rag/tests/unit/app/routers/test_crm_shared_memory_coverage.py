import importlib.util
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


class _DummyConn:
    def __init__(self, fetch_results=None, fetchrow_results=None, fetch_error=None):
        self.fetch_results = list(fetch_results or [])
        self.fetchrow_results = list(fetchrow_results or [])
        self.fetch_error = fetch_error

    async def fetch(self, _query, *args):
        if self.fetch_error:
            raise self.fetch_error
        if self.fetch_results:
            return self.fetch_results.pop(0)
        return []

    async def fetchrow(self, _query, *args):
        if self.fetch_error:
            raise self.fetch_error
        if self.fetchrow_results:
            return self.fetchrow_results.pop(0)
        return None


class _AcquireCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyPool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _AcquireCtx(self.conn)


def _load_module(monkeypatch):
    def cached(ttl, prefix):
        def decorator(fn):
            return fn

        return decorator

    def handle_database_error(err):
        return HTTPException(status_code=500, detail=f"db:{err}")

    class _Logger:
        def info(self, *_args, **_kwargs):
            pass

        def warning(self, *_args, **_kwargs):
            pass

        def error(self, *_args, **_kwargs):
            pass

    monkeypatch.setitem(sys.modules, "core.cache", types.SimpleNamespace(cached=cached))
    monkeypatch.setitem(
        sys.modules,
        "app.utils.error_handlers",
        types.SimpleNamespace(handle_database_error=handle_database_error),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.utils.logging_utils",
        types.SimpleNamespace(get_logger=lambda _name: _Logger()),
    )
    monkeypatch.setitem(
        sys.modules, "app.dependencies", types.SimpleNamespace(get_database_pool=lambda: None)
    )

    backend_path = Path(__file__).resolve().parents[4] / "backend"
    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.crm_shared_memory"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "crm_shared_memory.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_client(module, pool):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_database_pool] = lambda: pool
    return TestClient(app)


@pytest.mark.asyncio
async def test_get_practice_codes_success(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(fetch_results=[[{"code": "KITAS"}, {"code": "PT_PMA"}]])
    result = await module._get_practice_codes(conn)
    assert result == ["KITAS", "PT_PMA"]


@pytest.mark.asyncio
async def test_get_practice_codes_failure(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(fetch_error=RuntimeError("db"))
    result = await module._get_practice_codes(conn)
    assert result == []


def test_search_renewal_query(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(
        fetch_results=[
            [{"practice_id": 1, "practice_code": "KITAS"}],
            [],
        ]
    )
    client = _make_client(module, _DummyPool(conn))

    response = client.get("/api/crm/shared-memory/search", params={"q": "renewal soon"})

    assert response.status_code == 200
    data = response.json()
    assert data["practices"]
    assert data["summary"]["practices_found"] == 1


def test_search_client_query(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(
        fetch_results=[
            [{"id": 1, "full_name": "John Smith"}],
            [{"id": 10, "status": "completed"}],
            [],
        ]
    )
    client = _make_client(module, _DummyPool(conn))

    response = client.get("/api/crm/shared-memory/search", params={"q": "John Smith"})

    assert response.status_code == 200
    data = response.json()
    assert data["clients"]
    assert data["practices"]


def test_search_practice_type_query(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(
        fetch_results=[
            [{"code": "KITAS"}],
            [{"id": 2, "status": "in_progress"}],
        ]
    )
    client = _make_client(module, _DummyPool(conn))

    response = client.get("/api/crm/shared-memory/search", params={"q": "kitas active"})

    assert response.status_code == 200
    data = response.json()
    assert data["practices"]


def test_search_urgent_query(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(
        fetch_results=[
            [],
            [{"id": 3, "priority": "urgent"}],
        ]
    )
    client = _make_client(module, _DummyPool(conn))

    response = client.get("/api/crm/shared-memory/search", params={"q": "urgent"})

    assert response.status_code == 200
    data = response.json()
    assert data["practices"]


def test_search_recent_interactions(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(
        fetch_results=[
            [],
            [{"id": 1, "interaction_type": "call"}],
        ]
    )
    client = _make_client(module, _DummyPool(conn))

    response = client.get(
        "/api/crm/shared-memory/search", params={"q": "recent interactions today"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["interactions"]


def test_search_database_error(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(fetch_error=RuntimeError("boom"))
    client = _make_client(module, _DummyPool(conn))

    response = client.get("/api/crm/shared-memory/search", params={"q": "renewal"})

    assert response.status_code == 500
    assert "db:boom" in response.json()["detail"]


def test_get_upcoming_renewals(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(fetch_results=[[{"practice_id": 1}]])
    client = _make_client(module, _DummyPool(conn))

    response = client.get("/api/crm/shared-memory/upcoming-renewals")

    assert response.status_code == 200
    assert response.json()["total_renewals"] == 1


def test_get_client_full_context(monkeypatch):
    module = _load_module(monkeypatch)
    client_row = {
        "id": 1,
        "full_name": "Client",
        "first_contact_date": None,
        "last_interaction_date": None,
    }
    practices = [
        {"status": "completed"},
        {"status": "in_progress"},
    ]
    interactions = [{"action_items": ["a", "b"]}]
    renewals = [{"id": 1}]
    conn = _DummyConn(
        fetchrow_results=[client_row],
        fetch_results=[practices, interactions, renewals],
    )
    client = _make_client(module, _DummyPool(conn))

    response = client.get("/api/crm/shared-memory/client/1/full-context")

    assert response.status_code == 200
    data = response.json()
    assert data["practices"]["total"] == 2
    assert data["practices"]["completed"] == 1
    assert data["action_items"] == ["a", "b"]


def test_get_client_full_context_not_found(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(fetchrow_results=[None])
    client = _make_client(module, _DummyPool(conn))

    response = client.get("/api/crm/shared-memory/client/1/full-context")

    assert response.status_code == 404


def test_get_team_overview(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(
        fetchrow_results=[{"count": 5}, {"count": 2}, {"count": 3}],
        fetch_results=[
            [{"status": "completed", "count": 1}],
            [{"assigned_to": "A", "count": 2}],
            [{"code": "KITAS", "name": "KITAS", "count": 2}],
        ],
    )
    client = _make_client(module, _DummyPool(conn))

    response = client.get("/api/crm/shared-memory/team-overview")

    assert response.status_code == 200
    data = response.json()
    assert data["total_active_clients"] == 5
    assert data["renewals_next_30_days"] == 2
    assert data["interactions_last_7_days"] == 3
