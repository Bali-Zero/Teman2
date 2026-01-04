import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


def _load_module(monkeypatch, genai_available=True, genai_client=None):
    class ResourceExhausted(Exception):
        pass

    class ServiceUnavailable(Exception):
        pass

    google_exceptions = types.SimpleNamespace(
        ResourceExhausted=ResourceExhausted, ServiceUnavailable=ServiceUnavailable
    )
    monkeypatch.setitem(sys.modules, "google.api_core.exceptions", google_exceptions)

    genai_stub = types.SimpleNamespace(
        GENAI_AVAILABLE=genai_available,
        get_genai_client=lambda: genai_client,
    )
    monkeypatch.setitem(sys.modules, "llm.genai_client", genai_stub)

    prompts_stub = types.SimpleNamespace(
        FEW_SHOT_EXAMPLES=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ],
        SYSTEM_INSTRUCTION="system",
    )
    monkeypatch.setitem(sys.modules, "prompts.jaksel_persona", prompts_stub)

    settings_stub = types.SimpleNamespace(google_api_key="key", openrouter_api_key="key")
    monkeypatch.setitem(
        sys.modules, "app.core.config", types.SimpleNamespace(settings=settings_stub)
    )

    backend_path = Path(__file__).resolve().parents[4] / "backend"
    module_name = "services.llm_clients.gemini_service"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(
        module_name, backend_path / "services" / "llm_clients" / "gemini_service.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module, ResourceExhausted, ServiceUnavailable


class _DummyChat:
    def __init__(self, chunks, error=None):
        self.chunks = chunks
        self.error = error

    async def send_message_stream(self, _message):
        if self.error:
            raise self.error
        for chunk in self.chunks:
            yield chunk


class _DummyGenAIClient:
    def __init__(self, available=True, chat=None):
        self.is_available = available
        self._chat = chat
        self._auth_method = "test"

    def create_chat(self, model, system_instruction, history):
        return self._chat


@pytest.mark.asyncio
async def test_generate_response_stream_gemini_success(monkeypatch):
    chat = _DummyChat(["a", "b"])
    client = _DummyGenAIClient(available=True, chat=chat)
    module, _, _ = _load_module(monkeypatch, genai_client=client)

    service = module.GeminiJakselService()
    chunks = []
    async for chunk in service.generate_response_stream("hello"):
        chunks.append(chunk)

    assert chunks == ["a", "b"]


@pytest.mark.asyncio
async def test_generate_response_stream_fallback(monkeypatch):
    chat = _DummyChat([], error=RuntimeError("429"))
    client = _DummyGenAIClient(available=True, chat=chat)
    module, _, _ = _load_module(monkeypatch, genai_client=client)
    service = module.GeminiJakselService()

    async def _fallback(_message, _history, _context):
        for chunk in ["x", "y"]:
            yield chunk

    service._fallback_to_openrouter_stream = _fallback

    chunks = []
    async for chunk in service.generate_response_stream("hello"):
        chunks.append(chunk)

    assert chunks == ["x", "y"]


@pytest.mark.asyncio
async def test_generate_response_fallback(monkeypatch):
    client = _DummyGenAIClient(available=False, chat=None)
    module, _, _ = _load_module(monkeypatch, genai_client=client)
    service = module.GeminiJakselService()
    service._fallback_to_openrouter = AsyncMock(return_value="fallback")

    result = await service.generate_response("hello")

    assert result == "fallback"


def test_convert_to_openai_messages(monkeypatch):
    client = _DummyGenAIClient(available=False, chat=None)
    module, _, _ = _load_module(monkeypatch, genai_client=client)
    service = module.GeminiJakselService()

    messages = service._convert_to_openai_messages(
        message="hello",
        history=[{"role": "user", "content": "prev"}],
        context="ctx",
    )

    assert messages[0]["role"] == "system"
    assert "CONTEXT" in messages[-1]["content"]


@pytest.mark.asyncio
async def test_openrouter_fallback_missing(monkeypatch):
    client = _DummyGenAIClient(available=False, chat=None)
    module, _, _ = _load_module(monkeypatch, genai_client=client)
    service = module.GeminiJakselService()

    with pytest.raises(RuntimeError, match="OpenRouter fallback not available"):
        await service._fallback_to_openrouter("hello", None, "")


@pytest.mark.asyncio
async def test_gemini_service_wrapper(monkeypatch):
    client = _DummyGenAIClient(available=False, chat=None)
    module, _, _ = _load_module(monkeypatch, genai_client=client)
    service = module.GeminiService()
    service._service.generate_response = AsyncMock(return_value="ok")

    result = await service.generate_response("hi", context=["a", "b"])

    assert result == "ok"
