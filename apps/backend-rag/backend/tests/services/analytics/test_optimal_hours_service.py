from datetime import datetime
from typing import Any

from backend.services.analytics.optimal_hours import OptimalHoursService


class FakePool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append((query, args))
        return self.rows


async def test_identify_optimal_hours_returns_error_when_no_sessions() -> None:
    pool = FakePool([])
    service = OptimalHoursService(pool)  # type: ignore[arg-type]

    result = await service.identify_optimal_hours(user_email="team@example.com", days=14)

    assert result == {"error": "No sessions found"}
    query, args = pool.calls[0]
    assert "user_email = $1" in query
    assert args[0] == "team@example.com"
    assert isinstance(args[1], datetime)


async def test_identify_optimal_hours_ranks_productivity_windows() -> None:
    pool = FakePool(
        [
            {"hour": 9, "duration_minutes": 60, "conversations_count": 12},
            {"hour": 9, "duration_minutes": 60, "conversations_count": 6},
            {"hour": 15, "duration_minutes": 30, "conversations_count": 15},
            {"hour": 20, "duration_minutes": 0, "conversations_count": 99},
        ],
    )
    service = OptimalHoursService(pool)  # type: ignore[arg-type]

    result = await service.identify_optimal_hours()

    assert result["optimal_windows"] == [
        {
            "hour": "15:00",
            "conversations_per_hour": 30.0,
            "total_hours_worked": 0.5,
            "total_conversations": 15,
        },
        {
            "hour": "09:00",
            "conversations_per_hour": 9.0,
            "total_hours_worked": 2.0,
            "total_conversations": 18,
        },
        {
            "hour": "20:00",
            "conversations_per_hour": 0,
            "total_hours_worked": 0.0,
            "total_conversations": 99,
        },
    ]
    assert result["all_hours"] == result["optimal_windows"]
    assert result["recommendation"] == "Most productive: 15:00, 09:00, 20:00"

    query, args = pool.calls[0]
    assert "user_email = $1" not in query
    assert len(args) == 1
    assert isinstance(args[0], datetime)
