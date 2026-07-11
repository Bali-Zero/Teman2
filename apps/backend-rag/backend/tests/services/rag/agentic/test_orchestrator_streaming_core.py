from types import SimpleNamespace

import pytest

from backend.services.rag.agentic import orchestrator_streaming_core
from backend.services.rag.agentic.orchestrator_streaming_core import OrchestratorStreamingCore


class FakeStreamingManager:
    def create_done_event(self, *, execution_time: float, route_used: str, **kwargs) -> dict:
        return {
            "type": "done",
            "data": {"execution_time": execution_time, "route_used": route_used, **kwargs},
        }


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
