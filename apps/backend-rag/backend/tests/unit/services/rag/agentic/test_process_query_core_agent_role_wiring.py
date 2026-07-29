"""T4 unified principal (spec `2026-07-24-zantara-bot-consultant-assistant-
spec.md` §5 item T4 — "two parallel auth systems") — process_query_core()
`agent_role` wiring.

Before this change, `OrchestratorCore.process_query_core` (the sync `/query`
endpoint's call path — the one `wa_inbox_bot.py` actually uses) had NO
`agent_role` parameter at all: only `OrchestratorStreamingCore.stream_query_core`
(the workspace-stream JWT path) threaded `AgentRole` onto `AgentState.agent_role`,
the single field `tool_authorizer.py` reads for RBAC. A WhatsApp sender's
`agent_role` was therefore ALWAYS `None`, hard-denying every `SENSITIVE_TOOLS`
entry regardless of who was actually texting.

This file proves the new `agent_role` kwarg on `process_query_core`:
1. is stamped onto `state.agent_role` — the exact field
   `_prepare_react_loop` already stamps for the streaming path, read
   generically by `reasoning.py` via `getattr(state, "agent_role", None)`
   at every `execute_tool` call site regardless of which caller set it;
2. defaults to `None` when omitted — byte-identical to `process_query_core`'s
   behavior before this parameter existed;
3. is completely independent from `profile`/`state.caller_profile` (the
   pre-existing WA team-assistant V1 carry, see
   `test_process_query_core_team_crm_wiring.py`) — neither one influences
   the other's cache-skip gate or state field.

Follows the exact `wired_core` fixture pattern established in
test_curated_qa_grounding_injection.py / test_process_query_core_team_crm_wiring.py:
a real OrchestratorCore with just enough mocked dependencies to drive
process_query_core() past the cache step, halted deliberately right after
routing/state-stamping so the rest of the (heavy) ReAct pipeline never needs
to be faked.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.agents.team_agent_config import ROLE_ADMIN, ROLE_EXECUTIVE_CONSULTANT
from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
from backend.services.tools.definitions import AgentState


class _StopAfterRouting(Exception):
    """Sentinel used to halt process_query_core right after routing/state-
    stamping — proves we reached (and passed) the cache-gate step without
    needing to fake the rest of the ReAct/response-building stack."""


@pytest.fixture
def wired_core() -> OrchestratorCore:
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
        return core


@pytest.mark.asyncio
async def test_agent_role_kwarg_is_stamped_onto_state(wired_core: OrchestratorCore) -> None:
    """GUILT: passing `agent_role=ROLE_ADMIN` (the T4-derived owner
    principal) reaches `state.agent_role` — the exact field
    `tool_authorizer.py` reads via `getattr(state, "agent_role", None)`."""
    state = AgentState(query="q")
    wired_core.routing_manager = SimpleNamespace(
        route_query=AsyncMock(return_value=("flash", False, state)),
    )
    wired_core.prompt_builder.build_system_prompt = MagicMock(side_effect=_StopAfterRouting)

    with pytest.raises(_StopAfterRouting):
        await wired_core.process_query_core(
            query="show me team hours",
            user_id="whatsapp_628230102328",
            conversation_history=None,
            start_time=0.0,
            agent_role=ROLE_ADMIN,
        )

    assert state.agent_role is ROLE_ADMIN


@pytest.mark.asyncio
async def test_omitted_agent_role_stamps_none(wired_core: OrchestratorCore) -> None:
    """FLAG-OFF / INNOCENCE: every caller that does not pass `agent_role`
    at all (every caller today, and the WA path with T4's flag off) gets
    `state.agent_role is None` — byte-identical to `process_query_core`'s
    behavior before this parameter existed."""
    state = AgentState(query="q")
    wired_core.routing_manager = SimpleNamespace(
        route_query=AsyncMock(return_value=("flash", False, state)),
    )
    wired_core.prompt_builder.build_system_prompt = MagicMock(side_effect=_StopAfterRouting)

    with pytest.raises(_StopAfterRouting):
        await wired_core.process_query_core(
            query="what is a KITAS",
            user_id="web-user-1",
            conversation_history=None,
            start_time=0.0,
        )

    assert state.agent_role is None


@pytest.mark.asyncio
async def test_explicit_none_agent_role_stamps_none(wired_core: OrchestratorCore) -> None:
    """INNOCENCE: an explicit `agent_role=None` (e.g. a client/unknown WA
    sender for whom `_derive_wa_agent_role` returned None) behaves exactly
    like omitting the kwarg."""
    state = AgentState(query="q")
    wired_core.routing_manager = SimpleNamespace(
        route_query=AsyncMock(return_value=("flash", False, state)),
    )
    wired_core.prompt_builder.build_system_prompt = MagicMock(side_effect=_StopAfterRouting)

    with pytest.raises(_StopAfterRouting):
        await wired_core.process_query_core(
            query="what is a KITAS",
            user_id="whatsapp_628899999999",
            conversation_history=None,
            start_time=0.0,
            agent_role=None,
        )

    assert state.agent_role is None


@pytest.mark.asyncio
async def test_agent_role_independent_of_cache_skip_gate(wired_core: OrchestratorCore) -> None:
    """Regression guard: the FAQ/semantic cache skip gate is keyed on
    `profile` (`is_team_or_creator_profile`) ONLY — `agent_role` being set
    must NOT accidentally couple into it. A caller with `agent_role` set
    but `profile=None` still hits both caches exactly as before T4."""
    state = AgentState(query="q")
    wired_core.routing_manager = SimpleNamespace(
        route_query=AsyncMock(return_value=("flash", False, state)),
    )
    wired_core.prompt_builder.build_system_prompt = MagicMock(side_effect=_StopAfterRouting)

    with pytest.raises(_StopAfterRouting):
        await wired_core.process_query_core(
            query="what is a KITAS",
            user_id="whatsapp_628230102328",
            conversation_history=None,
            start_time=0.0,
            agent_role=ROLE_ADMIN,
        )

    wired_core.check_faq_cache.assert_awaited_once()
    wired_core.check_semantic_cache.assert_awaited_once()
    assert state.agent_role is ROLE_ADMIN


@pytest.mark.asyncio
async def test_agent_role_and_profile_are_independently_stamped(
    wired_core: OrchestratorCore,
) -> None:
    """The realistic T4-armed shape: a DB-resolved team sender carries BOTH
    the pre-existing V1 `profile` (for team_crm_tools.py self-scoping) AND
    the new `agent_role` (for tool_authorizer.py RBAC) — set together,
    neither one clobbers or depends on the other."""
    state = AgentState(query="q")
    wired_core.routing_manager = SimpleNamespace(
        route_query=AsyncMock(return_value=("flash", False, state)),
    )
    wired_core.prompt_builder.build_system_prompt = MagicMock(side_effect=_StopAfterRouting)

    with pytest.raises(_StopAfterRouting):
        await wired_core.process_query_core(
            query="log my timesheet",
            user_id="whatsapp_628111000222",
            conversation_history=None,
            start_time=0.0,
            profile={"role": "team", "name": "Adit", "email": "adit@balizero.com"},
            agent_role=ROLE_EXECUTIVE_CONSULTANT,
        )

    assert state.caller_profile == {
        "role": "team",
        "name": "Adit",
        "email": "adit@balizero.com",
    }
    assert state.agent_role is ROLE_EXECUTIVE_CONSULTANT
