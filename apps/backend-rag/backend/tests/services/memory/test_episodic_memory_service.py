from datetime import datetime, timezone

import pytest

from backend.services.memory.episodic_memory_service import (
    Emotion,
    EpisodicMemoryService,
    EventType,
)


def test_extract_datetime_parses_specific_date() -> None:
    service = EpisodicMemoryService()

    extracted = service._extract_datetime("Meeting completed on 15/06/2026")

    assert extracted == datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


def test_detect_event_type_and_emotion_from_keywords() -> None:
    service = EpisodicMemoryService()

    assert service._detect_event_type("Abbiamo completato la pratica") == EventType.MILESTONE
    assert service._detect_event_type("The process is blocked") == EventType.PROBLEM
    assert service._detect_emotion("Urgente, serve risposta subito") == Emotion.URGENT
    assert service._detect_emotion("No signal words here") == Emotion.NEUTRAL


def test_extract_title_removes_temporal_expression_and_truncates() -> None:
    service = EpisodicMemoryService()
    long_message = "Oggi " + ("approval completed " * 20)

    title = service._extract_title(long_message, max_length=40)

    assert "Oggi" not in title
    assert title.endswith("...")
    assert len(title) == 40


@pytest.mark.asyncio
async def test_database_paths_degrade_without_pool() -> None:
    service = EpisodicMemoryService()

    add_result = await service.add_event(
        user_id="user@example.com",
        title="Visa approved",
        event_type=EventType.MILESTONE,
        emotion=Emotion.POSITIVE,
    )

    assert add_result == {"status": "error", "message": "Database not available"}
    assert await service.get_timeline("user@example.com") == []
    assert await service.get_recent_events("user@example.com") == []
    assert await service.delete_event(event_id=1, user_id="user@example.com") is False
    assert await service.get_stats("user@example.com") == {}


@pytest.mark.asyncio
async def test_extract_and_save_event_ignores_messages_without_temporal_signal() -> None:
    service = EpisodicMemoryService()

    result = await service.extract_and_save_event(
        user_id="user@example.com",
        message="The visa was approved",
    )

    assert result is None


@pytest.mark.asyncio
async def test_context_summary_formats_recent_events(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EpisodicMemoryService()

    async def fake_recent_events(
        user_id: str,
        days: int = 30,
        limit: int = 5,
    ) -> list[dict[str, str]]:
        assert user_id == "user@example.com"
        assert days == 30
        assert limit == 5
        return [
            {
                "occurred_at": "2026-07-05T12:00:00+00:00",
                "title": "Visa approved",
                "event_type": "milestone",
                "emotion": "positive",
            },
        ]

    monkeypatch.setattr(service, "get_recent_events", fake_recent_events)

    summary = await service.get_context_summary("user@example.com")

    assert summary.startswith("### Recent Timeline")
    assert "2026-07-05: Visa approved (positive)" in summary
