import importlib.util
import sys
import types
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_module(monkeypatch, service=None):
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    async def get_database_pool():
        return None

    async def get_current_user():
        return {"email": "user@example.com"}

    if service is None:

        class _Service:
            def __init__(self, pool=None):
                self.pool = pool

            async def add_contribution(self, **_kwargs):
                return {"status": "recorded"}

            async def refute_fact(self, **_kwargs):
                return {"status": "refuted"}

            async def get_collective_context(self, **_kwargs):
                return [{"id": 1}]

            async def get_stats(self):
                return {"total": 1}

        service = _Service

    monkeypatch.setitem(
        sys.modules,
        "backend.app.dependencies",
        types.SimpleNamespace(get_database_pool=get_database_pool, redis_url='redis://localhost:6379'),
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.app.routers.auth",
        types.SimpleNamespace(get_current_user=get_current_user, redis_url='redis://localhost:6379'),
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.services.memory.collective_memory_service",
        types.SimpleNamespace(CollectiveMemoryService=service, redis_url='redis://localhost:6379'),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("backend.app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "backend.app.routers", routers_pkg)

    module_name = "backend.app.routers.collective_memory"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "collective_memory.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_client(module):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_db_pool] = lambda: None
    app.dependency_overrides[module.get_current_user] = lambda: {"email": "user@example.com"}
    return TestClient(app)


def test_contribute_fact_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.post(
        "/api/collective-memory/contribute",
        json={"content": "fact", "category": "general"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Fact recorded"


def test_contribute_fact_error(monkeypatch):
    class _Service:
        def __init__(self, pool=None):
            self.pool = pool

        async def add_contribution(self, **_kwargs):
            raise RuntimeError("fail")

    module = _load_module(monkeypatch, service=_Service)
    client = _make_client(module)

    response = client.post(
        "/api/collective-memory/contribute",
        json={"content": "fact", "category": "general"},
    )

    assert response.status_code == 500
    assert "fail" in response.json()["detail"]


def test_refute_fact_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.post("/api/collective-memory/refute", json={"memory_id": 1})

    assert response.status_code == 200
    assert response.json()["message"] == "Fact refuted"


def test_refute_fact_error(monkeypatch):
    class _Service:
        def __init__(self, pool=None):
            self.pool = pool

        async def refute_fact(self, **_kwargs):
            raise RuntimeError("refute fail")

    module = _load_module(monkeypatch, service=_Service)
    client = _make_client(module)

    response = client.post("/api/collective-memory/refute", json={"memory_id": 1})

    assert response.status_code == 500
    assert "refute fail" in response.json()["detail"]


def test_get_collective_facts_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/api/collective-memory/facts?category=general")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1


def test_get_collective_facts_error(monkeypatch):
    class _Service:
        def __init__(self, pool=None):
            self.pool = pool

        async def get_collective_context(self, **_kwargs):
            raise RuntimeError("facts fail")

    module = _load_module(monkeypatch, service=_Service)
    client = _make_client(module)

    response = client.get("/api/collective-memory/facts")

    assert response.status_code == 500
    assert "facts fail" in response.json()["detail"]


def test_get_collective_stats_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/api/collective-memory/stats")

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1


def test_get_collective_stats_error(monkeypatch):
    class _Service:
        def __init__(self, pool=None):
            self.pool = pool

        async def get_stats(self):
            raise RuntimeError("stats fail")

    module = _load_module(monkeypatch, service=_Service)
    client = _make_client(module)

    response = client.get("/api/collective-memory/stats")

    assert response.status_code == 500
    assert "stats fail" in response.json()["detail"]
