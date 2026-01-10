"""
Direct coverage tests for LLMGateway.

This test suite provides comprehensive coverage by testing the module directly
with proper environment setup.

Author: Nuzantara Team
Date: 2025-01-04
Version: 1.0.0
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), "../../../../backend")
sys.path.insert(0, backend_path)

# Set environment variables to avoid config issues
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

# Mock dependencies before importing
with patch.dict(
    "sys.modules",
    {
        "backend.app.core.config": MagicMock(),
        "backend.app.core.circuit_breaker": MagicMock(),
        "backend.app.core.error_classification": MagicMock(),
        "backend.app.metrics": MagicMock(),
        "backend.app.utils.tracing": MagicMock(),
        "backend.llm.genai_client": MagicMock(),
        "backend.services.llm_clients.openrouter_client": MagicMock(),
        "backend.services.llm_clients.pricing": MagicMock(),
    },
):
    # Configure mocks
    sys.modules["backend.llm.genai_client"].GENAI_AVAILABLE = True
    sys.modules["backend.services.llm_clients.pricing"].create_token_usage = Mock(
        return_value=Mock(cost_usd=0.001)
    )

    # Mock CircuitBreaker
    class MockCircuitBreaker:
        def __init__(self, failure_threshold=5, success_threshold=2, timeout=60.0, name=""):
            self.failure_threshold = failure_threshold
            self.success_threshold = success_threshold
            self.timeout = timeout
            self.name = name
            self.failures = 0
            self.successes = 0

        def is_open(self):
            return self.failures >= self.failure_threshold

        def record_success(self):
            self.successes += 1
            if self.successes >= self.success_threshold:
                self.failures = 0
                self.successes = 0

        def record_failure(self):
            self.failures += 1

    sys.modules["backend.app.core.circuit_breaker"].CircuitBreaker = MockCircuitBreaker
    sys.modules["backend.app.core.error_classification"].ErrorClassifier = Mock()
    sys.modules["backend.app.core.error_classification"].ErrorClassifier.classify_error = Mock(
        return_value=("quota", "high")
    )
    sys.modules["backend.app.core.error_classification"].get_error_context = Mock(return_value={})
    sys.modules["backend.app.utils.tracing"].trace_span = Mock()
    sys.modules["backend.app.utils.tracing"].set_span_attribute = Mock()
    sys.modules["backend.app.utils.tracing"].set_span_status = Mock()
    sys.modules["backend.app.metrics"].metrics_collector = Mock()

    # Mock OpenRouter
    class MockModelTier:
        RAG = "rag"

    sys.modules["backend.services.llm_clients.openrouter_client"].ModelTier = MockModelTier
    sys.modules["backend.services.llm_clients.openrouter_client"].OpenRouterClient = Mock()

    # Now import the module
    try:
        from backend.services.rag.agentic.llm_gateway import (
            TIER_FALLBACK,
            TIER_FLASH,
            TIER_LITE,
            TIER_PRO,
            LLMGateway,
        )

        IMPORT_SUCCESS = True
    except ImportError as e:
        print(f"Import failed: {e}")
        IMPORT_SUCCESS = False


pytestmark = pytest.mark.skipif(not IMPORT_SUCCESS, reason="Could not import LLMGateway")


@pytest.fixture
def mock_genai_client():
    """Mock GenAI client for testing."""
    client = MagicMock()
    client.is_available = True
    client._auth_method = "api_key"
    client._client = MagicMock()
    client._client.aio = MagicMock()
    client._client.aio.models = MagicMock()
    client._client.aio.models.generate_content = AsyncMock()
    return client


@pytest.fixture
def sample_gemini_tools():
    """Sample Gemini function declarations for testing."""
    return [
        {
            "name": "search_web",
            "description": "Search the web for information",
            "parameters": {
                "type": "OBJECT",
                "properties": {"query": {"type": "STRING", "description": "Search query"}},
                "required": ["query"],
            },
        }
    ]


@pytest.fixture
def llm_gateway(mock_genai_client, sample_gemini_tools):
    """Create LLMGateway instance with mocked dependencies."""
    with patch("backend.services.rag.agentic.llm_gateway.get_genai_client", return_value=mock_genai_client):
        gateway = LLMGateway(gemini_tools=sample_gemini_tools)
        gateway._genai_client = mock_genai_client
        gateway._available = True
        return gateway


class TestLLMGatewayBasic:
    """Basic tests for LLMGateway."""

    def test_init_without_tools(self, mock_genai_client):
        """Test initialization without Gemini tools."""
        with patch(
            "backend.services.rag.agentic.llm_gateway.get_genai_client", return_value=mock_genai_client
        ):
            gateway = LLMGateway()
            assert gateway.gemini_tools == []
            assert gateway._genai_client == mock_genai_client
            assert gateway._available is True
            assert gateway.model_name_pro == "gemini-3-flash-preview"
            assert gateway.model_name_flash == "gemini-3-flash-preview"
            assert gateway.model_name_fallback == "gemini-2.0-flash"

    def test_init_with_tools(self, mock_genai_client, sample_gemini_tools):
        """Test initialization with Gemini tools."""
        with patch(
            "backend.services.rag.agentic.llm_gateway.get_genai_client", return_value=mock_genai_client
        ):
            gateway = LLMGateway(gemini_tools=sample_gemini_tools)
            assert gateway.gemini_tools == sample_gemini_tools

    def test_set_gemini_tools(self, llm_gateway):
        """Test setting Gemini tools after initialization."""
        new_tools = [{"name": "test_tool", "description": "Test"}]
        llm_gateway.set_gemini_tools(new_tools)
        assert llm_gateway.gemini_tools == new_tools

    def test_get_fallback_chain_pro(self, llm_gateway):
        """Test fallback chain for PRO tier."""
        chain = llm_gateway._get_fallback_chain(TIER_PRO)
        expected = [
            llm_gateway.model_name_pro,
            llm_gateway.model_name_flash,
            llm_gateway.model_name_fallback,
        ]
        assert chain == expected

    def test_get_fallback_chain_flash(self, llm_gateway):
        """Test fallback chain for FLASH tier."""
        chain = llm_gateway._get_fallback_chain(TIER_FLASH)
        expected = [llm_gateway.model_name_flash, llm_gateway.model_name_fallback]
        assert chain == expected

    def test_get_fallback_chain_fallback(self, llm_gateway):
        """Test fallback chain for FALLBACK tier."""
        chain = llm_gateway._get_fallback_chain(TIER_FALLBACK)
        expected = [llm_gateway.model_name_fallback]
        assert chain == expected


class TestCircuitBreakerFunctionality:
    """Test circuit breaker functionality."""

    def test_get_circuit_breaker_new(self, llm_gateway):
        """Test creating new circuit breaker."""
        circuit = llm_gateway._get_circuit_breaker("test-model")
        assert circuit.name == "llm_test-model"
        assert circuit.failure_threshold == 5
        assert circuit.success_threshold == 2
        assert circuit.timeout == 60.0

    def test_get_circuit_breaker_existing(self, llm_gateway):
        """Test reusing existing circuit breaker."""
        circuit1 = llm_gateway._get_circuit_breaker("test-model")
        circuit2 = llm_gateway._get_circuit_breaker("test-model")
        assert circuit1 is circuit2

    def test_is_circuit_open_false(self, llm_gateway):
        """Test circuit breaker is closed."""
        assert llm_gateway._is_circuit_open("test-model") is False

    def test_is_circuit_open_true(self, llm_gateway):
        """Test circuit breaker is open."""
        circuit = llm_gateway._get_circuit_breaker("test-model")
        for _ in range(6):
            circuit.record_failure()
        assert llm_gateway._is_circuit_open("test-model") is True

    def test_record_success(self, llm_gateway):
        """Test recording successful call."""
        circuit = llm_gateway._get_circuit_breaker("test-model")
        for _ in range(6):
            circuit.record_failure()
        assert circuit.is_open()

        for _ in range(2):
            circuit.record_success()
        assert not circuit.is_open()

    def test_record_failure(self, llm_gateway):
        """Test recording failed call."""
        error = Exception("Test error")
        llm_gateway._record_failure("test-model", error)

        from backend.app.core.error_classification import ErrorClassifier

        ErrorClassifier.classify_error.assert_called_with(error)


class TestSendMessageFunctionality:
    """Test send_message functionality."""

    async def test_send_message_success(self, llm_gateway, mock_genai_client):
        """Test successful message sending."""
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20

        mock_genai_client._client.aio.models.generate_content.return_value = mock_response

        response, model, obj, usage = await llm_gateway.send_message(
            chat=None, message="Hello", tier=TIER_FLASH
        )

        assert response == "Test response"
        assert model == llm_gateway.model_name_flash
        assert obj == mock_response
        assert usage.cost_usd == 0.001

    async def test_send_message_quota_exhausted_fallback(self, llm_gateway, mock_genai_client):
        """Test fallback when quota exhausted."""
        mock_genai_client._client.aio.models.generate_content.side_effect = [
            ResourceExhausted("Quota exceeded"),
            Mock(text="Fallback response", usage_metadata=None),
        ]

        response, model, obj, usage = await llm_gateway.send_message(
            chat=None, message="Hello", tier=TIER_FLASH
        )

        assert response == "Fallback response"
        assert model == llm_gateway.model_name_fallback

    async def test_send_message_service_unavailable_fallback(self, llm_gateway, mock_genai_client):
        """Test fallback when service unavailable."""
        mock_genai_client._client.aio.models.generate_content.side_effect = [
            ServiceUnavailable("Service unavailable"),
            Mock(text="Fallback response", usage_metadata=None),
        ]

        response, model, obj, usage = await llm_gateway.send_message(
            chat=None, message="Hello", tier=TIER_FLASH
        )

        assert response == "Fallback response"
        assert model == llm_gateway.model_name_fallback

    async def test_send_message_all_models_fail(self, llm_gateway, mock_genai_client):
        """Test when all models fail."""
        mock_genai_client._client.aio.models.generate_content.side_effect = ResourceExhausted(
            "All models quota exceeded"
        )

        with pytest.raises(RuntimeError, match="All LLM models failed"):
            await llm_gateway.send_message(chat=None, message="Hello", tier=TIER_FLASH)

    async def test_send_message_circuit_breaker_open(self, llm_gateway, mock_genai_client):
        """Test behavior when circuit breaker is open."""
        circuit = llm_gateway._get_circuit_breaker(llm_gateway.model_name_flash)
        for _ in range(6):
            circuit.record_failure()

        mock_response = Mock()
        mock_response.text = "Fallback response"
        mock_response.usage_metadata = None
        mock_genai_client._client.aio.models.generate_content.return_value = mock_response

        response, model, obj, usage = await llm_gateway.send_message(
            chat=None, message="Hello", tier=TIER_FLASH
        )

        assert model == llm_gateway.model_name_fallback

    async def test_send_message_with_images(self, llm_gateway, mock_genai_client):
        """Test message sending with images."""
        sample_images = [
            {
                "base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=",
                "name": "test.jpg",
            }
        ]

        mock_response = Mock()
        mock_response.text = "I see an image"
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 50
        mock_response.usage_metadata.candidates_token_count = 30

        mock_genai_client._client.aio.models.generate_content.return_value = mock_response

        response, model, obj, usage = await llm_gateway.send_message(
            chat=None, message="What do you see?", tier=TIER_FLASH, images=sample_images
        )

        assert response == "I see an image"
        call_args = mock_genai_client._client.aio.models.generate_content.call_args
        assert "contents" in call_args.kwargs


class TestOpenRouterIntegration:
    """Test OpenRouter client integration."""

    def test_get_openrouter_client_new(self, llm_gateway):
        """Test lazy loading OpenRouter client."""
        from backend.services.llm_clients.openrouter_client import OpenRouterClient

        mock_client = Mock()
        OpenRouterClient.return_value = mock_client

        client = llm_gateway._get_openrouter_client()
        assert client == mock_client
        OpenRouterClient.assert_called_once_with(default_tier="rag")

    def test_get_openrouter_client_cached(self, llm_gateway):
        """Test caching of OpenRouter client."""
        from backend.services.llm_clients.openrouter_client import OpenRouterClient

        mock_client = Mock()
        OpenRouterClient.return_value = mock_client

        client1 = llm_gateway._get_openrouter_client()
        client2 = llm_gateway._get_openrouter_client()

        assert client1 == client2
        assert OpenRouterClient.call_count == 1

    async def test_call_openrouter_success(self, llm_gateway):
        """Test successful OpenRouter call."""
        mock_client = AsyncMock()
        mock_result = Mock()
        mock_result.content = "OpenRouter response"
        mock_result.model_name = "openrouter-model"
        mock_client.complete.return_value = mock_result

        llm_gateway._openrouter_client = mock_client

        messages = [{"role": "user", "content": "Hello"}]
        system_prompt = "You are helpful"

        response = await llm_gateway._call_openrouter(messages, system_prompt)
        assert response == "OpenRouter response"
        mock_client.complete.assert_called_once()

    async def test_call_openrouter_unavailable(self, llm_gateway):
        """Test OpenRouter call when client unavailable."""
        llm_gateway._openrouter_client = None

        with pytest.raises(RuntimeError, match="OpenRouter client not available"):
            await llm_gateway._call_openrouter([], "")


class TestCreateChatWithHistory:
    """Test chat session creation with history."""

    def test_create_chat_with_history_success(self, llm_gateway, mock_genai_client):
        """Test successful chat creation with history."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        mock_chat = Mock()
        mock_genai_client.create_chat_session.return_value = mock_chat

        chat = llm_gateway.create_chat_with_history(history, TIER_FLASH)

        assert chat == mock_chat
        mock_genai_client.create_chat_session.assert_called_once_with(
            model=llm_gateway.model_name_flash,
            history=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
        )

    def test_create_chat_with_history_empty(self, llm_gateway, mock_genai_client):
        """Test chat creation with empty history."""
        mock_chat = Mock()
        mock_genai_client.create_chat_session.return_value = mock_chat

        chat = llm_gateway.create_chat_with_history([])

        assert chat == mock_chat
        mock_genai_client.create_chat_session.assert_called_once_with(
            model=llm_gateway.model_name_flash, history=[]
        )

    def test_create_chat_with_history_invalid_type(self, llm_gateway, mock_genai_client):
        """Test chat creation with invalid history type."""
        mock_chat = Mock()
        mock_genai_client.create_chat_session.return_value = mock_chat

        chat = llm_gateway.create_chat_with_history("invalid")

        assert chat == mock_chat
        mock_genai_client.create_chat_session.assert_called_once_with(
            model=llm_gateway.model_name_flash, history=[]
        )

    def test_create_chat_with_history_genai_unavailable(self, llm_gateway):
        """Test chat creation when GenAI client unavailable."""
        llm_gateway._available = False

        chat = llm_gateway.create_chat_with_history([])

        assert chat is None


