import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest
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

    def get_min_size(self):
        return 1

    def get_max_size(self):
        return 4

    def get_size(self):
        return 2


def _load_module(monkeypatch, settings_overrides=None):
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    settings_stub = types.SimpleNamespace(
        qdrant_url="http://qdrant.local",
        qdrant_api_key="",
        redis_url='redis://localhost:6379'
    )
    if settings_overrides:
        for key, value in settings_overrides.items():
            setattr(settings_stub, key, value)

    config_mock = types.ModuleType("backend.app.core.config")
    config_mock.settings = settings_stub
    config_mock.Settings = types.SimpleNamespace() # Dummy Settings class
    monkeypatch.setitem(sys.modules, "backend.app.core.config", config_mock)

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("backend.app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "backend.app.routers", routers_pkg)

    module_name = "backend.app.routers.health"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "health.py"
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


class _Response:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("bad status")

    def json(self):
        return self._payload


class _AsyncClient:
    def __init__(self, responses):
        self.responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, path):
        return self.responses[path]


@pytest.mark.asyncio
async def test_get_qdrant_stats_success(monkeypatch):
    module = _load_module(monkeypatch, settings_overrides={"qdrant_api_key": "key"})
    responses = {
        "/collections": _Response({"result": {"collections": [{"name": "c1"}, {"name": "c2"}]}}),
        "/collections/c1": _Response({"result": {"points_count": 3}}),
        "/collections/c2": _Response({"result": {"points_count": 7}}),
    }

    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **_kwargs: _AsyncClient(responses))

    result = await module.get_qdrant_stats()

    assert result["collections"] == 2
    assert result["total_documents"] == 10


@pytest.mark.asyncio
async def test_get_qdrant_stats_skips_failed_collection(monkeypatch):
    module = _load_module(monkeypatch)

    class _FailClient(_AsyncClient):
        async def get(self, path):
            if path == "/collections/bad":
                raise RuntimeError("boom")
            return await super().get(path)

    responses = {
        "/collections": _Response({"result": {"collections": [{"name": "ok"}, {"name": "bad"}]}}),
        "/collections/ok": _Response({"result": {"points_count": 2}}),
    }

    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **_kwargs: _FailClient(responses))

    result = await module.get_qdrant_stats()

    assert result["collections"] == 2
    assert result["total_documents"] == 2


@pytest.mark.asyncio
async def test_get_qdrant_stats_failure(monkeypatch):
    module = _load_module(monkeypatch)

    class _FailClient:
        async def __aenter__(self):
            raise RuntimeError("no connect")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **_kwargs: _FailClient())

    result = await module.get_qdrant_stats()

    assert result["collections"] == 0
    assert result["total_documents"] == 0
    assert "error" in result


def test_health_check_initializing(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "initializing"
    assert payload["database"]["status"] == "initializing"


def test_health_check_healthy(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    class _Embedder:
        provider = "test"
        model = "model"
        dimensions = 3

    class _SearchService:
        embedder = _Embedder()

    client.app.state.search_service = _SearchService()

    async def _stats():
        return {"collections": 1, "total_documents": 5}

    monkeypatch.setattr(module, "get_qdrant_stats", _stats)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["database"]["collections"] == 1
    assert payload["embeddings"]["model"] == "model"


def test_health_check_embedder_attribute_error(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    class _SearchService:
        pass

    client.app.state.search_service = _SearchService()

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "initializing"
    assert payload["embeddings"]["status"] == "loading"


@pytest.mark.asyncio
async def test_health_check_degraded_on_exception(monkeypatch):
    module = _load_module(monkeypatch)

    class _BadApp:
        @property
        def state(self):
            raise RuntimeError("boom")

    class _BadRequest:
        app = _BadApp()

    result = await module.health_check(_BadRequest())

    assert result.status == "degraded"
    assert result.database["status"] == "error"


def test_detailed_health_all_healthy(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    class _Embedder:
        provider = "prov"
        model = "model"

    class _SearchService:
        embedder = _Embedder()

    class _AiClient:
        pass

    class _Conn:
        async def execute(self, _query):
            return None

    class _HealthMonitor:
        def get_status(self):
            return {"ok": True}

    class _Registry:
        def get_status(self):
            return {"count": 1}

    client.app.state.search_service = _SearchService()
    client.app.state.ai_client = _AiClient()
    client.app.state.db_pool = _DummyPool(_Conn())
    client.app.state.memory_service = object()
    client.app.state.intelligent_router = object()
    client.app.state.health_monitor = _HealthMonitor()
    client.app.state.service_registry = _Registry()

    response = client.get("/health/detailed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["services"]["database"]["status"] == "healthy"
    assert payload["registry"]["count"] == 1


def test_detailed_health_critical(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/health/detailed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "critical"
    assert payload["services"]["search"]["status"] == "unavailable"
    assert payload["services"]["ai"]["status"] == "unavailable"


def test_detailed_health_database_error(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    class _BadPool:
        def acquire(self):
            raise RuntimeError("db down")

    client.app.state.db_pool = _BadPool()

    response = client.get("/health/detailed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["services"]["database"]["status"] == "error"
    assert "db down" in payload["services"]["database"]["error"]


def test_readiness_check_not_ready(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["ready"] is False


def test_readiness_check_ready(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)
    client.app.state.search_service = object()
    client.app.state.ai_client = object()
    client.app.state.services_initialized = True

    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True


def test_liveness_check(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/health/live")

    assert response.status_code == 200
    payload = response.json()
    assert payload["alive"] is True


def test_qdrant_metrics_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    monkeypatch.setitem(
        sys.modules,
        "backend.core.qdrant_db",
        types.SimpleNamespace(get_qdrant_metrics=lambda: {"search_count": 1}, redis_url='redis://localhost:6379'),
    )

    response = client.get("/health/metrics/qdrant")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["metrics"]["search_count"] == 1


def test_qdrant_metrics_error(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    def _raise():
        raise RuntimeError("metrics fail")

    monkeypatch.setitem(
        sys.modules, "backend.core.qdrant_db", types.SimpleNamespace(get_qdrant_metrics=_raise, redis_url='redis://localhost:6379')
    )

    response = client.get("/health/metrics/qdrant")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert "metrics fail" in payload["error"]
