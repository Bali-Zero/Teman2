import types
from unittest.mock import patch

import pytest
from backend.llm.base import LLMMessage, LLMResponse
from backend.llm.client import UnifiedLLMClient, create_default_client


class DummyProvider:
    def __init__(self, name, available=True, response=None, stream_chunks=None, error=None):
        self._name = name
        self._available = available
        self._response = response
        self._stream_chunks = stream_chunks or []
        self._error = error
        self.generate_calls = 0
        self.stream_calls = 0

    @property
    def name(self):
        return self._name

    @property
    def is_available(self):
        return self._available

    async def generate(self, messages, temperature=0.7, max_tokens=4096, **kwargs):
        self.generate_calls += 1
        if self._error:
            raise self._error
        return self._response

    async def stream(self, messages, temperature=0.7, **kwargs):
        self.stream_calls += 1
        if self._error:
            raise self._error
        for chunk in self._stream_chunks:
            yield chunk


@pytest.mark.asyncio
async def test_generate_skips_unavailable_and_returns_first_success():
    msg = [LLMMessage(role="user", content="hi")]
    provider1 = DummyProvider("p1", available=False)
    provider2 = DummyProvider(
        "p2",
        available=True,
        response=LLMResponse(content="ok", model="m", tokens_used=1, provider="p2"),
    )
    client = UnifiedLLMClient([provider1, provider2])
    response = await client.generate(msg)
    assert response.content == "ok"
    assert provider1.generate_calls == 0
    assert provider2.generate_calls == 1


@pytest.mark.asyncio
async def test_generate_fallback_on_error():
    msg = [LLMMessage(role="user", content="hi")]
    provider1 = DummyProvider("p1", available=True, error=RuntimeError("fail"))
    provider2 = DummyProvider(
        "p2",
        available=True,
        response=LLMResponse(content="ok", model="m", tokens_used=1, provider="p2"),
    )
    client = UnifiedLLMClient([provider1, provider2])
    response = await client.generate(msg)
    assert response.content == "ok"
    assert provider1.generate_calls == 1
    assert provider2.generate_calls == 1


@pytest.mark.asyncio
async def test_generate_all_fail_raises():
    msg = [LLMMessage(role="user", content="hi")]
    provider1 = DummyProvider("p1", available=True, error=RuntimeError("fail1"))
    provider2 = DummyProvider("p2", available=True, error=RuntimeError("fail2"))
    client = UnifiedLLMClient([provider1, provider2])
    with pytest.raises(RuntimeError) as exc:
        await client.generate(msg)
    assert "All providers failed" in str(exc.value)


@pytest.mark.asyncio
async def test_stream_fallback_and_yields():
    msg = [LLMMessage(role="user", content="hi")]
    provider1 = DummyProvider("p1", available=True, error=RuntimeError("stream fail"))
    provider2 = DummyProvider("p2", available=True, stream_chunks=["a", "b"])
    client = UnifiedLLMClient([provider1, provider2])
    chunks = []
    async for chunk in client.stream(msg):
        chunks.append(chunk)
    assert chunks == ["a", "b"]
    assert provider1.stream_calls == 1
    assert provider2.stream_calls == 1


@pytest.mark.asyncio
async def test_stream_all_fail_raises():
    msg = [LLMMessage(role="user", content="hi")]
    provider1 = DummyProvider("p1", available=True, error=RuntimeError("fail1"))
    provider2 = DummyProvider("p2", available=True, error=RuntimeError("fail2"))
    client = UnifiedLLMClient([provider1, provider2])
    with pytest.raises(RuntimeError) as exc:
        async for _ in client.stream(msg):
            pass
    assert "All providers failed for streaming" in str(exc.value)


def test_get_available_providers():
    provider1 = DummyProvider("p1", available=True)
    provider2 = DummyProvider("p2", available=False)
    client = UnifiedLLMClient([provider1, provider2])
    assert client.get_available_providers() == ["p1"]


def test_create_default_client_uses_provider_chain():
    providers_module = types.ModuleType("backend.llm.providers")

    class GeminiProvider:
        def __init__(self):
            self.name = "gemini"
            self.is_available = True

    class OpenRouterProvider:
        def __init__(self, tier="rag"):
            self.name = f"openrouter:{tier}"
            self.is_available = True

    class DeepSeekProvider:
        def __init__(self):
            self.name = "deepseek"
            self.is_available = True

    providers_module.GeminiProvider = GeminiProvider
    providers_module.OpenRouterProvider = OpenRouterProvider
    providers_module.DeepSeekProvider = DeepSeekProvider

    with patch.dict("sys.modules", {"backend.llm.providers": providers_module}):
        client = create_default_client()

    names = [p.name for p in client.providers]
    assert names == ["gemini", "openrouter:rag", "deepseek"]
