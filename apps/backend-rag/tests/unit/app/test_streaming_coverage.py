import importlib.util
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_module(monkeypatch, validate_user=None):
    async def _validate_auth_mixed(**_kwargs):
        return validate_user

    monkeypatch.setitem(
        sys.modules,
        "app.auth.validation",
        types.SimpleNamespace(validate_auth_mixed=_validate_auth_mixed),
    )

    def get_request_state(state, key, expected_type=None):
        value = getattr(state, key, None)
        if expected_type and not isinstance(value, expected_type):
            return None
        return value

    def get_app_state(state, key, default=None):
        return getattr(state, key, default)

    monkeypatch.setitem(
        sys.modules,
        "app.utils.state_helpers",
        types.SimpleNamespace(get_app_state=get_app_state, get_request_state=get_request_state),
    )

    @contextmanager
    def trace_span(*_args, **_kwargs):
        yield None

    monkeypatch.setitem(
        sys.modules,
        "app.utils.tracing",
        types.SimpleNamespace(
            add_span_event=lambda *_args, **_kwargs: None,
            set_span_status=lambda *_args, **_kwargs: None,
            trace_span=trace_span,
        ),
    )

    monkeypatch.setitem(
        sys.modules,
        "services.routing.intelligent_router",
        types.SimpleNamespace(IntelligentRouter=object),
    )

    backend_path = Path(__file__).resolve().parents[3] / "backend"
    module_name = "app.streaming"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "app" / "streaming.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _DummyRouter:
    async def stream_chat(self, **_kwargs):
        yield {"type": "token", "data": "hello"}
        yield {"type": "done", "data": None}


class _DummyCollaborator:
    def __init__(self, name="User", role="member", identifier="u1"):
        self.name = name
        self.role = role
        self.id = identifier


class _DummyCollaboratorService:
    async def identify(self, _email):
        return _DummyCollaborator()


class _DummyMemory:
    profile_facts = ["fact"]
    summary = "summary"
    counters = {"count": 1}


class _DummyMemoryService:
    async def get_memory(self, _user_id):
        return _DummyMemory()


def _make_client(module, user=None, services_initialized=True):
    app = FastAPI()
    app.include_router(module.router)

    @app.middleware("http")
    async def _inject_state(request, call_next):
        if user is not None:
            request.state.user = user
        return await call_next(request)

    app.state.services_initialized = services_initialized
    app.state.intelligent_router = _DummyRouter()
    app.state.collaborator_service = _DummyCollaboratorService()
    app.state.memory_service = _DummyMemoryService()
    return TestClient(app)


def test_parse_history():
    module = _load_module(pytest.MonkeyPatch())
    assert module._parse_history(None) == []
    assert module._parse_history("not-json") == []
    assert module._parse_history('[{"role":"user","content":"hi"}]') == [
        {"role": "user", "content": "hi"}
    ]


def test_get_stream_auth_required(monkeypatch):
    module = _load_module(monkeypatch, validate_user=None)
    client = _make_client(module, user=None, services_initialized=True)

    response = client.get("/bali-zero/chat-stream", params={"query": "hi"})

    assert response.status_code == 401


def test_get_stream_success(monkeypatch):
    module = _load_module(monkeypatch, validate_user=None)
    client = _make_client(module, user={"email": "user@example.com"}, services_initialized=True)

    with client.stream("GET", "/bali-zero/chat-stream", params={"query": "hi"}) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert '"type": "metadata"' in body
    assert '"type": "token"' in body
    assert '"type": "done"' in body


def test_get_stream_services_not_ready(monkeypatch):
    module = _load_module(monkeypatch, validate_user={"email": "user@example.com"})
    client = _make_client(module, user=None, services_initialized=False)

    response = client.get("/bali-zero/chat-stream", params={"query": "hi"})

    assert response.status_code == 503


def test_post_stream_message_required(monkeypatch):
    module = _load_module(monkeypatch, validate_user={"email": "user@example.com"})
    client = _make_client(module, user=None, services_initialized=True)

    response = client.post("/api/chat/stream", json={"message": "   "})

    assert response.status_code == 400


def test_post_stream_success(monkeypatch):
    module = _load_module(monkeypatch, validate_user=None)
    client = _make_client(module, user={"email": "user@example.com"}, services_initialized=True)
    client.app.state.conversation_service = types.SimpleNamespace(
        get_history=AsyncMock(
            return_value={"messages": [{"role": "user", "content": "hi"}], "source": "db"}
        ),
        save_conversation=AsyncMock(),
    )

    with client.stream("POST", "/api/chat/stream", json={"message": "hello"}) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert '"type": "metadata"' in body
