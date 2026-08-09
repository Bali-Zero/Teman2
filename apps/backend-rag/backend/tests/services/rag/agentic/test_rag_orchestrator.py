from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langsmith import tracing_context
from langsmith.run_helpers import get_tracing_context
from openinference.instrumentation import config as openinference_config
from opentelemetry.context import get_value

from backend.services.rag.agentic import orchestrator as orchestrator_module
from backend.services.rag.agentic.orchestrator import AgenticRAGOrchestrator


def _bare_orchestrator() -> AgenticRAGOrchestrator:
    return object.__new__(AgenticRAGOrchestrator)


@pytest.mark.asyncio
async def test_process_query_delegates_to_core_and_dispatches_memory_save() -> None:
    result = SimpleNamespace(answer="Processed answer")
    orchestrator = _bare_orchestrator()
    orchestrator._initialized = False
    orchestrator.initialize = AsyncMock()
    orchestrator.core = SimpleNamespace(process_query_core=AsyncMock(return_value=result))
    orchestrator.memory_handler = SimpleNamespace(create_save_task=Mock())

    returned = await orchestrator.process_query(
        "How do I renew KITAS?",
        user_id="user-1",
        conversation_history=[{"role": "user", "content": "old"}],
        start_time=123.0,
        session_id="session-1",
    )

    assert returned is result
    orchestrator.initialize.assert_awaited_once()
    orchestrator.core.process_query_core.assert_awaited_once()
    kwargs = orchestrator.core.process_query_core.await_args.kwargs
    assert kwargs["query"] == "How do I renew KITAS?"
    assert kwargs["user_id"] == "user-1"
    assert kwargs["conversation_history"] == [{"role": "user", "content": "old"}]
    assert kwargs["start_time"] == 123.0
    assert kwargs["session_id"] == "session-1"
    assert kwargs["tool_execution_counter"] == {"count": 0}
    orchestrator.memory_handler.create_save_task.assert_called_once_with(
        user_id="user-1",
        query="How do I renew KITAS?",
        answer="Processed answer",
        session_id="session-1",
        metrics_collector=pytest.importorskip("backend.app.metrics").metrics_collector,
        # W-1 (P0-MEM follow-up): forwarded verbatim. None is the innocence
        # case — a non-WhatsApp caller keeps keying memory on `user_id`.
        memory_subject=None,
    )


@pytest.mark.asyncio
async def test_process_query_skips_background_memory_for_anonymous_user() -> None:
    orchestrator = _bare_orchestrator()
    orchestrator._initialized = True
    orchestrator.core = SimpleNamespace(
        process_query_core=AsyncMock(return_value=SimpleNamespace(answer="ok")),
    )
    orchestrator.memory_handler = SimpleNamespace(create_save_task=Mock())

    await orchestrator.process_query("hello", user_id="anonymous")

    orchestrator.memory_handler.create_save_task.assert_not_called()


