"""SPEC v2 D3-L2 (F1b): curated_qa grounding injection.

NOT verbatim serving — a curated_qa hit is prepended to the ReAct system
context as high-priority evidence; the LLM still answers the real question
and the abstain gate still runs downstream (the injection never short-
circuits the query, unlike the FAQ cache exact-match path).

Two layers of coverage:
1. `_inject_curated_qa_grounding()` in isolation — the actual new retrieval/
   formatting/threshold/exception-handling logic.
2. One process_query_core() wiring test — proves the call site actually
   flows the injected string into the system prompt's additional_context,
   and that the ReAct loop (and therefore the abstain gate) still executes
   afterwards rather than being bypassed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic import orchestrator_core as orchestrator_core_module
from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
from backend.services.tools.definitions import AgentState


def make_core() -> OrchestratorCore:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.semantic_cache = None
    core.faq_cache = None
    core.retriever = None
    core.entity_extractor = None
    core.kg_retrieval = None
    core.kg_langgraph_orchestrator = None
    core.db_pool = None
    core.reasoning_engine = None
    core.llm_gateway = object()
    core.context_manager = None
    core.query_gates = None
    core.prompt_builder = None
    core.routing_manager = None
    core._surface_router = None
    core._specialized_router = None
    core._multi_agent_coordinator = None
    core._kg_auto_expansion = None
    return core


def _search_result(hits: list[dict]) -> dict:
    return {"query": "q", "results": hits, "collection": "curated_qa"}


def _hit(score: float, answer: str = "curated answer", **meta_overrides) -> dict:
    metadata = {
        "answer": answer,
        "domain": "visa",
        "source_ref": "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q1",
        "source_date": "2026-07-15",
        "confidence_class": "BERSYARAT",
        "source_priority": 80,
        **meta_overrides,
    }
    return {"id": "abc", "text": "curated question", "metadata": metadata, "score": score}


# ── _inject_curated_qa_grounding() isolated tests ───────────────────────────


@pytest.mark.asyncio
async def test_no_retriever_returns_empty_string() -> None:
    core = make_core()
    core.retriever = None

    result = await core._inject_curated_qa_grounding("What is the E33 deposit amount?")

    assert result == ""


@pytest.mark.asyncio
async def test_disabled_via_env_returns_empty_string(monkeypatch) -> None:
    monkeypatch.setenv("CURATED_QA_INJECTION_ENABLED", "false")
    monkeypatch.setattr(orchestrator_core_module, "_CURATED_QA_INJECTION_ENABLED", False)
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(return_value=_search_result([_hit(0.95)])),
    )

    result = await core._inject_curated_qa_grounding("query")

    assert result == ""
    core.retriever.search_collection.assert_not_called()


@pytest.mark.asyncio
async def test_hit_above_threshold_is_prepended_with_source_tag() -> None:
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(
            return_value=_search_result(
                [_hit(0.95, answer="The E33 deposit is USD 130,000.")],
            ),
        ),
    )

    with patch("backend.app.metrics.curated_qa_injections_total") as mock_counter:
        result = await core._inject_curated_qa_grounding("What is the E33 deposit amount?")

    assert "The E33 deposit is USD 130,000." in result
    assert "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q1" in result
    assert "2026-07-15" in result
    assert "CURATED" in result
    mock_counter.inc.assert_called_once()

    core.retriever.search_collection.assert_awaited_once()
    _, kwargs = core.retriever.search_collection.call_args
    assert kwargs["collection_name"] == "curated_qa"
    assert kwargs["limit"] == 2


@pytest.mark.asyncio
async def test_hit_below_threshold_is_filtered_out() -> None:
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(return_value=_search_result([_hit(0.42)])),
    )

    result = await core._inject_curated_qa_grounding("unrelated small talk")

    assert result == ""


@pytest.mark.asyncio
async def test_multiple_hits_above_threshold_all_included() -> None:
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(
            return_value=_search_result(
                [
                    _hit(0.95, answer="Answer one.", source_ref="doc#Q1"),
                    _hit(0.91, answer="Answer two.", source_ref="doc#Q2"),
                ],
            ),
        ),
    )

    with patch("backend.app.metrics.curated_qa_injections_total"):
        result = await core._inject_curated_qa_grounding("query")

    assert "Answer one." in result
    assert "Answer two." in result


@pytest.mark.asyncio
async def test_no_hits_returns_empty_string_without_metrics_increment() -> None:
    core = make_core()
    core.retriever = SimpleNamespace(search_collection=AsyncMock(return_value=_search_result([])))

    with patch("backend.app.metrics.curated_qa_injections_total") as mock_counter:
        result = await core._inject_curated_qa_grounding("query")

    assert result == ""
    mock_counter.inc.assert_not_called()


@pytest.mark.asyncio
async def test_exception_in_search_is_caught_and_returns_empty_string() -> None:
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(side_effect=RuntimeError("qdrant down")),
    )

    # Must not raise — defensive per spec ("any exception in this step logs
    # and continues without injection").
    result = await core._inject_curated_qa_grounding("query")

    assert result == ""


@pytest.mark.asyncio
async def test_non_dict_search_result_is_treated_as_miss() -> None:
    """Guards against under-specced test doubles (bare AsyncMock() retrievers
    elsewhere in the suite auto-vivify nested AsyncMocks) and any real-world
    contract violation from search_collection returning something unexpected.
    Must not create/leak an un-awaited coroutine from a stray `.get()` call."""
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(return_value="not-a-dict"),
    )

    result = await core._inject_curated_qa_grounding("query")

    assert result == ""


@pytest.mark.asyncio
async def test_hit_with_missing_answer_metadata_is_skipped() -> None:
    core = make_core()
    hit = _hit(0.95)
    hit["metadata"].pop("answer")
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(return_value=_search_result([hit])),
    )

    result = await core._inject_curated_qa_grounding("query")

    assert result == ""


# ── process_query_core() wiring test ────────────────────────────────────────


class _StopAfterPromptBuild(Exception):
    """Sentinel exception used to stop process_query_core right after the
    system prompt is built — everything downstream (ReAct loop, grading
    gates) is proven to still be reachable (not bypassed) because we let
    execution get there before intentionally halting it."""


@pytest.fixture
def wired_core() -> OrchestratorCore:
    """A OrchestratorCore wired just enough to drive process_query_core()
    from the top down to (and slightly past) the curated_qa injection call
    site, without needing to fake the entire ReAct/response-building stack.
    """
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
        entity_ext.extract_entities = AsyncMock(return_value={})

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
        # Gate never triggers — reach the FAQ/semantic-cache/injection steps.
        core.query_gates.run_all_gates = MagicMock(return_value=SimpleNamespace(triggered=False))
        # Routing returns a plain AgentState and a fast model tier.
        core.routing_manager.route_query = AsyncMock(
            return_value=("flash", False, AgentState(query="q")),
        )
        # Halt right after the system prompt is built — proves injection ran
        # BEFORE routing/prompt-build, and that the pipeline was going on to
        # the ReAct loop next (not short-circuited by the injection).
        core.prompt_builder.build_system_prompt = MagicMock(
            side_effect=_StopAfterPromptBuild,
        )
        return core


@pytest.mark.asyncio
async def test_process_query_core_injects_curated_context_into_system_prompt(
    wired_core: OrchestratorCore,
) -> None:
    core = wired_core
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(
            return_value=_search_result(
                [_hit(0.95, answer="Curated grounding answer.")],
            ),
        ),
    )

    with pytest.raises(_StopAfterPromptBuild):
        await core.process_query_core(
            query="What is the E33 deposit amount?",
            user_id="u1",
            conversation_history=None,
            start_time=0.0,
        )

    _, kwargs = core.prompt_builder.build_system_prompt.call_args
    assert "Curated grounding answer." in kwargs["additional_context"]


@pytest.mark.asyncio
async def test_process_query_core_omits_curated_context_on_miss(
    wired_core: OrchestratorCore,
) -> None:
    core = wired_core
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(return_value=_search_result([])),
    )

    with pytest.raises(_StopAfterPromptBuild):
        await core.process_query_core(
            query="unrelated small talk",
            user_id="u1",
            conversation_history=None,
            start_time=0.0,
        )

    _, kwargs = core.prompt_builder.build_system_prompt.call_args
    assert "CURATED" not in kwargs["additional_context"]


@pytest.mark.asyncio
async def test_process_query_core_survives_injection_exception_and_still_builds_prompt(
    wired_core: OrchestratorCore,
) -> None:
    core = wired_core
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(side_effect=RuntimeError("qdrant down")),
    )

    # The pipeline must still reach prompt-build (and therefore the ReAct
    # loop / abstain gate downstream) even though injection blew up.
    with pytest.raises(_StopAfterPromptBuild):
        await core.process_query_core(
            query="query",
            user_id="u1",
            conversation_history=None,
            start_time=0.0,
        )

    core.prompt_builder.build_system_prompt.assert_called_once()
