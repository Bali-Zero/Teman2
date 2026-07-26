"""W0 safety pre-arm — T-VIS: per-request Gemini tool-declaration override.

Context: `LLMGateway._gemini_tools` is set ONCE at orchestrator-construction
time (`orchestrator.py.__init__` -> `set_gemini_tools`) and the gateway
instance is SHARED across every concurrent request — mutating
`self._gemini_tools` per request would be a request-isolation bug (request A
could leak its tool schema into request B). The fix threads an OPTIONAL
per-call `gemini_tools` override through `send_message` ->
`_send_with_fallback` -> `_call_model`, so a caller can narrow the tool
declarations sent to Gemini for THIS call only, without touching the shared
`_gemini_tools` list at all.

Guilt/innocence pairs:
- GUILT: passing an override with a narrower tool set must be what actually
  reaches the raw google-genai `generate_content` call — not the shared list.
- INNOCENCE: omitting the override (None, the default) must reproduce
  EXACTLY today's behaviour — the shared `_gemini_tools` list, unchanged.
- Edge case: an override of `[]` (every tool filtered out for this caller)
  must mean "send no tools", not silently fall back to the shared list —
  `None` and `[]` are semantically different ("no override" vs "override to
  nothing") and the guard must not conflate them (cicatrix-superscar.md
  family #3 — under-match by falsy-conflation is the same bug class as
  over-match by substring).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.llm_gateway import LLMGateway


def _decl(name: str) -> dict:
    return {
        "name": name,
        "description": f"{name} description",
        "parameters": {"type": "OBJECT", "properties": {}, "required": []},
    }


def _make_fake_response():
    resp = MagicMock()
    resp.text = "Hello from Gemini"
    resp.candidates = []
    resp.usage_metadata = MagicMock(prompt_token_count=1, candidates_token_count=1)
    return resp


@pytest.fixture
def gateway_with_raw_client():
    """Mirrors test_llm_gateway_cost_recorder.py's fixture — a gateway whose
    genai client exposes the raw SDK call path `_call_model` drives."""
    with patch("backend.services.rag.agentic.llm_gateway.get_genai_client") as mock_get:
        mock_client = MagicMock()
        mock_client.is_available = True
        mock_client._client.aio.models.generate_content = AsyncMock(
            return_value=_make_fake_response(),
        )
        mock_get.return_value = mock_client
        gw = LLMGateway()
        gw._available = True
        gw.set_gemini_tools([_decl("shared_tool")])
        yield gw, mock_client


def _sent_tool_names(mock_client) -> set[str]:
    config = mock_client._client.aio.models.generate_content.call_args.kwargs["config"]
    tools = getattr(config, "tools", None)
    if not tools:
        return set()
    return {fd.name for fd in tools[0].function_declarations}


class TestCallModelGeminiToolsOverride:
    @pytest.mark.asyncio
    async def test_guilt_override_replaces_shared_tools(self, gateway_with_raw_client):
        gateway, mock_client = gateway_with_raw_client

        await gateway._call_model(
            "gemini-3-flash",
            with_tools=True,
            chat=None,
            message="hi",
            gemini_tools_override=[_decl("scoped_tool")],
        )

        assert _sent_tool_names(mock_client) == {"scoped_tool"}

    @pytest.mark.asyncio
    async def test_innocence_no_override_uses_shared_tools_unchanged(
        self, gateway_with_raw_client
    ):
        gateway, mock_client = gateway_with_raw_client

        await gateway._call_model(
            "gemini-3-flash",
            with_tools=True,
            chat=None,
            message="hi",
            gemini_tools_override=None,
        )

        assert _sent_tool_names(mock_client) == {"shared_tool"}

    @pytest.mark.asyncio
    async def test_empty_override_sends_no_tools_does_not_fall_back(
        self, gateway_with_raw_client
    ):
        """[] must mean 'send nothing', never a silent fallback to the
        shared list — distinguishes 'no override' (None) from 'override to
        empty' ([])."""
        gateway, mock_client = gateway_with_raw_client

        await gateway._call_model(
            "gemini-3-flash",
            with_tools=True,
            chat=None,
            message="hi",
            gemini_tools_override=[],
        )

        assert _sent_tool_names(mock_client) == set()

    @pytest.mark.asyncio
    async def test_override_with_tools_false_sends_no_tools_either_way(
        self, gateway_with_raw_client
    ):
        """with_tools=False must still short-circuit the tools branch
        entirely regardless of override — unrelated call sites
        (enable_function_calling=False) must see zero behaviour change."""
        gateway, mock_client = gateway_with_raw_client

        await gateway._call_model(
            "gemini-3-flash",
            with_tools=False,
            chat=None,
            message="hi",
            gemini_tools_override=[_decl("scoped_tool")],
        )

        assert _sent_tool_names(mock_client) == set()

    @pytest.mark.asyncio
    async def test_override_applies_on_chat_history_branch_too(self, gateway_with_raw_client):
        """The chat-with-.history branch (~line 690) builds config the same
        way as the fallback branch — must honour the override too."""
        from types import SimpleNamespace

        gateway, mock_client = gateway_with_raw_client
        chat = SimpleNamespace(history=[])

        await gateway._call_model(
            "gemini-3-flash",
            with_tools=True,
            chat=chat,
            message="hi",
            gemini_tools_override=[_decl("scoped_tool")],
        )

        assert _sent_tool_names(mock_client) == {"scoped_tool"}


class TestSendMessageForwardsGeminiToolsOverride:
    @pytest.mark.asyncio
    async def test_send_message_forwards_override_to_send_with_fallback(self):
        with patch("backend.services.rag.agentic.llm_gateway.get_genai_client"):
            gateway = LLMGateway()

        from backend.services.llm_clients.pricing import create_token_usage

        override = [_decl("scoped_tool")]
        usage = create_token_usage(prompt_tokens=1, completion_tokens=1, model="m")

        with patch.object(gateway, "_send_with_fallback") as mock_send:
            mock_send.return_value = ("r", "m", MagicMock(), usage)
            await gateway.send_message(chat=MagicMock(), message="hi", gemini_tools=override)

        assert mock_send.call_args.kwargs["gemini_tools_override"] == override

    @pytest.mark.asyncio
    async def test_send_message_default_forwards_none(self):
        with patch("backend.services.rag.agentic.llm_gateway.get_genai_client"):
            gateway = LLMGateway()

        from backend.services.llm_clients.pricing import create_token_usage

        usage = create_token_usage(prompt_tokens=1, completion_tokens=1, model="m")

        with patch.object(gateway, "_send_with_fallback") as mock_send:
            mock_send.return_value = ("r", "m", MagicMock(), usage)
            await gateway.send_message(chat=MagicMock(), message="hi")

        assert mock_send.call_args.kwargs["gemini_tools_override"] is None
