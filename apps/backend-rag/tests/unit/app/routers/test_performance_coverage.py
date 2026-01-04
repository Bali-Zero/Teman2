import importlib.util
import sys
import types
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _Cache:
    def __init__(self):
        self.cache = {}
        self.hits = 2
        self.misses = 3

    async def clear(self):
        self.cache.clear()


class _PerfMonitor:
    def __init__(self, metrics=None, error=None):
        self.metrics = metrics or {"p95_ms": 10}
        self.error = error

    def get_metrics(self):
        if self.error:
            raise self.error
        return self.metrics


def _load_module(monkeypatch, perf_monitor, embedding_cache, search_cache):
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    monkeypatch.setitem(
        sys.modules,
        "services.misc.performance_optimizer",
        types.SimpleNamespace(
            perf_monitor=perf_monitor,
            embedding_cache=embedding_cache,
            search_cache=search_cache,
        ),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.performance"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "performance.py"
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


def test_get_performance_metrics_success(monkeypatch):
    perf_monitor = _PerfMonitor(metrics={"p95_ms": 9})
    module = _load_module(monkeypatch, perf_monitor, _Cache(), _Cache())
    client = _make_client(module)

    response = client.get("/api/performance/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["p95_ms"] == 9


def test_get_performance_metrics_error(monkeypatch):
    perf_monitor = _PerfMonitor(error=RuntimeError("boom"))
    module = _load_module(monkeypatch, perf_monitor, _Cache(), _Cache())
    client = _make_client(module)

    response = client.get("/api/performance/metrics")

    assert response.status_code == 500
    assert "boom" in response.json()["detail"]


def test_clear_caches_success(monkeypatch):
    embed = _Cache()
    search = _Cache()
    module = _load_module(monkeypatch, _PerfMonitor(), embed, search)
    client = _make_client(module)

    response = client.post("/api/performance/clear-cache")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "caches_cleared"


def test_clear_caches_error(monkeypatch):
    embed = _Cache()

    async def _fail():
        raise RuntimeError("clear failed")

    embed.clear = _fail
    module = _load_module(monkeypatch, _PerfMonitor(), embed, _Cache())
    client = _make_client(module)

    response = client.post("/api/performance/clear-cache")

    assert response.status_code == 500
    assert "clear failed" in response.json()["detail"]


def test_clear_embedding_cache(monkeypatch):
    module = _load_module(monkeypatch, _PerfMonitor(), _Cache(), _Cache())
    client = _make_client(module)

    response = client.post("/api/performance/clear-cache/embedding")

    assert response.status_code == 200
    assert response.json()["status"] == "embedding_cache_cleared"


def test_clear_search_cache(monkeypatch):
    module = _load_module(monkeypatch, _PerfMonitor(), _Cache(), _Cache())
    client = _make_client(module)

    response = client.post("/api/performance/clear-cache/search")

    assert response.status_code == 200
    assert response.json()["status"] == "search_cache_cleared"


def test_get_cache_stats_success(monkeypatch):
    embed = _Cache()
    embed.cache = {"a": 1}
    search = _Cache()
    search.cache = {"b": 2, "c": 3}
    module = _load_module(monkeypatch, _PerfMonitor(), embed, search)
    client = _make_client(module)

    response = client.get("/api/performance/cache/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["embedding_cache"]["size"] == 1
    assert payload["search_cache"]["size"] == 2


def test_get_cache_stats_error(monkeypatch):
    class _BadCache:
        @property
        def cache(self):
            raise RuntimeError("bad cache")

    module = _load_module(monkeypatch, _PerfMonitor(), _BadCache(), _Cache())
    client = _make_client(module)

    response = client.get("/api/performance/cache/stats")

    assert response.status_code == 500
    assert "bad cache" in response.json()["detail"]
