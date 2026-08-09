import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.rag.agentic import orchestrator_streaming_core
from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
from backend.services.rag.agentic.orchestrator_streaming_core import OrchestratorStreamingCore
from backend.services.rag.agentic.schema import (
    AnalyticsReceiptStatus,
    CoreResult,
    EvidenceProvenance,
    FinalizationStatus,
    ProducerOrigin,
    TrustedBypassReason,
)
from backend.services.tools.definitions import AgentState


class FakeStreamingManager:
    def __init__(self) -> None:
        self.processed_user_ids: list[str | None] = []

    def create_done_event(self, *, execution_time: float, route_used: str, **kwargs) -> dict:
        return {
            "type": "done",
            "data": {"execution_time": execution_time, "route_used": route_used, **kwargs},
        }

    def create_initial_status_event(self, correlation_id: str) -> dict:
        return {"type": "status", "data": {"correlation_id": correlation_id}}

    def create_error_event(
        self,
        *,
        error_type: str,
        message: str,
        correlation_id: str,
    ) -> dict:
        return {
            "type": "error",
            "data": {
                "error_type": error_type,
                "message": message,
                "correlation_id": correlation_id,
            },
        }

    async def process_event_stream(self, *, event_generator, **kwargs):
        self.processed_user_ids.append(kwargs.get("user_id"))
        async for event in event_generator:
            yield event


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "expected_origin", "expected_provenance", "expected_trust"),
    [
        (
            CoreResult(answer="hello", model_used="greeting-gate"),
            ProducerOrigin.QUERY_GATE,
            None,
            TrustedBypassReason.DETERMINISTIC_QUERY_GATE,
        ),
        (
            CoreResult(
                answer="cached",
                sources=[{"source": "cache-source"}],
                model_used="cache",
                cache_hit=True,
            ),
            ProducerOrigin.SEMANTIC_CACHE,
            EvidenceProvenance.SEMANTIC_CACHE,
            None,
        ),
    ],
)
async def test_gate_and_cache_stream_cross_finalization_before_first_token(
    monkeypatch,
    result: CoreResult,
    expected_origin: ProducerOrigin,
    expected_provenance: EvidenceProvenance | None,
    expected_trust: TrustedBypassReason | None,
) -> None:
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(orchestrator_streaming_core.asyncio, "sleep", no_sleep)
    real_core = OrchestratorCore.__new__(OrchestratorCore)
    real_core.db_pool = None
    real_core.prepare_query_context = AsyncMock(return_value=({}, [], {}, "", None))
    real_core.check_gates_and_cache = AsyncMock(return_value=result)
    streaming_core = OrchestratorStreamingCore(
        core=real_core,
        streaming_manager=FakeStreamingManager(),
    )

    with patch.object(streaming_core, "_mark_react_stream_unfinalized") as marker:
        events = [
            event
            async for event in streaming_core.stream_query_core(
                query="stream contract",
                user_id="contract-user",
                conversation_history=None,
                session_id=None,
                images=None,
                tool_execution_counter={"count": 0},
                correlation_id="contract-correlation",
            )
        ]

    marker.assert_not_called()

    first_token_index = next(
        index for index, event in enumerate(events) if event["type"] == "token"
    )
    finalization_metadata = next(
        event
        for event in events[:first_token_index]
        if event["type"] == "metadata" and "finalization_status" in event["data"]
    )
    assert (
        finalization_metadata["data"]["finalization_status"] is FinalizationStatus.SHADOW_RECORDED
    )
    assert finalization_metadata["data"]["producer_origin"] is expected_origin
    assert finalization_metadata["data"]["evidence_provenance"] is expected_provenance
    assert finalization_metadata["data"]["trusted_bypass_reason"] is expected_trust
    assert finalization_metadata["data"]["analytics_receipt"] is AnalyticsReceiptStatus.SKIPPED
    assert result.answer in {"hello", "cached"}


def test_react_stream_gap_is_fail_visible_and_cannot_claim_complete() -> None:
    core = OrchestratorStreamingCore(core=object(), streaming_manager=FakeStreamingManager())

    with (
        patch.object(orchestrator_streaming_core, "add_span_event") as span_event,
        patch.object(orchestrator_streaming_core.logger, "warning") as warning,
    ):
        core._mark_react_stream_unfinalized()

    assert orchestrator_streaming_core.REACT_STREAM_FINALIZATION_COMPLETE is False
    span_event.assert_called_once_with(
        "finalization.stream_react_unfinalized",
        {
            "coverage_complete": False,
            "reason": "tokens_emitted_before_confidence_and_analytics",
        },
    )
    warning.assert_called_once()