@pytest.mark.asyncio
async def test_trusted_wa_process_observability_omits_raw_identifiers_and_errors(
    monkeypatch,
    caplog,
) -> None:
    user_canary = "whatsapp_SYNTHETIC_USER_CANARY_81c2"
    session_canary = "SYNTHETIC_SESSION_CANARY_4e15"
    subject_canary = "wa-subject-SYNTHETIC_CANARY_8ac0"
    query_canary = "SYNTHETIC_QUERY_CANARY_9d33"
    trace_attributes = {}
    trace_calls: list[str] = []

    @contextmanager
    def capture_trace(name, attributes):
        trace_calls.append(name)
        trace_attributes.update(attributes)
        yield None

    monkeypatch.setattr(orchestrator_module, "trace_span", capture_trace)
    orchestrator = _bare_orchestrator()
    orchestrator._initialized = True
    orchestrator.core = SimpleNamespace(
        process_query_core=AsyncMock(return_value=SimpleNamespace(answer="safe answer")),
    )
    orchestrator.memory_handler = SimpleNamespace(create_save_task=Mock())

    with caplog.at_level(
        "DEBUG",
        logger="backend.services.rag.agentic.orchestrator",
    ):
        result = await orchestrator.process_query(
            query_canary,
            user_id=user_canary,
            session_id=session_canary,
            memory_subject=subject_canary,
            is_whatsapp=True,
        )

    assert result.answer == "safe answer"
    rendered_trace = repr(trace_attributes)
    for canary in (
        user_canary,
        session_canary,
        subject_canary,
        query_canary,
    ):
        assert canary not in caplog.text
        assert canary not in rendered_trace
    orchestrator.memory_handler.create_save_task.assert_not_called()
    assert trace_calls == []
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_non_wa_process_query_keeps_manual_otel_span(monkeypatch) -> None:
    trace_calls: list[tuple[str, dict]] = []

    @contextmanager
    def capture_trace(name, attributes):
        trace_calls.append((name, attributes))
        yield None

    monkeypatch.setattr(orchestrator_module, "trace_span", capture_trace)
    orchestrator = _bare_orchestrator()
    orchestrator._initialized = True
    orchestrator.core = SimpleNamespace(
        process_query_core=AsyncMock(return_value=SimpleNamespace(answer="ordinary answer")),
    )
    orchestrator.memory_handler = SimpleNamespace(create_save_task=Mock())

    result = await orchestrator.process_query(
        "ordinary non-WA query",
        user_id="anonymous",
        is_whatsapp=False,
    )

    assert result.answer == "ordinary answer"
    assert [name for name, _attributes in trace_calls] == ["orchestrator.process_query"]


@pytest.mark.asyncio
async def test_trusted_wa_cold_start_skips_memory_and_kg_initializers() -> None:
    """A first WA request cannot warm memory or KG as a hidden side effect."""
    orchestrator = _bare_orchestrator()
    orchestrator._initialized = False
    orchestrator.initialize = AsyncMock(
        side_effect=AssertionError("trusted WA reached automatic initializers"),
    )
    orchestrator.core = SimpleNamespace(
        process_query_core=AsyncMock(return_value=SimpleNamespace(answer="safe answer")),
    )
    orchestrator.memory_handler = SimpleNamespace(create_save_task=Mock())

    result = await orchestrator.process_query(
        "synthetic public question",
        user_id="synthetic-wa-user",
        conversation_history=[{"role": "user", "content": "bounded history"}],
        session_id="synthetic-wa-session",
        profile={"role": "team", "id": "synthetic-team"},
        is_whatsapp=True,
    )

    assert result.answer == "safe answer"
    orchestrator.initialize.assert_not_awaited()
    orchestrator.memory_handler.create_save_task.assert_not_called()


@pytest.mark.asyncio
async def test_trusted_wa_disables_langsmith_and_openinference_tracing() -> None:
    """Raw WA inputs cannot be captured by global tracing instrumentation."""
    observations: list[tuple[object, object]] = []

    async def inspect_trace_context(**_kwargs):
        observations.append(
            (
                get_tracing_context().get("enabled"),
                get_value(openinference_config._SUPPRESS_INSTRUMENTATION_KEY),
            )
        )
        return SimpleNamespace(answer="safe answer")

    orchestrator = _bare_orchestrator()
    orchestrator._initialized = True
    orchestrator.core = SimpleNamespace(process_query_core=inspect_trace_context)
    orchestrator.memory_handler = SimpleNamespace(create_save_task=Mock())

    with tracing_context(enabled=True):
        await orchestrator.process_query(
            "RAW_WA_QUERY_CANARY",
            user_id="RAW_WA_USER_CANARY",
            session_id="RAW_WA_SESSION_CANARY",
            is_whatsapp=True,
        )
        await orchestrator.process_query(
            "ordinary non-WA question",
            user_id="anonymous",
            is_whatsapp=False,
        )

    assert observations == [(False, True), (True, None)]


