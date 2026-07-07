from datetime import datetime
from typing import Any

from backend.services.analytics.performance_trend import PerformanceTrendService


class FakePool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append((query, args))
        return self.rows


async def test_analyze_performance_trends_returns_error_when_no_sessions() -> None:
    pool = FakePool([])
    service = PerformanceTrendService(pool)  # type: ignore[arg-type]

    result = await service.analyze_performance_trends("zero@balizero.com", weeks=2)

    assert result == {"error": "No sessions found"}
    assert len(pool.calls) == 1
    query, args = pool.calls[0]
    assert "team_work_sessions" in query
    assert "status = 'completed'" in query
    assert args[0] == "zero@balizero.com"
    assert isinstance(args[1], datetime)


async def test_analyze_performance_trends_aggregates_weeks_and_handles_null_counts() -> None:
    pool = FakePool(
        [
            {
                "session_start": datetime(2025, 1, 6, 9, 0),
                "duration_minutes": 60,
                "conversations_count": 10,
                "activities_count": 4,
            },
            {
                "session_start": datetime(2025, 1, 8, 11, 0),
                "duration_minutes": None,
                "conversations_count": None,
                "activities_count": None,
            },
            {
                "session_start": datetime(2025, 1, 13, 10, 0),
                "duration_minutes": 120,
                "conversations_count": 16,
                "activities_count": 7,
            },
        ],
    )
    service = PerformanceTrendService(pool)  # type: ignore[arg-type]

    result = await service.analyze_performance_trends("team@example.com")

    assert result["weekly_breakdown"] == [
        {
            "week": "2025-W01",
            "hours": 1.0,
            "conversations": 10,
            "activities": 4,
            "sessions": 2,
            "conversations_per_hour": 10.0,
        },
        {
            "week": "2025-W02",
            "hours": 2.0,
            "conversations": 16,
            "activities": 7,
            "sessions": 1,
            "conversations_per_hour": 8.0,
        },
    ]
    assert result["trend"] == {
        "direction": "Increasing",
        "total_weeks_analyzed": 2,
    }
    assert result["averages"] == {
        "hours_per_week": 1.5,
        "conversations_per_week": 13.0,
    }
