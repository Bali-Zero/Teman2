"""WA team-assistant Phase 2 (2026-07-20 ruling) — process_query_core() wiring.

Two contracts under test, both inside `OrchestratorCore.process_query_core`:

1. `state.caller_profile` is stamped from `user_context["profile"]` right
   after routing (`routing_manager.route_query`) — the same request-scoped
   carry pattern VASSAL already uses for `state.agent_role`. Read
   downstream by `reasoning.py` and forwarded to `team_crm_tools.py` via
   `tool_executor.execute_tool(caller_profile=...)`.
2. Team/creator senders' FAQ-cache and semantic-cache READS are skipped
   outright (ruling: "team-answer MAI in cache/log in chiaro") — every
   other caller (profile=None, or any other role) is unaffected.

Follows the exact `wired_core` fixture pattern established in
test_curated_qa_grounding_injection.py: a real OrchestratorCore with just
enough mocked dependencies to drive process_query_core() past the cache
step, halted deliberately right after routing/state-stamping so the rest
of the (heavy) ReAct pipeline never needs to be faked.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        # Gate never triggers — reach the cache steps.
        core.query_gates.run_all_gates = MagicMock(return_value=SimpleNamespace(triggered=False))
        # Spy on the cache checks directly (never a real Redis/vector call).
        core.check_faq_cache = AsyncMock(return_value=None)
        core.check_semantic_cache = AsyncMock(return_value=None)
        # Each test wires its own routing_manager (returns a fresh AgentState
        # it can assert on) and halts at prompt_builder, past the cache step.
        return core


@pytest.mark.asyncio
async def test_team_profile_skips_both_cache_checks(wired_core: OrchestratorCore) -> None:
    state = AgentState(query="q")
    wired_core.routing_manager = SimpleNamespace(
        route_query=AsyncMock(return_value=("flash", False, state)),
    )
    wired_core.prompt_builder.build_system_prompt = MagicMock(side_effect=_StopAfterRouting)

    with pytest.raises(_StopAfterRouting):
        await wired_core.process_query_core(
            query="what are my clients",
            user_id="whatsapp_628111000222",
            conversation_history=None,
            start_time=0.0,
            profile={"role": "team", "name": "Member Alpha", "email": "alpha@balizero.com"},
        )

    wired_core.check_faq_cache.assert_not_awaited()
    wired_core.check_semantic_cache.assert_not_awaited()
    # And the second contract: state.caller_profile was stamped.
    assert state.caller_profile == {
        "role": "team",
        "name": "Member Alpha",
        "email": "alpha@balizero.com",
    }


@pytest.mark.asyncio
async def test_creator_profile_skips_both_cache_checks(wired_core: OrchestratorCore) -> None:
    state = AgentState(query="q")
    wired_core.routing_manager = SimpleNamespace(
        route_query=AsyncMock(return_value=("flash", False, state)),
    )
    wired_core.prompt_builder.build_system_prompt = MagicMock(side_effect=_StopAfterRouting)

    with pytest.raises(_StopAfterRouting):
        await wired_core.process_query_core(
            query="how many clients do we have",
            user_id="whatsapp_628230102328",
            conversation_history=None,
            start_time=0.0,
            profile={"role": "creator"},
        )

    wired_core.check_faq_cache.assert_not_awaited()
    wired_core.check_semantic_cache.assert_not_awaited()
    assert state.caller_profile == {"role": "creator"}


@pytest.mark.asyncio
async def test_innocence_no_profile_still_hits_both_caches(wired_core: OrchestratorCore) -> None:
    """Every existing caller (web chat, non-team WA senders) passes
    profile=None — cache reads must remain exactly as before this PR."""
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

    wired_core.check_faq_cache.assert_awaited_once()
    wired_core.check_semantic_cache.assert_awaited_once()
    # No `profile` kwarg was passed, so the merge at step 1a2 never fires —
    # caller_profile ends up whatever prepare_query_context's own "profile"
    # key was (empty dict on this fixture's context-load fallback path, or
    # None on a clean load in prod). Either way it must be falsy: the point
    # of this test is that a non-team/creator sender is a complete no-op.
    assert not state.caller_profile


@pytest.mark.asyncio
async def test_innocence_client_profile_role_still_hits_both_caches(
    wired_core: OrchestratorCore,
) -> None:
    """Defense-in-depth: even if a "client"-role profile ever reached this
    method (it shouldn't — V1's innocence contract omits `profile` entirely
    for client/unknown senders), the cache gate only recognizes
    team/creator, so a client role does not accidentally skip caching."""
    state = AgentState(query="q")
    wired_core.routing_manager = SimpleNamespace(
        route_query=AsyncMock(return_value=("flash", False, state)),
    )
    wired_core.prompt_builder.build_system_prompt = MagicMock(side_effect=_StopAfterRouting)

    with pytest.raises(_StopAfterRouting):
        await wired_core.process_query_core(
            query="what is a KITAS",
            user_id="whatsapp_628999999999",
            conversation_history=None,
            start_time=0.0,
            profile={"role": "client"},
        )

    wired_core.check_faq_cache.assert_awaited_once()
    wired_core.check_semantic_cache.assert_awaited_once()
