from datetime import datetime
from typing import Any

from backend.services.analytics.pattern_analyzer import PatternAnalyzerService


class FakePool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append((query, args))
        return self.rows


async def test_analyze_work_patterns_returns_error_when_no_sessions() -> None:
    pool = FakePool([])
    service = PatternAnalyzerService(pool)  # type: ignore[arg-type]

    result = await service.analyze_work_patterns(user_email="ops@example.com", days=10)

    assert result == {"error": "No sessions found"}
    query, args = pool.calls[0]
    assert "user_email = $1" in query
    assert args[0] == "ops@example.com"
    assert isinstance(args[1], datetime)


async def test_analyze_work_patterns_calculates_consistency_and_day_distribution() -> None:
    pool = FakePool(
        [
            {
                "session_start": datetime(2025, 1, 6, 9, 0),
                "duration_minutes": 240,
                "day_of_week": 1,
                "start_hour": 9,
            },
            {
                "session_start": datetime(2025, 1, 11, 10, 0),
                "duration_minutes": 300,
                "day_of_week": 6,
                "start_hour": 10,
            },
        ],
    )
    service = PatternAnalyzerService(pool)  # type: ignore[arg-type]

    result = await service.analyze_work_patterns(days=14)

    assert result["patterns"] == {
        "avg_start_hour": 9.5,
        "start_hour_variance": 0.71,
        "preferred_start_time": "09:30",
        "avg_session_duration_hours": 4.5,
        "duration_variance_minutes": 42.4,
    }
    assert result["day_distribution"] == {"weekdays": 1, "weekends": 1}
    assert result["consistency_score"] == 92.9
    assert result["consistency_rating"] == "Excellent"
    assert result["total_sessions_analyzed"] == 2
    assert result["period_days"] == 14

    query, args = pool.calls[0]
    assert "user_email = $1" not in query
    assert len(args) == 1
    assert isinstance(args[0], datetime)
