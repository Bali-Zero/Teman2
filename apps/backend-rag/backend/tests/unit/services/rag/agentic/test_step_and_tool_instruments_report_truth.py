"""The response must report how many steps ran and which tools were called.

Why this exists. On 2026-08-10 a live investigation into WhatsApp silences
needed one question answered — "did the ReAct loop run out of budget?" — and the
two response fields that exist to answer it could not. `total_steps` was wired to
`len(result.tools_called)` (`agentic_rag.py`), i.e. the same number as the field
right above it under a name promising something else; and nothing on the main
ReAct path ever populated `tools_called`, so BOTH read 0 on every response, on
healthy ones with eight sources exactly as on degenerate ones with none.

An instrument that reads the same on the sick and the healthy patient is not a
weak instrument, it is an absent one. These tests pin the two properties that
make it present: the counts come from the state that produced the answer, and
they are allowed to DIFFER from each other.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.orchestrator_response import OrchestratorResponseBuilder
from backend.services.rag.agentic.schema import CoreResult


class _Action:
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        self.arguments: dict[str, Any] = {}


class _Step:
    def __init__(self, tool_name: str | None) -> None:
        self.action = _Action(tool_name) if tool_name else None


class _State:
    """The parts of AgentState that build_core_result reads."""

    def __init__(self, *, current_step: int, tool_names: list[str | None]) -> None:
        self.current_step = current_step
        self.steps = [_Step(name) for name in tool_names]
        self.final_answer = "an answer"
        self.query = "What is the minimum paid-up capital for a PT PMA?"
        self.evidence_score = 0.85
        self.verification_score = 0.9


class _TokenUsage:
    prompt_tokens = 10
    completion_tokens = 20
    total_tokens = 30
    cost_usd = 0.0


def _build(state: _State) -> CoreResult:
    return OrchestratorResponseBuilder().build_core_result(
        state=state,
        sources=[{"collection": "legal_unified"}],
        extracted_entities={},
        model_used="gemini",
        token_usage=_TokenUsage(),
        timings={"total": 1.0},
        start_time=0.0,
    )


def test_steps_and_tools_are_read_from_the_state_that_answered() -> None:
    result = _build(_State(current_step=2, tool_names=["vector_search", "get_pricing"]))

    assert result.steps_taken == 2
    assert result.tools_called == ["vector_search", "get_pricing"]


def test_steps_taken_may_exceed_the_tool_count() -> None:
    """A step can be a thought with no tool call.

    This is the case the old wiring could not represent at all: `total_steps`
    WAS `len(tools_called)`, so the two could never disagree, and a loop that
    burned three steps to make one tool call reported "1 step".
    """
    result = _build(_State(current_step=3, tool_names=["vector_search", None, None]))

    assert result.steps_taken == 3
    assert result.tools_called == ["vector_search"]
    assert result.steps_taken != len(result.tools_called)


def test_a_response_that_retrieved_does_not_report_zero_tools() -> None:
    """The live signature that made the investigation impossible.

    Eight sources returned, and the response said `tools_called=0`,
    `total_steps=0` — the same reading a response with nothing at all gives.
    """
    result = _build(_State(current_step=1, tool_names=["vector_search"]))

    assert result.tools_called != []
    assert result.steps_taken > 0


def test_a_fast_path_result_keeps_its_own_tools_and_reports_no_steps() -> None:
    """Innocence: the three fast-paths build CoreResult directly.

    They set `tools_called` explicitly and never run the loop, so `steps_taken`
    staying 0 is the honest reading, not a regression — the guard here is that
    this change does not silently overwrite what they declare.
    """
    result = CoreResult(
        answer="fast path answer",
        tools_called=["kg_langgraph"],
    )

    assert result.tools_called == ["kg_langgraph"]
    assert result.steps_taken == 0


def test_missing_state_attributes_degrade_to_zero_not_to_a_crash() -> None:
    """A state without steps must not take the response down with it."""

    class _Bare:
        final_answer = "answer"
        query = "q"
        evidence_score = 0.85
        verification_score = 0.0

    result = _build(_Bare())  # type: ignore[arg-type]

    assert result.steps_taken == 0
    assert result.tools_called == []


async def _call_router(result: CoreResult) -> Any:
    """Drive the real /query handler over a CoreResult and return its response.

    The handler is called directly (the pattern used by
    `tests/unit/app/routers/test_agentic_rag_router.py`) so the assertion lands
    on the router's own field mapping, not on a client's serialization.
    """
    from backend.app.routers.agentic_rag import AgenticQueryRequest, query_agentic_rag

    orchestrator = AsyncMock()
    orchestrator.process_query = AsyncMock(return_value=result)

    ab_manager = MagicMock()
    ab_manager.metrics_tracker = MagicMock()
    ab_manager.metrics_tracker.record_query_metrics = AsyncMock()
    ab_manager.assign_variant = MagicMock(return_value="control")
    ab_manager.get_variant_config = MagicMock(return_value={})

    with (
        patch("backend.app.routers.agentic_rag.get_optional_database_pool", return_value=None),
        patch("backend.app.routers.agentic_rag.get_ab_test_manager", return_value=ab_manager),
    ):
        return await query_agentic_rag(
            request=AgenticQueryRequest(query="What is the paid-up capital for a PT PMA?"),
            current_user={"email": "test@example.com", "user_id": "123"},
            orchestrator=orchestrator,
            db_pool=None,
            is_wa_inbox_bot=False,
        )


@pytest.mark.asyncio
async def test_the_api_reports_steps_and_tools_as_two_different_numbers() -> None:
    """The line that actually lied: `total_steps=len(result.tools_called)`.

    The builder tests above pin the two fields on the result object; this one
    pins the API response, which is what a person debugging a live silence
    reads. Under the old wiring `total_steps` was BY CONSTRUCTION equal to
    `tools_called`, so this exact pair of assertions was unsatisfiable.
    """
    response = await _call_router(
        CoreResult(answer="an answer", tools_called=["vector_search"], steps_taken=3)
    )

    assert response.total_steps == 3
    assert response.tools_called == 1


def test_populating_tools_called_does_not_re_attribute_a_react_result() -> None:
    """`tools_called` is not only displayed — it decides producer attribution.

    `classify_result_origin` calls a result SPECIALIZED_SERVICE_ROUTER when its
    tools intersect {autonomous_research, cross_oracle_synthesis,
    client_journey}. Those three are SpecializedServiceRouter CATEGORY strings
    (`orchestrator_core.py:1527`), never ReAct tool names — measured against the
    agentic tool executor, whose closed set is vector_search / calculator /
    web_search / visa_oracle / generate_image / crm_query / get_pricing. So
    filling a field that used to be permanently empty on the ReAct path cannot
    move a result into another origin.

    This test exists so that stays true: name a future ReAct tool
    `client_journey` and the attribution silently changes with no other symptom.
    """
    from backend.services.rag.agentic.orchestrator_finalization import classify_result_origin
    from backend.services.rag.agentic.schema import ProducerOrigin

    result = _build(
        _State(current_step=2, tool_names=["vector_search", "get_pricing", "web_search"])
    )
    result.route_used = "react"

    origin, bypass = classify_result_origin(result)

    assert origin is ProducerOrigin.REACT_PIPELINE
    assert bypass is None


@pytest.mark.asyncio
async def test_the_api_does_not_report_steps_for_a_result_that_ran_none() -> None:
    """Innocence: a fast-path result declares tools and no loop.

    Reporting its tool count as a step count would be the same lie with the
    sign flipped — inventing steps that never ran.
    """
    response = await _call_router(
        CoreResult(answer="fast path", tools_called=["kg_langgraph", "get_pricing"])
    )

    assert response.tools_called == 2
    assert response.total_steps == 0
