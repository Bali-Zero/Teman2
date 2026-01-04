import importlib.util
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt


class _DummyConn:
    def __init__(self, row=None):
        self.row = row
        self.executed = []

    async def fetchrow(self, _query, *args):
        return self.row

    async def execute(self, query, *args):
        self.executed.append((query.strip(), args))


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


def _load_module(monkeypatch, pool=None):
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    settings_stub = types.SimpleNamespace(
        jwt_secret_key="secret",
        jwt_algorithm="HS256",
        jwt_access_token_expire_hours=1,
    )
    monkeypatch.setitem(
        sys.modules, "app.core.config", types.SimpleNamespace(settings=settings_stub)
    )

    async def get_database_pool():
        return pool

    monkeypatch.setitem(
        sys.modules, "app.dependencies", types.SimpleNamespace(get_database_pool=get_database_pool)
    )

    cookie_calls = {}

    def set_auth_cookies(response, jwt_token, max_age_hours):
        cookie_calls["set"] = {"token": jwt_token, "max_age": max_age_hours}
        response.headers["x-csrf"] = "token"
        return "csrf-token"

    def clear_auth_cookies(response):
        cookie_calls["clear"] = True
        response.headers["x-cleared"] = "1"

    monkeypatch.setitem(
        sys.modules,
        "app.utils.cookie_auth",
        types.SimpleNamespace(
            set_auth_cookies=set_auth_cookies, clear_auth_cookies=clear_auth_cookies
        ),
    )

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
            log_warning=lambda *_args, **_kwargs: None,
        ),
    )

    audit_service = types.SimpleNamespace(
        pool=None, connect=AsyncMock(), log_auth_event=AsyncMock()
    )
    monkeypatch.setitem(
        sys.modules,
        "services.monitoring.audit_service",
        types.SimpleNamespace(get_audit_service=lambda: audit_service),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.auth"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "auth.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)

    return module, audit_service, cookie_calls, settings_stub


def _make_client(module, pool):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_database_pool] = lambda: pool
    return TestClient(app)


def test_verify_password_exception(monkeypatch):
    module, _, _, _ = _load_module(monkeypatch)
    monkeypatch.setattr(
        module.bcrypt, "checkpw", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad"))
    )

    assert module.verify_password("a", "b") is False


def test_create_access_token(monkeypatch):
    module, _, _, settings_stub = _load_module(monkeypatch)
    token = module.create_access_token({"sub": "1"}, expires_delta=timedelta(hours=1))
    payload = jwt.decode(
        token, settings_stub.jwt_secret_key, algorithms=[settings_stub.jwt_algorithm]
    )
    assert payload["sub"] == "1"


def test_login_user_not_found(monkeypatch):
    conn = _DummyConn(row=None)
    module, audit_service, _, _ = _load_module(monkeypatch, pool=_DummyPool(conn))
    client = _make_client(module, _DummyPool(conn))

    response = client.post("/api/auth/login", json={"email": "user@example.com", "pin": "1234"})

    assert response.status_code == 401
    audit_service.log_auth_event.assert_awaited()


def test_login_inactive(monkeypatch):
    row = {
        "id": "1",
        "email": "user@example.com",
        "name": "User",
        "password_hash": "hash",
        "role": "member",
        "status": "inactive",
        "metadata": None,
        "language_preference": "en",
        "active": False,
        "linked_client_id": None,
        "portal_access": False,
        "avatar": None,
    }
    conn = _DummyConn(row=row)
    module, audit_service, _, _ = _load_module(monkeypatch, pool=_DummyPool(conn))
    client = _make_client(module, _DummyPool(conn))

    response = client.post("/api/auth/login", json={"email": "user@example.com", "pin": "1234"})

    assert response.status_code == 401
    audit_service.log_auth_event.assert_awaited()


def test_login_invalid_pin(monkeypatch):
    row = {
        "id": "1",
        "email": "user@example.com",
        "name": "User",
        "password_hash": "hash",
        "role": "member",
        "status": "active",
        "metadata": None,
        "language_preference": "en",
        "active": True,
        "linked_client_id": None,
        "portal_access": False,
        "avatar": None,
    }
    conn = _DummyConn(row=row)
    module, audit_service, _, _ = _load_module(monkeypatch, pool=_DummyPool(conn))
    client = _make_client(module, _DummyPool(conn))
    monkeypatch.setattr(module, "verify_password", lambda *_args, **_kwargs: False)

    response = client.post("/api/auth/login", json={"email": "user@example.com", "pin": "1234"})

    assert response.status_code == 401
    audit_service.log_auth_event.assert_awaited()


