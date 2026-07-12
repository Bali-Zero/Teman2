from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

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
    assert streaming_core.kwargs["tool_execution_counter"] == {"count": 0}
    assert isinstance(streaming_core.kwargs["correlation_id"], str)


def test_create_error_event_matches_streaming_contract() -> None:
    orchestrator = _bare_orchestrator()

    event = orchestrator._create_error_event(
        error_type="fatal",
        message="Backend unavailable",
        correlation_id="corr-9",
    )

    assert event["type"] == "error"
    assert event["data"]["error_type"] == "fatal"
    assert event["data"]["message"] == "Backend unavailable"
    assert event["data"]["correlation_id"] == "corr-9"
    assert isinstance(event["data"]["timestamp"], float)
