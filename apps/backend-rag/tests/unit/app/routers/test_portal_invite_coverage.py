import importlib.util
import sys
import types
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_module(monkeypatch, invite_service=None, email_service=None):
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    async def get_database_pool():
        return None

    async def get_current_user():
        return {"email": "team@example.com", "role": "admin"}

    if invite_service is None:

        class _InviteService:
            def __init__(self, _pool):
                self.pool = _pool

            async def create_invitation(self, **_kwargs):
                return {
                    "invite_url": "/portal/register?token=tok",
                    "client_name": "Client",
                    "client_id": 1,
                    "invitation_id": 2,
                    "email": "client@example.com",
                }

            async def get_client_invitations(self, _client_id):
                return [{"id": 1}]

            async def resend_invitation(self, **_kwargs):
                return {"invite_url": "/portal/register?token=tok2"}

            async def validate_token(self, _token):
                return {
                    "client_name": "Client",
                    "email": "client@example.com",
                    "invitation_id": 1,
                    "client_id": 2,
                }

            async def complete_registration(self, **_kwargs):
                return {"user_id": "user-1", "email": "client@example.com"}

        invite_service = _InviteService

    if email_service is None:

        class _EmailService:
            def __init__(self, _pool):
                self.pool = _pool

            async def send_email(self, **_kwargs):
                return None

        email_service = _EmailService

    class _Logger:
        def info(self, *_args, **_kwargs):
            pass

        def warning(self, *_args, **_kwargs):
            pass

        def error(self, *_args, **_kwargs):
            pass

    monkeypatch.setitem(
        sys.modules,
        "app.core.config",
        types.SimpleNamespace(settings=types.SimpleNamespace(frontend_url="https://front")),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.dependencies",
        types.SimpleNamespace(
            get_current_user=get_current_user, get_database_pool=get_database_pool
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.utils.logging_utils",
        types.SimpleNamespace(get_logger=lambda _name: _Logger()),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.portal",
        types.SimpleNamespace(InviteService=invite_service),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.integrations.zoho_email_service",
        types.SimpleNamespace(ZohoEmailService=email_service),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.portal_invite"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "portal_invite.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_client(module, user):
    app = FastAPI()
    app.include_router(module.router)
    app.dependency_overrides[module.get_current_user] = lambda: user
    app.dependency_overrides[module.get_database_pool] = lambda: None
    app.dependency_overrides[module.get_invite_service] = lambda: module.InviteService(None)
    app.dependency_overrides[module.get_email_service] = lambda: module.ZohoEmailService(None)
    return TestClient(app)


def test_send_invitation_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module, {"email": "team@example.com", "role": "admin"})

    response = client.post(
        "/api/portal/invite/send",
        json={"client_id": 1, "email": "client@example.com"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["email_sent"] is True


def test_send_invitation_client_forbidden(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module, {"email": "client@example.com", "role": "client"})

    response = client.post(
        "/api/portal/invite/send",
        json={"client_id": 1, "email": "client@example.com"},
    )

    assert response.status_code == 403


def test_send_invitation_email_error(monkeypatch):
    class _EmailService:
        def __init__(self, _pool):
            self.pool = _pool

        async def send_email(self, **_kwargs):
            raise RuntimeError("email down")

    module = _load_module(monkeypatch, email_service=_EmailService)
    client = _make_client(module, {"email": "team@example.com", "role": "admin"})

    response = client.post(
        "/api/portal/invite/send",
        json={"client_id": 1, "email": "client@example.com"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["email_sent"] is False
    assert "email down" in payload["email_error"]


def test_send_invitation_value_error(monkeypatch):
    class _InviteService:
        def __init__(self, _pool):
            self.pool = _pool

        async def create_invitation(self, **_kwargs):
            raise ValueError("bad client")

    module = _load_module(monkeypatch, invite_service=_InviteService)
    client = _make_client(module, {"email": "team@example.com", "role": "admin"})

    response = client.post(
        "/api/portal/invite/send",
        json={"client_id": 1, "email": "client@example.com"},
    )

    assert response.status_code == 400
    assert "bad client" in response.json()["detail"]


def test_get_client_invitations_forbidden(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module, {"email": "client@example.com", "role": "client"})

    response = client.get("/api/portal/invite/client/1")

    assert response.status_code == 403


def test_get_client_invitations_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module, {"email": "team@example.com", "role": "admin"})

    response = client.get("/api/portal/invite/client/1")

    assert response.status_code == 200
    assert response.json()["data"] == [{"id": 1}]


def test_resend_invitation_forbidden(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module, {"email": "client@example.com", "role": "client"})

    response = client.post("/api/portal/invite/resend/1")

    assert response.status_code == 403


def test_resend_invitation_value_error(monkeypatch):
    class _InviteService:
        def __init__(self, _pool):
            self.pool = _pool

        async def resend_invitation(self, **_kwargs):
            raise ValueError("bad")

    module = _load_module(monkeypatch, invite_service=_InviteService)
    client = _make_client(module, {"email": "team@example.com", "role": "admin"})

    response = client.post("/api/portal/invite/resend/1")

    assert response.status_code == 400


def test_validate_token_invalid(monkeypatch):
    class _InviteService:
        def __init__(self, _pool):
            self.pool = _pool

        async def validate_token(self, _token):
            return None

    module = _load_module(monkeypatch, invite_service=_InviteService)
    client = _make_client(module, {"email": "team@example.com", "role": "admin"})

    response = client.get("/api/portal/invite/validate/tok")

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["error"] == "invalid_token"


def test_validate_token_error(monkeypatch):
    class _InviteService:
        def __init__(self, _pool):
            self.pool = _pool

        async def validate_token(self, _token):
            return {"error": "expired", "message": "expired"}

    module = _load_module(monkeypatch, invite_service=_InviteService)
    client = _make_client(module, {"email": "team@example.com", "role": "admin"})

    response = client.get("/api/portal/invite/validate/tok")

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["error"] == "expired"


def test_complete_registration_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(module, {"email": "team@example.com", "role": "admin"})

    response = client.post(
        "/api/portal/invite/complete",
        json={"token": "tok", "pin": "1234"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["redirect_to"] == "/login"


def test_complete_registration_value_error(monkeypatch):
    class _InviteService:
        def __init__(self, _pool):
            self.pool = _pool

        async def complete_registration(self, **_kwargs):
            raise ValueError("bad")

    module = _load_module(monkeypatch, invite_service=_InviteService)
    client = _make_client(module, {"email": "team@example.com", "role": "admin"})

    response = client.post(
        "/api/portal/invite/complete",
        json={"token": "tok", "pin": "1234"},
    )

    assert response.status_code == 400
