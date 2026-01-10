import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi import FastAPI, HTTPException
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


class _MemoryCache:
    def __init__(self):
        self.messages = {}

    def add_message(self, session_id, role, content):
        self.messages.setdefault(session_id, []).append({"role": role, "content": content})

    def get_messages(self, session_id, limit=20):
        return self.messages.get(session_id, [])[-limit:]


def _load_module(
    monkeypatch,
    auto_crm_mode="ok",
    mem_cache=None,
    orchestrator_context=None,
    orchestrator_init_error=False,
    orchestrator_context_error=False,
):
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    def handle_database_error(exc):
        return HTTPException(status_code=500, detail=str(exc))

    class _Logger:
        def debug(self, *_args, **_kwargs):
            pass

        def info(self, *_args, **_kwargs):
            pass

        def warning(self, *_args, **_kwargs):
            pass

        def error(self, *_args, **_kwargs):
            pass

    monkeypatch.setitem(
        sys.modules,
        "app.utils.logging_utils",
        types.SimpleNamespace(
            get_logger=lambda _name: _Logger(),
            log_error=lambda *_args, **_kwargs: None,
            log_success=lambda *_args, **_kwargs: None,
            log_warning=lambda *_args, **_kwargs: None,
            redis_url='redis://localhost:6379'
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.utils.error_handlers",
        types.SimpleNamespace(handle_database_error=handle_database_error, redis_url='redis://localhost:6379'),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.metrics",
        types.SimpleNamespace(
            metrics_collector=types.SimpleNamespace(
                record_cache_db_consistency_error=lambda **_kwargs: None,
                redis_url='redis://localhost:6379'
            ),
            redis_url='redis://localhost:6379'
        ),
    )

    async def get_database_pool():
        return None

    def get_current_user():
        return {"email": "user@example.com"}

    monkeypatch.setitem(
        sys.modules,
        "app.dependencies",
        types.SimpleNamespace(
            get_current_user=get_current_user,
            get_database_pool=get_database_pool,
            redis_url='redis://localhost:6379'
        ),
    )

    mem_cache = mem_cache or _MemoryCache()

    class _Context:
        def __init__(self):
            self.user_id = "user@example.com"
            self.profile_facts = ["fact1"]
            self.summary = "summary"
            self.counters = {"notes": 1}
            self.has_data = True

    context_value = orchestrator_context or _Context()

    class _MemoryOrchestrator:
        def __init__(self, db_pool=None):
            self.db_pool = db_pool

        async def initialize(self):
            if orchestrator_init_error:
                raise RuntimeError("init failed")

        async def get_user_context(self, _user_id):
            if orchestrator_context_error:
                raise RuntimeError("context failed")
            return context_value

    monkeypatch.setitem(
        sys.modules,
        "services.memory",
        types.SimpleNamespace(
            MemoryOrchestrator=_MemoryOrchestrator,
            get_memory_cache=lambda: mem_cache,
            redis_url='redis://localhost:6379'
        ),
    )

    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = [str(backend_path / "services")]
    crm_pkg = types.ModuleType("services.crm")
    crm_pkg.__path__ = [str(backend_path / "services" / "crm")]
    monkeypatch.setitem(sys.modules, "services", services_pkg)
    monkeypatch.setitem(sys.modules, "services.crm", crm_pkg)

    if auto_crm_mode == "ok":
        auto_crm_module = types.SimpleNamespace(get_auto_crm_service=lambda: "auto-crm", redis_url='redis://localhost:6379')
    elif auto_crm_mode == "missing":
        auto_crm_module = types.ModuleType("services.crm.auto_crm_service")
    else:
        auto_crm_module = types.SimpleNamespace(get_auto_crm_service=lambda: (_ for _ in ()).throw(RuntimeError("crm error"))
        )

    monkeypatch.setitem(sys.modules, "services.crm.auto_crm_service", auto_crm_module)

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.conversations"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "conversations.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module, mem_cache


def _make_client(module, pool=None, current_user=None):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_current_user] = lambda: current_user or {
        "email": "user@example.com"
    }
    app.dependency_overrides[module.get_database_pool] = lambda: pool
    return TestClient(app)


def test_get_auto_crm_success(monkeypatch):
    module, _ = _load_module(monkeypatch, auto_crm_mode="ok")

    crm_service = module.get_auto_crm()
    assert crm_service == "auto-crm"
    assert module.get_auto_crm() == "auto-crm"


def test_get_auto_crm_import_error(monkeypatch):
    module, _ = _load_module(monkeypatch, auto_crm_mode="missing")

    assert module.get_auto_crm() is None


def test_get_auto_crm_exception(monkeypatch):
    module, _ = _load_module(monkeypatch, auto_crm_mode="error")

    assert module.get_auto_crm() is None


