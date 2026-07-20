"""SPEC v2 D3-L2 (F1b): curated_qa grounding injection.

NOT verbatim serving — a curated_qa hit is prepended to the ReAct system
context as high-priority evidence; the LLM still answers the real question
and the abstain gate still runs downstream (the injection never short-
circuits the query, unlike the FAQ cache exact-match path).

Domain gate (2026-07-18): the 0.90 raw-cosine gate almost never fired for
real paraphrased queries (0.46-0.74 cosine vs stored questions). Lowering the
threshold alone pollutes cross-domain answers (a "register PT PMA" query can
score high against a visa Q&A). The fix injects ONLY when the query has a
concrete, classified domain AND each retrieved hit's own `domain` tag matches
it. Note: NO Qdrant `filter` is passed — search_collection re-wraps a native
filter into a malformed query that Qdrant 400s (the reason injection was dead
in prod even after #2684's "domain filter"); the per-hit recheck is the real,
sufficient domain gate.

Staleness gate (Phase-0 safety rail, MAJOR 7/8): a hit's `active` metadata
field (written True at harvest time, per-class TTL in the FAQ sink, and
flipped to False by curated_qa_regen_trigger.py on a regulatory-delta
match) is rechecked per-hit — an inactive point is excluded from injection
even if it clears score AND domain. Missing `active` (pre-Phase-0 points)
defaults to included, never silently dropped.

Three layers of coverage:
1. `_inject_curated_qa_grounding()` in isolation — retrieval/formatting/
   threshold/domain-gate/staleness-gate/exception-handling logic.
2. Domain-gate guilt + innocence — proves a matching domain injects (calling
   search WITHOUT a Qdrant filter) and a mismatched/general domain never does,
   even when a same-score foreign-domain hit is present.
3. One process_query_core() wiring test — proves the call site actually
   flows the injected string into the system prompt's additional_context,
   and that the ReAct loop (and therefore the abstain gate) still executes
   afterwards rather than being bypassed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic import orchestrator_core as orchestrator_core_module
from backend.services.rag.agentic.entity_extractor import EntityExtractionService
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


VISA_ENTITIES = {"domain": "visa"}


# ── _inject_curated_qa_grounding() isolated tests ───────────────────────────


@pytest.mark.asyncio
async def test_no_retriever_returns_empty_string() -> None:
    core = make_core()
    core.retriever = None

    result = await core._inject_curated_qa_grounding(
        "What is the E33 deposit amount?",
        VISA_ENTITIES,
    )

    assert result == ""


@pytest.mark.asyncio
async def test_disabled_via_env_returns_empty_string(monkeypatch) -> None:
    monkeypatch.setenv("CURATED_QA_INJECTION_ENABLED", "false")
    monkeypatch.setattr(orchestrator_core_module, "_CURATED_QA_INJECTION_ENABLED", False)
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(return_value=_search_result([_hit(0.95)])),
    )

    result = await core._inject_curated_qa_grounding("query", VISA_ENTITIES)

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
        result = await core._inject_curated_qa_grounding(
            "What is the E33 deposit amount?",
            VISA_ENTITIES,
        )

    assert "The E33 deposit is USD 130,000." in result
    assert "E33-DEFINITIVE-CHATKB-2026-07-15.md#Q1" in result
    assert "2026-07-15" in result
    assert "CURATED" in result
    mock_counter.inc.assert_called_once()

    core.retriever.search_collection.assert_awaited_once()
    _, kwargs = core.retriever.search_collection.call_args
    assert kwargs["collection_name"] == "curated_qa"
    assert kwargs["limit"] == 2
    # REGRESSION (2026-07-18): the injection must NOT pass a Qdrant-native
    # `filter` — search_collection re-wraps it through the simplified-format
    # converter, producing a malformed filter that Qdrant 400s and kills the
    # whole search (curated_qa injection was dead in prod for exactly this).
    # Domain scoping is enforced by the per-hit recheck, not a Qdrant filter.
    assert kwargs.get("filter") is None


@pytest.mark.asyncio
async def test_paraphrased_query_score_now_qualifies_under_new_threshold() -> None:
    """GUILT — the whole point of the fix: a real paraphrased-query cosine
    score (0.46-0.74 range, per the prod measurement) must now clear the
    calibrated 0.58 threshold, where it would NOT have cleared the old 0.90
    gate."""
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(
            return_value=_search_result([_hit(0.65, answer="Paraphrase-matched answer.")]),
        ),
    )

    with patch("backend.app.metrics.curated_qa_injections_total"):
        result = await core._inject_curated_qa_grounding("paraphrased visa question", VISA_ENTITIES)

    assert "Paraphrase-matched answer." in result


@pytest.mark.asyncio
async def test_hit_below_threshold_is_filtered_out() -> None:
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(return_value=_search_result([_hit(0.42)])),
    )

    result = await core._inject_curated_qa_grounding("unrelated small talk", VISA_ENTITIES)

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
        result = await core._inject_curated_qa_grounding("query", VISA_ENTITIES)

    assert "Answer one." in result
    assert "Answer two." in result


@pytest.mark.asyncio
async def test_no_hits_returns_empty_string_without_metrics_increment() -> None:
    core = make_core()
    core.retriever = SimpleNamespace(search_collection=AsyncMock(return_value=_search_result([])))

    with patch("backend.app.metrics.curated_qa_injections_total") as mock_counter:
        result = await core._inject_curated_qa_grounding("query", VISA_ENTITIES)

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
    result = await core._inject_curated_qa_grounding("query", VISA_ENTITIES)

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

    result = await core._inject_curated_qa_grounding("query", VISA_ENTITIES)

    assert result == ""


@pytest.mark.asyncio
async def test_hit_with_missing_answer_metadata_is_skipped() -> None:
    core = make_core()
    hit = _hit(0.95)
    hit["metadata"].pop("answer")
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(return_value=_search_result([hit])),
    )

    result = await core._inject_curated_qa_grounding("query", VISA_ENTITIES)

    assert result == ""


@pytest.mark.asyncio
async def test_threshold_env_override_is_respected(monkeypatch) -> None:
    """The module-level threshold constant is env-configurable
    (CURATED_QA_SCORE_THRESHOLD). Simulate an operator raising it back up and
    verify a hit that would have qualified under the default 0.58 no longer
    does."""
    monkeypatch.setattr(orchestrator_core_module, "_CURATED_QA_SCORE_THRESHOLD", 0.99)
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(return_value=_search_result([_hit(0.65)])),
    )

    result = await core._inject_curated_qa_grounding("query", VISA_ENTITIES)

    assert result == ""


# ── Staleness gate (MAJOR 7/8): guilt + innocence ───────────────────────────


@pytest.mark.asyncio
async def test_inactive_hit_is_skipped_even_above_score_and_domain_match() -> None:
    """GUILT — a hit flagged active=False (TTL-expired at write time, or
    quarantined by curated_qa_regen_trigger.py after a regulatory-delta
    match) must never be injected, even though it clears the score
    threshold AND the domain gate."""
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(
            return_value=_search_result(
                [_hit(0.95, answer="Stale answer, must not appear.", active=False)],
            ),
        ),
    )

    result = await core._inject_curated_qa_grounding("query", VISA_ENTITIES)

    assert result == ""


@pytest.mark.asyncio
async def test_active_hit_is_still_injected() -> None:
    """INNOCENCE — an explicitly active=True hit is unaffected by the
    staleness gate."""
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(
            return_value=_search_result(
                [_hit(0.95, answer="Fresh answer.", active=True)],
            ),
        ),
    )

    with patch("backend.app.metrics.curated_qa_injections_total"):
        result = await core._inject_curated_qa_grounding("query", VISA_ENTITIES)

    assert "Fresh answer." in result


@pytest.mark.asyncio
async def test_hit_missing_active_field_defaults_to_included() -> None:
    """INNOCENCE — a pre-Phase-0 Qdrant point written before this rail
    existed has no `active` key at all. Missing must default to "still
    active", never be treated as silently inactive (that would mass-hide
    every point written before this rail shipped)."""
    core = make_core()
    hit = _hit(0.95, answer="Legacy point, no active field.")
    assert "active" not in hit["metadata"]
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(return_value=_search_result([hit])),
    )

    with patch("backend.app.metrics.curated_qa_injections_total"):
        result = await core._inject_curated_qa_grounding("query", VISA_ENTITIES)

    assert "Legacy point, no active field." in result


@pytest.mark.asyncio
async def test_mixed_active_and_inactive_hits_only_active_one_injected() -> None:
    """GUILT + INNOCENCE together — one inactive, one active hit in the
    same result set: only the active one is injected."""
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(
            return_value=_search_result(
                [
                    _hit(0.95, answer="Stale, excluded.", source_ref="doc#Q1", active=False),
                    _hit(0.93, answer="Fresh, included.", source_ref="doc#Q2", active=True),
                ],
            ),
        ),
    )

    with patch("backend.app.metrics.curated_qa_injections_total"):
        result = await core._inject_curated_qa_grounding("query", VISA_ENTITIES)

    assert "Fresh, included." in result
    assert "Stale, excluded." not in result


# ── Domain gate: guilt + innocence ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_missing_domain_returns_empty_string_and_never_calls_search() -> None:
    """INNOCENCE — no extracted_entities at all (or a domain-less dict) must
    short-circuit before ever calling search_collection."""
    core = make_core()
    search_mock = AsyncMock(return_value=_search_result([_hit(0.99)]))
    core.retriever = SimpleNamespace(search_collection=search_mock)

    result = await core._inject_curated_qa_grounding("some query", None)

    assert result == ""
    search_mock.assert_not_called()


@pytest.mark.asyncio
async def test_general_domain_returns_empty_string_and_never_calls_search() -> None:
    """INNOCENCE — the classifier's general/fallback sentinel
    (EntityExtractionService.DOMAIN_GENERAL == "general") must short-circuit
    before ever calling search_collection, exactly like a missing domain."""
    core = make_core()
    search_mock = AsyncMock(return_value=_search_result([_hit(0.99)]))
    core.retriever = SimpleNamespace(search_collection=search_mock)

    result = await core._inject_curated_qa_grounding(
        "some general small-talk query",
        {"domain": EntityExtractionService.DOMAIN_GENERAL},
    )

    assert result == ""
    search_mock.assert_not_called()


@pytest.mark.asyncio
async def test_concrete_domain_query_searches_without_a_qdrant_filter() -> None:
    """GUILT + REGRESSION — a concrete non-general domain (e.g. company) DOES
    call search, but WITHOUT any Qdrant `filter` kwarg. Passing a native
    {"must": [...]} filter here is the bug that made curated_qa injection 400
    and go dark in prod; domain scoping is done by the per-hit recheck below."""
    core = make_core()
    search_mock = AsyncMock(return_value=_search_result([]))
    core.retriever = SimpleNamespace(search_collection=search_mock)

    result = await core._inject_curated_qa_grounding(
        "how do I register a PT PMA company",
        {"domain": "company"},
    )

    assert result == ""  # no company-domain curated_qa content exists yet
    search_mock.assert_awaited_once()
    _, kwargs = search_mock.call_args
    assert kwargs.get("filter") is None


@pytest.mark.asyncio
async def test_company_domain_query_never_injects_a_leaked_visa_hit() -> None:
    """INNOCENCE — the core anti-pollution guarantee: a company-domain query
    must return "" even though the search layer returns a high-scoring
    VISA-tagged hit (all curated_qa content is visa-domain today, and retrieval
    is unfiltered by design — there is no Qdrant-level domain filter). The
    orchestrator's per-hit `hit_domain != domain` recheck is the ONLY and
    sufficient domain gate (match on the entity, not a single upstream signal —
    scar family #3)."""
    core = make_core()
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(
            return_value=_search_result(
                [_hit(0.95, answer="A visa-domain answer that must never leak.")],
            ),
        ),
    )

    result = await core._inject_curated_qa_grounding(
        "how do I register a PT PMA company",
        {"domain": "company"},
    )

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
        # Domain must be concrete (non-general) for the injection call site to
        # reach the retriever — see the domain-gate tests above for the
        # general/missing-domain short-circuit itself.
        entity_ext.extract_entities = AsyncMock(return_value={"domain": "visa"})

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
async def test_process_query_core_omits_curated_context_on_general_domain(
    wired_core: OrchestratorCore,
) -> None:
    """INNOCENCE end-to-end: even with a hit that would qualify on score,
    a general-domain classification must keep the wiring silent."""
    core = wired_core
    core.entity_extractor.extract_entities = AsyncMock(
        return_value={"domain": EntityExtractionService.DOMAIN_GENERAL},
    )
    search_mock = AsyncMock(
        return_value=_search_result([_hit(0.95, answer="Should never appear.")]),
    )
    core.retriever = SimpleNamespace(search_collection=search_mock)

    with pytest.raises(_StopAfterPromptBuild):
        await core.process_query_core(
            query="unrelated small talk",
            user_id="u1",
            conversation_history=None,
            start_time=0.0,
        )

    _, kwargs = core.prompt_builder.build_system_prompt.call_args
    assert "Should never appear." not in kwargs["additional_context"]
    search_mock.assert_not_called()


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