class TestHealthCheck:
    """Test health check functionality."""

    async def test_health_check_all_healthy(self, llm_gateway, mock_genai_client):
        """Test health check when all services are healthy."""
        mock_genai_client.generate_content = AsyncMock(return_value={"text": "pong"})

        with patch("backend.services.llm_clients.openrouter_client.OpenRouterClient") as mock_openrouter:
            mock_openrouter.return_value = Mock()

            status = await llm_gateway.health_check()

            assert status["gemini_pro"] is True
            assert status["gemini_flash"] is True
            assert status["gemini_flash_lite"] is True
            assert status["openrouter"] is True

    async def test_health_check_genai_unavailable(self, llm_gateway):
        """Test health check when GenAI client unavailable."""
        llm_gateway._available = False

        with patch("backend.services.llm_clients.openrouter_client.OpenRouterClient") as mock_openrouter:
            mock_openrouter.return_value = Mock()

            status = await llm_gateway.health_check()

            assert status["gemini_pro"] is False
            assert status["gemini_flash"] is False
            assert status["gemini_flash_lite"] is False
            assert status["openrouter"] is True


class TestEdgeCases:
    """Test edge cases and error conditions."""

    async def test_send_message_genai_unavailable(self, llm_gateway):
        """Test sending message when GenAI client unavailable."""
        llm_gateway._available = False

        with pytest.raises(RuntimeError, match="All LLM models failed"):
            await llm_gateway.send_message(chat=None, message="Hello", tier=TIER_FLASH)

    async def test_send_message_no_genai_client(self, llm_gateway):
        """Test sending message when GenAI client is None."""
        llm_gateway._genai_client = None

        with pytest.raises(RuntimeError, match="All LLM models failed"):
            await llm_gateway.send_message(chat=None, message="Hello", tier=TIER_FLASH)


