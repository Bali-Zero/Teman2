"""
Comprehensive tests for OpenRouterClient
Target: 100% coverage
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestModelTier:
    """Tests for ModelTier enum"""

    def test_model_tier_values(self):
        """Test all model tier values"""
        from services.openrouter_client import ModelTier

        assert ModelTier.FAST.value == "fast"
        assert ModelTier.BALANCED.value == "balanced"
        assert ModelTier.POWERFUL.value == "powerful"
        assert ModelTier.RAG.value == "rag"


class TestCompletionResult:
    """Tests for CompletionResult dataclass"""

    def test_completion_result_creation(self):
        """Test creating CompletionResult"""
        from services.openrouter_client import CompletionResult

        result = CompletionResult(
            content="Hello world",
            model_used="google/gemini-2.0-flash-exp:free",
            model_name="Gemini 2.0 Flash",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.0,
        )

        assert result.content == "Hello world"
        assert result.model_used == "google/gemini-2.0-flash-exp:free"
        assert result.total_tokens == 15

    def test_completion_result_defaults(self):
        """Test CompletionResult with defaults"""
        from services.openrouter_client import CompletionResult

        result = CompletionResult(content="Test", model_used="test-model", model_name="Test Model")

        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0
        assert result.cost == 0.0


class TestFallbackChains:
    """Tests for fallback chain constants"""

    def test_fallback_chains_exist(self):
        """Test that fallback chains are defined"""
        from services.openrouter_client import FALLBACK_CHAINS, ModelTier

        assert ModelTier.RAG in FALLBACK_CHAINS
        assert ModelTier.POWERFUL in FALLBACK_CHAINS
        assert ModelTier.BALANCED in FALLBACK_CHAINS
        assert ModelTier.FAST in FALLBACK_CHAINS

    def test_fallback_chain_length(self):
        """Test fallback chains have max 3 models (OpenRouter limit)"""
        from services.openrouter_client import FALLBACK_CHAINS

        for tier, chain in FALLBACK_CHAINS.items():
            assert len(chain) <= 3, f"Tier {tier} has more than 3 models"


class TestModelInfo:
    """Tests for model info constants"""

    def test_model_info_structure(self):
        """Test model info has required fields"""
        from services.openrouter_client import MODEL_INFO

        for model_id, info in MODEL_INFO.items():
            assert "name" in info
            assert "context" in info
            assert isinstance(info["context"], int)


class TestOpenRouterClient:
    """Tests for OpenRouterClient class"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings"""
        with patch("services.openrouter_client.settings") as mock:
            mock.openrouter_api_key = "test-api-key"
            yield mock

    @pytest.fixture
    def client(self, mock_settings):
        """Create OpenRouterClient instance"""
        from services.openrouter_client import OpenRouterClient

        return OpenRouterClient(api_key="test-api-key")

    @pytest.fixture
    def client_no_key(self):
        """Create OpenRouterClient without API key"""
        with patch("services.openrouter_client.settings") as mock:
            mock.openrouter_api_key = None
            with patch.dict("os.environ", {}, clear=True):
                from services.openrouter_client import OpenRouterClient

                return OpenRouterClient(api_key=None)

    def test_init_with_api_key(self, mock_settings):
        """Test initialization with API key"""
        from services.openrouter_client import ModelTier, OpenRouterClient

        client = OpenRouterClient(api_key="test-key")

        assert client.api_key == "test-key"
        assert client.default_tier == ModelTier.RAG
        assert client.timeout == 120.0

    def test_init_custom_params(self, mock_settings):
        """Test initialization with custom parameters"""
        from services.openrouter_client import ModelTier, OpenRouterClient

        client = OpenRouterClient(
            api_key="test-key",
            default_tier=ModelTier.FAST,
            timeout=60.0,
            site_url="https://test.com",
            site_name="Test Site",
        )

        assert client.default_tier == ModelTier.FAST
        assert client.timeout == 60.0
        assert client.site_url == "https://test.com"
        assert client.site_name == "Test Site"

    def test_init_from_settings(self, mock_settings):
        """Test initialization from settings"""
        from services.openrouter_client import OpenRouterClient

        client = OpenRouterClient()
        assert client.api_key == "test-api-key"

    def test_init_from_env(self):
        """Test initialization from environment"""
        with patch("services.openrouter_client.settings") as mock:
            mock.openrouter_api_key = None
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-key"}):
                from services.openrouter_client import OpenRouterClient

                client = OpenRouterClient()
                assert client.api_key == "env-key"

    def test_init_no_key_warning(self):
        """Test warning when no API key"""
        with patch("services.openrouter_client.settings") as mock:
            mock.openrouter_api_key = None
            with patch.dict("os.environ", {}, clear=True):
                from services.openrouter_client import OpenRouterClient

                client = OpenRouterClient(api_key=None)
                assert client.api_key is None

    def test_get_fallback_chain_default(self, client):
        """Test getting default fallback chain"""

        chain = client.get_fallback_chain()

        assert len(chain) == 3
        assert "google/gemini-2.0-flash-exp:free" in chain

    def test_get_fallback_chain_specific_tier(self, client):
        """Test getting fallback chain for specific tier"""
        from services.openrouter_client import ModelTier

        chain = client.get_fallback_chain(ModelTier.FAST)

        assert "meta-llama/llama-3.2-3b-instruct:free" in chain

    def test_get_headers(self, client):
        """Test getting API headers"""
        headers = client._get_headers()

        assert headers["Authorization"] == "Bearer test-api-key"
        assert headers["Content-Type"] == "application/json"
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers

    @pytest.mark.asyncio
    async def test_complete_no_api_key(self, client_no_key):
        """Test complete raises error without API key"""
        with pytest.raises(ValueError, match="API key not configured"):
            await client_no_key.complete([{"role": "user", "content": "Test"}])

    @pytest.mark.asyncio
    async def test_complete_success(self, client):
        """Test successful completion"""
        mock_response = {
            "choices": [{"message": {"content": "Hello!"}}],
            "model": "google/gemini-2.0-flash-exp:free",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await client.complete([{"role": "user", "content": "Hi"}])

            assert result.content == "Hello!"
            assert result.model_used == "google/gemini-2.0-flash-exp:free"
            assert result.total_tokens == 15

    @pytest.mark.asyncio
    async def test_complete_with_specific_model(self, client):
        """Test completion with specific model"""
        mock_response = {
            "choices": [{"message": {"content": "Response"}}],
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "usage": {},
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await client.complete(
                [{"role": "user", "content": "Hi"}],
                model_id="meta-llama/llama-3.3-70b-instruct:free",
            )

            assert result.model_used == "meta-llama/llama-3.3-70b-instruct:free"

    @pytest.mark.asyncio
    async def test_complete_with_tools(self, client):
        """Test completion with tools"""
        mock_response = {
            "choices": [{"message": {"content": "Tool response"}}],
            "model": "google/gemini-2.0-flash-exp:free",
            "usage": {},
        }

        tools = [{"type": "function", "function": {"name": "test"}}]

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await client.complete([{"role": "user", "content": "Hi"}], tools=tools)

            assert result.content == "Tool response"

    @pytest.mark.asyncio
    async def test_complete_with_custom_params(self, client):
        """Test completion with custom parameters"""
        mock_response = {
            "choices": [{"message": {"content": "Custom"}}],
            "model": "google/gemini-2.0-flash-exp:free",
            "usage": {},
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await client.complete(
                [{"role": "user", "content": "Hi"}], temperature=0.5, max_tokens=1000, top_p=0.9
            )

            assert result.content == "Custom"

    @pytest.mark.asyncio
    async def test_complete_unknown_model(self, client):
        """Test completion with unknown model in response"""
        mock_response = {
            "choices": [{"message": {"content": "Test"}}],
            "model": "unknown/model",
            "usage": {},
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await client.complete([{"role": "user", "content": "Hi"}])

            assert result.model_used == "unknown/model"
            assert result.model_name == "unknown/model"

    @pytest.mark.asyncio
    async def test_complete_stream_no_api_key(self, client_no_key):
        """Test streaming raises error without API key"""
        with pytest.raises(ValueError, match="API key not configured"):
            async for _ in client_no_key.complete_stream([{"role": "user", "content": "Test"}]):
                pass

    @pytest.mark.asyncio
    async def test_complete_stream_success(self, client):
        """Test successful streaming"""

        # Create mock async iterator for streaming
        async def mock_stream():
            yield "data: " + json.dumps({"choices": [{"delta": {"content": "Hello"}}]})
            yield "data: " + json.dumps({"choices": [{"delta": {"content": " World"}}]})
            yield "data: [DONE]"

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_lines = mock_stream

            mock_stream_cm = MagicMock()
            mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream_cm.__aexit__ = AsyncMock(return_value=None)

            mock_client.stream = MagicMock(return_value=mock_stream_cm)

            mock_client_cm = MagicMock()
            mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cm.__aexit__ = AsyncMock(return_value=None)

            MockClient.return_value = mock_client_cm

            chunks = []
            async for chunk in client.complete_stream([{"role": "user", "content": "Hi"}]):
                chunks.append(chunk)

            assert "Hello" in chunks
            assert " World" in chunks

    @pytest.mark.asyncio
    async def test_complete_stream_with_model_id(self, client):
        """Test streaming with specific model"""

        async def mock_stream():
            yield "data: " + json.dumps({"choices": [{"delta": {"content": "Test"}}]})
            yield "data: [DONE]"

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_lines = mock_stream

            mock_stream_cm = MagicMock()
            mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream_cm.__aexit__ = AsyncMock(return_value=None)

            mock_client.stream = MagicMock(return_value=mock_stream_cm)

            mock_client_cm = MagicMock()
            mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cm.__aexit__ = AsyncMock(return_value=None)

            MockClient.return_value = mock_client_cm

            chunks = []
            async for chunk in client.complete_stream(
                [{"role": "user", "content": "Hi"}], model_id="specific-model"
            ):
                chunks.append(chunk)

            assert "Test" in chunks

    @pytest.mark.asyncio
    async def test_complete_stream_invalid_json(self, client):
        """Test streaming handles invalid JSON"""

        async def mock_stream():
            yield "data: {invalid json}"
            yield "data: " + json.dumps({"choices": [{"delta": {"content": "Valid"}}]})
            yield "data: [DONE]"

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_lines = mock_stream

            mock_stream_cm = MagicMock()
            mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream_cm.__aexit__ = AsyncMock(return_value=None)

            mock_client.stream = MagicMock(return_value=mock_stream_cm)

            mock_client_cm = MagicMock()
            mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cm.__aexit__ = AsyncMock(return_value=None)

            MockClient.return_value = mock_client_cm

            chunks = []
            async for chunk in client.complete_stream([{"role": "user", "content": "Hi"}]):
                chunks.append(chunk)

            assert "Valid" in chunks

    @pytest.mark.asyncio
    async def test_complete_stream_empty_content(self, client):
        """Test streaming handles empty content"""

        async def mock_stream():
            yield "data: " + json.dumps({"choices": [{"delta": {}}]})
            yield "data: " + json.dumps({"choices": [{"delta": {"content": ""}}]})
            yield "data: " + json.dumps({"choices": [{"delta": {"content": "Hello"}}]})
            yield "data: [DONE]"

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_lines = mock_stream

            mock_stream_cm = MagicMock()
            mock_stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream_cm.__aexit__ = AsyncMock(return_value=None)

            mock_client.stream = MagicMock(return_value=mock_stream_cm)

            mock_client_cm = MagicMock()
            mock_client_cm.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cm.__aexit__ = AsyncMock(return_value=None)

            MockClient.return_value = mock_client_cm

            chunks = []
            async for chunk in client.complete_stream([{"role": "user", "content": "Hi"}]):
                chunks.append(chunk)

            assert chunks == ["Hello"]

    @pytest.mark.asyncio
    async def test_check_credits_success(self, client):
        """Test checking credits"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"credits": 10.0}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await client.check_credits()

            assert result["credits"] == 10.0

    @pytest.mark.asyncio
    async def test_check_credits_no_api_key(self, client_no_key):
        """Test checking credits without API key"""
        result = await client_no_key.check_credits()

        assert "error" in result
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_check_credits_error(self, client):
        """Test checking credits with error"""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            MockClient.return_value.__aenter__.return_value = mock_client

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
    async def test_smart_complete(self, mock_client):
        """Test smart_complete function"""
        from services.openrouter_client import CompletionResult, smart_complete

        mock_client.complete.return_value = CompletionResult(
            content="Result", model_used="test", model_name="Test"
        )

        result = await smart_complete("Test prompt")

        assert result.content == "Result"
        mock_client.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_smart_complete_with_system(self, mock_client):
        """Test smart_complete with system prompt"""
        from services.openrouter_client import CompletionResult, smart_complete

        mock_client.complete.return_value = CompletionResult(
            content="Result", model_used="test", model_name="Test"
        )

        result = await smart_complete("Test prompt", system="System prompt")

        assert result.content == "Result"
        call_args = mock_client.complete.call_args
        messages = call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "System prompt"

    @pytest.mark.asyncio
    async def test_smart_complete_stream(self, mock_client):
        """Test smart_complete_stream function"""
        from services.openrouter_client import smart_complete_stream

        async def mock_stream(*args, **kwargs):
            yield "Hello"
            yield " World"

        mock_client.complete_stream = mock_stream

        chunks = []
        async for chunk in smart_complete_stream("Test"):
            chunks.append(chunk)

        assert chunks == ["Hello", " World"]

    @pytest.mark.asyncio
    async def test_smart_complete_stream_with_system(self, mock_client):
        """Test smart_complete_stream with system prompt"""
        from services.openrouter_client import smart_complete_stream

        async def mock_stream(*args, **kwargs):
            yield "Result"

        mock_client.complete_stream = mock_stream

        chunks = []
        async for chunk in smart_complete_stream("Test", system="System"):
            chunks.append(chunk)

        assert "Result" in chunks