@pytest.mark.asyncio
async def test_trusted_wa_stream_disables_global_tracing() -> None:
    """The future trusted WA streaming lane has the same telemetry boundary."""
    observations: list[tuple[object, object]] = []

    class InspectingStreamingCore:
        async def stream_query_core(self, **_kwargs):
            observations.append(
                (
                    get_tracing_context().get("enabled"),
                    get_value(openinference_config._SUPPRESS_INSTRUMENTATION_KEY),
                )
            )
            yield {"type": "done", "data": None}

    orchestrator = _bare_orchestrator()
    orchestrator.streaming_core = InspectingStreamingCore()

    with tracing_context(enabled=True):
        _ = [
            event
            async for event in orchestrator.stream_query(
                "RAW_WA_STREAM_QUERY_CANARY",
                user_id="RAW_WA_STREAM_USER_CANARY",
                session_id="RAW_WA_STREAM_SESSION_CANARY",
                is_whatsapp=True,
            )
        ]
        _ = [
            event
            async for event in orchestrator.stream_query(
                "ordinary non-WA stream question",
                user_id="ordinary-user",
                is_whatsapp=False,
            )
        ]

    assert observations == [(False, True), (True, None)]


@pytest.mark.asyncio
async def test_stream_query_forwards_runtime_arguments_to_streaming_core() -> None:
    class FakeStreamingCore:
        def __init__(self) -> None:
            self.kwargs = None

        async def stream_query_core(self, **kwargs):
            self.kwargs = kwargs
            yield {"type": "token", "data": "hi"}
            yield {"type": "done", "data": None}

    streaming_core = FakeStreamingCore()
    orchestrator = _bare_orchestrator()
    orchestrator.streaming_core = streaming_core

    events = [
        event
        async for event in orchestrator.stream_query(
            "question",
            user_id="user-2",
            conversation_history=[],
            session_id="session-2",
            images=[{"mime": "image/png"}],
            channel="whatsapp",
            agent_role="support",
        )
    ]

    assert events == [
        {"type": "token", "data": "hi"},
        {"type": "done", "data": None},
    ]
    assert streaming_core.kwargs["query"] == "question"
    assert streaming_core.kwargs["user_id"] == "user-2"
    assert streaming_core.kwargs["session_id"] == "session-2"
    assert streaming_core.kwargs["images"] == [{"mime": "image/png"}]
    assert streaming_core.kwargs["channel"] == "whatsapp"
    assert streaming_core.kwargs["agent_role"] == "support"
    # A caller-controlled channel overlay is not WhatsApp authority.
    assert streaming_core.kwargs["is_whatsapp"] is False
    assert streaming_core.kwargs["profile"] is None
    assert streaming_core.kwargs["tool_execution_counter"] == {"count": 0}
    assert isinstance(streaming_core.kwargs["correlation_id"], str)


@pytest.mark.asyncio
async def test_stream_query_forwards_explicit_server_side_surface_state() -> None:
    class FakeStreamingCore:
        def __init__(self) -> None:
            self.kwargs = None

        async def stream_query_core(self, **kwargs):
            self.kwargs = kwargs
            yield {"type": "done", "data": None}

    streaming_core = FakeStreamingCore()
    orchestrator = _bare_orchestrator()
    orchestrator.streaming_core = streaming_core
    profile = {"role": "team", "id": "synthetic-team"}

    events = [
        event
        async for event in orchestrator.stream_query(
            "question",
            user_id="synthetic-user",
            profile=profile,
            is_whatsapp=True,
        )
    ]

    assert events == [{"type": "done", "data": None}]
    assert streaming_core.kwargs["profile"] is profile
    assert streaming_core.kwargs["is_whatsapp"] is True


def test_create_error_event_matches_streaming_contract() -> None:
    orchestrator = _bare_orchestrator()

    event = orchestrator._create_error_event(
        error_type="fatal",
        message="Backend unavailable",
        correlation_id="corr-9",
    )

    assert event["type"] == "error"
    assert event["data"] == {"message": "Backend unavailable"}
    assert isinstance(event["timestamp"], float)
