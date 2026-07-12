from datetime import datetime
from typing import Any

from backend.services.analytics.team_insights import TeamInsightsService


class FakePool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append((query, args))
        return self.rows


async def test_generate_team_insights_returns_error_when_no_sessions() -> None:
    pool = FakePool([])
    service = TeamInsightsService(pool)  # type: ignore[arg-type]

    result = await service.generate_team_insights(days=5)

    assert result == {"error": "No team sessions found"}
    query, args = pool.calls[0]
    assert "team_work_sessions" in query
    assert isinstance(args[0], datetime)


async def test_generate_team_insights_summarizes_team_and_collaboration_windows() -> None:
    pool = FakePool(
        [
            {
                "user_name": "Alice",
                "user_email": "alice@example.com",
                "session_start": datetime(2025, 1, 6, 9, 0),
                "session_end": datetime(2025, 1, 6, 11, 0),
                "duration_minutes": 120,
                "conversations_count": 12,
                "activities_count": 5,
                "start_hour": 9,
                "day_of_week": 1,
            },
            {
                "user_name": "Bob",
                "user_email": "bob@example.com",
                "session_start": datetime(2025, 1, 6, 10, 0),
                "session_end": datetime(2025, 1, 6, 11, 0),
                "duration_minutes": 60,
                "conversations_count": 3,
                "activities_count": 4,
                "start_hour": 10,
                "day_of_week": 1,
            },
        ],
    )
    service = TeamInsightsService(pool)  # type: ignore[arg-type]

    result = await service.generate_team_insights(days=7)

    assert result["team_summary"] == {
        "active_members": 2,
        "total_hours_worked": 3.0,
        "total_conversations": 15,
        "total_activities": 9,
        "avg_hours_per_member": 1.5,
        "avg_conversations_per_member": 7.5,
    }
    assert result["team_health_score"] == 100.0
    assert result["health_rating"] == "Excellent"
    assert result["period_days"] == 7

    windows = result["collaboration_windows"]
    assert [window["hour"] for window in windows] == ["10:00", "11:00"]
    assert all(window["team_members_online"] == 2 for window in windows)
    assert {member for window in windows for member in window["members"]} == {
        "alice@example.com",
        "bob@example.com",
    }
    assert any("Best collaboration time: 10:00" in insight for insight in result["insights"])
