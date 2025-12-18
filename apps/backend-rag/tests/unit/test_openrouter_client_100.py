"""
Complete 100% Coverage Tests for OpenRouter Client

Tests all functions, classes and edge cases in openrouter_client.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestModelTier:
    """Tests for ModelTier enum"""

    def test_model_tier_values(self):
        """Test all ModelTier values exist"""
        from services.openrouter_client import ModelTier

        assert ModelTier.FAST.value == "fast"
        assert ModelTier.BALANCED.value == "balanced"
        assert ModelTier.POWERFUL.value == "powerful"
        assert ModelTier.RAG.value == "rag"


class TestFallbackChains:
    """Tests for fallback chain configuration"""

    def test_fallback_chains_exist(self):
        """Test all fallback chains are configured"""
        from services.openrouter_client import FALLBACK_CHAINS, ModelTier

        assert ModelTier.RAG in FALLBACK_CHAINS
        assert ModelTier.POWERFUL in FALLBACK_CHAINS
        assert ModelTier.BALANCED in FALLBACK_CHAINS
        assert ModelTier.FAST in FALLBACK_CHAINS

        # Each chain should have exactly 3 models (OpenRouter limit)
        for tier, chain in FALLBACK_CHAINS.items():
            assert len(chain) == 3, f"Chain for {tier} should have 3 models"

    def test_model_info_exists(self):
        """Test MODEL_INFO contains expected models"""
        from services.openrouter_client import MODEL_INFO

        assert "google/gemini-2.0-flash-exp:free" in MODEL_INFO
        assert "meta-llama/llama-3.3-70b-instruct:free" in MODEL_INFO
        assert MODEL_INFO["google/gemini-2.0-flash-exp:free"]["context"] == 1_000_000


class TestCompletionResult:
    """Tests for CompletionResult dataclass"""

    def test_completion_result_defaults(self):
        """Test CompletionResult with default values"""
        from services.openrouter_client import CompletionResult

        result = CompletionResult(content="Hello", model_used="test-model", model_name="Test Model")

        assert result.content == "Hello"
        assert result.model_used == "test-model"
        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0
        assert result.cost == 0.0

    def test_completion_result_full(self):
        """Test CompletionResult with all values"""
        from services.openrouter_client import CompletionResult

        result = CompletionResult(
            content="Response",
            model_used="model-id",
            model_name="Model Name",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.0,
        )

        assert result.total_tokens == 150


class TestOpenRouterClient:
    """Tests for OpenRouterClient class"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings"""
        with patch("services.openrouter_client.settings") as mock:
            mock.openrouter_api_key = "test-api-key"
            yield mock

    def test_init_with_api_key(self, mock_settings):
        """Test initialization with explicit API key"""
        from services.openrouter_client import ModelTier, OpenRouterClient

        client = OpenRouterClient(api_key="explicit-key")

        assert client.api_key == "explicit-key"
        assert client.default_tier == ModelTier.RAG
        assert client.timeout == 120.0

    def test_init_from_settings(self, mock_settings):
        """Test initialization from settings"""
        from services.openrouter_client import OpenRouterClient

        client = OpenRouterClient()

        assert client.api_key == "test-api-key"

    def test_init_from_env(self):
        """Test initialization from environment"""
        from services.openrouter_client import OpenRouterClient

        with patch("services.openrouter_client.settings") as mock_settings:
            mock_settings.openrouter_api_key = None
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key"}):
                with patch("services.openrouter_client.os.getenv", return_value="env-key"):
                    client = OpenRouterClient()
                    assert client.api_key == "env-key"

    def test_init_no_key_warning(self):
        """Test warning when no API key"""
        from services.openrouter_client import OpenRouterClient

        with patch("services.openrouter_client.settings") as mock_settings:
            mock_settings.openrouter_api_key = None
            with patch("services.openrouter_client.os.getenv", return_value=None):
                with patch("services.openrouter_client.logger") as mock_logger:
                    client = OpenRouterClient(api_key=None)
                    mock_logger.warning.assert_called()

    def test_get_fallback_chain_default(self, mock_settings):
        """Test get_fallback_chain with default tier"""
        from services.openrouter_client import FALLBACK_CHAINS, ModelTier, OpenRouterClient

        client = OpenRouterClient(default_tier=ModelTier.BALANCED)
        chain = client.get_fallback_chain()

        assert chain == FALLBACK_CHAINS[ModelTier.BALANCED]

    def test_get_fallback_chain_explicit(self, mock_settings):
        """Test get_fallback_chain with explicit tier"""
        from services.openrouter_client import FALLBACK_CHAINS, ModelTier, OpenRouterClient

        client = OpenRouterClient()
        chain = client.get_fallback_chain(ModelTier.FAST)

        assert chain == FALLBACK_CHAINS[ModelTier.FAST]

    def test_get_headers(self, mock_settings):
        """Test _get_headers returns correct headers"""
        from services.openrouter_client import OpenRouterClient

        client = OpenRouterClient(api_key="test-key")
        headers = client._get_headers()

        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers

    @pytest.mark.asyncio
    async def test_complete_no_api_key(self, mock_settings):
        """Test complete raises error without API key"""
        from services.openrouter_client import OpenRouterClient

        with patch("services.openrouter_client.settings") as mock:
            mock.openrouter_api_key = None
            with patch("services.openrouter_client.os.getenv", return_value=None):
                client = OpenRouterClient(api_key=None)
                client.api_key = None  # Force no key

                with pytest.raises(ValueError, match="API key not configured"):
                    await client.complete([{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_complete_with_model_id(self, mock_settings):
        """Test complete with specific model ID"""
        from services.openrouter_client import OpenRouterClient

        client = OpenRouterClient(api_key="test-key")

        mock_response = {
            "choices": [{"message": {"content": "Hello"}}],
            "model": "specific-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_resp

            result = await client.complete(
                [{"role": "user", "content": "Hi"}], model_id="specific-model"
            )

            assert result.content == "Hello"
            assert result.model_used == "specific-model"
            assert result.total_tokens == 15

            # Check payload used specific model
            call_args = mock_instance.post.call_args
            payload = call_args.kwargs["json"]
            assert payload["model"] == "specific-model"
            assert "models" not in payload

    @pytest.mark.asyncio
    async def test_complete_with_fallback(self, mock_settings):
        """Test complete with fallback chain"""
        from services.openrouter_client import ModelTier, OpenRouterClient

        client = OpenRouterClient(api_key="test-key")

        mock_response = {
            "choices": [{"message": {"content": "Response"}}],
            "model": "google/gemini-2.0-flash-exp:free",
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_resp

            result = await client.complete([{"role": "user", "content": "Hi"}], tier=ModelTier.RAG)

            assert result.content == "Response"
            assert "Gemini" in result.model_name

            # Check payload used models array
            call_args = mock_instance.post.call_args
            payload = call_args.kwargs["json"]
            assert "models" in payload
            assert "model" not in payload

    @pytest.mark.asyncio
    async def test_complete_with_tools(self, mock_settings):
        """Test complete with tools"""
        from services.openrouter_client import OpenRouterClient

        client = OpenRouterClient(api_key="test-key")

        mock_response = {
            "choices": [{"message": {"content": "Tool response"}}],
            "model": "test-model",
            "usage": {},
        }

        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()
            mock_instance.post.return_value = mock_resp

            result = await client.complete([{"role": "user", "content": "Hi"}], tools=tools)

            call_args = mock_instance.post.call_args
            payload = call_args.kwargs["json"]
            assert "tools" in payload

    @pytest.mark.asyncio
    async def test_complete_stream_no_api_key(self, mock_settings):
        """Test complete_stream raises error without API key"""
        from services.openrouter_client import OpenRouterClient

        with patch("services.openrouter_client.settings") as mock:
            mock.openrouter_api_key = None
            with patch("services.openrouter_client.os.getenv", return_value=None):
                client = OpenRouterClient(api_key=None)
                client.api_key = None

                with pytest.raises(ValueError, match="API key not configured"):
                    async for _ in client.complete_stream([{"role": "user", "content": "test"}]):
                        pass

    @pytest.mark.asyncio
    async def test_complete_stream_success(self, mock_settings):
        """Test complete_stream with successful streaming"""
        from services.openrouter_client import OpenRouterClient

        client = OpenRouterClient(api_key="test-key")

        # Simulate SSE stream
        async def mock_aiter_lines():
            yield 'data: {"choices": [{"delta": {"content": "Hello"}}]}'
            yield 'data: {"choices": [{"delta": {"content": " World"}}]}'
            yield "data: [DONE]"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response = AsyncMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_lines = mock_aiter_lines

            mock_instance.stream.return_value.__aenter__.return_value = mock_response

            chunks = []
            async for chunk in client.complete_stream([{"role": "user", "content": "Hi"}]):
                chunks.append(chunk)

            assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_complete_stream_with_model_id(self, mock_settings):
        """Test complete_stream with specific model"""
        from services.openrouter_client import OpenRouterClient

        client = OpenRouterClient(api_key="test-key")

        async def mock_aiter_lines():
            yield 'data: {"choices": [{"delta": {"content": "OK"}}]}'
            yield "data: [DONE]"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response = AsyncMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_lines = mock_aiter_lines

            mock_instance.stream.return_value.__aenter__.return_value = mock_response

            async for _ in client.complete_stream(
                [{"role": "user", "content": "Hi"}], model_id="specific-model"
            ):
                pass

    @pytest.mark.asyncio
    async def test_complete_stream_json_error(self, mock_settings):
        """Test complete_stream handles JSON decode errors"""
        from services.openrouter_client import OpenRouterClient

        client = OpenRouterClient(api_key="test-key")

        async def mock_aiter_lines():
            yield "data: invalid-json"  # Should be skipped
            yield 'data: {"choices": [{"delta": {"content": "OK"}}]}'
            yield "data: [DONE]"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response = AsyncMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_lines = mock_aiter_lines

            mock_instance.stream.return_value.__aenter__.return_value = mock_response

            chunks = []
            async for chunk in client.complete_stream([{"role": "user", "content": "Hi"}]):
                chunks.append(chunk)

            assert chunks == ["OK"]  # Invalid JSON was skipped

    @pytest.mark.asyncio
    async def test_check_credits_success(self, mock_settings):
        """Test check_credits success"""
        from services.openrouter_client import OpenRouterClient

        client = OpenRouterClient(api_key="test-key")

        mock_data = {"credits": 10.5, "usage": {"requests": 100}}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_data
            mock_instance.get.return_value = mock_resp

            result = await client.check_credits()

            assert result == mock_data

    @pytest.mark.asyncio
    async def test_check_credits_no_key(self, mock_settings):
        """Test check_credits without API key"""
        from services.openrouter_client import OpenRouterClient

        with patch("services.openrouter_client.settings") as mock:
            mock.openrouter_api_key = None
            with patch("services.openrouter_client.os.getenv", return_value=None):
                client = OpenRouterClient(api_key=None)
                client.api_key = None

                result = await client.check_credits()

                assert "error" in result

    @pytest.mark.asyncio
    async def test_check_credits_error(self, mock_settings):
        """Test check_credits with error response"""
        from services.openrouter_client import OpenRouterClient

        client = OpenRouterClient(api_key="test-key")

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_instance.get.return_value = mock_resp

            result = await client.check_credits()

            assert "error" in result
            assert "401" in result["error"]


class TestConvenienceFunctions:
    """Tests for convenience functions"""

    @pytest.fixture
    def mock_client(self):
        """Mock the singleton client"""
        with patch("services.openrouter_client.openrouter_client") as mock:
            mock.complete = AsyncMock()
            mock.complete_stream = AsyncMock()
            yield mock

    @pytest.mark.asyncio
    async def test_smart_complete_simple(self, mock_client):
        """Test smart_complete with simple prompt"""
        from services.openrouter_client import CompletionResult, smart_complete

        mock_client.complete.return_value = CompletionResult(
            content="4", model_used="test", model_name="Test"
        )

        result = await smart_complete("What is 2+2?")

        mock_client.complete.assert_called_once()
        call_args = mock_client.complete.call_args
        messages = call_args[0][0]

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert result.content == "4"

    @pytest.mark.asyncio
    async def test_smart_complete_with_system(self, mock_client):
        """Test smart_complete with system prompt"""
        from services.openrouter_client import CompletionResult, smart_complete

        mock_client.complete.return_value = CompletionResult(
            content="OK", model_used="test", model_name="Test"
        )

        await smart_complete("Hello", system="Be helpful")

        call_args = mock_client.complete.call_args
        messages = call_args[0][0]

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Be helpful"

    @pytest.mark.asyncio
    async def test_smart_complete_stream_simple(self, mock_client):
        """Test smart_complete_stream with simple prompt"""
        from services.openrouter_client import smart_complete_stream

        async def mock_stream(*args, **kwargs):
            yield "Hello"
            yield " World"

        mock_client.complete_stream.return_value = mock_stream()

        chunks = []
        async for chunk in smart_complete_stream("Hi"):
            chunks.append(chunk)

        assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_smart_complete_stream_with_system(self, mock_client):
        """Test smart_complete_stream with system prompt"""
        from services.openrouter_client import smart_complete_stream

        async def mock_stream(*args, **kwargs):
            yield "OK"

        mock_client.complete_stream.return_value = mock_stream()

        async for _ in smart_complete_stream("Hello", system="Be concise"):
            pass

        call_args = mock_client.complete_stream.call_args
        messages = call_args[0][0]

        assert len(messages) == 2
        assert messages[0]["role"] == "system"


class TestSingleton:
    """Tests for singleton instance"""

    def test_singleton_exists(self):
        """Test openrouter_client singleton is created"""
        from services.openrouter_client import ModelTier, OpenRouterClient, openrouter_client

        assert isinstance(openrouter_client, OpenRouterClient)
        assert openrouter_client.default_tier == ModelTier.RAG
