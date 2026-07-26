from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.services.rag.agentic import orchestrator_streaming_core
from backend.services.rag.agentic.orchestrator_streaming_core import OrchestratorStreamingCore


class FakeStreamingManager:
    def create_done_event(self, *, execution_time: float, route_used: str, **kwargs) -> dict:
        return {
            "type": "done",
            "data": {"execution_time": execution_time, "route_used": route_used, **kwargs},
        }

    def create_initial_status_event(self, correlation_id: str) -> dict:
        return {"type": "status", "data": {"correlation_id": correlation_id}}


@pytest.mark.asyncio
async def test_stream_core_result_yields_metadata_tokens_sources_and_done(monkeypatch) -> None:
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(orchestrator_streaming_core.asyncio, "sleep", no_sleep)
    result = SimpleNamespace(
        answer="Hello world",
        sources=[{"title": "source"}],
        model_used="greeting-gate",
        timings={"total": 0.25},
    )
    core = OrchestratorStreamingCore(core=object(), streaming_manager=FakeStreamingManager())

    events = [event async for event in core._stream_core_result(result, route_used="gate")]

    assert events[0]["type"] == "metadata"
    assert events[0]["data"] == {
        "status": "greeting",
        "route": "gate",
        "model_used": "greeting-gate",
    }
    assert events[1:3] == [
        {"type": "token", "data": "Hello "},
        {"type": "token", "data": "world "},
    ]
    assert events[3] == {"type": "sources", "data": [{"title": "source"}]}
    assert events[4] == {
        "type": "done",
        "data": {"execution_time": 0.25, "route_used": "gate"},
    }


@pytest.mark.asyncio
async def test_stream_core_result_uses_verification_status_for_non_gate() -> None:
    result = SimpleNamespace(
        answer="Answer",
        sources=[],
        model_used="gemini",
        verification_status="unchecked",
        timings={"total": 0.0},
    )
    core = OrchestratorStreamingCore(core=object(), streaming_manager=FakeStreamingManager())

    events = [event async for event in core._stream_core_result(result, route_used="agentic")]

    assert events[0]["data"]["status"] == "unchecked"
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_single_event_generator_yields_original_event() -> None:
    core = OrchestratorStreamingCore(core=object(), streaming_manager=FakeStreamingManager())
    event = {"type": "token", "data": "hello"}

    assert [item async for item in core._single_event_generator(event)] == [event]


# ─────────────────────────────────────────────────────────────────────────
# TOURNIQUET (2026-07-21) — CRM pre-call must be gated to authenticated
# staff. The prefetch calls crm_tool.execute() DIRECTLY (bypasses
# tool_executor/ToolAuthorizer entirely), so Part 1's SENSITIVE_TOOLS deny
# in tool_authorizer.py does not cover this path on its own. See memory
# `discovery_crm_pii_public_exposure_blog_ask_timesheet_2026_07_21`.
# ─────────────────────────────────────────────────────────────────────────


class _StopAfterCrmPrefetch(Exception):
    """Sentinel raised right after the CRM pre-call block completes, so the
    test never has to mock the real ReAct loop machinery downstream."""


class FakeReasoningEngine:
    def __init__(self, tool_map: dict) -> None:
        self.tool_map = tool_map


class FakeCoreForCrmPrefetch:
    """Minimal OrchestratorCore stand-in: just enough surface to drive
    stream_query_core through context-prep + gate-check + the CRM pre-call
    block, then bail out via prepare_react_execution before touching the
    real ReAct loop."""

    def __init__(self, tool_map: dict) -> None:
        self.reasoning_engine = FakeReasoningEngine(tool_map)

    async def prepare_query_context(self, **_kwargs):
        return ({"user_id": "u"}, [], {}, "", None)

    async def check_gates_and_cache(self, **_kwargs):
        return None

    async def prepare_react_execution(self, **_kwargs):
        raise _StopAfterCrmPrefetch


async def _drain_until_crm_prefetch(core: OrchestratorStreamingCore, **kwargs) -> None:
    with pytest.raises(_StopAfterCrmPrefetch):
        async for _event in core.stream_query_core(**kwargs):
            pass


@pytest.mark.asyncio
async def test_crm_prefetch_skipped_for_no_principal_streaming_caller() -> None:
    """GUILT: agent_role=None (public /stream — blog/IG/anon web-chat) must
    never call crm_tool.execute() directly, even when the query matches a
    CRM keyword."""
    crm_tool = SimpleNamespace(execute=AsyncMock(return_value="42 active clients"))
    fake_core = FakeCoreForCrmPrefetch(tool_map={"crm_query": crm_tool})
    streaming_core = OrchestratorStreamingCore(
        core=fake_core, streaming_manager=FakeStreamingManager()
    )

    await _drain_until_crm_prefetch(
        streaming_core,
        query="quanti clienti attivi abbiamo",
        user_id="anonymous",
        conversation_history=None,
        session_id=None,
        images=None,
        tool_execution_counter={"count": 0},
        correlation_id="cid-no-principal",
        agent_role=None,
    )

    crm_tool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_crm_prefetch_fires_for_authenticated_staff_caller() -> None:
    """INNOCENCE: staff callers (agent_role set, /workspace-stream) keep the
    existing CRM pre-call UX — no regression from the tourniquet."""
    crm_tool = SimpleNamespace(execute=AsyncMock(return_value="42 active clients online"))
    fake_core = FakeCoreForCrmPrefetch(tool_map={"crm_query": crm_tool})
    streaming_core = OrchestratorStreamingCore(
        core=fake_core, streaming_manager=FakeStreamingManager()
    )

    await _drain_until_crm_prefetch(
        streaming_core,
        query="quanti clienti attivi abbiamo",
        user_id="damar@balizero.com",
        conversation_history=None,
        session_id=None,
        images=None,
        tool_execution_counter={"count": 0},
        correlation_id="cid-staff",
        agent_role=SimpleNamespace(role_id="visa_specialist"),
    )

    crm_tool.execute.assert_called_once_with(query_type="client_stats")
