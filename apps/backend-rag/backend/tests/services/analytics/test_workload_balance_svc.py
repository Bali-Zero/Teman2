from datetime import datetime
from typing import Any

from backend.services.analytics.workload_balance import WorkloadBalanceService


class FakePool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.calls.append((query, args))
        return self.rows


async def test_analyze_workload_balance_returns_error_when_no_sessions() -> None:
    pool = FakePool([])
    service = WorkloadBalanceService(pool)  # type: ignore[arg-type]

    result = await service.analyze_workload_balance(days=3)

    assert result == {"error": "No sessions found"}
    query, args = pool.calls[0]
    assert "GROUP BY user_name, user_email" in query
    assert isinstance(args[0], datetime)


async def test_analyze_workload_balance_calculates_distribution_and_recommendations() -> None:
    pool = FakePool(
        [
            {
                "user_name": "Alice",
                "user_email": "alice@example.com",
                "total_minutes": 360,
                "total_conversations": 30,
                "session_count": 2,
            },
            {
                "user_name": "Bob",
                "user_email": "bob@example.com",
                "total_minutes": 180,
                "total_conversations": 10,
                "session_count": 1,
            },
            {
                "user_name": "Chen",
                "user_email": "chen@example.com",
                "total_minutes": 0,
                "total_conversations": None,
                "session_count": 1,
            },
        ],
    )
    service = WorkloadBalanceService(pool)  # type: ignore[arg-type]

    result = await service.analyze_workload_balance()

    assert result["team_distribution"] == [
        {
            "user": "Alice",
            "email": "alice@example.com",
            "hours": 6.0,
            "conversations": 30,
            "sessions": 2,
            "hours_share_percent": 66.7,
            "conversations_share_percent": 75.0,
            "deviation_from_ideal": 3.0,
        },
        {
            "user": "Bob",
            "email": "bob@example.com",
            "hours": 3.0,
            "conversations": 10,
            "sessions": 1,
            "hours_share_percent": 33.3,
            "conversations_share_percent": 25.0,
            "deviation_from_ideal": 0.0,
        },
        {
            "user": "Chen",
            "email": "chen@example.com",
            "hours": 0.0,
            "conversations": 0,
            "sessions": 1,
            "hours_share_percent": 0.0,
            "conversations_share_percent": 0.0,
            "deviation_from_ideal": -3.0,
        },
    ]
    assert result["balance_metrics"] == {
        "balance_score": 0,
        "balance_rating": "Imbalanced",
        "ideal_hours_per_person": 3.0,
        "total_team_hours": 9.0,
        "team_size": 3,
    }
    assert any("Alice" in item for item in result["recommendations"])
    assert any("Chen" in item for item in result["recommendations"])