def test_history_falls_back_to_memory_cache(monkeypatch):
    mem_cache = _MemoryCache()
    mem_cache.add_message("session-1", "user", "hello")
    module, _ = _load_module(monkeypatch, mem_cache=mem_cache)

    conn = types.SimpleNamespace(fetchrow=AsyncMock(return_value=None))
    pool = _DummyPool(conn)
    client = _make_client(module, pool=pool)

    response = client.get("/api/bali-zero/conversations/history?session_id=session-1&limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["messages"] == [{"role": "user", "content": "hello"}]
    assert payload["total_messages"] == 1


def test_list_conversations_formats_title_preview(monkeypatch):
    module, _ = _load_module(monkeypatch)
    conn = types.SimpleNamespace(fetchrow=AsyncMock(return_value={"total": 2}),
        fetch=AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "session_id": "s1",
                    "messages": [
                        {"role": "user", "content": "U" * 60},
                        {"role": "assistant", "content": "A" * 120},
                    ],
                    "metadata": None,
                    "created_at": datetime(2024, 1, 1, 12, 0, 0),
                },
                {
                    "id": 2,
                    "session_id": "s2",
                    "messages": [{"role": "assistant", "content": "Hi"}],
                    "metadata": None,
                    "created_at": datetime(2024, 1, 2, 12, 0, 0),
                },
            ]
        ),
    )
    pool = _DummyPool(conn)
    client = _make_client(module, pool=pool)

    response = client.get("/api/bali-zero/conversations/list?limit=2&offset=0")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["conversations"][0]["title"].endswith("...")
    assert payload["conversations"][0]["preview"].endswith("...")
    assert payload["conversations"][1]["title"] == "New Conversation"
    assert payload["conversations"][1]["preview"] == "Hi"


def test_list_conversations_error(monkeypatch):
    module, _ = _load_module(monkeypatch)
    conn = types.SimpleNamespace(fetchrow=AsyncMock(side_effect=RuntimeError("db failure")))
    pool = _DummyPool(conn)
    client = _make_client(module, pool=pool)

    response = client.get("/api/bali-zero/conversations/list")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert "db failure" in payload["error"]


def test_get_conversation_success(monkeypatch):
    module, _ = _load_module(monkeypatch)
    conn = types.SimpleNamespace(fetchrow=AsyncMock(
            return_value={
                "id": 11,
                "session_id": "s1",
                "messages": [{"role": "user", "content": "hello"}],
                "metadata": {"tag": "x"},
                "created_at": datetime(2024, 2, 2, 10, 0, 0),
            }
        )
    )
    pool = _DummyPool(conn)
    client = _make_client(module, pool=pool)

    response = client.get("/api/bali-zero/conversations/11")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["message_count"] == 1
    assert payload["metadata"]["tag"] == "x"


def test_get_conversation_not_found(monkeypatch):
    module, _ = _load_module(monkeypatch)
    conn = types.SimpleNamespace(fetchrow=AsyncMock(return_value=None))
    pool = _DummyPool(conn)
    client = _make_client(module, pool=pool)

    response = client.get("/api/bali-zero/conversations/404")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_conversation_success(monkeypatch):
    module, _ = _load_module(monkeypatch)
    conn = types.SimpleNamespace(fetchrow=AsyncMock(return_value={"id": 7}),
        execute=AsyncMock(return_value="DELETE 1"),
    )
    pool = _DummyPool(conn)
    client = _make_client(module, pool=pool)

    response = client.delete("/api/bali-zero/conversations/7")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["deleted_id"] == 7


def test_delete_conversation_not_found(monkeypatch):
    module, _ = _load_module(monkeypatch)
    conn = types.SimpleNamespace(fetchrow=AsyncMock(return_value=None))
    pool = _DummyPool(conn)
    client = _make_client(module, pool=pool)

    response = client.delete("/api/bali-zero/conversations/7")

    assert response.status_code == 404


def test_clear_conversation_history_database_error(monkeypatch):
    module, _ = _load_module(monkeypatch)
    conn = types.SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError("db fail")))
    pool = _DummyPool(conn)
    client = _make_client(module, pool=pool)

    response = client.delete("/api/bali-zero/conversations/clear")

    assert response.status_code == 500
    assert "db fail" in response.json()["detail"]


def test_get_conversation_stats_empty(monkeypatch):
    module, _ = _load_module(monkeypatch)
    conn = types.SimpleNamespace(fetchrow=AsyncMock(return_value=None))
    pool = _DummyPool(conn)
    client = _make_client(module, pool=pool)

    response = client.get("/api/bali-zero/conversations/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_conversations"] == 0
    assert payload["total_messages"] == 0
    assert payload["last_conversation"] is None


def test_get_user_memory_context_no_orchestrator(monkeypatch):
    module, _ = _load_module(monkeypatch, orchestrator_init_error=True)
    client = _make_client(module, pool=None)

    response = client.get("/api/bali-zero/conversations/memory/context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["has_data"] is False
    assert payload["error"] == "Memory service not available"


def test_get_user_memory_context_success(monkeypatch):
    module, _ = _load_module(monkeypatch)
    client = _make_client(module, pool=None)

    response = client.get("/api/bali-zero/conversations/memory/context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["profile_facts"] == ["fact1"]
    assert payload["summary"] == "summary"
    assert payload["counters"]["notes"] == 1
    assert payload["has_data"] is True


def test_get_user_memory_context_error(monkeypatch):
    module, _ = _load_module(monkeypatch, orchestrator_context_error=True)
    client = _make_client(module, pool=None)

    response = client.get("/api/bali-zero/conversations/memory/context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert "context failed" in payload["error"]