class _RawReactReasoningEngine:
    def __init__(self, outcome: str) -> None:
        self.outcome = outcome
        self.tool_map: dict = {}
        self.last_kwargs: dict = {}

    async def execute_react_loop_stream(self, **kwargs):
        self.last_kwargs = kwargs
        yield {"type": "token", "data": "raw-token"}
        if self.outcome == "error":
            raise RuntimeError("raw stream failed")
        if self.outcome == "cancel":
            raise asyncio.CancelledError


class _RawReactCore:
    def __init__(self, outcome: str) -> None:
        self.reasoning_engine = _RawReactReasoningEngine(outcome)
        self.llm_gateway = SimpleNamespace(
            create_chat_with_history=lambda **_kwargs: object(),
        )
        self.metrics_manager = SimpleNamespace(
            extract_collections_from_state=lambda _state: set(),
            extract_sources_from_state=lambda _state: [],
        )
        self.db_pool = None

    async def prepare_query_context(self, **_kwargs):
        return ({"profile": None}, [], {}, "", None)

    async def check_gates_and_cache(self, **_kwargs):
        return None

    async def prepare_react_execution(self, **_kwargs):
        state = AgentState(query="raw stream contract", intent_type="business_complex")
        state.evidence_score = 0.8
        state.trusted_tools_used = True
        return ("gemini-parent", False, state, "system prompt")


@pytest.mark.asyncio
async def test_trusted_wa_stream_uses_only_profile_and_bounded_history() -> None:
    """Streaming WA skips context, KG and analytics side effects entirely."""
    core = _RawReactCore("complete")
    core.db_pool = object()
    core.prepare_query_context = AsyncMock(return_value=({}, [], {}, "", None))
    core.context_manager = SimpleNamespace(
        enrich_user_context=AsyncMock(return_value={"memory_facts": ["private"]}),
    )
    core.extract_entities_and_kg_context = AsyncMock(return_value=({}, "", None))
    original_prepare_react = core.prepare_react_execution
    core.prepare_react_execution = AsyncMock(wraps=original_prepare_react)
    streaming_manager = FakeStreamingManager()
    streaming_core = OrchestratorStreamingCore(
        core=core,
        streaming_manager=streaming_manager,
    )
    trusted_profile = {"role": "team", "id": "synthetic-team"}
    bounded_history = [{"role": "user", "content": "bounded history"}]

    with patch(
        "backend.db.repositories.query_analytics_repository.QueryAnalyticsRepository",
    ) as analytics_repo:
        events = [
            event
            async for event in streaming_core.stream_query_core(
                query="RAW_STREAM_QUERY_CANARY",
                user_id="RAW_STREAM_USER_CANARY",
                conversation_history=bounded_history,
                session_id="RAW_STREAM_SESSION_CANARY",
                images=None,
                tool_execution_counter={"count": 0},
                correlation_id="synthetic-correlation",
                profile=trusted_profile,
                is_whatsapp=True,
            )
        ]

    assert any(event["type"] == "done" for event in events)
    core.prepare_query_context.assert_not_awaited()
    core.context_manager.enrich_user_context.assert_not_awaited()
    core.extract_entities_and_kg_context.assert_not_awaited()
    analytics_repo.assert_not_called()
    prepare_kwargs = core.prepare_react_execution.await_args.kwargs
    assert prepare_kwargs["user_context"] == {"profile": trusted_profile}
    assert prepare_kwargs["history"] == bounded_history
    assert core.reasoning_engine.last_kwargs["user_id"] == "anonymous"
    assert set(streaming_manager.processed_user_ids) == {"anonymous"}