@pytest.mark.asyncio
async def test_process_query_core_threads_curated_grounding_into_multi_agent_process(
    wired_core: OrchestratorCore,
) -> None:
    """WIRING (multi-agent grounding fix, 2026-07-18): a curated_qa hit
    injected into system_context_for_prompt must reach
    MultiAgentCoordinator.process(grounding_context=...) when
    requires_multi_agent() routes the query to the multi-agent branch —
    proving the fix for the branch that previously called process() with
    only the extracted entities, dropping the curated/KG grounding entirely.
    """
    core = wired_core
    core.retriever = SimpleNamespace(
        search_collection=AsyncMock(
            return_value=_search_result(
                [_hit(0.95, answer="Curated grounding answer.")],
            ),
        ),
    )
    mock_coordinator = MagicMock()
    mock_coordinator.process = AsyncMock(return_value={"final_answer": "x"})
    core._multi_agent_coordinator = mock_coordinator

    with patch(
        "backend.services.rag.agentic.orchestrator_core.requires_multi_agent",
        return_value=True,
    ):
        result = await core.process_query_core(
            query="What is the E33 deposit amount?",
            user_id="u1",
            conversation_history=None,
            start_time=0.0,
        )

    assert result.answer == "x"
    mock_coordinator.process.assert_awaited_once()
    _, kwargs = mock_coordinator.process.call_args
    assert "Curated grounding answer." in kwargs["grounding_context"]
