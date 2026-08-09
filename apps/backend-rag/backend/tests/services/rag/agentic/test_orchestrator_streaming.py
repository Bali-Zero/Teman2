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


def test_create_error_event_exposes_only_generic_message() -> None:
    manager = OrchestratorStreamingManager()

    event = manager.create_error_event(
        error_type="validation",
        message="Malformed event",
        correlation_id="corr-1",
    )

    assert event["type"] == "error"
    assert event["data"] == {"message": "Malformed event"}
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
    assert events[0]["data"] == {"message": "Stream aborted due to too many malformed events"}
    assert metrics.stream_event_none_total.count == 1
    assert metrics.stream_event_invalid_type_total.count == 1


def test_validation_failure_does_not_log_raw_event(
    metrics: _Metrics,
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = OrchestratorStreamingManager()
    raw_event_canary = "SYNTHETIC_RAW_STREAM_EVENT_CANARY_1c4a"

    assert manager.validate_event({"type": [], "data": raw_event_canary}, "corr") is None

    assert raw_event_canary not in caplog.text


@pytest.mark.asyncio
async def test_processing_exception_is_generic_in_log_and_sse(
    metrics: _Metrics,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = OrchestratorStreamingManager(max_event_errors=1)
    exception_canary = "SYNTHETIC_RAW_STREAM_EXCEPTION_CANARY_77b2"
    user_canary = "SYNTHETIC_RAW_STREAM_USER_CANARY_3a0d"

    def fail_validation(_raw_event: Any, _correlation_id: str) -> None:
        raise RuntimeError(exception_canary)

    monkeypatch.setattr(manager, "validate_event", fail_validation)
    events = [
        event
        async for event in manager.process_event_stream(
            _events([{"type": "token", "data": "unused"}]),
            correlation_id="corr-safe",
            user_id=user_canary,
        )
    ]

    assert events == [
        {
            "type": "error",
            "data": {"message": "Unable to process the streamed response."},
            "timestamp": events[0]["timestamp"],
        }
    ]
    assert exception_canary not in caplog.text
    assert user_canary not in caplog.text


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
