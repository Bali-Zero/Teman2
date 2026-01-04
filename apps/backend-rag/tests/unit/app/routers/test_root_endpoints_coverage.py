import importlib.util
import sys
import types
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


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
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.root_endpoints"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "root_endpoints.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_client(module):
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


def test_root_endpoint(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "ZANTARA RAG Backend Ready"


def test_get_csrf_token(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/api/csrf-token")

    assert response.status_code == 200
    payload = response.json()
    assert payload["csrfToken"] == response.headers["X-CSRF-Token"]
    assert payload["sessionId"] == response.headers["X-Session-Id"]


def test_dashboard_stats_no_db_pool(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/api/dashboard/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["system_health"] == "unknown"
    assert payload["error"] == "Database pool not initialized"


def test_dashboard_stats_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    class _Conn:
        def __init__(self):
            self.values = [5, 42]

        async def fetchval(self, _query):
            return self.values.pop(0)

    client.app.state.db_pool = _DummyPool(_Conn())

    response = client.get("/api/dashboard/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_agents"] == "5"
    assert payload["system_health"] == "99.9%"
    assert payload["knowledge_base"]["vectors"] == "42"


def test_dashboard_stats_error(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    class _Conn:
        async def fetchval(self, _query):
            raise RuntimeError("db down")

    client.app.state.db_pool = _DummyPool(_Conn())

    response = client.get("/api/dashboard/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["system_health"] == "error"
    assert "Failed to retrieve statistics" == payload["error"]
