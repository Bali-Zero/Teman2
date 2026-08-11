"""Channel overlay on the NON-streaming path (2026-08-11).

`stream_query` has honoured `channel` since the overlays were written; its
non-streaming twin `process_query_core` never did — it had no such parameter.
That asymmetry mattered because the WhatsApp inbox bot sends
`"channel": "whatsapp"` on every call (`wa_inbox_bot.py`) and reaches the
backend through `/api/agentic-rag/query`, i.e. THIS path. Its declared
150-word budget was accepted by the request model and dropped on the floor.

Measured on the live worker before the fix — same question, same endpoint,
two runs each:

    channel="whatsapp"  ->  611 / 875 chars   (via the streaming twin)
    channel="webapp"    -> 1348 / 2163 chars
    channel omitted     -> 1964 / 1900 chars  (what WhatsApp actually got)

Production replies over the recorded history measure a median of 1586
characters against inbound client messages whose median is 57.

The corpus below is deliberately asymmetric about defaults, because the code
is: the streaming path defaults an absent channel to `"webapp"`, this one does
NOT. Adding a default here would reshape every existing non-streaming caller's
answers, so "no channel declared" must keep producing a byte-identical prompt.
Both halves are pinned — remove the append and `test_guilt_*` goes red; add a
`or "webapp"` default and `test_innocence_no_channel_*` goes red.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
from backend.services.tools.definitions import AgentState

_BASE_PROMPT = "SYSTEM-PROMPT-BODY"


class _StopAtChat(Exception):
    """Halt right where the assembled prompt is handed to the LLM gateway.

    Asserting on `create_chat_with_history(system_instruction=...)` — rather
    than on the local variable — is the point: it is the last place the prompt
    can still be changed, so a future edit that appends the overlay and then
    overwrites `system_prompt` cannot pass this corpus.
    """


@pytest.fixture
def wired_core() -> OrchestratorCore:
    """Same fixture shape as test_process_query_core_agent_role_wiring.py:
    a real OrchestratorCore with just enough mocked dependencies to drive
    `process_query_core` past the gates and caches and into prompt assembly."""
    with (
        patch("backend.services.rag.agentic.orchestrator_core.QueryPlanner"),
        patch("backend.services.rag.agentic.orchestrator_core.MultiAgentCoordinator"),
        patch(
            "backend.services.rag.agentic.orchestrator_core.requires_multi_agent",
            return_value=False,
        ),
        patch("backend.services.rag.agentic.orchestrator_core.KGAutoExpansion"),
    ):
        entity_ext = MagicMock()
        entity_ext.extract_entities = AsyncMock(return_value={"domain": "general"})

        core = OrchestratorCore(
            llm_gateway=MagicMock(),
            reasoning_engine=MagicMock(),
            prompt_builder=MagicMock(),
            query_gates=MagicMock(),
            memory_handler=MagicMock(),
            context_window_manager=MagicMock(),
            entity_extractor=entity_ext,
            kg_retrieval=None,
            semantic_cache=None,
            faq_cache=None,
            db_pool=None,
        )
        core.context_manager.get_basic_context = AsyncMock(
            return_value={"profiles": [], "facts": []},
        )
        core.retriever = None  # curated_qa injection no-ops without a retriever
        core.query_gates.run_all_gates = MagicMock(return_value=SimpleNamespace(triggered=False))
        core.check_faq_cache = AsyncMock(return_value=None)
        core.check_semantic_cache = AsyncMock(return_value=None)
        core.prompt_builder.build_system_prompt = MagicMock(return_value=_BASE_PROMPT)
        core.routing_manager = SimpleNamespace(
            route_query=AsyncMock(return_value=("flash", False, AgentState(query="q"))),
        )
        return core


async def _prompt_handed_to_the_model(core: OrchestratorCore, **kwargs) -> str:
    """Drive `process_query_core` and return the system prompt it hands over."""
    seen: dict[str, str] = {}

    def _capture(**call_kwargs):
        seen["prompt"] = call_kwargs["system_instruction"]
        raise _StopAtChat

    core.llm_gateway.create_chat_with_history = MagicMock(side_effect=_capture)

    with pytest.raises(_StopAtChat):
        await core.process_query_core(
            query="berapa lama proses KITAS?",
            user_id="whatsapp_628230102328",
            conversation_history=None,
            start_time=0.0,
            **kwargs,
        )

    return seen["prompt"]


@pytest.mark.asyncio
async def test_guilt_whatsapp_channel_reaches_the_system_prompt(wired_core) -> None:
    """GUILT: the WhatsApp bot's declared channel now shapes the prompt.

    Asserting on the budget line and not merely on "some block was appended":
    `Max words: 150` is the thing that was being dropped, and it is what makes
    the answer short. A block without it would satisfy a weaker assertion and
    change nothing for the client.
    """
    prompt = await _prompt_handed_to_the_model(wired_core, channel="whatsapp")

    assert prompt.startswith(_BASE_PROMPT), "the overlay must APPEND, never replace"
    assert "<channel_context>" in prompt
    assert "Channel: whatsapp" in prompt
    assert "Max words: 150" in prompt
    assert "Markdown: no" in prompt


@pytest.mark.asyncio
async def test_innocence_no_channel_leaves_the_prompt_byte_identical(wired_core) -> None:
    """INNOCENCE: every caller that declares nothing keeps today's prompt.

    This is the assertion that forbids copying the streaming twin's
    `or "webapp"` default into this path. Byte-identity, not "no whatsapp
    block" — a webapp block would also make the weaker assertion pass while
    silently reshaping every existing non-streaming caller's answers.
    """
    prompt = await _prompt_handed_to_the_model(wired_core)

    assert prompt == _BASE_PROMPT


@pytest.mark.asyncio
async def test_innocence_explicit_none_behaves_like_omitting_it(wired_core) -> None:
    """INNOCENCE: `channel=None` — what the router passes for any caller that
    did not set the body field — is the same no-op as omitting the kwarg."""
    prompt = await _prompt_handed_to_the_model(wired_core, channel=None)

    assert prompt == _BASE_PROMPT


@pytest.mark.asyncio
async def test_innocence_unknown_channel_appends_nothing_and_does_not_raise(
    wired_core,
) -> None:
    """INNOCENCE: `channel` is a client-settable body field. An unrecognised
    value must be inert, not an error and not a way to get caller text into
    the system prompt — `build_channel_context` is a closed lookup over
    CHANNEL_CONFIGS, so the vocabulary is fixed server-side."""
    prompt = await _prompt_handed_to_the_model(wired_core, channel="carrier-pigeon")

    assert prompt == _BASE_PROMPT
    assert "carrier-pigeon" not in prompt


@pytest.mark.asyncio
async def test_innocence_channel_does_not_touch_the_cache_skip_gate(wired_core) -> None:
    """Regression guard, mirroring the `agent_role` wiring corpus: the
    FAQ/semantic cache gate is keyed on `profile` only. Declaring a channel
    must not couple into it — a WhatsApp client still hits both caches."""
    await _prompt_handed_to_the_model(wired_core, channel="whatsapp")

    wired_core.check_faq_cache.assert_awaited_once()
    wired_core.check_semantic_cache.assert_awaited_once()
