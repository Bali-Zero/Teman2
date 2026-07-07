from datetime import datetime
from typing import Any

from backend.services.analytics.productivity_scorer import ProductivityScorerService


class FakePool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append((query, args))
        return self.rows


async def test_calculate_productivity_scores_returns_empty_list_for_no_sessions() -> None:
    pool = FakePool([])
    service = ProductivityScorerService(pool)  # type: ignore[arg-type]

    result = await service.calculate_productivity_scores(days=2)

    assert result == []
    query, args = pool.calls[0]
    assert "GROUP BY user_name, user_email" in query
    assert isinstance(args[0], datetime)


async def test_calculate_productivity_scores_skips_zero_hours_and_sorts_by_score() -> None:
    pool = FakePool(
        [
            {
                "user_name": "Bob",
                "user_email": "bob@example.com",
                "total_minutes": 60,
                "total_conversations": 1,
                "total_activities": 6,
                "session_count": 1,
            },
            {
                "user_name": "Alice",
                "user_email": "alice@example.com",
                "total_minutes": 240,
                "total_conversations": 20,
                "total_activities": 120,
                "session_count": 1,
            },
            {
                "user_name": "Chen",
                "user_email": "chen@example.com",
                "total_minutes": 0,
                "total_conversations": 99,
                "total_activities": 99,
                "session_count": 1,
            },
        ],
    )
    service = ProductivityScorerService(pool)  # type: ignore[arg-type]

    result = await service.calculate_productivity_scores()

    assert result == [
        {
            "user": "Alice",
            "email": "alice@example.com",
            "productivity_score": 100.0,
            "rating": "Excellent",
            "metrics": {
                "conversations_per_hour": 5.0,
                "activities_per_hour": 30.0,
                "avg_session_hours": 4.0,
                "total_hours": 4.0,
                "sessions": 1,
            },
        },
        {
            "user": "Bob",
            "email": "bob@example.com",
            "productivity_score": 21.5,
            "rating": "Needs Attention",
            "metrics": {
                "conversations_per_hour": 1.0,
                "activities_per_hour": 6.0,
                "avg_session_hours": 1.0,
                "total_hours": 1.0,
                "sessions": 1,
            },
        },
    ]
