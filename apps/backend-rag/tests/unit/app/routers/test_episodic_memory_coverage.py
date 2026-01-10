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

            async def add_event(self, **_kwargs):
                return {"status": "ok", "event_id": 1}

            async def extract_and_save_event(self, **_kwargs):
                return {"event_id": 2}

            async def get_timeline(self, **_kwargs):
                return [{"id": 1}]

            async def get_context_summary(self, **_kwargs):
                return "summary"

            async def get_stats(self, **_kwargs):
                return {"total": 1}

            async def delete_event(self, **_kwargs):
                return True

        service = _Service

    class _Enum(str):
        def __new__(cls, value):
            if value not in cls._values:
                raise ValueError("invalid")
            return str.__new__(cls, value)

    class EventType(_Enum):
        _values = {"milestone", "general"}
        MILESTONE = "milestone"
        GENERAL = "general"

    class Emotion(_Enum):
        _values = {"neutral", "positive"}
        NEUTRAL = "neutral"
        POSITIVE = "positive"

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
        "backend.services.memory.episodic_memory_service",
        types.SimpleNamespace(
            EpisodicMemoryService=service,
            EventType=EventType,
            Emotion=Emotion,
            redis_url='redis://localhost:6379'
        ),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("backend.app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "backend.app.routers", routers_pkg)

    module_name = "backend.app.routers.episodic_memory"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "episodic_memory.py"
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


def test_add_event_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.post(
        "/api/episodic-memory/events",
        json={
            "title": "Started project",
            "description": "desc",
            "event_type": "milestone",
            "emotion": "positive",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["event_id"] == 1


def test_add_event_invalid_type_emotion(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.post(
        "/api/episodic-memory/events",
        json={
            "title": "Started project",
            "event_type": "unknown",
            "emotion": "unknown",
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_add_event_error_status(monkeypatch):
    class _Service:
        def __init__(self, pool=None):
            self.pool = pool

        async def add_event(self, **_kwargs):
            return {"status": "error", "message": "failed"}

    module = _load_module(monkeypatch, service=_Service)
    client = _make_client(module)

    response = client.post(
        "/api/episodic-memory/events",
        json={"title": "Started project"},
    )

    assert response.status_code == 500
    assert "failed" in response.json()["detail"]


def test_extract_event_no_temporal(monkeypatch):
    class _Service:
        def __init__(self, pool=None):
            self.pool = pool

        async def extract_and_save_event(self, **_kwargs):
            return None

    module = _load_module(monkeypatch, service=_Service)
    client = _make_client(module)

    response = client.post(
        "/api/episodic-memory/extract",
        json={"message": "Hello"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] is None
    assert "No temporal reference" in payload["message"]


def test_timeline_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/api/episodic-memory/timeline?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1


def test_context_summary_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/api/episodic-memory/context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == "summary"
    assert payload["has_events"] is True


def test_context_summary_empty(monkeypatch):
    class _Service:
        def __init__(self, pool=None):
            self.pool = pool

        async def get_context_summary(self, **_kwargs):
            return ""

    module = _load_module(monkeypatch, service=_Service)
    client = _make_client(module)

    response = client.get("/api/episodic-memory/context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["has_events"] is False


def test_stats_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/api/episodic-memory/stats")

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1


def test_delete_event_not_found(monkeypatch):
    class _Service:
        def __init__(self, pool=None):
            self.pool = pool

        async def delete_event(self, **_kwargs):
            return False

    module = _load_module(monkeypatch, service=_Service)
    client = _make_client(module)

    response = client.delete("/api/episodic-memory/events/1")

    assert response.status_code == 404


def test_delete_event_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.delete("/api/episodic-memory/events/1")

    assert response.status_code == 200
    assert response.json()["message"] == "Event deleted"