class TestIntegrationFlows:
    """Integration-style tests for complete flows."""

    async def test_complete_fallback_chain(self, llm_gateway, mock_genai_client):
        """Test complete fallback chain from PRO to fallback."""
        responses = [
            ResourceExhausted("Pro quota exceeded"),
            ResourceExhausted("Flash quota exceeded"),
            Mock(text="Final fallback response", usage_metadata=None),
        ]
        mock_genai_client._client.aio.models.generate_content.side_effect = responses

        response, model, obj, usage = await llm_gateway.send_message(
            chat=None, message="Hello", tier=TIER_PRO
        )

        assert response == "Final fallback response"
        assert model == llm_gateway.model_name_fallback

    async def test_function_calling_with_tools(
        self, llm_gateway, mock_genai_client, sample_gemini_tools
    ):
        """Test function calling with proper tool configuration."""
        mock_response = Mock()
        mock_response.text = None
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 15
        mock_response.usage_metadata.candidates_token_count = 10

        mock_genai_client._client.aio.models.generate_content.return_value = mock_response

        response, model, obj, usage = await llm_gateway.send_message(
            chat=None, message="Search web for Bali", tier=TIER_FLASH, enable_function_calling=True
        )

        assert response == ""
        assert model == llm_gateway.model_name_flash
        assert obj == mock_response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