@pytest.mark.asyncio
async def test_trusted_wa_stream_ignores_preloaded_memory_context() -> None:
    """Even a supplied fast-path context cannot re-enable WA enrichment."""
    core = _RawReactCore("complete")
    core.prepare_query_context = AsyncMock(return_value=({}, [], {}, "", None))
    core.context_manager = SimpleNamespace(
        enrich_user_context=AsyncMock(return_value={"memory_facts": ["private"]}),
    )
    core.extract_entities_and_kg_context = AsyncMock(return_value=({}, "", None))
    original_prepare_react = core.prepare_react_execution
    core.prepare_react_execution = AsyncMock(wraps=original_prepare_react)
    streaming_core = OrchestratorStreamingCore(
        core=core,
        streaming_manager=FakeStreamingManager(),
    )
    trusted_profile = {"role": "team", "id": "synthetic-team"}

    events = [
        event
        async for event in streaming_core.stream_query_core(
            query="synthetic public question",
            user_id="synthetic-wa-user",
            conversation_history=[],
            session_id=None,
            images=None,
            tool_execution_counter={"count": 0},
            correlation_id="synthetic-correlation",
            initial_user_context={
                "profile": {"id": "untrusted-preload"},
                "memory_facts": ["must not transit"],
            },
            profile=trusted_profile,
            is_whatsapp=True,
        )
    ]

    assert any(event["type"] == "done" for event in events)
    core.prepare_query_context.assert_not_awaited()
    core.context_manager.enrich_user_context.assert_not_awaited()
    core.extract_entities_and_kg_context.assert_not_awaited()
    prepare_kwargs = core.prepare_react_execution.await_args.kwargs
    assert prepare_kwargs["user_context"] == {"profile": trusted_profile}
    assert prepare_kwargs["history"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "expect_error_event", "expect_cancel"),
    [
        ("complete", False, False),
        ("error", True, False),
        ("cancel", False, True),
    ],
)
async def test_real_raw_react_stream_marks_every_terminal_path_exactly_once(
    outcome: str,
    expect_error_event: bool,
    expect_cancel: bool,
) -> None:
    streaming_core = OrchestratorStreamingCore(
        core=_RawReactCore(outcome),
        streaming_manager=FakeStreamingManager(),
    )

    with patch.object(streaming_core, "_mark_react_stream_unfinalized") as marker:
        if expect_cancel:
            with pytest.raises(asyncio.CancelledError):
                async for _event in streaming_core.stream_query_core(
                    query="raw stream contract",
                    user_id="contract-user",
                    conversation_history=None,
                    session_id=None,
                    images=None,
                    tool_execution_counter={"count": 0},
                    correlation_id="contract-correlation",
                ):
                    pass
            events = []
        else:
            events = [
                event
                async for event in streaming_core.stream_query_core(
                    query="raw stream contract",
                    user_id="contract-user",
                    conversation_history=None,
                    session_id=None,
                    images=None,
                    tool_execution_counter={"count": 0},
                    correlation_id="contract-correlation",
                )
            ]

    marker.assert_called_once_with()
    assert any(event.get("data") == "raw-token" for event in events) is not expect_cancel
    assert any(event["type"] == "error" for event in events) is expect_error_event


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
        self.prepare_kwargs = None

    async def prepare_query_context(self, **_kwargs):
        return ({"user_id": "u"}, [], {}, "", None)

    async def check_gates_and_cache(self, **_kwargs):
        return None

    async def prepare_react_execution(self, **kwargs):
        self.prepare_kwargs = kwargs
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "is_whatsapp"),
    [
        ({"role": "client", "id": "synthetic-client"}, False),
        (None, True),
    ],
)
async def test_crm_prefetch_skips_non_workspace_surfaces_and_forwards_state(
    profile,
    is_whatsapp,
) -> None:
    crm_tool = SimpleNamespace(execute=AsyncMock(return_value="42 active clients"))
    fake_core = FakeCoreForCrmPrefetch(tool_map={"crm_query": crm_tool})
    streaming_core = OrchestratorStreamingCore(
        core=fake_core,
        streaming_manager=FakeStreamingManager(),
    )

    await _drain_until_crm_prefetch(
        streaming_core,
        query="quanti clienti attivi abbiamo",
        user_id="synthetic-user",
        conversation_history=None,
        session_id=None,
        images=None,
        tool_execution_counter={"count": 0},
        correlation_id="cid-surface-state",
        agent_role=SimpleNamespace(role_id="admin"),
        profile=profile,
        is_whatsapp=is_whatsapp,
    )

    crm_tool.execute.assert_not_called()
    assert fake_core.prepare_kwargs["profile"] is profile
    assert fake_core.prepare_kwargs["is_whatsapp"] is is_whatsapp


@pytest.mark.asyncio
async def test_react_stream_failure_is_generic_in_sse_and_logs(caplog) -> None:
    exception_canary = "SYNTHETIC_STREAM_EXCEPTION_CANARY_3c19"

    class ExplodingReasoningEngine:
        tool_map: dict = {}

        async def execute_react_loop_stream(self, **_kwargs):
            raise RuntimeError(exception_canary)
            yield  # pragma: no cover - makes this an async generator

    class ExplodingCore(_RawReactCore):
        def __init__(self) -> None:
            super().__init__("complete")
            self.reasoning_engine = ExplodingReasoningEngine()

    streaming_core = OrchestratorStreamingCore(
        core=ExplodingCore(),
        streaming_manager=FakeStreamingManager(),
    )

    with caplog.at_level(
        "ERROR",
        logger="backend.services.rag.agentic.orchestrator_streaming_core",
    ):
        events = [
            event
            async for event in streaming_core.stream_query_core(
                query="synthetic public query",
                user_id="synthetic-public-user",
                conversation_history=None,
                session_id="synthetic-session",
                images=None,
                tool_execution_counter={"count": 0},
                correlation_id="contract-correlation",
            )
        ]

    error_event = next(event for event in events if event["type"] == "error")
    assert error_event["data"]["message"] == "Unable to complete the streamed response."
    assert exception_canary not in repr(events)
    assert exception_canary not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
