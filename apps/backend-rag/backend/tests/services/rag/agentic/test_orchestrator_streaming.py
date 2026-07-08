from __future__ import annotations

from typing import Any

import pytest

from backend.services.rag.agentic import orchestrator_streaming as module
from backend.services.rag.agentic.orchestrator_streaming import OrchestratorStreamingManager


class _Counter:
    def __init__(self) -> None:
        self.count = 0

    def inc(self) -> None:
        self.count += 1


class _Metrics:
    def __init__(self) -> None:
        self.stream_event_none_total = _Counter()
        self.stream_event_invalid_type_total = _Counter()
        self.stream_event_validation_failed_total = _Counter()
        self.stream_event_processing_error_total = _Counter()


@pytest.fixture
def metrics(monkeypatch: pytest.MonkeyPatch) -> _Metrics:
    fake_metrics = _Metrics()
    monkeypatch.setattr(module, "metrics_collector", fake_metrics)
    return fake_metrics


async def _events(items: list[Any]):
    for item in items:
        yield item


def test_create_error_event_includes_traceable_payload() -> None:
    manager = OrchestratorStreamingManager()

    event = manager.create_error_event(
        error_type="validation",
        message="Malformed event",
        correlation_id="corr-1",
    )

    assert event["type"] == "error"
    assert event["data"]["error_type"] == "validation"
    assert event["data"]["message"] == "Malformed event"
    assert event["data"]["correlation_id"] == "corr-1"
    assert isinstance(event["data"]["timestamp"], float)
    assert isinstance(event["timestamp"], float)


def test_validate_event_accepts_schema_and_drops_none_or_invalid(metrics: _Metrics) -> None:
    manager = OrchestratorStreamingManager()

    assert manager.validate_event({"type": "token", "data": "hi"}, "corr") == {
        "type": "token",
        "data": "hi",
    }
    assert manager.validate_event(None, "corr") is None
    assert manager.validate_event("not an event", "corr") is None

    assert metrics.stream_event_none_total.count == 1
    assert metrics.stream_event_invalid_type_total.count == 1


def test_validate_event_can_skip_pydantic_schema(metrics: _Metrics) -> None:
    manager = OrchestratorStreamingManager(event_validation_enabled=False)
    raw_event = {"custom": object()}

    assert manager.validate_event(raw_event, "corr") is raw_event
    assert metrics.stream_event_validation_failed_total.count == 0


@pytest.mark.asyncio
async def test_process_event_stream_aborts_after_malformed_events(metrics: _Metrics) -> None:
    manager = OrchestratorStreamingManager(max_event_errors=2)

    events = [
        event
        async for event in manager.process_event_stream(
            _events([None, "bad", {"type": "token", "data": "unreached"}]),
            correlation_id="corr-2",
            user_id="user-1",
        )
    ]

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert events[0]["data"]["error_type"] == "too_many_errors"
    assert metrics.stream_event_none_total.count == 1
    assert metrics.stream_event_invalid_type_total.count == 1


def test_status_done_and_metadata_event_factories() -> None:
    manager = OrchestratorStreamingManager()

    assert manager.create_initial_status_event("corr-3")["data"] == {
        "status": "processing",
        "correlation_id": "corr-3",
    }
    assert manager.create_done_event(
        execution_time=1.234,
        route_used="agentic",
        evidence_score=0.87654,
        confidence_zone="NORMAL",
    ) == {
        "type": "done",
        "data": {
            "execution_time": 1.23,
            "route_used": "agentic",
            "evidence_score": 0.877,
            "confidence_zone": "NORMAL",
        },
    }
    assert manager.create_metadata_event({"route": "gate"})["data"] == {"route": "gate"}


@pytest.mark.asyncio
async def test_stream_text_response_preserves_whitespace_between_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(module.asyncio, "sleep", no_sleep)
    manager = OrchestratorStreamingManager()

    events = [
        event
        async for event in manager.stream_text_response(
            "Hello  world",
            status="ok",
            route="direct",
            delay=0,
        )
    ]

    assert events[0] == {
        "type": "metadata",
        "data": {"status": "ok", "route": "direct"},
        "timestamp": events[0]["timestamp"],
    }
    assert events[1:-1] == [
        {"type": "token", "data": "Hello"},
        {"type": "token", "data": "  "},
        {"type": "token", "data": "world"},
    ]
    assert events[-1] == {"type": "done", "data": None}
