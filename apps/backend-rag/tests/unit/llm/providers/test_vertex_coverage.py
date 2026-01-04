import asyncio
import types
from unittest.mock import patch

import pytest
from llm.base import LLMMessage
from llm.providers.vertex import VertexProvider


class DummyModel:
    def __init__(self):
        self.last_prompt = None

    def generate_content(self, prompt):
        self.last_prompt = prompt
        return types.SimpleNamespace(text="ok")


class DummyVertexService:
    def __init__(self, project_id=None, location=None):
        self.project_id = project_id
        self.location = location
        self.model = DummyModel()

    def _ensure_initialized(self):
        return None


class DummyLoop:
    async def run_in_executor(self, _executor, func):
        return func()


def test_vertex_init_import_error():
    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "services.llm_clients.vertex_ai_service":
            raise ImportError("nope")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        provider = VertexProvider()

    assert provider.is_available is False
    with pytest.raises(RuntimeError):
        asyncio.run(provider.generate([LLMMessage(role="user", content="hi")]))


def test_vertex_init_exception():
    module = types.ModuleType("services.llm_clients.vertex_ai_service")

    class VertexAIService:
        def __init__(self, project_id=None, location=None):
            raise RuntimeError("boom")

    module.VertexAIService = VertexAIService
    with patch.dict("sys.modules", {"services.llm_clients.vertex_ai_service": module}):
        provider = VertexProvider()

    assert provider.is_available is False


@pytest.mark.asyncio
async def test_vertex_generate_success():
    module = types.ModuleType("services.llm_clients.vertex_ai_service")
    module.VertexAIService = DummyVertexService
    with patch.dict("sys.modules", {"services.llm_clients.vertex_ai_service": module}):
        provider = VertexProvider(project_id="p1", location="loc")
        with patch("asyncio.get_event_loop", return_value=DummyLoop()):
            messages = [
                LLMMessage(role="system", content="sys"),
                LLMMessage(role="user", content="hi"),
            ]
            response = await provider.generate(messages)

    assert response.content == "ok"
    assert provider.is_available is True
    assert provider._service.model.last_prompt.startswith("sys")
    assert "user: hi" in provider._service.model.last_prompt


@pytest.mark.asyncio
async def test_vertex_stream_yields():
    module = types.ModuleType("services.llm_clients.vertex_ai_service")
    module.VertexAIService = DummyVertexService
    with patch.dict("sys.modules", {"services.llm_clients.vertex_ai_service": module}):
        provider = VertexProvider()
        with patch("asyncio.get_event_loop", return_value=DummyLoop()):
            chunks = []
            async for chunk in provider.stream([LLMMessage(role="user", content="hi")]):
                chunks.append(chunk)
    assert chunks == ["ok"]
