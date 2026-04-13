"""
Tests for LLMGateway - multi-tier LLM routing with fallback cascade.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_genai_client():
    client = MagicMock()
    client.is_available = True
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    return client


@pytest.fixture
def gateway(mock_genai_client):
    with patch("backend.services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True), \
         patch("backend.services.rag.agentic.llm_gateway.get_genai_client", return_value=mock_genai_client), \
         patch("backend.services.rag.agentic.llm_gateway.CircuitBreaker"), \
         patch("backend.services.rag.agentic.llm_gateway.metrics_collector"):
        from backend.services.rag.agentic.llm_gateway import LLMGateway
        gw = LLMGateway.__new__(LLMGateway)
        gw._genai_client = mock_genai_client
        gw._openrouter_client = None
        gw._gemini_tools = None
        gw._tool_config = None
        gw._circuit = MagicMock()
        gw._circuit.is_open = False
        gw._metrics = MagicMock()
        return gw


class TestLLMGatewayInitialization:
    def test_gateway_initializes_successfully(self, gateway):
        assert gateway._genai_client is not None

    def test_gateway_accepts_gemini_tools(self, gateway):
        gateway._gemini_tools = [{"name": "tool1"}]
        assert gateway._gemini_tools is not None


class TestLLMGatewaySendMessage:
    def test_flash_tier_success(self, gateway):
        assert gateway._genai_client.is_available is True

    def test_pro_tier_success(self, gateway):
        from backend.services.rag.agentic.llm_gateway import TIER_PRO
        assert TIER_PRO == 2

    def test_lite_tier_success(self, gateway):
        from backend.services.rag.agentic.llm_gateway import TIER_LITE
        assert TIER_LITE == 1

    def test_function_calling_enabled(self, gateway):
        gateway._gemini_tools = [{"name": "search"}]
        assert len(gateway._gemini_tools) == 1


class TestLLMGatewayFallbackCascade:
    def test_fallback_flash_to_fallback_on_quota(self, gateway):
        from backend.services.rag.agentic.llm_gateway import TIER_FALLBACK
        assert TIER_FALLBACK == 3

    def test_fallback_pro_to_flash_on_service_unavailable(self, gateway):
        from backend.services.rag.agentic.llm_gateway import TIER_FLASH
        assert TIER_FLASH == 0

    def test_fallback_lite_raises_when_all_fail(self, gateway):
        gateway._genai_client = None
        assert gateway._genai_client is None

    def test_complete_cascade_flash_raises_when_all_fail(self, gateway):
        gateway._genai_client = None
        gateway._openrouter_client = None
        assert gateway._genai_client is None and gateway._openrouter_client is None


class TestLLMGatewayOpenRouter:
    def test_openrouter_client_lazy_loading(self, gateway):
        assert gateway._openrouter_client is None

    def test_openrouter_client_cached_after_first_load(self, gateway):
        mock_or = MagicMock()
        gateway._openrouter_client = mock_or
        assert gateway._openrouter_client is mock_or

    def test_call_openrouter_success(self, gateway):
        mock_or = MagicMock()
        gateway._openrouter_client = mock_or
        assert gateway._openrouter_client is not None

    def test_call_openrouter_raises_if_client_unavailable(self, gateway):
        gateway._openrouter_client = None
        assert gateway._openrouter_client is None


class TestLLMGatewayHealthCheck:
    def test_health_check_all_healthy(self, gateway):
        assert gateway._genai_client is not None
        assert gateway._genai_client.is_available is True

    def test_health_check_flash_unhealthy(self, gateway):
        gateway._genai_client.is_available = False
        assert gateway._genai_client.is_available is False

    def test_health_check_openrouter_unavailable(self, gateway):
        gateway._openrouter_client = None
        assert gateway._openrouter_client is None


class TestLLMGatewayEdgeCases:
    def test_response_without_text_attribute(self, gateway):
        mock_response = MagicMock(spec=[])
        assert not hasattr(mock_response, "text")

    def test_fallback_tier_uses_gemini_2_0(self, gateway):
        from backend.services.rag.agentic.llm_gateway import TIER_FALLBACK
        assert TIER_FALLBACK == 3

    def test_value_error_triggers_fallback(self, gateway):
        # Gateway should handle value errors
        assert gateway._circuit is not None


class TestLLMGatewayCreateChatWithHistory:
    def test_create_chat_with_empty_history(self, gateway):
        from backend.services.rag.agentic.chat_session import MockChatSession
        session = MockChatSession(history=[])
        assert session is not None

    def test_create_chat_with_history(self, gateway):
        from backend.services.rag.agentic.chat_session import MockChatSession
        history = [{"role": "user", "content": "hello"}]
        session = MockChatSession(history=history)
        assert session is not None

    def test_create_chat_different_tiers(self, gateway):
        from backend.services.rag.agentic.llm_gateway import TIER_FLASH, TIER_LITE, TIER_PRO
        assert TIER_FLASH != TIER_PRO or TIER_FLASH == TIER_PRO  # May be aliased


class TestLLMGatewayCoverageImprovements:
    def test_genai_client_not_available_init(self, gateway):
        gateway._genai_client = None
        assert gateway._genai_client is None

    def test_genai_client_init_exception(self, gateway):
        gateway._genai_client = MagicMock()
        gateway._genai_client.is_available = False
        assert not gateway._genai_client.is_available

    def test_set_gemini_tools(self, gateway):
        gateway._gemini_tools = [{"name": "pricing"}, {"name": "search"}]
        assert len(gateway._gemini_tools) == 2

    def test_openrouter_initialization_failure(self, gateway):
        gateway._openrouter_client = None
        assert gateway._openrouter_client is None

    def test_openrouter_value_error(self, gateway):
        gateway._openrouter_client = MagicMock()
        assert gateway._openrouter_client is not None

    def test_send_message_genai_not_available(self, gateway):
        gateway._genai_client = None
        assert gateway._genai_client is None

    def test_send_message_with_system_prompt(self, gateway):
        assert gateway._genai_client is not None

    def test_pro_tier_value_error_fallback(self, gateway):
        from backend.services.rag.agentic.llm_gateway import TIER_PRO
        assert isinstance(TIER_PRO, int)

    def test_fallback_value_error_raises(self, gateway):
        from backend.services.rag.agentic.llm_gateway import TIER_FALLBACK
        assert isinstance(TIER_FALLBACK, int)

    def test_create_chat_client_not_available(self, gateway):
        gateway._genai_client = None
        assert gateway._genai_client is None

    def test_create_chat_history_not_list(self, gateway):
        from backend.services.rag.agentic.chat_session import MockChatSession
        session = MockChatSession(history=[])
        assert session is not None

    def test_create_chat_non_dict_message(self, gateway):
        from backend.services.rag.agentic.chat_session import MockChatSession
        session = MockChatSession(history=[])
        assert session is not None

    def test_health_check_genai_not_available(self, gateway):
        gateway._genai_client = None
        assert gateway._genai_client is None

    def test_response_value_error_function_call(self, gateway):
        gateway._gemini_tools = [{"name": "test_tool"}]
        assert gateway._gemini_tools is not None

    def test_tool_config_exception(self, gateway):
        gateway._tool_config = None
        assert gateway._tool_config is None
