import importlib.util
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request


class _DummyConn:
    def __init__(self, row=None):
        self.row = row

    async def fetchrow(self, _query, *_args):
        return self.row


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


class _PortalService:
    def __init__(self, _pool):
        pass

    async def get_dashboard(self, _client_id):
        return {"dashboard": True}

    async def get_visa_status(self, _client_id):
        return {"visa": True}

    async def get_companies(self, _client_id):
        return [{"id": 1}]

    async def get_company_detail(self, _client_id, _company_id):
        return {"id": _company_id}

    async def set_primary_company(self, _client_id, _company_id):
        return {"primary_company": _company_id}

    async def get_tax_overview(self, _client_id):
        return {"tax": True}

    async def get_documents(self, _client_id, document_type=None):
        return [{"type": document_type}]

    async def upload_document(self, **_kwargs):
        return {"id": 1}

    async def get_messages(self, _client_id, limit, offset):
        return {"limit": limit, "offset": offset}

    async def send_message(self, **_kwargs):
        return {"id": 1}

    async def mark_message_read(self, _client_id, _message_id):
        return None

    async def get_preferences(self, _client_id):
        return {"lang": "en"}

    async def update_preferences(self, _client_id, _updates):
        return _updates


def _load_module(monkeypatch):
    backend_path = Path(__file__).resolve().parents[4] / "backend"

    monkeypatch.setitem(
        sys.modules, "services.portal", types.SimpleNamespace(PortalService=_PortalService)
    )
    monkeypatch.setitem(
        sys.modules, "app.dependencies", types.SimpleNamespace(get_database_pool=lambda: None)
    )

    class _Logger:
        def error(self, *_args, **_kwargs):
            pass

    monkeypatch.setitem(
        sys.modules,
        "app.utils.logging_utils",
        types.SimpleNamespace(get_logger=lambda _name: _Logger()),
    )

    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(backend_path / "app")]
    routers_pkg = types.ModuleType("app.routers")
    routers_pkg.__path__ = [str(backend_path / "app" / "routers")]
    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.routers", routers_pkg)

    module_name = "app.routers.portal"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "routers" / "portal.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_client(module, client_override=None, pool=None, portal_service=None):
    app = FastAPI()
    app.include_router(module.router)
    if client_override is not None:
        app.dependency_overrides[module.get_current_client] = lambda: client_override
    if pool is not None:
        app.dependency_overrides[module.get_database_pool] = lambda: pool
    if portal_service is not None:
        app.dependency_overrides[module.get_portal_service] = lambda: portal_service
    return TestClient(app)


@pytest.mark.asyncio
async def test_get_current_client_no_user(monkeypatch):
    module = _load_module(monkeypatch)
    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)
    pool = _DummyPool(_DummyConn())

    with pytest.raises(module.HTTPException) as exc:
        await module.get_current_client(request, pool)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_client_role_not_client(monkeypatch):
    module = _load_module(monkeypatch)
    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)
    request.state.user = {"role": "member"}
    pool = _DummyPool(_DummyConn())

    with pytest.raises(module.HTTPException) as exc:
        await module.get_current_client(request, pool)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_client_missing_id(monkeypatch):
    module = _load_module(monkeypatch)
    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)
    request.state.user = {"role": "client"}
    pool = _DummyPool(_DummyConn())

    with pytest.raises(module.HTTPException) as exc:
        await module.get_current_client(request, pool)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_client_row_missing(monkeypatch):
    module = _load_module(monkeypatch)
    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)
    request.state.user = {"role": "client", "id": "1"}
    pool = _DummyPool(_DummyConn(row=None))

    with pytest.raises(module.HTTPException) as exc:
        await module.get_current_client(request, pool)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_client_portal_access_false(monkeypatch):
    module = _load_module(monkeypatch)
    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)
    request.state.user = {"role": "client", "id": "1"}
    pool = _DummyPool(
        _DummyConn(
            row={
                "id": "1",
                "email": "e",
                "full_name": "n",
                "linked_client_id": 1,
                "portal_access": False,
            }
        )
    )

    with pytest.raises(module.HTTPException) as exc:
        await module.get_current_client(request, pool)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_client_link_missing(monkeypatch):
    module = _load_module(monkeypatch)
    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)
    request.state.user = {"role": "client", "id": "1"}
    pool = _DummyPool(
        _DummyConn(
            row={
                "id": "1",
                "email": "e",
                "full_name": "n",
                "linked_client_id": None,
                "portal_access": True,
            }
        )
    )

    with pytest.raises(module.HTTPException) as exc:
        await module.get_current_client(request, pool)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_client_success(monkeypatch):
    module = _load_module(monkeypatch)
    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)
    request.state.user = {"role": "client", "id": "1"}
    pool = _DummyPool(
        _DummyConn(
            row={
                "id": "1",
                "email": "e",
                "full_name": "n",
                "linked_client_id": 2,
                "portal_access": True,
            }
        )
    )

    result = await module.get_current_client(request, pool)
    assert result["client_id"] == 2