def test_login_success_team_member(monkeypatch):
    row = {
        "id": "1",
        "email": "user@example.com",
        "name": "User",
        "password_hash": "hash",
        "role": "member",
        "status": "active",
        "metadata": None,
        "language_preference": "en",
        "active": True,
        "linked_client_id": None,
        "portal_access": False,
        "avatar": None,
    }
    conn = _DummyConn(row=row)
    module, audit_service, cookie_calls, _ = _load_module(monkeypatch, pool=_DummyPool(conn))
    client = _make_client(module, _DummyPool(conn))
    monkeypatch.setattr(module, "verify_password", lambda *_args, **_kwargs: True)

    response = client.post("/api/auth/login", json={"email": "user@example.com", "pin": "1234"})

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["redirectTo"] == "/dashboard"
    assert cookie_calls["set"]["max_age"] == 1
    audit_service.log_auth_event.assert_awaited()


def test_login_success_client(monkeypatch):
    row = {
        "id": "2",
        "email": "client@example.com",
        "name": "Client",
        "password_hash": "hash",
        "role": "client",
        "status": "active",
        "metadata": None,
        "language_preference": "en",
        "active": True,
        "linked_client_id": 99,
        "portal_access": True,
        "avatar": None,
    }
    conn = _DummyConn(row=row)
    module, _, _, _ = _load_module(monkeypatch, pool=_DummyPool(conn))
    client = _make_client(module, _DummyPool(conn))
    monkeypatch.setattr(module, "verify_password", lambda *_args, **_kwargs: True)

    response = client.post("/api/auth/login", json={"email": "client@example.com", "pin": "1234"})

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["redirectTo"] == "/portal"
    assert data["data"]["user"]["client_id"] == 99


def test_get_profile_invalid_token(monkeypatch):
    conn = _DummyConn(row=None)
    module, _, _, _ = _load_module(monkeypatch, pool=_DummyPool(conn))
    client = _make_client(module, _DummyPool(conn))

    response = client.get("/api/auth/profile", headers={"Authorization": "Bearer bad"})

    assert response.status_code == 401


def test_get_profile_valid_token(monkeypatch):
    row = {
        "id": "1",
        "email": "user@example.com",
        "name": "User",
        "role": "member",
        "status": "active",
        "metadata": None,
        "language_preference": "en",
        "avatar": None,
    }
    conn = _DummyConn(row=row)
    module, _, _, settings_stub = _load_module(monkeypatch, pool=_DummyPool(conn))
    client = _make_client(module, _DummyPool(conn))

    token = jwt.encode(
        {
            "sub": "1",
            "email": "user@example.com",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings_stub.jwt_secret_key,
        algorithm=settings_stub.jwt_algorithm,
    )
    response = client.get("/api/auth/profile", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_logout_clears_cookie(monkeypatch):
    module, _, cookie_calls, _ = _load_module(monkeypatch)
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_current_user] = lambda: {
        "id": "1",
        "email": "u",
        "role": "member",
    }
    client = TestClient(app)

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert cookie_calls["clear"] is True


def test_check_auth(monkeypatch):
    module, _, _, _ = _load_module(monkeypatch)
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_current_user] = lambda: {
        "id": "1",
        "email": "u",
        "role": "member",
    }
    client = TestClient(app)

    response = client.get("/api/auth/check")

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_csrf_token(monkeypatch):
    module, _, _, _ = _load_module(monkeypatch)
    client = _make_client(module, _DummyPool(_DummyConn()))

    response = client.get("/api/auth/csrf-token")

    assert response.status_code == 200
    data = response.json()
    assert len(data["csrfToken"]) == 64
    assert data["sessionId"].startswith("session_")


def test_refresh_token_success(monkeypatch):
    row = {
        "id": "1",
        "email": "user@example.com",
        "name": "User",
        "role": "member",
        "status": "active",
        "metadata": None,
        "language_preference": "en",
        "linked_client_id": None,
        "portal_access": False,
        "avatar": None,
    }
    conn = _DummyConn(row=row)
    module, _, cookie_calls, _ = _load_module(monkeypatch, pool=_DummyPool(conn))
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_database_pool] = lambda: _DummyPool(conn)
    app.dependency_overrides[module.get_current_user] = lambda: {
        "id": "1",
        "email": "user@example.com",
        "role": "member",
    }
    client = TestClient(app)

    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    assert cookie_calls["set"]["max_age"] == 1


def test_refresh_token_user_missing(monkeypatch):
    conn = _DummyConn(row=None)
    module, _, _, _ = _load_module(monkeypatch, pool=_DummyPool(conn))
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_database_pool] = lambda: _DummyPool(conn)
    app.dependency_overrides[module.get_current_user] = lambda: {
        "id": "1",
        "email": "user@example.com",
        "role": "member",
    }
    client = TestClient(app)

    response = client.post("/api/auth/refresh")

    assert response.status_code == 401
