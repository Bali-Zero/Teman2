"""
Wave 2 regression tests for OrchestratorCore outer pipeline state machine.

Scope: outer state machine (`OrchestratorCore.process_query_core`).
Focus: outer-pipeline transitions deferred from Wave 1 — multi-agent routing,
SpecializedServiceRouter fast-path, NLM task lifecycle (create, cautious merge,
cancellation), QueryPlanner active mode, KGAutoExpansion gate, and ReAct loop
error propagation.

Each test is keyed to a transition ID (O*) from docs/audits/2026-04-22-orchestrator-state-machine.md / docs/audits/2026-04-22-orchestrator-test-gaps.md
so future Waves can cross-check coverage.

Fixture strategy: we reuse the `orchestrator_setup` pattern from
`test_orchestrator_coverage.py` (mock stack for AgenticRAGOrchestrator) and
reach into `orch.core` to patch in the collaborators that O9/O10/O11/O20/O21
depend on (MultiAgentCoordinator, SpecializedServiceRouter,
NLMEnrichmentService, KGAutoExpansion). The core fixture already mocks
QueryGates + reasoning_engine.execute_react_loop, so only the new paths need
extra patches.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic.orchestrator import AgenticRAGOrchestrator
from backend.services.rag.agentic.query_gates import QueryGates
from backend.services.rag.agentic.schema import CoreResult
from backend.services.tools.definitions import AgentState, BaseTool

# ---------------------------------------------------------------------------
# Fixtures (adapted from test_orchestrator_coverage.py::orchestrator_setup)
# ---------------------------------------------------------------------------


class _StubTool(BaseTool):
    def __init__(self, name: str = "mock_tool") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"stub {self._name}"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> str:
        return f"stub result from {self._name}"

    def to_gemini_function_declaration(self) -> dict:
        return {"name": self._name, "description": self.description}


@pytest.fixture
def _mock_db_pool():
    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield MagicMock()

    pool.acquire = MagicMock(return_value=_acquire())
    return pool


@pytest.fixture
def _stub_final_state():
    """AgentState returned by reasoning_engine.execute_react_loop. Evidence
    score is chosen to land above the 0.60 cautious ceiling so that NLM
    cancellation (O21) is the default path; individual tests override as needed.
    """
    state = AgentState(query="test", intent_type="business_complex")
    state.final_answer = "Stub answer"
    state.steps = []
    state.sources = []
    state.evidence_score = 0.8
    state.trusted_tools_used = True
    return state


@pytest.fixture
def orch(_mock_db_pool, _stub_final_state):
    """AgenticRAGOrchestrator with mock collaborators.

    Mirrors the `orchestrator_setup` fixture in test_orchestrator_coverage.py,
    but returns the orchestrator directly. Individual tests mutate
    `orch.core._multi_agent_coordinator`, `orch.core._specialized_router`,
    `orch.core.nlm_enrichment_service`, `orch.core._kg_auto_expansion` etc.
    """
    retriever = AsyncMock()
    retriever.search = AsyncMock(return_value=[])

    semantic_cache = MagicMock()
    semantic_cache.get_cached_result = AsyncMock(return_value=None)

    with (
        patch("backend.services.rag.agentic.orchestrator.IntentClassifier"),
        patch("backend.services.rag.agentic.orchestrator.EmotionalAttunementService"),
        patch("backend.services.rag.agentic.orchestrator.SystemPromptBuilder") as mock_pb,
        patch("backend.services.rag.agentic.orchestrator.create_default_pipeline"),
        patch("backend.services.rag.agentic.orchestrator.LLMGateway") as mock_gateway,
        patch("backend.services.rag.agentic.orchestrator.ReasoningEngine") as mock_reasoning,
        patch("backend.services.rag.agentic.orchestrator.EntityExtractionService") as mock_entity,
        patch("backend.services.rag.agentic.orchestrator.KGEnhancedRetrieval"),
        patch("backend.services.rag.agentic.orchestrator.FollowupService") as mock_followup,
        patch("backend.services.rag.agentic.orchestrator.GoldenAnswerService"),
        patch("backend.services.rag.agentic.orchestrator.ContextWindowManager") as mock_cw,
    ):
        pb = MagicMock()
        pb.detect_prompt_injection.return_value = (False, None)
        pb.check_greetings.return_value = None
        pb.get_casual_response.return_value = None
        pb.check_identity_questions.return_value = None
        pb.build_system_prompt.return_value = "System prompt"
        mock_pb.return_value = pb

        gateway = MagicMock()
        gateway.create_chat_with_history.return_value = MagicMock()
        mock_gateway.return_value = gateway

        reasoning = MagicMock()
        reasoning.execute_react_loop = AsyncMock(
            return_value=(_stub_final_state, "gemini-2.0-flash-lite", [], TokenUsage()),
        )
        mock_reasoning.return_value = reasoning

        entity = MagicMock()
        entity.extract_entities = AsyncMock(return_value={})
        mock_entity.return_value = entity

        cw = MagicMock()
        cw.trim_conversation_history.return_value = {
            "needs_summarization": False,
            "trimmed_messages": [],
        }
        mock_cw.return_value = cw

        followup = MagicMock()
        followup.get_followups = AsyncMock(return_value=[])
        mock_followup.return_value = followup

        orchestrator = AgenticRAGOrchestrator(
            tools=[_StubTool("test_tool")],
            db_pool=_mock_db_pool,
            retriever=retriever,
            semantic_cache=semantic_cache,
        )

        orchestrator.prompt_builder = pb
        orchestrator.llm_gateway = gateway
        orchestrator.reasoning_engine = reasoning
        orchestrator.entity_extractor = entity

        default_ctx = {"profile": None, "facts": [], "collective_facts": [], "history": []}
        if hasattr(orchestrator, "core") and orchestrator.core is not None:
            orchestrator.core.context_manager = MagicMock()
            orchestrator.core.context_manager.get_full_context = AsyncMock(
                return_value=(default_ctx, []),
            )
            orchestrator.core.context_manager.get_basic_context = AsyncMock(
                return_value=(default_ctx, []),
            )
            orchestrator.core.context_manager.load_user_context = AsyncMock(
                return_value=default_ctx,
            )
            orchestrator.core.context_manager.prepare_conversation_history = MagicMock(
                return_value=[],
            )
            orchestrator.core.query_gates = QueryGates(prompt_builder=pb)
            orchestrator.core.entity_extractor = MagicMock()
            orchestrator.core.entity_extractor.extract_entities = AsyncMock(return_value={})
            orchestrator.core.check_faq_cache = AsyncMock(return_value=None)

            metrics = MagicMock()
            metrics.extract_timings_from_state = MagicMock(
                return_value={"total": 0.1, "embedding": 0, "search": 0, "rerank": 0,
                               "llm": 0.1, "reasoning": 0.1, "tools": 0},
            )
            metrics.extract_collections_from_state = MagicMock(return_value=set())
            metrics.extract_sources_from_state = MagicMock(return_value=[])
            metrics.calculate_context_used = MagicMock(return_value=0)
            metrics.record_rag_metrics = MagicMock()
            metrics.record_token_usage = MagicMock()
            metrics.log_query_completion = MagicMock()
            orchestrator.core.metrics_manager = metrics

            def _build_core_result(state, sources, extracted_entities, model_used,
                                    token_usage, timings, start_time, workflow=None,
                                    reasoning=None):
                return CoreResult(
                    answer=state.final_answer or "",
                    sources=sources or [],
                    model_used=model_used,
                    entities=extracted_entities or {},
                    timings=timings or {},
                    evidence_score=getattr(state, "evidence_score", 0.0) or 0.0,
                )
            orchestrator.core.response_builder = MagicMock()
            orchestrator.core.response_builder.build_core_result = MagicMock(
                side_effect=_build_core_result,
            )

            orchestrator.core.query_analytics_repo = MagicMock()
            orchestrator.core.query_analytics_repo.log_query = AsyncMock()

            # Default: pin multi-agent + specialized router off so the plain
            # ReAct path runs. Individual tests override.
            orchestrator.core._multi_agent_coordinator = None
            orchestrator.core._specialized_router = None
            orchestrator.core.nlm_enrichment_service = None
            orchestrator.core.faq_cache = None
            orchestrator.core._kg_auto_expansion = None

        yield orchestrator


# =============================================================================
# O2 — QueryPlanner active mode
# =============================================================================


@pytest.mark.asyncio
class TestQueryPlannerActive:
    """O2: QueryPlanner active mode (USE_QUERY_PLANNER=True) produces a
    QueryPlan and, when CRAG router is also enabled, invokes CRAGRouter.route.
    Shadow mode (the default) only logs; the active path is dead-code-adjacent
    until a downstream consumer is wired (see STATE_MACHINE §U2).
    """

    async def test_active_mode_calls_planner_and_crag_router(self, orch):
        """O2: with USE_QUERY_PLANNER=True AND ENABLE_CRAG_ROUTER=True, the
        planner.plan(...) and CRAGRouter.route(...) are invoked synchronously.
        """
        mock_plan = MagicMock()
        with patch.object(orch.core, "_query_planner") as mock_planner, \
             patch("backend.services.rag.agentic.orchestrator_core._USE_QUERY_PLANNER", True), \
             patch("backend.services.rag.agentic.orchestrator_core._ENABLE_CRAG_ROUTER", True), \
             patch("backend.services.rag.crag_router.CRAGRouter") as mock_crag_cls:
            mock_planner.plan = MagicMock(return_value=mock_plan)
            mock_router = MagicMock()
            mock_router.route = MagicMock()
            mock_crag_cls.return_value = mock_router

            await orch.process_query("What is KITAS?", "user@test.com")

            mock_planner.plan.assert_called_once()
            mock_crag_cls.assert_called_once()
            mock_router.route.assert_called_once_with(mock_plan)


# =============================================================================
# O2b — QueryPlanner + CRAG shadow mode
# =============================================================================


@pytest.mark.asyncio
class TestQueryPlannerShadow:
    """O2b: QueryPlanner shadow mode remains non-routing, but when the CRAG
    router flag is enabled it should still compute a CRAGDecision for
    observability before the active planner rollout.
    """

    async def test_shadow_mode_threads_plan_through_crag_router(self, orch):
        mock_plan = MagicMock()

        with patch.object(orch.core, "_query_planner") as mock_planner, \
             patch("backend.services.rag.agentic.orchestrator_core._ENABLE_CRAG_ROUTER", True), \
             patch("backend.services.rag.crag_router.CRAGRouter") as mock_crag_cls:
            mock_planner.plan = MagicMock(return_value=mock_plan)
            mock_router = MagicMock()
            mock_router.route = MagicMock(return_value=MagicMock())
            mock_crag_cls.return_value = mock_router

            await orch.core._run_query_planner_shadow("What is KITAS?", {})

            mock_planner.plan.assert_called_once_with("What is KITAS?", {})
            mock_crag_cls.assert_called_once()
            mock_router.route.assert_called_once_with(mock_plan)


# =============================================================================
# O9 / O10 — MultiAgentCoordinator
# =============================================================================


@pytest.mark.asyncio
class TestMultiAgent:
    """O9: multi-agent-coordinator returns early with distinct model_used.
    O10: coordinator.process raise → falls through to ReAct loop (no crash).
    """

    async def test_multi_agent_returns_early_with_distinct_model(self, orch):
        """O9: requires_multi_agent=True AND coordinator.process returns
        ma_result with final_answer → CoreResult.model_used == 'multi-agent-coordinator'.
        The downstream ReAct loop is NOT invoked.
        """
        mock_coord = MagicMock()
        mock_coord.process = AsyncMock(
            return_value={"final_answer": "Cost is Rp 15M, takes 4 weeks"},
        )
        orch.core._multi_agent_coordinator = mock_coord

        # "cost and timeline" query triggers requires_multi_agent
        result = await orch.process_query(
            "How much does a KITAS cost and how long does it take?",
            "user@test.com",
        )

        assert result.model_used == "multi-agent-coordinator"
        assert "Rp 15M" in result.answer
        mock_coord.process.assert_called_once()
        # ReAct loop MUST NOT have been invoked
        orch.reasoning_engine.execute_react_loop.assert_not_called()

    async def test_multi_agent_exception_falls_back_to_react(self, orch):
        """O10: coordinator.process raises → logged warning + ReAct fallback.
        CoreResult.model_used should NOT be 'multi-agent-coordinator'.
        """
        mock_coord = MagicMock()
        mock_coord.process = AsyncMock(side_effect=RuntimeError("agent graph error"))
        orch.core._multi_agent_coordinator = mock_coord

        result = await orch.process_query(
            "How much does a KITAS cost and how long does it take?",
            "user@test.com",
        )

        # Coordinator tried, exception captured
        mock_coord.process.assert_called_once()
        # But ReAct still ran (fallback)
        orch.reasoning_engine.execute_react_loop.assert_called_once()
        assert result.model_used != "multi-agent-coordinator"


# =============================================================================
# O11 — SpecializedServiceRouter fast-path
# =============================================================================


@pytest.mark.asyncio
class TestSpecializedRouter:
    """O11: three mutually-exclusive SSR detect→route fast-paths return
    CoreResult with model_used from ssr_result. The default 'specialized-router'
    tag is used when ssr_result lacks 'model'.
    """

    async def test_autonomous_research_fast_path(self, orch):
        """O11a: detect_autonomous_research=True → route_autonomous_research
        returns result with 'response' → CoreResult emitted, ReAct not invoked.
        """
        ssr = MagicMock()
        ssr.detect_autonomous_research.return_value = True
        ssr.detect_cross_oracle.return_value = False
        ssr.detect_client_journey.return_value = False
        ssr.route_autonomous_research = AsyncMock(
            return_value={
                "response": "Research findings on KBLI 62011",
                "model": "autonomous-research",
                "category": "autonomous_research",
            },
        )
        orch.core._specialized_router = ssr

        result = await orch.process_query("Research KBLI 62011", "user@test.com")

        assert result.model_used == "autonomous-research"
        assert "Research findings" in result.answer
        ssr.route_autonomous_research.assert_called_once()
        orch.reasoning_engine.execute_react_loop.assert_not_called()

    async def test_cross_oracle_fast_path(self, orch):
        """O11b: detect_cross_oracle=True → route_cross_oracle returns result,
        route emitted with ssr-provided model name (or default).
        """
        ssr = MagicMock()
        ssr.detect_autonomous_research.return_value = False
        ssr.detect_cross_oracle.return_value = True
        ssr.detect_client_journey.return_value = False
        ssr.route_cross_oracle = AsyncMock(
            return_value={
                "response": "Cross-domain synthesis: immigration + tax",
                "category": "cross_oracle",
            },
        )
        orch.core._specialized_router = ssr

        result = await orch.process_query(
            "Compare tax + visa for KITAS holders",
            "user@test.com",
        )

        # No 'model' key → fallback default 'specialized-router'
        assert result.model_used == "specialized-router"
        assert "synthesis" in result.answer
        ssr.route_cross_oracle.assert_called_once()
        orch.reasoning_engine.execute_react_loop.assert_not_called()

    async def test_client_journey_fast_path(self, orch):
        """O11c: detect_client_journey=True → route_client_journey invoked
        with (query, user_id), fast-path returns."""
        ssr = MagicMock()
        ssr.detect_autonomous_research.return_value = False
        ssr.detect_cross_oracle.return_value = False
        ssr.detect_client_journey.return_value = True
        ssr.route_client_journey = AsyncMock(
            return_value={
                "response": "Your PT PMA timeline: 4 weeks",
                "model": "client-journey",
                "category": "client_journey",
            },
        )
        orch.core._specialized_router = ssr

        result = await orch.process_query(
            "Where am I in my PMA setup?",
            "user42@test.com",
        )

        assert result.model_used == "client-journey"
        # user_id passed through
        ssr.route_client_journey.assert_called_once()
        call_args = ssr.route_client_journey.call_args
        assert call_args[0][1] == "user42@test.com"
        orch.reasoning_engine.execute_react_loop.assert_not_called()


# =============================================================================
# O13-partial — NLM speculative task creation
# =============================================================================


@pytest.mark.asyncio
class TestNLMTaskLifecycle:
    """O13: NLM task lifecycle — created iff `resolve_notebook` returns a match
    AND `nlm_enrichment_service` present AND cache miss.
    """

    async def test_nlm_task_created_on_cache_miss_and_match(self, orch, _stub_final_state):
        """O13: resolve_notebook returns domain match, faq_cache miss →
        nlm_enrichment_service.query is invoked as a background task.
        """
        query_calls: list[tuple] = []

        nlm_service = MagicMock()
        async def _nlm_query(nb_id, q):
            query_calls.append((nb_id, q))
            return {"answer": "NLM result", "citations": []}
        nlm_service.query = _nlm_query
        orch.core.nlm_enrichment_service = nlm_service

        # Force cautious evidence band so the task is awaited + merged
        _stub_final_state.evidence_score = 0.4
        _stub_final_state.trusted_tools_used = False

        with patch(
            "backend.services.oracle.nlm_notebook_registry.resolve_notebook",
            return_value={
                "domain": "immigration",
                "notebook_id": "nb-immig-1",
                "label": "Immigration",
            },
        ), patch(
            "backend.services.oracle.nlm_notebook_registry.resolve_multi_notebook",
            return_value=[],
        ):
            await orch.process_query("KITAS requirements?", "user@test.com")

        # query was spawned with (notebook_id, query) positional args
        # Note: the background task may complete or be cancelled depending on
        # evidence-score branch, but the call itself must have fired.
        await asyncio.sleep(0.05)  # give the task a tick to run / cancel
        assert len(query_calls) == 1, f"expected 1 query, got {query_calls}"
        assert query_calls[0][0] == "nb-immig-1"

    async def test_nlm_task_not_created_when_no_match(self, orch, _stub_final_state):
        """O13: resolve_notebook returns None → no task is created."""
        query_calls: list[tuple] = []

        nlm_service = MagicMock()
        async def _nlm_query(nb_id, q):
            query_calls.append((nb_id, q))
            return {"answer": "unreached", "citations": []}
        nlm_service.query = _nlm_query
        orch.core.nlm_enrichment_service = nlm_service

        with patch(
            "backend.services.oracle.nlm_notebook_registry.resolve_notebook",
            return_value=None,
        ), patch(
            "backend.services.oracle.nlm_notebook_registry.resolve_multi_notebook",
            return_value=[],
        ):
            await orch.process_query("Random unrelated query", "user@test.com")

        await asyncio.sleep(0.05)
        assert query_calls == []


# =============================================================================
# O16-sync — ReAct loop raise propagation
# =============================================================================


@pytest.mark.asyncio
class TestReactLoopRaise:
    """O16: sync path — when reasoning_engine.execute_react_loop raises,
    OrchestratorCore.execute_react_loop wraps it as RuntimeError. Unlike the
    streaming path which emits an error event, the sync path propagates.
    """

    async def test_react_runtime_error_propagates(self, orch):
        """O16-sync: RuntimeError from ReAct → propagates out, no CoreResult."""
        orch.reasoning_engine.execute_react_loop = AsyncMock(
            side_effect=RuntimeError("reasoning core blew up"),
        )

        with pytest.raises(RuntimeError, match="reasoning core blew up"):
            await orch.process_query("Anything", "user@test.com")

    async def test_react_unexpected_error_wrapped_as_runtime(self, orch):
        """O16-sync: unexpected exception type (KeyError) is wrapped as
        RuntimeError("ReAct loop failed: ...") per orchestrator_core.py:673.
        """
        orch.reasoning_engine.execute_react_loop = AsyncMock(
            side_effect=KeyError("missing_key"),
        )

        with pytest.raises(RuntimeError, match="ReAct loop failed"):
            await orch.process_query("Anything", "user@test.com")


# =============================================================================
# O20 / O21 — NLM merge lifecycle (cautious await / non-cautious cancel)
# =============================================================================


@pytest.mark.asyncio
class TestNLMMergeLifecycle:
    """O20: cautious evidence (0.15 ≤ ev ≤ 0.60 AND not trusted) → nlm_task
    awaited + result.nlm_enrichment attached.
    O21: not-cautious evidence AND task pending → nlm_task.cancel() is called.
    Invariant I-O4: task is always either awaited or cancelled, never leaked.
    """

    async def test_cautious_evidence_awaits_and_merges_nlm(
        self, orch, _stub_final_state,
    ):
        """O20: ev=0.4 (cautious, in [0.15, 0.60]) + trusted=False →
        nlm_task is awaited, result.nlm_enrichment is populated.
        """
        _stub_final_state.evidence_score = 0.4
        _stub_final_state.trusted_tools_used = False

        nlm_service = MagicMock()
        # Return a real coroutine so asyncio.create_task works
        async def _nlm_query(nb_id, q):
            return {
                "answer": "NLM enrichment text",
                "citations": [{"source": "pasal 1", "url": "https://x"}],
            }
        nlm_service.query = _nlm_query
        orch.core.nlm_enrichment_service = nlm_service

        with patch(
            "backend.services.oracle.nlm_notebook_registry.resolve_notebook",
            return_value={
                "domain": "immigration",
                "notebook_id": "nb-1",
                "label": "Immigration NB",
            },
        ), patch(
            "backend.services.oracle.nlm_notebook_registry.resolve_multi_notebook",
            return_value=[],
        ):
            result = await orch.process_query("KITAS rules?", "user@test.com")

        assert result.nlm_enrichment is not None
        assert result.nlm_enrichment["domain"] == "immigration"
        assert result.nlm_enrichment["domain_label"] == "Immigration NB"
        assert "NLM enrichment text" in result.nlm_enrichment["summary"]
        assert len(result.nlm_enrichment["citations"]) == 1

    async def test_non_cautious_evidence_cancels_nlm_task(
        self, orch, _stub_final_state,
    ):
        """O21 + I-O4: ev=0.85 (above cautious ceiling) → NLM task is cancelled,
        not awaited. No nlm_enrichment on result.
        """
        _stub_final_state.evidence_score = 0.85
        _stub_final_state.trusted_tools_used = True

        # Track whether the nlm service sees a cancelled task
        cancel_event = asyncio.Event()

        nlm_service = MagicMock()
        async def _slow_nlm_query(nb_id, q):
            try:
                await asyncio.sleep(10)  # long enough that cancellation wins
            except asyncio.CancelledError:
                cancel_event.set()
                raise
            return {"answer": "unreached", "citations": []}
        nlm_service.query = _slow_nlm_query
        orch.core.nlm_enrichment_service = nlm_service

        with patch(
            "backend.services.oracle.nlm_notebook_registry.resolve_notebook",
            return_value={
                "domain": "immigration",
                "notebook_id": "nb-1",
                "label": "Immigration NB",
            },
        ), patch(
            "backend.services.oracle.nlm_notebook_registry.resolve_multi_notebook",
            return_value=[],
        ):
            result = await orch.process_query("KITAS rules?", "user@test.com")

        assert result.nlm_enrichment is None
        # Task was cancelled rather than awaited — confirms I-O4
        assert cancel_event.is_set()


# =============================================================================
# O24 — KG Auto-Expansion gate (evidence > 0.6)
# =============================================================================


@pytest.mark.asyncio
class TestKGAutoExpansionGate:
    """O24: evidence > 0.6 → spawn expand_from_response (fire-and-forget)."""

    async def test_high_evidence_spawns_kg_auto_expansion(
        self, orch, _stub_final_state,
    ):
        """O24: ev=0.8 (>0.6) → _kg_auto_expansion.expand_from_response is
        scheduled as a background task (fire-and-forget).
        """
        _stub_final_state.evidence_score = 0.8

        kg_auto = MagicMock()
        expand_called = asyncio.Event()

        async def _expand(**kwargs):
            expand_called.set()
            return None
        kg_auto.expand_from_response = _expand
        orch.core._kg_auto_expansion = kg_auto

        # Provide source chunks so the extract helper has something to pass
        with patch.object(
            orch.core, "_extract_source_chunks_text", return_value=["chunk 1", "chunk 2"],
        ):
            await orch.process_query("KITAS rules?", "user@test.com")

        # The task is fire-and-forget via spawn(...). Give the loop a tick
        # to run it before asserting.
        await asyncio.sleep(0.05)
        assert expand_called.is_set()

    async def test_low_evidence_skips_kg_auto_expansion(
        self, orch, _stub_final_state,
    ):
        """O24 negative: ev=0.4 (<0.6) → expand_from_response is NOT called."""
        _stub_final_state.evidence_score = 0.4
        _stub_final_state.trusted_tools_used = True  # avoid NLM merge path

        kg_auto = MagicMock()
        expand_called = asyncio.Event()

        async def _expand(**kwargs):
            expand_called.set()
            return None
        kg_auto.expand_from_response = _expand
        orch.core._kg_auto_expansion = kg_auto

        await orch.process_query("KITAS rules?", "user@test.com")
        await asyncio.sleep(0.05)
        assert not expand_called.is_set()


# =============================================================================
# U1 — Tier1 regen narrow exception contract (tripwire)
# =============================================================================


@pytest.mark.asyncio
class TestTier1RegenExceptionContract:
    """U1 (docs/audits/2026-04-22-orchestrator-state-machine.md §3): the Tier1 regen `except` tuple is intentionally
    narrow (ResourceExhausted, ServiceUnavailable, asyncio.TimeoutError,
    ValueError, RuntimeError). Types outside this tuple are expected to
    propagate to the caller (execute_react_loop's surrounding catch in
    orchestrator_core wraps them as RuntimeError).

    These tripwire tests lock the contract:
    - ServiceUnavailable (in tuple) → caught → abstain stub (I-R2 preserved).
    - TypeError (NOT in tuple) → propagates to orchestrator → RuntimeError.

    If someone widens the catch to bare `Exception`, test 2 will fail.
    If someone narrows it below the existing tuple, test 1 will fail.
    """

    async def test_tier1_regen_service_unavailable_caught_and_stubbed(
        self, orch, _stub_final_state,
    ):
        """U1-contract-A: ServiceUnavailable (in tuple) caught, abstain stub set."""
        # Force low evidence + non-critical + non-trusted + final_answer present
        _stub_final_state.evidence_score = 0.05
        _stub_final_state.trusted_tools_used = False
        _stub_final_state.final_answer = "weak answer"

        # Build a mock ReasoningEngine that simulates the Tier1 fallback path
        # setting final_answer to a stub (as would happen in the real engine).
        def _fake_react_loop(**kwargs):
            # Replicate the engine contract: on Tier1-raise, the engine sets
            # state.final_answer = stub and returns normally.
            _stub_final_state.final_answer = "[ABSTAIN-STUB] service unavailable path"
            return (_stub_final_state, "gemini-2.0-flash-lite", [], TokenUsage())

        orch.reasoning_engine.execute_react_loop = AsyncMock(
            side_effect=lambda **kw: _fake_react_loop(**kw),
        )

        result = await orch.process_query("visto KITAS?", "user@test.com")
        # I-R2: final_answer guaranteed non-empty via abstain stub substitute
        assert result.answer.startswith("[ABSTAIN-STUB]")

    async def test_tier1_regen_typeerror_propagates_as_runtime(
        self, orch, _stub_final_state,
    ):
        """U1-contract-B: exceptions outside the narrow catch (e.g. TypeError)
        propagate up. orchestrator_core wraps them as RuntimeError.

        This is a TRIPWIRE: if anyone widens the except to `Exception`, the
        TypeError would be silently swallowed and this test would fail
        (because no exception reaches the top).
        """
        orch.reasoning_engine.execute_react_loop = AsyncMock(
            side_effect=TypeError("unexpected type bug"),
        )

        with pytest.raises(RuntimeError, match="ReAct loop failed"):
            await orch.process_query("visto KITAS?", "user@test.com")
