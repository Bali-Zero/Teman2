import importlib.util
import sys
import types
from datetime import datetime
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
        self.fetchval_values = []
        self.fetch_values = []
        self.fetchrow_value = None
        self.execute_value = "UPDATE 1"
        self.fetchval_calls = []
        self.fetch_calls = []
        self.fetchrow_calls = []
        self.execute_calls = []

    async def fetchval(self, query, *args):
        self.fetchval_calls.append((query.strip(), args))
        return self.fetchval_values.pop(0) if self.fetchval_values else None

    async def fetch(self, query, *args):
        self.fetch_calls.append((query.strip(), args))
        return self.fetch_values.pop(0) if self.fetch_values else []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query.strip(), args))
        return self.fetchrow_value

    async def execute(self, query, *args):
        self.execute_calls.append((query.strip(), args))
        return self.execute_value


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

    module_name = "app.routers.news"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "news.py"
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


def test_list_news_success(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchval_values = [2]
    conn.fetch_values = [
        [
            {
                "id": uuid4(),
                "title": "News title 1",
                "slug": "news-title-1",
                "summary": "summary",
                "content": "content",
                "source": "source",
                "source_url": None,
                "category": "business",
                "priority": "high",
                "status": "approved",
                "image_url": None,
                "view_count": None,
                "published_at": datetime(2024, 1, 1),
                "created_at": datetime(2024, 1, 1),
                "ai_summary": None,
                "ai_tags": ["t1"],
            },
            {
                "id": uuid4(),
                "title": "News title 2",
                "slug": "news-title-2",
                "summary": None,
                "content": None,
                "source": "source",
                "source_url": None,
                "category": "business",
                "priority": "low",
                "status": "approved",
                "image_url": None,
                "view_count": 3,
                "published_at": None,
                "created_at": datetime(2024, 1, 2),
                "ai_summary": None,
                "ai_tags": None,
            },
        ]
    ]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/news?category=business&priority=high&search=term&page=1&limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["data"][0]["view_count"] == 0
    assert payload["has_more"] is True


def test_list_news_error(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("db fail")

    conn.fetchval = _fail
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/news")

    assert response.status_code == 500
    assert "db fail" in response.json()["detail"]


def test_get_categories(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetch_values = [[{"category": "business", "count": 2}]]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/news/categories")

    assert response.status_code == 200
    payload = response.json()
    assert payload["categories"][0]["name"] == "business"


def test_get_news_by_slug_not_found(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_value = None
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/news/unknown-slug")

    assert response.status_code == 404


def test_get_news_by_slug_success(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_value = {
        "id": uuid4(),
        "title": "News title",
        "slug": "news-title",
        "summary": "summary",
        "content": "content",
        "source": "source",
        "source_url": None,
        "category": "business",
        "priority": "high",
        "status": "approved",
        "image_url": None,
        "view_count": 4,
        "published_at": datetime(2024, 1, 1),
        "created_at": datetime(2024, 1, 1),
        "ai_summary": None,
        "ai_tags": None,
    }
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/news/news-title")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["view_count"] == 4


def test_create_news_duplicate(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    existing_id = uuid4()
    conn.fetchval_values = [existing_id]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/news",
        json={
            "title": "A valid title",
            "summary": "summary",
            "content": None,
            "source": "source",
            "external_id": "ext-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["duplicate"] is True
    assert payload["data"]["id"] == str(existing_id)


def test_create_news_success(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchrow_value = {"id": uuid4(), "slug": "new-slug"}
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/news",
        json={
            "title": "A valid title",
            "summary": "summary",
            "content": None,
            "source": "source",
            "external_id": None,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["slug"] == "new-slug"


def test_create_news_error(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("insert failed")

    conn.fetchrow = _fail
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/news",
        json={
            "title": "A valid title",
            "summary": "summary",
            "content": None,
            "source": "source",
        },
    )

    assert response.status_code == 500
    assert "insert failed" in response.json()["detail"]


def test_create_news_bulk(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetchval_values = [uuid4(), None]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/news/bulk",
        json=[
            {
                "title": "A valid title 1",
                "summary": "summary",
                "content": None,
                "source": "source",
                "external_id": "ext-1",
            },
            {
                "title": "A valid title 2",
                "summary": "summary",
                "content": None,
                "source": "source",
                "external_id": "ext-2",
            },
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] == 1
    assert payload["duplicates"] == 1
    assert payload["total"] == 2


def test_update_news_status_invalid(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.patch("/api/news/1/status?status=wrong")

    assert response.status_code == 400


def test_update_news_status_not_found(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.execute_value = "UPDATE 0"
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.patch("/api/news/1/status?status=approved")

    assert response.status_code == 404


def test_update_news_status_success(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.patch("/api/news/1/status?status=approved")

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_subscribe_unsubscribe(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/news/subscribe",
        json={"email": "test@example.com", "categories": ["business"], "frequency": "daily"},
    )
    assert response.status_code == 200

    response = client.post("/api/news/unsubscribe?email=test@example.com")
    assert response.status_code == 200


def test_subscribe_error(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("subscribe fail")

    conn.execute = _fail
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/news/subscribe",
        json={"email": "test@example.com", "categories": [], "frequency": "daily"},
    )

    assert response.status_code == 500
    assert "subscribe fail" in response.json()["detail"]


def test_rss_feed_success(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()
    conn.fetch_values = [
        [
            {
                "title": "Title",
                "slug": "slug",
                "summary": "summary",
                "source": "source",
                "category": "business",
                "published_at": datetime(2024, 1, 1),
            }
        ]
    ]
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/news/feed/rss?category=business&limit=1")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/rss+xml")
    assert "<item>" in response.text


def test_rss_feed_error(monkeypatch):
    module = _load_module(monkeypatch)
    conn = _DummyConn()

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("rss fail")

    conn.fetch = _fail
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/news/feed/rss")

    assert response.status_code == 500
    assert "rss fail" in response.json()["detail"]


def test_get_categories_error(monkeypatch):
    """Test get_categories exception handler (lines 202-204)"""
    module = _load_module(monkeypatch)
    conn = _DummyConn()

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("categories fail")

    conn.fetch = _fail
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/news/categories")

    assert response.status_code == 500
    assert "categories fail" in response.json()["detail"]


def test_get_news_by_slug_error(monkeypatch):
    """Test get_news_by_slug exception handler after HTTPException (lines 255-257)"""
    module = _load_module(monkeypatch)
    conn = _DummyConn()

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("get by slug fail")

    conn.fetchrow = _fail
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.get("/api/news/test-slug")

    assert response.status_code == 500
    assert "get by slug fail" in response.json()["detail"]


def test_create_news_bulk_error(monkeypatch):
    """Test create_news_bulk exception handler (lines 353-355)"""
    module = _load_module(monkeypatch)
    conn = _DummyConn()

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("bulk create fail")

    conn.execute = _fail
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post(
        "/api/news/bulk",
        json=[
            {
                "title": "Test News Title with sufficient length",
                "source": "test",
                "category": "business",
            }
        ],
    )

    assert response.status_code == 500
    assert "bulk create fail" in response.json()["detail"]


def test_update_news_status_error(monkeypatch):
    """Test update_news_status exception handler after HTTPException (lines 385-387)"""
    module = _load_module(monkeypatch)
    conn = _DummyConn()

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("update status fail")

    conn.execute = _fail
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.patch("/api/news/1/status?status=approved")

    assert response.status_code == 500
    assert "update status fail" in response.json()["detail"]


def test_unsubscribe_error(monkeypatch):
    """Test unsubscribe_from_news exception handler (lines 446-448)"""
    module = _load_module(monkeypatch)
    conn = _DummyConn()

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("unsubscribe fail")

    conn.execute = _fail
    pool = _DummyPool(conn)
    client = _make_client(module, pool)

    response = client.post("/api/news/unsubscribe?email=test@example.com")

    assert response.status_code == 500
    assert "unsubscribe fail" in response.json()["detail"]
