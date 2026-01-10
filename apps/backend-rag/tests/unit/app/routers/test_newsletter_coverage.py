import importlib.util
import sys
import types
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _AcquireCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyConn:
    def __init__(self):
        self.fetchrow_values = []
        self.fetchval_value = None
        self.fetch_values = []
        self.execute_calls = []
        self.fetchrow_calls = []
        self.fetchval_calls = []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query.strip(), args))
        return self.fetchrow_values.pop(0) if self.fetchrow_values else None

    async def fetchval(self, query, *args):
        self.fetchval_calls.append((query.strip(), args))
        return self.fetchval_value

    async def fetch(self, query, *args):
        return self.fetch_values.pop(0) if self.fetch_values else []

    async def execute(self, query, *args):
        self.execute_calls.append((query.strip(), args))
        return "OK"


class _DummyPool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _AcquireCtx(self.conn)


def _load_module(monkeypatch):
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    async def get_database_pool():
        return None

    class _Logger:
        def info(self, *_args, **_kwargs):
            pass

    monkeypatch.setitem(
        sys.modules,
        "app.dependencies",
        types.SimpleNamespace(get_database_pool=get_database_pool, redis_url='redis://localhost:6379'),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.utils.logging_utils",
        types.SimpleNamespace(get_logger=lambda _name: _Logger(), redis_url='redis://localhost:6379'),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.newsletter"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "newsletter.py"
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


def test_subscribe_new(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [None, {"id": str(uuid4())}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/blog/newsletter/subscribe",
        json={"email": "user@example.com", "frequency": "weekly"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_subscribe_already_confirmed(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [{"id": str(uuid4()), "confirmed": True, "unsubscribed_at": None}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/blog/newsletter/subscribe",
        json={"email": "user@example.com", "frequency": "weekly"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ALREADY_SUBSCRIBED"


def test_subscribe_resubscribe(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [
        {
            "id": str(uuid4()),
            "confirmed": False,
            "unsubscribed_at": "2024-01-01T00:00:00",
        }
    ]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/blog/newsletter/subscribe",
        json={"email": "user@example.com", "frequency": "daily"},
    )

    assert response.status_code == 200
    assert "Please check your email" in response.json()["message"]


def test_subscribe_resend_confirmation(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [{"id": str(uuid4()), "confirmed": False, "unsubscribed_at": None}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/blog/newsletter/subscribe",
        json={"email": "user@example.com", "frequency": "weekly"},
    )

    assert response.status_code == 200
    assert "Confirmation email resent" in response.json()["message"]


def test_confirm_subscription_invalid(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [None]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/blog/newsletter/confirm",
        json={"subscriberId": "1", "token": "bad"},
    )

    assert response.status_code == 404


def test_confirm_subscription_already_confirmed(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [{"id": "1", "email": "user@example.com", "confirmed": True}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/blog/newsletter/confirm",
        json={"subscriberId": "1", "token": "tok"},
    )

    assert response.status_code == 200
    assert "already confirmed" in response.json()["message"]


def test_confirm_subscription_success(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [{"id": "1", "email": "user@example.com", "confirmed": False}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/blog/newsletter/confirm",
        json={"subscriberId": "1", "token": "tok"},
    )

    assert response.status_code == 200
    assert "confirmed successfully" in response.json()["message"]


def test_unsubscribe_missing_fields(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post("/api/blog/newsletter/unsubscribe", json={})

    assert response.status_code == 400


def test_unsubscribe_not_found(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [None]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/blog/newsletter/unsubscribe",
        json={"email": "user@example.com"},
    )

    assert response.status_code == 404


def test_unsubscribe_success(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [{"id": "1", "email": "user@example.com"}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/blog/newsletter/unsubscribe",
        json={"subscriberId": "1"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Successfully unsubscribed"


def test_update_preferences_no_changes(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [{"id": "1"}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.patch(
        "/api/blog/newsletter/preferences",
        json={"subscriberId": "1"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "No changes"


def test_update_preferences_success(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [{"id": "1"}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.patch(
        "/api/blog/newsletter/preferences",
        json={"subscriberId": "1", "frequency": "daily"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Preferences updated"


def test_list_subscribers(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetch_values = [
        [
            {
                "id": "1",
                "email": "user@example.com",
                "name": None,
                "categories": None,
                "frequency": None,
                "language": None,
                "confirmed": None,
                "created_at": None,
            }
        ]
    ]
    conn.fetchval_value = 1
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get(
        "/api/blog/newsletter/subscribers?category=business&frequency=weekly&confirmed=true"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["subscribers"][0]["frequency"] == "weekly"


def test_log_newsletter_send(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/blog/newsletter/log?article_id=1&recipient_count=2&sent_count=2&failed_count=0"
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_update_preferences_with_email(monkeypatch):
    """Test update_preferences with email instead of subscriberId (covers line 296-301, 304)"""
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [{"id": "1"}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.patch(
        "/api/blog/newsletter/preferences",
        json={"email": "user@example.com", "frequency": "daily"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Preferences updated"


def test_update_preferences_with_categories(monkeypatch):
    """Test update_preferences with categories (covers line 312-314)"""
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [{"id": "1"}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.patch(
        "/api/blog/newsletter/preferences",
        json={"subscriberId": "1", "categories": ["tech", "news"]},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Preferences updated"


def test_update_preferences_with_language(monkeypatch):
    """Test update_preferences with language (covers line 322-324)"""
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [{"id": "1"}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.patch(
        "/api/blog/newsletter/preferences",
        json={"subscriberId": "1", "language": "it"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Preferences updated"


def test_unsubscribe_with_email(monkeypatch):
    """Test unsubscribe with email instead of subscriberId (covers line 262-265)"""
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_values = [{"id": "1", "email": "user@example.com"}]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/blog/newsletter/unsubscribe",
        json={"email": "user@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Successfully unsubscribed"


def test_list_subscribers_no_filters(monkeypatch):
    """Test list_subscribers without filters (covers more query paths)"""
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetch_values = [
        [
            {
                "id": "1",
                "email": "user@example.com",
                "name": "Test User",
                "categories": ["tech"],
                "frequency": "weekly",
                "language": "en",
                "confirmed": True,
                "created_at": "2024-01-01T00:00:00",
            }
        ]
    ]
    conn.fetchval_value = 1
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/blog/newsletter/subscribers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["subscribers"]) == 1


def test_list_subscribers_only_category(monkeypatch):
    """Test list_subscribers with only category filter"""
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetch_values = [[]]
    conn.fetchval_value = 0
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/blog/newsletter/subscribers?category=tech")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