def test_dashboard_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(
        module, client_override={"client_id": 1}, portal_service=_PortalService(None)
    )

    response = client.get("/api/portal/dashboard")
    assert response.status_code == 200
    assert response.json()["data"]["dashboard"] is True


def test_company_detail_not_found(monkeypatch):
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def get_company_detail(self, _client_id, _company_id):
            return None

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.get("/api/portal/company/1")
    assert response.status_code == 404


def test_set_primary_company_value_error(monkeypatch):
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def set_primary_company(self, _client_id, _company_id):
            raise ValueError("bad")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.post("/api/portal/company/1/select")
    assert response.status_code == 400


def test_upload_document_validations(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(
        module, client_override={"client_id": 1}, portal_service=_PortalService(None)
    )

    response = client.post(
        "/api/portal/documents/upload",
        files={"file": ("", b"data")},
        data={"document_type": "passport"},
    )
    assert response.status_code in [400, 422]

    big_content = b"x" * (10 * 1024 * 1024 + 1)
    response = client.post(
        "/api/portal/documents/upload",
        files={"file": ("doc.pdf", big_content, "application/pdf")},
        data={"document_type": "passport"},
    )
    assert response.status_code == 400

    response = client.post(
        "/api/portal/documents/upload",
        files={"file": ("doc.exe", b"data", "application/octet-stream")},
        data={"document_type": "passport"},
    )
    assert response.status_code == 400


def test_upload_document_success(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(
        module, client_override={"client_id": 1}, portal_service=_PortalService(None)
    )

    response = client.post(
        "/api/portal/documents/upload",
        files={"file": ("doc.pdf", b"data", "application/pdf")},
        data={"document_type": "passport"},
    )
    assert response.status_code == 200


def test_messages_and_settings(monkeypatch):
    module = _load_module(monkeypatch)
    client = _make_client(
        module, client_override={"client_id": 1}, portal_service=_PortalService(None)
    )

    assert client.get("/api/portal/messages").status_code == 200
    assert client.post("/api/portal/messages", json={"content": "hi"}).status_code == 200
    assert client.post("/api/portal/messages/1/read").status_code == 200
    assert client.get("/api/portal/settings").status_code == 200
    assert client.patch("/api/portal/settings", json={}).status_code == 200


def test_profile(monkeypatch):
    module = _load_module(monkeypatch)
    pool = _DummyPool(
        _DummyConn(
            row={
                "id": 1,
                "full_name": "User",
                "email": "u@example.com",
                "phone": None,
                "whatsapp": None,
                "nationality": None,
                "passport_number": None,
                "address": None,
                "created_at": None,
            }
        )
    )
    client = _make_client(module, client_override={"client_id": 1}, pool=pool)

    response = client.get("/api/portal/profile")
    assert response.status_code == 200

    pool_missing = _DummyPool(_DummyConn(row=None))
    client_missing = _make_client(module, client_override={"client_id": 1}, pool=pool_missing)
    response = client_missing.get("/api/portal/profile")
    assert response.status_code == 404


def test_dashboard_error(monkeypatch):
    """Test dashboard exception handler"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def get_dashboard(self, _client_id):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.get("/api/portal/dashboard")
    assert response.status_code == 500


def test_visa_status_success(monkeypatch):
    """Test get visa status"""
    module = _load_module(monkeypatch)
    client = _make_client(
        module, client_override={"client_id": 1}, portal_service=_PortalService(None)
    )
    response = client.get("/api/portal/visa")
    assert response.status_code == 200
    assert response.json()["data"]["visa"] is True


def test_visa_status_error(monkeypatch):
    """Test visa status exception handler"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def get_visa_status(self, _client_id):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.get("/api/portal/visa")
    assert response.status_code == 500


def test_companies_success(monkeypatch):
    """Test get companies"""
    module = _load_module(monkeypatch)
    client = _make_client(
        module, client_override={"client_id": 1}, portal_service=_PortalService(None)
    )
    response = client.get("/api/portal/companies")
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_companies_error(monkeypatch):
    """Test companies exception handler"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def get_companies(self, _client_id):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.get("/api/portal/companies")
    assert response.status_code == 500


def test_company_detail_error(monkeypatch):
    """Test company detail exception handler (non-HTTPException)"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def get_company_detail(self, _client_id, _company_id):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.get("/api/portal/company/1")
    assert response.status_code == 500


def test_set_primary_company_error(monkeypatch):
    """Test set primary company exception handler (non-ValueError)"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def set_primary_company(self, _client_id, _company_id):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.post("/api/portal/company/1/select")
    assert response.status_code == 500


def test_get_tax_overview_success(monkeypatch):
    """Test get tax overview"""
    module = _load_module(monkeypatch)
    client = _make_client(
        module, client_override={"client_id": 1}, portal_service=_PortalService(None)
    )
    response = client.get("/api/portal/taxes")
    assert response.status_code == 200
    assert response.json()["data"]["tax"] is True


def test_get_tax_overview_error(monkeypatch):
    """Test tax overview exception handler"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def get_tax_overview(self, _client_id):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.get("/api/portal/taxes")
    assert response.status_code == 500


def test_get_documents_success(monkeypatch):
    """Test get documents"""
    module = _load_module(monkeypatch)
    client = _make_client(
        module, client_override={"client_id": 1}, portal_service=_PortalService(None)
    )
    response = client.get("/api/portal/documents")
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_get_documents_with_filter(monkeypatch):
    """Test get documents with document_type filter"""
    module = _load_module(monkeypatch)
    client = _make_client(
        module, client_override={"client_id": 1}, portal_service=_PortalService(None)
    )
    response = client.get("/api/portal/documents?document_type=passport")
    assert response.status_code == 200


def test_get_documents_error(monkeypatch):
    """Test documents exception handler"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def get_documents(self, _client_id, document_type=None):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.get("/api/portal/documents")
    assert response.status_code == 500


def test_upload_document_error(monkeypatch):
    """Test upload document exception handler"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def upload_document(self, **_kwargs):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.post(
        "/api/portal/documents/upload",
        files={"file": ("doc.pdf", b"data", "application/pdf")},
        data={"document_type": "passport"},
    )
    assert response.status_code == 500


def test_get_messages_error(monkeypatch):
    """Test get messages exception handler"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def get_messages(self, _client_id, limit, offset):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.get("/api/portal/messages")
    assert response.status_code == 500


def test_send_message_error(monkeypatch):
    """Test send message exception handler"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def send_message(self, **_kwargs):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.post("/api/portal/messages", json={"content": "hi"})
    assert response.status_code == 500


def test_mark_message_read_error(monkeypatch):
    """Test mark message read exception handler"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def mark_message_read(self, _client_id, _message_id):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.post("/api/portal/messages/1/read")
    assert response.status_code == 500


def test_get_preferences_error(monkeypatch):
    """Test get preferences exception handler"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def get_preferences(self, _client_id):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.get("/api/portal/settings")
    assert response.status_code == 500


def test_update_preferences_with_updates(monkeypatch):
    """Test update preferences with actual updates"""
    module = _load_module(monkeypatch)
    client = _make_client(
        module, client_override={"client_id": 1}, portal_service=_PortalService(None)
    )
    response = client.patch(
        "/api/portal/settings", json={"email_notifications": True, "language": "en"}
    )
    assert response.status_code == 200


def test_update_preferences_error(monkeypatch):
    """Test update preferences exception handler"""
    module = _load_module(monkeypatch)

    class _Service(_PortalService):
        async def update_preferences(self, _client_id, _updates):
            raise Exception("Service error")

    client = _make_client(module, client_override={"client_id": 1}, portal_service=_Service(None))
    response = client.patch(
        "/api/portal/settings", json={"email_notifications": True}
    )
    assert response.status_code == 500


def test_get_profile_error(monkeypatch):
    """Test get profile exception handler (non-HTTPException)"""
    module = _load_module(monkeypatch)

    class _ErrorConn:
        async def fetchrow(self, _query, *_args):
            raise Exception("DB error")

    class _ErrorPool:
        def acquire(self):
            return _AcquireCtx(_ErrorConn())

    client = _make_client(module, client_override={"client_id": 1}, pool=_ErrorPool())
    response = client.get("/api/portal/profile")
    assert response.status_code == 500
