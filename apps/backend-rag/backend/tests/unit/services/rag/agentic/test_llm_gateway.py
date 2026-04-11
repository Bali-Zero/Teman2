"""
Unit tests for backend/services/rag/agentic/llm_gateway.py

Covers: LLMGateway init, _available property, set_gemini_tools,
        _get_model_for_tier, _get_fallback_chain, _get_circuit_breaker,
        _is_circuit_open, _record_success, _record_failure,
        create_chat_with_history, send_message, _get_openrouter_client,
        _send_with_fallback, tier constants.
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from backend.services.rag.agentic.llm_gateway import (
    TIER_FALLBACK,
    TIER_FLASH,
    TIER_LITE,
    TIER_PRO,
    LLMGateway,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def gateway():
    """LLMGateway with mocked GenAI."""
    with patch("backend.services.rag.agentic.llm_gateway.get_genai_client") as mock_get:
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_get.return_value = mock_client
        gw = LLMGateway()
        gw._available = True
        yield gw


@pytest.fixture
def gateway_no_genai():
    """LLMGateway without GenAI available."""
    with patch("backend.services.rag.agentic.llm_gateway.GENAI_AVAILABLE", False):
        gw = LLMGateway()
        yield gw


# ============================================================================
# Tier Constants
# ============================================================================


class TestTierConstants:
    def test_tier_values(self):
        assert TIER_FLASH == 0
        assert TIER_LITE == 1
        assert TIER_PRO == 2
        assert TIER_FALLBACK == 3


# ============================================================================
# Init
# ============================================================================


class TestInit:
    def test_init_default(self, gateway):
        assert gateway._gemini_tools == []
        assert gateway._openrouter_client is None
        assert gateway._circuit_breaker_threshold == 5
        assert gateway._max_fallback_depth == 3
        assert gateway._max_fallback_cost_usd == 0.10

    def test_init_with_tools(self):
        with patch("backend.services.rag.agentic.llm_gateway.get_genai_client"):
            tools = [{"name": "tool1"}]
            gw = LLMGateway(gemini_tools=tools)
            assert gw._gemini_tools == tools


# ============================================================================
# _available property
# ============================================================================


class TestAvailable:
    def test_set_available(self, gateway):
        gateway._available = True
        assert gateway._available is True
        gateway._available = False
        assert gateway._available is False

    def test_available_without_override(self, gateway_no_genai):
        # Without override, checks actual client
        assert gateway_no_genai._available is False


# ============================================================================
# gemini_tools / set_gemini_tools
# ============================================================================


class TestGeminiTools:
    def test_get_gemini_tools(self, gateway):
        assert gateway.gemini_tools == []

    def test_set_gemini_tools(self, gateway):
        tools = [{"name": "test_tool"}]
        gateway.set_gemini_tools(tools)
        assert gateway.gemini_tools == tools

    def test_set_gemini_tools_none(self, gateway):
        gateway.set_gemini_tools(None)
        assert gateway.gemini_tools == []


# ============================================================================
# _get_model_for_tier
# ============================================================================


class TestGetModelForTier:
    def test_flash_tier(self, gateway):
        model = gateway._get_model_for_tier(TIER_FLASH)
        assert model == gateway.model_name_flash

    def test_pro_tier(self, gateway):
        model = gateway._get_model_for_tier(TIER_PRO)
        assert model == gateway.model_name_pro

    def test_lite_tier(self, gateway):
        model = gateway._get_model_for_tier(TIER_LITE)
        assert model == gateway.model_name_fallback

    def test_fallback_tier(self, gateway):
        model = gateway._get_model_for_tier(TIER_FALLBACK)
        assert model == gateway.model_name_fallback

    def test_unknown_tier_defaults_flash(self, gateway):
        model = gateway._get_model_for_tier(99)
        assert model == gateway.model_name_flash


# ============================================================================
# _get_fallback_chain
# ============================================================================


class TestGetFallbackChain:
    def test_flash_chain(self, gateway):
        chain = gateway._get_fallback_chain(TIER_FLASH)
        assert gateway.model_name_flash in chain
        assert gateway.model_name_fallback in chain

    def test_pro_chain(self, gateway):
        chain = gateway._get_fallback_chain(TIER_PRO)
        assert gateway.model_name_pro in chain
        assert gateway.model_name_fallback in chain

    def test_no_duplicates(self, gateway):
        chain = gateway._get_fallback_chain(TIER_FLASH)
        assert len(chain) == len(set(chain))

    def test_fallback_tier_chain(self, gateway):
        chain = gateway._get_fallback_chain(TIER_FALLBACK)
        assert gateway.model_name_fallback in chain


# ============================================================================
# Circuit Breaker
# ============================================================================


class TestCircuitBreaker:
    def test_get_circuit_breaker_creates(self, gateway):
        cb = gateway._get_circuit_breaker("test_model")
        assert cb is not None

    def test_get_circuit_breaker_reuses(self, gateway):
        cb1 = gateway._get_circuit_breaker("test_model")
        cb2 = gateway._get_circuit_breaker("test_model")
        assert cb1 is cb2

    def test_is_circuit_open_default(self, gateway):
        assert gateway._is_circuit_open("test_model") is False

    def test_record_success(self, gateway):
        gateway._record_success("test_model")
        # Should not raise

    @patch("backend.services.rag.agentic.llm_gateway.ErrorClassifier")
    @patch("backend.services.rag.agentic.llm_gateway.get_error_context")
    def test_record_failure(self, mock_ctx, mock_classifier, gateway):
        mock_classifier.classify_error.return_value = ("transient", "low")
        mock_ctx.return_value = {}
        gateway._record_failure("test_model", Exception("test error"))


# ============================================================================
# create_chat_with_history
# ============================================================================


class TestCreateChatWithHistory:
    def test_no_client_returns_mock(self, gateway_no_genai):
        session = gateway_no_genai.create_chat_with_history(
            history_to_use=[{"role": "user", "content": "Hello"}],
        )
        assert session is not None

    def test_with_none_history(self, gateway_no_genai):
        session = gateway_no_genai.create_chat_with_history(history_to_use=None)
        assert session is not None

    def test_with_empty_history(self, gateway_no_genai):
        session = gateway_no_genai.create_chat_with_history(history_to_use=[])
        assert session is not None

    def test_with_client(self, gateway):
        mock_client = MagicMock()
        mock_client.is_available = True
        gateway._genai_client = mock_client

        session = gateway.create_chat_with_history(
            history_to_use=[{"role": "user", "content": "Hi"}],
            model_tier=TIER_FLASH,
            system_instruction="You are helpful.",
        )
        assert session is not None


# ============================================================================
# _get_openrouter_client
# ============================================================================


class TestGetOpenRouterClient:
    @patch("backend.services.rag.agentic.llm_gateway.OpenRouterClient")
    def test_lazy_init(self, mock_or, gateway):
        mock_instance = MagicMock()
        mock_or.return_value = mock_instance
        client = gateway._get_openrouter_client()
        assert client is mock_instance

    @patch("backend.services.rag.agentic.llm_gateway.OpenRouterClient")
    def test_reuses_instance(self, mock_or, gateway):
        mock_instance = MagicMock()
        mock_or.return_value = mock_instance
        c1 = gateway._get_openrouter_client()
        c2 = gateway._get_openrouter_client()
        assert c1 is c2
        assert mock_or.call_count == 1

    @patch("backend.services.rag.agentic.llm_gateway.OpenRouterClient")
    def test_init_failure(self, mock_or, gateway):
        import httpx
        mock_or.side_effect = httpx.HTTPError("fail")
        client = gateway._get_openrouter_client()
        assert client is None


# ============================================================================
# send_message
# ============================================================================


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_calls_fallback(self, gateway):
        mock_usage = MagicMock()
        mock_usage.cost_usd = 0.001
        gateway._send_with_fallback = AsyncMock(
            return_value=("response text", "model-name", MagicMock(), mock_usage),
        )
        text, model, obj, usage = await gateway.send_message(
            chat=None, message="Hello", tier=TIER_FLASH,
        )
        assert text == "response text"
        assert model == "model-name"
        gateway._send_with_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_message_all_fail(self, gateway):
        gateway._send_with_fallback = AsyncMock(side_effect=RuntimeError("All failed"))
        with pytest.raises(RuntimeError, match="All LLM models failed"):
            await gateway.send_message(chat=None, message="Hello")

    @pytest.mark.asyncio
    async def test_send_message_with_system_prompt(self, gateway):
        mock_usage = MagicMock()
        mock_usage.cost_usd = 0.0
        gateway._send_with_fallback = AsyncMock(
            return_value=("response", "model", None, mock_usage),
        )
        await gateway.send_message(
            chat=None, message="Hello",
            system_prompt="You are Zantara",
            tier=TIER_PRO,
        )
        call_kwargs = gateway._send_with_fallback.call_args[1]
        assert call_kwargs["system_prompt"] == "You are Zantara"
        assert call_kwargs["model_tier"] == TIER_PRO

    @pytest.mark.asyncio
    async def test_send_message_with_conversation(self, gateway):
        mock_usage = MagicMock()
        mock_usage.cost_usd = 0.0
        gateway._send_with_fallback = AsyncMock(
            return_value=("r", "m", None, mock_usage),
        )
        await gateway.send_message(
            chat=None, message="Hello",
            conversation_messages=[{"role": "user", "content": "prev"}],
        )
        call_kwargs = gateway._send_with_fallback.call_args[1]
        assert len(call_kwargs["conversation_messages"]) == 1

    @pytest.mark.asyncio
    async def test_send_message_with_images(self, gateway):
        mock_usage = MagicMock()
        mock_usage.cost_usd = 0.0
        gateway._send_with_fallback = AsyncMock(
            return_value=("r", "m", None, mock_usage),
        )
        await gateway.send_message(
            chat=None, message="What is this?",
            images=[{"base64": "data:image/png;base64,abc", "name": "test.png"}],
        )
        call_kwargs = gateway._send_with_fallback.call_args[1]
        assert call_kwargs["images"] is not None


# ============================================================================
# _get_genai_client
# ============================================================================


class TestGetGenAIClient:
    def test_lazy_load(self, gateway):
        gateway._genai_client = None
        with patch("backend.services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True):
            with patch("backend.services.rag.agentic.llm_gateway.get_genai_client") as mock_get:
                mock_client = MagicMock()
                mock_client.is_available = True
                mock_get.return_value = mock_client
                result = gateway._get_genai_client()
                assert result is not None

    def test_not_available(self):
        with patch("backend.services.rag.agentic.llm_gateway.GENAI_AVAILABLE", False):
            gw = LLMGateway()
            result = gw._get_genai_client()
            assert result is None

    def test_init_error(self, gateway):
        gateway._genai_client = None
        with patch("backend.services.rag.agentic.llm_gateway.GENAI_AVAILABLE", True):
            with patch("backend.services.rag.agentic.llm_gateway.get_genai_client", side_effect=Exception("fail")):
                result = gateway._get_genai_client()
                assert result is None
