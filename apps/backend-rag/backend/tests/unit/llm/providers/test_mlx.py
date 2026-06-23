"""
Unit tests for MLXProvider (OpenAI-compatible MLX server adapter).

Exercises generate() / stream() against a mocked httpx client (no live MLX
server needed), plus registry registration and the OpenAI-contract mapping that
ollama.py does NOT cover (choices[].message.content + usage.total_tokens).
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.llm.base import LLMMessage, LLMResponse
from backend.llm.providers.mlx import MLXProvider


@pytest.fixture
def mlx_provider():
    """MLXProvider with default model/url (connectivity deferred to first call)."""
    provider = MLXProvider(model="mlx-community/Qwen3-8B-4bit")
    provider._async_client = None
    return provider


class TestMLXProviderInit:
    def test_init_defaults(self):
        provider = MLXProvider()
        assert provider.name == "mlx"
        assert provider._base_url == "http://localhost:8080"
        # /v1 is appended internally, chat endpoint resolved.
        assert provider._chat_url == "http://localhost:8080/v1/chat/completions"
        assert provider.is_available is True

    def test_init_custom_url_without_v1(self):
        provider = MLXProvider(base_url="http://mini:8080")
        assert provider._chat_url == "http://mini:8080/v1/chat/completions"

    def test_init_url_already_has_v1_is_not_doubled(self):
        # Tolerate callers that pass the /v1 suffix already.
        provider = MLXProvider(base_url="http://localhost:8080/v1")
        assert provider._chat_url == "http://localhost:8080/v1/chat/completions"

    def test_init_trailing_slash_stripped(self):
        provider = MLXProvider(base_url="http://localhost:8080/")
        assert provider._chat_url == "http://localhost:8080/v1/chat/completions"


class TestMLXProviderGenerate:
    @pytest.mark.asyncio
    async def test_generate_maps_openai_response_to_llmresponse(self, mlx_provider):
        """content from choices[0].message.content, tokens from usage.total_tokens."""
        mock_data = {
            "model": "mlx-community/Qwen3-8B-4bit",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "  Hello from MLX  "},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mlx_provider._get_async_client = AsyncMock(return_value=mock_client)

        resp = await mlx_provider.generate([LLMMessage(role="user", content="hi")])

        assert isinstance(resp, LLMResponse)
        assert resp.content == "Hello from MLX"  # stripped
        assert resp.model == "mlx-community/Qwen3-8B-4bit"
        assert resp.tokens_used == 15
        assert resp.finish_reason == "stop"
        assert resp.provider == "mlx"

    @pytest.mark.asyncio
    async def test_generate_sends_openai_messages_array(self, mlx_provider):
        """The request body must use the OpenAI `messages` array, not a flat prompt."""
        captured = {}

        async def fake_post(url, json):
            captured["url"] = url
            captured["json"] = json
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
            return mock_response

        mock_client = AsyncMock()
        mock_client.post = fake_post
        mlx_provider._get_async_client = AsyncMock(return_value=mock_client)

        await mlx_provider.generate(
            [
                LLMMessage(role="system", content="be brief"),
                LLMMessage(role="user", content="hi"),
            ]
        )

        assert captured["url"].endswith("/v1/chat/completions")
        assert captured["json"]["messages"] == [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hi"},
        ]
        assert captured["json"]["stream"] is False
        # Qwen3 reasoning-mode suppressed by default (verified live 2026-06-20).
        assert captured["json"]["chat_template_kwargs"] == {"enable_thinking": False}

    @pytest.mark.asyncio
    async def test_generate_enable_thinking_opt_in(self, mlx_provider):
        """Callers can re-enable reasoning explicitly."""
        captured = {}

        async def fake_post(url, json):
            captured["json"] = json
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
            return mock_response

        mock_client = AsyncMock()
        mock_client.post = fake_post
        mlx_provider._get_async_client = AsyncMock(return_value=mock_client)

        await mlx_provider.generate(
            [LLMMessage(role="user", content="hi")], enable_thinking=True
        )

        assert captured["json"]["chat_template_kwargs"] == {"enable_thinking": True}

    @pytest.mark.asyncio
    async def test_generate_drops_ollama_think_kwarg(self, mlx_provider):
        """`think` is Ollama-native; MLX/OpenAI must never receive it."""
        captured = {}

        async def fake_post(url, json):
            captured["json"] = json
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
            return mock_response

        mock_client = AsyncMock()
        mock_client.post = fake_post
        mlx_provider._get_async_client = AsyncMock(return_value=mock_client)

        await mlx_provider.generate([LLMMessage(role="user", content="hi")], think=False)

        assert "think" not in captured["json"]

    @pytest.mark.asyncio
    async def test_generate_unavailable_raises(self):
        provider = MLXProvider()
        provider._available = False
        with pytest.raises(RuntimeError, match="not available"):
            await provider.generate([LLMMessage(role="user", content="x")])

    @pytest.mark.asyncio
    async def test_generate_non_200_raises(self, mlx_provider):
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mlx_provider._get_async_client = AsyncMock(return_value=mock_client)

        with pytest.raises(RuntimeError, match="MLX API error: 503"):
            await mlx_provider.generate([LLMMessage(role="user", content="x")])


class TestMLXProviderStream:
    @pytest.mark.asyncio
    async def test_stream_yields_openai_deltas(self, mlx_provider):
        """Stream parses OpenAI SSE `data: {...}` delta frames, ends on [DONE]."""
        lines = [
            'data: {"choices":[{"delta":{"content":"Hel"}}]}',
            'data: {"choices":[{"delta":{"content":"lo"}}]}',
            "",  # keep-alive blank line ignored
            'data: {"choices":[{"delta":{}}]}',  # empty delta ignored
            "data: [DONE]",
        ]

        async def mock_aiter_lines():
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        @asynccontextmanager
        async def mock_stream_ctx(*args, **kwargs):
            yield mock_response

        mock_client = MagicMock()
        mock_client.stream = mock_stream_ctx
        mlx_provider._get_async_client = AsyncMock(return_value=mock_client)

        chunks = [c async for c in mlx_provider.stream([LLMMessage(role="user", content="x")])]

        assert chunks == ["Hel", "lo"]
        assert all(isinstance(c, str) for c in chunks)


class TestMLXRegistry:
    def test_mlx_registered_in_provider_registry(self):
        from backend.llm.provider_registry import get_provider, list_providers

        assert "mlx" in list_providers()
        provider = get_provider("mlx", model="mlx-community/Qwen3-8B-4bit")
        assert provider is not None
        assert provider.name == "mlx"
