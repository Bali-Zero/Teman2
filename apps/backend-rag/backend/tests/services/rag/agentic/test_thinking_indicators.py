from __future__ import annotations

from backend.services.rag.agentic import thinking_indicators as thinking_module
from backend.services.rag.agentic.thinking_indicators import (
    ThinkingIndicatorService,
    ThinkingPhase,
    get_tool_display_name,
)


def test_get_tool_display_name_localized_and_fallback() -> None:
    assert get_tool_display_name("search_documents", "en") == "document search"
    assert get_tool_display_name("search_documents", "it") == "ricerca documenti"
    assert get_tool_display_name("unknown_tool", "en") == "unknown tool"


def test_get_message_formats_tool_and_falls_back_to_english() -> None:
    service = ThinkingIndicatorService(language="xx")

    assert (
        service.get_message(ThinkingPhase.TOOL_CALLING, tool_name="pricing")
        == "\U0001f527 Using pricing..."
    )
    assert (
        service.get_message(ThinkingPhase.TOOL_CALLING)
        == "\U0001f527 Using {tool_name}..."
    )


def test_create_thinking_event_updates_phase_and_allows_override(monkeypatch) -> None:
    times = iter([100.0, 100.5])
    monkeypatch.setattr(thinking_module.time, "time", lambda: next(times))
    service = ThinkingIndicatorService(language="en")

    event = service.create_thinking_event(
        ThinkingPhase.TOOL_CALLING,
        tool_name="pricing",
        message_override="Working",
    )

    assert event == {
        "type": "thinking",
        "data": "Working",
        "phase": "tool_calling",
        "timestamp": 100.5,
    }
    assert service._current_phase is ThinkingPhase.TOOL_CALLING
    assert service._phase_start_time == 100.0


def test_create_done_event_clears_streaming_indicator(monkeypatch) -> None:
    monkeypatch.setattr(thinking_module.time, "time", lambda: 200.0)

    assert ThinkingIndicatorService().create_done_event() == {
        "type": "thinking_done",
        "data": "",
        "timestamp": 200.0,
    }


def test_get_phase_duration_uses_current_phase_start(monkeypatch) -> None:
    service = ThinkingIndicatorService()

    assert service.get_phase_duration() == 0.0

    service._phase_start_time = 10.0
    monkeypatch.setattr(thinking_module.time, "time", lambda: 12.25)

    assert service.get_phase_duration() == 2.25


def test_should_show_thinking_respects_phase_thresholds(monkeypatch) -> None:
    now = 100.25
    monkeypatch.setattr(thinking_module.time, "time", lambda: now)
    service = ThinkingIndicatorService()
    service._phase_start_time = 100.0

    assert service.should_show_thinking(ThinkingPhase.ANALYZING) is False
    assert service.should_show_thinking(ThinkingPhase.REASONING) is False
    assert service.should_show_thinking(ThinkingPhase.SEARCHING) is True
    assert service.should_show_thinking(ThinkingPhase.TOOL_CALLING) is True
    assert service.should_show_thinking(ThinkingPhase.GENERATING) is True

    now = 101.25

    assert service.should_show_thinking(ThinkingPhase.ANALYZING) is True
    assert service.should_show_thinking(ThinkingPhase.REASONING) is True
