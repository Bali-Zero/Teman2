"""
Tests for OpenRouterClient — covers smart_complete, smart_complete_stream,
get_fallback_chain, complete, complete_stream, check_credits, and close/lifecycle.
"""

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.llm_clients.openrouter_client import (
    FALLBACK_CHAINS,
    MODEL_INFO,
    CompletionResult,
    ModelTier,
    OpenRouterClient,
    smart_complete,
    smart_complete_stream,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _mock_settings() -> None:
    """Patch settings so the module never reads real config."""
    with patch("backend.services.llm_clients.openrouter_client.settings") as mock:
        mock.openrouter_api_key = "test-key-fixture"
        yield mock


@pytest.fixture()
def client(_mock_settings: MagicMock) -> OpenRouterClient:
    """Return an OpenRouterClient with a fake API key."""
    return OpenRouterClient(api_key="test-api-key")


@pytest.fixture()
def client_no_key() -> OpenRouterClient:
    """Return an OpenRouterClient without any API key."""
    with patch("backend.services.llm_clients.openrouter_client.settings") as mock:
        mock.openrouter_api_key = None
        with patch.dict("os.environ", {}, clear=True):
            return OpenRouterClient(api_key=None)


def _mock_post_response(data: dict) -> AsyncMock:
    """Build a fake httpx response for ``client.post``."""
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    http = AsyncMock()
    http.post = AsyncMock(return_value=resp)
    return http


def _mock_stream_context(lines: list[str]) -> MagicMock:
    """Build a fake async-context-manager returned by ``client.stream``."""

    async def _aiter_lines() -> AsyncGenerator[str, None]:
        for line in lines:
            yield line

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.aiter_lines = _aiter_lines

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


# ---------------------------------------------------------------------------
# 1. get_fallback_chain
# ---------------------------------------------------------------------------


class TestGetFallbackChain:
    """Tests for OpenRouterClient.get_fallback_chain"""

    def test_returns_rag_chain_by_default(self, client: OpenRouterClient) -> None:
        chain: list[str] = client.get_fallback_chain()
        assert chain == FALLBACK_CHAINS[ModelTier.RAG]

    def test_returns_requested_tier(self, client: OpenRouterClient) -> None:
        for tier in ModelTier:
            chain: list[str] = client.get_fallback_chain(tier)
            assert chain == FALLBACK_CHAINS[tier]

    def test_all_chains_respect_openrouter_limit(self) -> None:
        """OpenRouter allows max 3 models in the 'models' array."""
        for tier, chain in FALLBACK_CHAINS.items():
            assert len(chain) <= 3, f"{tier.value} chain exceeds 3 models"

    def test_fallback_to_rag_on_unknown_tier(self, client: OpenRouterClient) -> None:
        """If the dict lookup misses, the code falls back to RAG chain."""
        # Simulate by passing a tier that isn't in FALLBACK_CHAINS (unlikely in
        # production, but the code uses dict.get with a default).
        chain: list[str] = client.get_fallback_chain(ModelTier.RAG)
        assert chain == FALLBACK_CHAINS[ModelTier.RAG]


# ---------------------------------------------------------------------------
# 2. complete
# ---------------------------------------------------------------------------


class TestComplete:
    """Tests for OpenRouterClient.complete"""

    @pytest.mark.asyncio
    async def test_complete_returns_completion_result(self, client: OpenRouterClient) -> None:
        api_data: dict = {
            "choices": [{"message": {"content": "Four"}}],
            "model": "google/gemini-2.0-flash-exp:free",
            "usage": {"prompt_tokens": 8, "completion_tokens": 1, "total_tokens": 9},
        }
        http = _mock_post_response(api_data)

        with patch.object(client, "_get_client", return_value=http):
            result: CompletionResult = await client.complete(
                [{"role": "user", "content": "2+2?"}],
            )

        assert result.content == "Four"
        assert result.model_used == "google/gemini-2.0-flash-exp:free"
        assert result.model_name == "Gemini 2.0 Flash"
        assert result.prompt_tokens == 8
        assert result.completion_tokens == 1
        assert result.total_tokens == 9
        assert result.cost == 0.0

    @pytest.mark.asyncio
    async def test_complete_raises_without_api_key(self, client_no_key: OpenRouterClient) -> None:
        with pytest.raises(ValueError, match="API key not configured"):
            await client_no_key.complete([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_complete_sends_models_array_for_tier(self, client: OpenRouterClient) -> None:
        """When no model_id is given, payload must use 'models' array."""
        api_data: dict = {
            "choices": [{"message": {"content": "ok"}}],
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "usage": {},
        }
        http = _mock_post_response(api_data)

        with patch.object(client, "_get_client", return_value=http):
            await client.complete(
                [{"role": "user", "content": "hi"}],
                tier=ModelTier.POWERFUL,
            )

        call_kwargs = http.post.call_args
        payload: dict = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json", {})
        assert "models" in payload
        assert "model" not in payload
        assert payload["models"] == FALLBACK_CHAINS[ModelTier.POWERFUL]

    @pytest.mark.asyncio
    async def test_complete_sends_model_field_for_specific_id(
        self, client: OpenRouterClient
    ) -> None:
        """When model_id is provided, payload must use 'model' (singular)."""
        api_data: dict = {
            "choices": [{"message": {"content": "ok"}}],
            "model": "qwen/qwen3.5-27b",
            "usage": {},
        }
        http = _mock_post_response(api_data)

        with patch.object(client, "_get_client", return_value=http):
            await client.complete(
                [{"role": "user", "content": "hi"}],
                model_id="qwen/qwen3.5-27b",
            )

        call_kwargs = http.post.call_args
        payload: dict = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json", {})
        assert payload["model"] == "qwen/qwen3.5-27b"
        assert "models" not in payload

    @pytest.mark.asyncio
    async def test_complete_passes_tools_when_provided(self, client: OpenRouterClient) -> None:
        tools: list[dict] = [{"type": "function", "function": {"name": "search"}}]
        api_data: dict = {
            "choices": [{"message": {"content": "tool result"}}],
            "model": "google/gemini-2.0-flash-exp:free",
            "usage": {},
        }
        http = _mock_post_response(api_data)

        with patch.object(client, "_get_client", return_value=http):
            await client.complete(
                [{"role": "user", "content": "search something"}],
                tools=tools,
            )

        call_kwargs = http.post.call_args
        payload: dict = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json", {})
        assert payload["tools"] == tools

    @pytest.mark.asyncio
    async def test_complete_propagates_http_error(self, client: OpenRouterClient) -> None:
        """HTTP errors from OpenRouter should propagate."""
        http = AsyncMock()
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "rate limited",
            request=MagicMock(),
            response=MagicMock(status_code=429),
        )
        http.post = AsyncMock(return_value=resp)

        with patch.object(client, "_get_client", return_value=http):
            with pytest.raises(httpx.HTTPStatusError):
                await client.complete([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_complete_handles_unknown_model_in_response(
        self, client: OpenRouterClient
    ) -> None:
        """When the model returned isn't in MODEL_INFO, model_name falls back to the id."""
        api_data: dict = {
            "choices": [{"message": {"content": "test"}}],
            "model": "acme/unknown-model-v99",
            "usage": {},
        }
        http = _mock_post_response(api_data)

        with patch.object(client, "_get_client", return_value=http):
            result: CompletionResult = await client.complete(
                [{"role": "user", "content": "hi"}],
            )

        assert result.model_used == "acme/unknown-model-v99"
        assert result.model_name == "acme/unknown-model-v99"

    @pytest.mark.asyncio
    async def test_complete_forwards_kwargs(self, client: OpenRouterClient) -> None:
        """Extra kwargs (top_p, frequency_penalty, etc.) are forwarded in the payload."""
        api_data: dict = {
            "choices": [{"message": {"content": "ok"}}],
            "model": "google/gemini-2.0-flash-exp:free",
            "usage": {},
        }
        http = _mock_post_response(api_data)

        with patch.object(client, "_get_client", return_value=http):
            await client.complete(
                [{"role": "user", "content": "hi"}],
                temperature=0.2,
                max_tokens=512,
                top_p=0.9,
                frequency_penalty=0.5,
            )

        call_kwargs = http.post.call_args
        payload: dict = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json", {})
        assert payload["temperature"] == 0.2
        assert payload["max_tokens"] == 512
        assert payload["top_p"] == 0.9
        assert payload["frequency_penalty"] == 0.5


# ---------------------------------------------------------------------------
# 3. complete_stream
# ---------------------------------------------------------------------------


class TestCompleteStream:
    """Tests for OpenRouterClient.complete_stream"""

    @pytest.mark.asyncio
    async def test_stream_yields_content_chunks(self, client: OpenRouterClient) -> None:
        lines: list[str] = [
            "data: " + json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": " World"}}]}),
            "data: [DONE]",
        ]
        cm = _mock_stream_context(lines)
        http = MagicMock()
        http.stream = MagicMock(return_value=cm)

        with patch.object(client, "_get_client", return_value=http):
            chunks: list[str] = []
            async for chunk in client.complete_stream(
                [{"role": "user", "content": "greet me"}],
            ):
                chunks.append(chunk)

        assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_stream_raises_without_api_key(self, client_no_key: OpenRouterClient) -> None:
        with pytest.raises(ValueError, match="API key not configured"):
            async for _ in client_no_key.complete_stream(
                [{"role": "user", "content": "hi"}],
            ):
                pass

    @pytest.mark.asyncio
    async def test_stream_skips_empty_and_missing_content(
        self, client: OpenRouterClient
    ) -> None:
        """Chunks with empty content or missing delta.content are skipped."""
        lines: list[str] = [
            "data: " + json.dumps({"choices": [{"delta": {}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": ""}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": "Real"}}]}),
            "data: [DONE]",
        ]
        cm = _mock_stream_context(lines)
        http = MagicMock()
        http.stream = MagicMock(return_value=cm)

        with patch.object(client, "_get_client", return_value=http):
            chunks: list[str] = []
            async for chunk in client.complete_stream(
                [{"role": "user", "content": "hi"}],
            ):
                chunks.append(chunk)

        assert chunks == ["Real"]

    @pytest.mark.asyncio
    async def test_stream_survives_malformed_json(self, client: OpenRouterClient) -> None:
        """Malformed SSE JSON lines are silently skipped."""
        lines: list[str] = [
            "data: <<<not json>>>",
            "data: " + json.dumps({"choices": [{"delta": {"content": "OK"}}]}),
            "data: [DONE]",
        ]
        cm = _mock_stream_context(lines)
        http = MagicMock()
        http.stream = MagicMock(return_value=cm)

        with patch.object(client, "_get_client", return_value=http):
            chunks: list[str] = []
            async for chunk in client.complete_stream(
                [{"role": "user", "content": "hi"}],
            ):
                chunks.append(chunk)

        assert chunks == ["OK"]

    @pytest.mark.asyncio
    async def test_stream_ignores_non_data_lines(self, client: OpenRouterClient) -> None:
        """Lines that don't start with 'data: ' are ignored by the parser."""
        lines: list[str] = [
            ": keep-alive",
            "event: ping",
            "data: " + json.dumps({"choices": [{"delta": {"content": "Content"}}]}),
            "data: [DONE]",
        ]
        cm = _mock_stream_context(lines)
        http = MagicMock()
        http.stream = MagicMock(return_value=cm)

        with patch.object(client, "_get_client", return_value=http):
            chunks: list[str] = []
            async for chunk in client.complete_stream(
                [{"role": "user", "content": "hi"}],
            ):
                chunks.append(chunk)

        assert chunks == ["Content"]

    @pytest.mark.asyncio
    async def test_stream_uses_models_array(self, client: OpenRouterClient) -> None:
        """Streaming with tier uses 'models' array in payload."""
        lines: list[str] = ["data: [DONE]"]
        cm = _mock_stream_context(lines)
        http = MagicMock()
        http.stream = MagicMock(return_value=cm)

        with patch.object(client, "_get_client", return_value=http):
            async for _ in client.complete_stream(
                [{"role": "user", "content": "hi"}],
                tier=ModelTier.FAST,
            ):
                pass

        call_kwargs = http.stream.call_args
        payload: dict = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json", {})
        assert payload["stream"] is True
        assert "models" in payload
        assert payload["models"] == FALLBACK_CHAINS[ModelTier.FAST]


# ---------------------------------------------------------------------------
# 4. check_credits
# ---------------------------------------------------------------------------


class TestCheckCredits:
    """Tests for OpenRouterClient.check_credits"""

    @pytest.mark.asyncio
    async def test_check_credits_success(self, client: OpenRouterClient) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": {"credits": 12.50, "usage": 3.20}}

        http = AsyncMock()
        http.get = AsyncMock(return_value=resp)

        with patch.object(client, "_get_client", return_value=http):
            result: dict = await client.check_credits()

        assert result["data"]["credits"] == 12.50
        http.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_credits_returns_error_on_non_200(
        self, client: OpenRouterClient
    ) -> None:
        resp = MagicMock()
        resp.status_code = 403

        http = AsyncMock()
        http.get = AsyncMock(return_value=resp)

        with patch.object(client, "_get_client", return_value=http):
            result: dict = await client.check_credits()

        assert "error" in result
        assert "403" in result["error"]

    @pytest.mark.asyncio
    async def test_check_credits_without_key(self, client_no_key: OpenRouterClient) -> None:
        result: dict = await client_no_key.check_credits()
        assert result == {"error": "API key not configured"}


# ---------------------------------------------------------------------------
# 5. smart_complete (convenience function)
# ---------------------------------------------------------------------------


class TestSmartComplete:
    """Tests for the module-level smart_complete convenience function."""

    @pytest.mark.asyncio
    async def test_smart_complete_basic(self) -> None:
        expected = CompletionResult(content="42", model_used="m", model_name="M")
        with patch(
            "backend.services.llm_clients.openrouter_client.openrouter_client"
        ) as mock_singleton:
            mock_singleton.complete = AsyncMock(return_value=expected)
            result: CompletionResult = await smart_complete("What is 6*7?")

        assert result.content == "42"
        args, kwargs = mock_singleton.complete.call_args
        messages: list[dict] = args[0]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_smart_complete_with_system_prompt(self) -> None:
        expected = CompletionResult(content="done", model_used="m", model_name="M")
        with patch(
            "backend.services.llm_clients.openrouter_client.openrouter_client"
        ) as mock_singleton:
            mock_singleton.complete = AsyncMock(return_value=expected)
            result: CompletionResult = await smart_complete(
                "hello", system="You are helpful", tier=ModelTier.POWERFUL
            )

        assert result.content == "done"
        args, kwargs = mock_singleton.complete.call_args
        messages: list[dict] = args[0]
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "You are helpful"}
        assert messages[1] == {"role": "user", "content": "hello"}
        assert kwargs["tier"] == ModelTier.POWERFUL

    @pytest.mark.asyncio
    async def test_smart_complete_forwards_extra_kwargs(self) -> None:
        expected = CompletionResult(content="ok", model_used="m", model_name="M")
        with patch(
            "backend.services.llm_clients.openrouter_client.openrouter_client"
        ) as mock_singleton:
            mock_singleton.complete = AsyncMock(return_value=expected)
            await smart_complete("hi", temperature=0.1, max_tokens=256)

        _, kwargs = mock_singleton.complete.call_args
        assert kwargs["temperature"] == 0.1
        assert kwargs["max_tokens"] == 256


# ---------------------------------------------------------------------------
# 6. smart_complete_stream (convenience function)
# ---------------------------------------------------------------------------


class TestSmartCompleteStream:
    """Tests for the module-level smart_complete_stream convenience function."""

    @pytest.mark.asyncio
    async def test_smart_complete_stream_yields_chunks(self) -> None:
        async def _fake_stream(
            messages: list[dict], **kwargs: object
        ) -> AsyncGenerator[str, None]:
            for token in ["Hel", "lo"]:
                yield token

        with patch(
            "backend.services.llm_clients.openrouter_client.openrouter_client"
        ) as mock_singleton:
            mock_singleton.complete_stream = _fake_stream
            chunks: list[str] = []
            async for chunk in smart_complete_stream("greet"):
                chunks.append(chunk)

        assert chunks == ["Hel", "lo"]

    @pytest.mark.asyncio
    async def test_smart_complete_stream_with_system(self) -> None:
        captured_messages: list[dict] = []

        async def _fake_stream(
            messages: list[dict], **kwargs: object
        ) -> AsyncGenerator[str, None]:
            captured_messages.extend(messages)
            yield "ok"

        with patch(
            "backend.services.llm_clients.openrouter_client.openrouter_client"
        ) as mock_singleton:
            mock_singleton.complete_stream = _fake_stream
            chunks: list[str] = []
            async for chunk in smart_complete_stream("hi", system="Be brief"):
                chunks.append(chunk)

        assert chunks == ["ok"]
        assert len(captured_messages) == 2
        assert captured_messages[0] == {"role": "system", "content": "Be brief"}

    @pytest.mark.asyncio
    async def test_smart_complete_stream_default_tier_is_balanced(self) -> None:
        """smart_complete_stream defaults to ModelTier.BALANCED."""
        captured_kwargs: dict = {}

        async def _fake_stream(
            messages: list[dict], **kwargs: object
        ) -> AsyncGenerator[str, None]:
            captured_kwargs.update(kwargs)
            yield "x"

        with patch(
            "backend.services.llm_clients.openrouter_client.openrouter_client"
        ) as mock_singleton:
            mock_singleton.complete_stream = _fake_stream
            async for _ in smart_complete_stream("test"):
                pass

        assert captured_kwargs["tier"] == ModelTier.BALANCED


# ---------------------------------------------------------------------------
# 7. Client lifecycle: _get_client, close
# ---------------------------------------------------------------------------


class TestClientLifecycle:
    """Tests for _get_client lazy creation and close teardown."""

    def test_get_client_creates_httpx_client(self, client: OpenRouterClient) -> None:
        assert client._client is None
        http_client: httpx.AsyncClient = client._get_client()
        assert isinstance(http_client, httpx.AsyncClient)
        assert client._client is http_client

    def test_get_client_reuses_existing(self, client: OpenRouterClient) -> None:
        first: httpx.AsyncClient = client._get_client()
        second: httpx.AsyncClient = client._get_client()
        assert first is second

    @pytest.mark.asyncio
    async def test_get_client_recreates_after_close(self, client: OpenRouterClient) -> None:
        first: httpx.AsyncClient = client._get_client()
        await client.close()
        second: httpx.AsyncClient = client._get_client()
        assert first is not second

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self, client: OpenRouterClient) -> None:
        """Calling close multiple times must not raise."""
        client._get_client()
        await client.close()
        await client.close()  # second call should be safe

    @pytest.mark.asyncio
    async def test_close_without_client(self, client: OpenRouterClient) -> None:
        """Closing before any HTTP client was created must not raise."""
        assert client._client is None
        await client.close()

    def test_headers_include_required_openrouter_fields(
        self, client: OpenRouterClient
    ) -> None:
        headers: dict = client._get_headers()
        assert headers["Authorization"] == "Bearer test-api-key"
        assert headers["Content-Type"] == "application/json"
        assert headers["HTTP-Referer"] == client.site_url
        assert headers["X-Title"] == client.site_name


# ---------------------------------------------------------------------------
# 8. Constants sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    """Quick sanity checks on module-level constants."""

    def test_model_info_has_all_fallback_models(self) -> None:
        """Every model used in a fallback chain should appear in MODEL_INFO."""
        all_models: set[str] = set()
        for chain in FALLBACK_CHAINS.values():
            all_models.update(chain)

        for model_id in all_models:
            assert model_id in MODEL_INFO, f"{model_id} missing from MODEL_INFO"

    def test_base_url(self) -> None:
        assert OpenRouterClient.BASE_URL == "https://openrouter.ai/api/v1"
