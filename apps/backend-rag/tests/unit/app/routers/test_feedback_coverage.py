import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _Ctx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyConn:
    def __init__(self, fetchval_values=None, fetchrow_value=None, fetchval_error=None):
        self.fetchval_values = list(fetchval_values or [])
        self.fetchrow_value = fetchrow_value
        self.fetchval_error = fetchval_error
        self.fetchval_calls = []
        self.fetchrow_calls = []

    async def fetchval(self, query, *args):
        self.fetchval_calls.append((query.strip(), args))
        if self.fetchval_error:
            raise self.fetchval_error
        return self.fetchval_values.pop(0) if self.fetchval_values else None

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query.strip(), args))
        if isinstance(self.fetchrow_value, Exception):
            raise self.fetchrow_value
        return self.fetchrow_value

    def transaction(self):
        return _Ctx()


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

    async def get_database_pool():
        return None

    monkeypatch.setitem(
        sys.modules,
        "app.dependencies",
        types.SimpleNamespace(get_database_pool=get_database_pool, redis_url='redis://localhost:6379'),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.feedback"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "feedback.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_client(module, pool, user_id=None, user_profile=None):
    app = FastAPI()

    @app.middleware("http")
    async def add_user_state(request, call_next):
        if user_id is not None:
            request.state.user_id = user_id
        if user_profile is not None:
            request.state.user_profile = user_profile
        return await call_next(request)

    app.include_router(module.router)
    app.dependency_overrides[module.get_database_pool] = lambda: pool
    return TestClient(app)


def test_submit_feedback_success_no_review(monkeypatch):
    module = _load_module(monkeypatch)
    rating_id = uuid4()
    conn = _DummyConn(fetchval_values=[rating_id])
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/v2/feedback/",
        json={"session_id": str(uuid4()), "rating": 5, "feedback_text": "ok"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["review_queue_id"] is None
    assert "review queue" not in payload["message"]


def test_submit_feedback_low_rating_creates_review(monkeypatch):
    module = _load_module(monkeypatch)
    rating_id = uuid4()
    review_id = uuid4()
    conn = _DummyConn(fetchval_values=[rating_id, review_id])
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/v2/feedback/",
        json={"session_id": str(uuid4()), "rating": 2, "feedback_text": "bad"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_queue_id"] == str(review_id)
    assert "review queue" in payload["message"]
    assert conn.fetchval_calls[1][1][1] == "high"


def test_submit_feedback_with_correction_creates_review(monkeypatch):
    module = _load_module(monkeypatch)
    rating_id = uuid4()
    review_id = uuid4()
    conn = _DummyConn(fetchval_values=[rating_id, review_id])
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/v2/feedback/",
        json={
            "session_id": str(uuid4()),
            "rating": 4,
            "feedback_text": "note",
            "correction_text": "fix",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_queue_id"] == str(review_id)
    assert conn.fetchval_calls[1][1][1] == "medium"
    combined_feedback = conn.fetchval_calls[0][1][4]
    assert combined_feedback.endswith("[Correction]: fix")


def test_submit_feedback_user_profile_id(monkeypatch):
    module = _load_module(monkeypatch)
    rating_id = uuid4()
    conn = _DummyConn(fetchval_values=[rating_id])
    pool = _DummyPool(conn)
    user_id = uuid4()
    client = _make_client(module, pool, user_profile={"id": str(user_id)})

    response = client.post(
        "/api/v2/feedback/",
        json={"session_id": str(uuid4()), "rating": 5},
    )

    assert response.status_code == 200
    assert conn.fetchval_calls[0][1][1] == user_id


def test_submit_feedback_invalid_user_profile_id(monkeypatch):
    module = _load_module(monkeypatch)
    rating_id = uuid4()
    conn = _DummyConn(fetchval_values=[rating_id])
    pool = _DummyPool(conn)
    client = _make_client(module, pool, user_profile={"id": "not-a-uuid"})

    response = client.post(
        "/api/v2/feedback/",
        json={"session_id": str(uuid4()), "rating": 5},
    )

    assert response.status_code == 200
    assert conn.fetchval_calls[0][1][1] is None


def test_submit_feedback_invalid_feedback_type(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(fetchval_values=[uuid4()])
    pool = _DummyPool(conn)
    request = module.RateConversationRequest.model_construct(
        session_id=uuid4(),
        rating=3,
        feedback_type="weird",
    )

    async def _call():
        return await module.submit_feedback(
            request=request,
            req=types.SimpleNamespace(state=types.SimpleNamespace(redis_url='redis://localhost:6379')),
            db_pool=pool,
        )

    with pytest.raises(module.HTTPException) as exc_info:
        asyncio.run(_call())

    assert exc_info.value.status_code == 400


def test_submit_feedback_db_error(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(fetchval_error=asyncpg.PostgresError("db"))
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/v2/feedback/",
        json={"session_id": str(uuid4()), "rating": 5},
    )

    assert response.status_code == 500
    assert "Database error" in response.json()["detail"]


def test_get_conversation_rating_invalid_session(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(fetchrow_value=None)
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/v2/feedback/ratings/not-a-uuid")

    assert response.status_code == 400


def test_get_conversation_rating_not_found(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(fetchrow_value=None)
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get(f"/api/v2/feedback/ratings/{uuid4()}")

    assert response.status_code == 404


def test_get_conversation_rating_success(monkeypatch):
    module = _load_module(monkeypatch)
    session_id = uuid4()
    rating = {
        "id": uuid4(),
        "session_id": session_id,
        "user_id": None,
        "rating": 4,
        "feedback_type": None,
        "feedback_text": None,
        "turn_count": None,
        "created_at": "2024-01-01T00:00:00",
    }
    conn = _DummyConn(fetchrow_value=rating)
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get(f"/api/v2/feedback/ratings/{session_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["rating"] == 4


def test_get_feedback_stats_success(monkeypatch):
    module = _load_module(monkeypatch)
    stats = {
        "total_pending": None,
        "total_resolved": 2,
        "total_ignored": None,
        "total_reviews": 5,
    }
    conn = _DummyConn(fetchrow_value=stats)
    conn.fetchval_values = [None, None]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/v2/feedback/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_pending"] == 0
    assert payload["total_resolved"] == 2
    assert payload["low_ratings_count"] == 0


def test_get_feedback_stats_error(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn(fetchrow_value=RuntimeError("stats fail"))
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/v2/feedback/stats")

    assert response.status_code == 500
    assert "stats fail" in response.json()["detail"]
