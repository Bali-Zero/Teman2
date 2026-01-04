import importlib.util
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _SessionService:
    def __init__(self, redis_url):
        self.redis_url = redis_url
        self.create_session_result = "session-1"
        self.history_result = [{"role": "user", "content": "hi"}]
        self.update_result = True
        self.update_with_ttl_result = True
        self.delete_result = True
        self.extend_result = True
        self.extend_custom_result = True
        self.info_result = {"ttl": 10}
        self.export_result = {"messages": []}
        self.analytics_result = {"total": 1}
        self.cleanup_result = 0
        self.health_result = True

    async def create_session(self):
        return self.create_session_result

    async def get_history(self, _session_id):
        return self.history_result

    async def update_history(self, _session_id, _history):
        return self.update_result

    async def update_history_with_ttl(self, _session_id, _history, _ttl_hours):
        return self.update_with_ttl_result

    async def delete_session(self, _session_id):
        return self.delete_result

    async def extend_ttl(self, _session_id):
        return self.extend_result

    async def extend_ttl_custom(self, _session_id, _ttl_hours):
        return self.extend_custom_result

    async def get_session_info(self, _session_id):
        return self.info_result

    async def export_session(self, _session_id, _format):
        return self.export_result

    async def get_analytics(self):
        return self.analytics_result

    async def cleanup_expired_sessions(self):
        return self.cleanup_result

    async def health_check(self):
        return self.health_result


def _load_module(monkeypatch, settings_overrides=None):
    backend_path = Path(__file__).resolve().parents[4] / "backend"
    module_path = backend_path / "app" / "routers" / "session.py"

    settings_stub = types.SimpleNamespace(redis_url="redis://custom:6379")
    if settings_overrides:
        for key, value in settings_overrides.items():
            setattr(settings_stub, key, value)

    monkeypatch.setitem(
        sys.modules, "app.core.config", types.SimpleNamespace(settings=settings_stub)
    )
    monkeypatch.setitem(
        sys.modules,
        "services.misc.session_service",
        types.SimpleNamespace(SessionService=_SessionService),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.session"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module, settings_stub


def _make_client(module, service):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_session_service] = lambda: service
    return TestClient(app)


def test_get_session_service_uses_settings(monkeypatch):
    module, settings_stub = _load_module(monkeypatch)
    module._session_service = None

    service = module.get_session_service()

    assert isinstance(service, _SessionService)
    assert service.redis_url == settings_stub.redis_url


def test_get_session_service_uses_default(monkeypatch):
    module, settings_stub = _load_module(monkeypatch)
    module._session_service = None
    delattr(settings_stub, "redis_url")

    service = module.get_session_service()

    assert service.redis_url == "redis://localhost:6379"


def test_create_session_success(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    client = _make_client(module, service)

    response = client.post("/api/sessions/create")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["session_id"] == "session-1"


def test_create_session_error(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")

    async def _fail():
        raise RuntimeError("boom")

    service.create_session = _fail
    client = _make_client(module, service)

    response = client.post("/api/sessions/create")

    assert response.status_code == 500
    assert "boom" in response.json()["detail"]


def test_get_session_not_found(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    service.history_result = None
    client = _make_client(module, service)

    response = client.get("/api/sessions/s1")

    assert response.status_code == 404


def test_get_session_success(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    client = _make_client(module, service)

    response = client.get("/api/sessions/s1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["history"] == [{"role": "user", "content": "hi"}]


def test_get_session_error(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")

    async def _fail(_session_id):
        raise RuntimeError("db")

    service.get_history = _fail
    client = _make_client(module, service)

    response = client.get("/api/sessions/s1")

    assert response.status_code == 500
    assert "db" in response.json()["detail"]


def test_update_session_success(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    client = _make_client(module, service)

    response = client.put("/api/sessions/s1", json={"history": [{"role": "user"}]})

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_update_session_failure(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    service.update_result = False
    client = _make_client(module, service)

    response = client.put("/api/sessions/s1", json={"history": [{"role": "user"}]})

    assert response.status_code == 400
    assert "Failed to update session" in response.json()["detail"]


def test_update_session_error(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")

    async def _fail(_session_id, _history):
        raise RuntimeError("write error")

    service.update_history = _fail
    client = _make_client(module, service)

    response = client.put("/api/sessions/s1", json={"history": [{"role": "user"}]})

    assert response.status_code == 500
    assert "write error" in response.json()["detail"]


def test_update_session_with_ttl_failure(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    service.update_with_ttl_result = False
    client = _make_client(module, service)

    response = client.put(
        "/api/sessions/s1/ttl", json={"history": [{"role": "user"}], "ttl_hours": 2}
    )

    assert response.status_code == 400


def test_delete_session_success(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    client = _make_client(module, service)

    response = client.delete("/api/sessions/s1")

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_delete_session_error(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")

    async def _fail(_session_id):
        raise RuntimeError("delete fail")

    service.delete_session = _fail
    client = _make_client(module, service)

    response = client.delete("/api/sessions/s1")

    assert response.status_code == 500
    assert "delete fail" in response.json()["detail"]


def test_extend_ttl_success(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    client = _make_client(module, service)

    response = client.post("/api/sessions/s1/extend")

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_extend_ttl_custom_success(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    client = _make_client(module, service)

    response = client.post("/api/sessions/s1/extend-custom", json={"ttl_hours": 5})

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_get_session_info_not_found(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    service.info_result = None
    client = _make_client(module, service)

    response = client.get("/api/sessions/s1/info")

    assert response.status_code == 404


def test_export_session_not_found(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    service.export_result = None
    client = _make_client(module, service)

    response = client.get("/api/sessions/s1/export?format=txt")

    assert response.status_code == 404


def test_analytics_success(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    client = _make_client(module, service)

    response = client.get("/api/sessions/analytics/overview")

    assert response.status_code == 200
    assert response.json()["analytics"]["total"] == 1


def test_cleanup_success(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")
    service.cleanup_result = 3
    client = _make_client(module, service)

    response = client.post("/api/sessions/cleanup")

    assert response.status_code == 200
    assert response.json()["cleaned"] == 3


@pytest.mark.asyncio
async def test_health_check_error(monkeypatch):
    module, _ = _load_module(monkeypatch)
    service = _SessionService("redis://x")

    async def _fail():
        raise RuntimeError("health down")

    service.health_check = _fail

    result = await module.health_check(service=service)

    assert result["success"] is False
    assert result["service"] == "session"
    assert "health down" in result["error"]
