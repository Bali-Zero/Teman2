import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from jose import jwt


def _load_module(
    monkeypatch,
    api_auth_enabled=True,
    api_auth_bypass_db=False,
    csrf_enabled=True,
    allowed_origin="http://example.com",
):
    settings_stub = types.SimpleNamespace(
        api_auth_enabled=api_auth_enabled,
        api_auth_bypass_db=api_auth_bypass_db,
        csrf_enabled=csrf_enabled,
        jwt_secret_key="secret",
        jwt_algorithm="HS256",
        zantara_allowed_origins=allowed_origin,
        dev_origins="",
        redis_url='redis://localhost:6379'
    )
    monkeypatch.setitem(
        sys.modules, "app.core.config", types.SimpleNamespace(settings=settings_stub, redis_url='redis://localhost:6379')
    )

    class _APIKeyAuth:
        def __init__(self):
            self.valid = "valid-key"

        def validate_api_key(self, key):
            if key == self.valid:
                return {"email": "svc@example.com", "role": "service", "auth_method": "api_key"}
            return None

        def get_service_stats(self):
            return {"total": 1}

    monkeypatch.setitem(
        sys.modules, "app.services.api_key_auth", types.SimpleNamespace(APIKeyAuth=_APIKeyAuth, redis_url='redis://localhost:6379')
    )

    cookie_state = {"token": None, "csrf_valid": True, "csrf_exempt": False}

    def get_jwt_from_cookie(_request):
        return cookie_state["token"]

    def is_csrf_exempt(_request):
        return cookie_state["csrf_exempt"]

    def validate_csrf(_request):
        return cookie_state["csrf_valid"]

    monkeypatch.setitem(
        sys.modules,
        "app.utils.cookie_auth",
        types.SimpleNamespace(
            get_jwt_from_cookie=get_jwt_from_cookie,
            is_csrf_exempt=is_csrf_exempt,
            validate_csrf=validate_csrf,
            redis_url='redis://localhost:6379'
        ),
    )

    backend_path = Path(__file__).resolve().parents[3] / "backend"
    module_name = "middleware.hybrid_auth"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "middleware" / "hybrid_auth.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module, cookie_state, settings_stub


def _make_client(module, protected_handler=None):
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"ok": True}

    if protected_handler is None:

        @app.get("/private")
        async def private():
            return {"ok": True}
    else:
        app.add_api_route("/private", protected_handler, methods=["GET"])

    @app.options("/private")
    async def private_options():
        return JSONResponse({"ok": True})

    app.add_middleware(module.HybridAuthMiddleware)
    return TestClient(app)


def test_options_passthrough(monkeypatch):
    module, _, _ = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.options("/private")

    assert response.status_code == 200


def test_public_endpoint(monkeypatch):
    module, _, _ = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Auth-Type"] == "public"


def test_auth_missing_returns_401_with_cors(monkeypatch):
    module, _, _ = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/private", headers={"Origin": "http://example.com"})

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://example.com"


def test_api_key_auth_success(monkeypatch):
    module, _, _ = _load_module(monkeypatch)
    client = _make_client(module)

    response = client.get("/private", headers={"X-API-Key": "valid-key"})

    assert response.status_code == 200
    assert response.headers["X-Auth-Type"] == "api_key"


def test_cookie_auth_csrf_failure(monkeypatch):
    module, cookie_state, _ = _load_module(monkeypatch, csrf_enabled=True)
    cookie_state["token"] = "jwt"
    cookie_state["csrf_valid"] = False
    client = _make_client(module)

    response = client.get("/private")

    assert response.status_code == 401


def test_cookie_auth_success(monkeypatch):
    module, cookie_state, settings_stub = _load_module(monkeypatch, csrf_enabled=False)
    token = jwt.encode(
        {"sub": "1", "email": "user@example.com"},
        settings_stub.jwt_secret_key,
        algorithm=settings_stub.jwt_algorithm,
    )
    cookie_state["token"] = token
    client = _make_client(module)

    response = client.get("/private")

    assert response.status_code == 200
    assert response.headers["X-Auth-Type"] == "jwt_cookie"


def test_header_jwt_bypassed(monkeypatch):
    module, _, _ = _load_module(monkeypatch, api_auth_bypass_db=True)
    client = _make_client(module)

    response = client.get("/private", headers={"Authorization": "Bearer token"})

    assert response.status_code == 401


def test_http_exception_serialization(monkeypatch):
    module, _, _ = _load_module(monkeypatch)
    monkeypatch.setattr(
        module.HybridAuthMiddleware,
        "authenticate_request",
        AsyncMock(
            side_effect=HTTPException(status_code=418, detail={"pool": object(), "ok": True})
        ),
    )
    client = _make_client(module)

    response = client.get("/private", headers={"X-API-Key": "valid-key"})

    assert response.status_code == 418
    detail = response.json()["detail"]
    assert detail["ok"] is True
    assert "object" in detail["pool"]


def test_dispatch_handles_unexpected_error(monkeypatch):
    module, _, _ = _load_module(monkeypatch)
    monkeypatch.setattr(
        module.HybridAuthMiddleware,
        "authenticate_request",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    client = _make_client(module)

    response = client.get("/private")

    assert response.status_code == 503
    assert "Authentication service temporarily unavailable" in response.json()["detail"]
