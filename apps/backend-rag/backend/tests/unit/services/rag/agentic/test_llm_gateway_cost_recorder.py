"""
Unit tests for the llm_cost_events recording added to LLMGateway._call_model().

Context: LLMGateway._call_model() calls the raw google-genai SDK directly
(``client._client.aio.models.generate_content``) instead of going through
``GenAIClient.generate_content()``, so it historically bypassed
``record_llm_call`` entirely — the Postgres ``llm_cost_events`` ledger
undercounted real Gemini traffic (~3x, verified against AI Studio usage
2026-07-17/19: 182 real gemini-3.5-flash requests vs 66 recorded).

These tests cover both raw call sites inside ``_call_model``:
- the chat-history branch (``chat`` has a ``.history`` attribute)
- the fallback/no-history branch (``chat`` is ``None``)

and assert the fail-open contract: a recorder exception must never break
the chat response.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.llm_gateway import LLMGateway


def _make_fake_response(prompt_tokens: int = 42, completion_tokens: int = 7) -> SimpleNamespace:
    """Build a fake google-genai response with usage_metadata + text."""
    return SimpleNamespace(
        text="Hello from Gemini",
        candidates=[],
        usage_metadata=SimpleNamespace(
            prompt_token_count=prompt_tokens,
            candidates_token_count=completion_tokens,
        ),
    )


@pytest.fixture
def gateway_with_raw_client():
    """LLMGateway whose genai client exposes the raw SDK call path used by
    _call_model (client._client.aio.models.generate_content)."""
    with patch("backend.services.rag.agentic.llm_gateway.get_genai_client") as mock_get:
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client._client.aio.models.generate_content = AsyncMock(
            return_value=_make_fake_response(),
        )
        mock_get.return_value = mock_client
        gw = LLMGateway()
        gw._available = True
        yield gw, mock_client


class TestCallModelRecordsCost:
    @pytest.mark.asyncio
    async def test_fallback_branch_records_llm_call_once(self, gateway_with_raw_client):
        """chat=None takes the 'Fallback: Build content directly' branch
        (~line 820) — must record exactly once with real token counts."""
        gateway, _mock_client = gateway_with_raw_client

        with patch(
            "backend.services.observability.record_llm_call",
            new_callable=AsyncMock,
        ) as mock_record:
            text, response, usage = await gateway._call_model(
                "gemini-3-flash",
                with_tools=False,
                chat=None,
                message="hi",
                images=None,
            )

        assert text == "Hello from Gemini"
        mock_record.assert_awaited_once()
        call_kwargs = mock_record.call_args.kwargs
        assert call_kwargs["provider"] == "gemini"
        assert call_kwargs["model"] == "gemini-3-flash"
        assert call_kwargs["input_tokens"] == 42
        assert call_kwargs["output_tokens"] == 7
        assert call_kwargs["success"] is True
        assert call_kwargs["endpoint"] == "rag.gateway.chat"
        assert call_kwargs["cost_usd"] >= 0

    @pytest.mark.asyncio
    async def test_chat_history_branch_records_llm_call_once(self, gateway_with_raw_client):
        """chat with a .history attribute takes the chat-session branch
        (~line 737) — must also record exactly once."""
        gateway, _mock_client = gateway_with_raw_client
        chat = SimpleNamespace(history=[])

        with patch(
            "backend.services.observability.record_llm_call",
            new_callable=AsyncMock,
        ) as mock_record:
            text, response, usage = await gateway._call_model(
                "gemini-3-flash",
                with_tools=False,
                chat=chat,
                message="hi",
                images=None,
            )

        assert text == "Hello from Gemini"
        mock_record.assert_awaited_once()
        call_kwargs = mock_record.call_args.kwargs
        assert call_kwargs["provider"] == "gemini"
        assert call_kwargs["input_tokens"] == 42
        assert call_kwargs["output_tokens"] == 7

    @pytest.mark.asyncio
    async def test_recorder_exception_does_not_break_response(self, gateway_with_raw_client):
        """Fail-open: if record_llm_call raises, _call_model must still
        return the real response instead of propagating the recorder error."""
        gateway, _mock_client = gateway_with_raw_client

        with patch(
            "backend.services.observability.record_llm_call",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db pool not initialised"),
        ):
            text, response, usage = await gateway._call_model(
                "gemini-3-flash",
                with_tools=False,
                chat=None,
                message="hi",
                images=None,
            )

        assert text == "Hello from Gemini"
        assert usage.prompt_tokens == 42
        assert usage.completion_tokens == 7
