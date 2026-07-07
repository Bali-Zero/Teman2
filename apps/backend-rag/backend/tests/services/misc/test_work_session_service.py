from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.services.misc.work_session_service import WorkSessionService


class FakePool:
    def __init__(
        self,
        *,
        fetchrows: list[dict[str, Any] | None] | None = None,
        fetches: list[list[dict[str, Any]]] | None = None,
    ) -> None:
        self.fetchrows = fetchrows or []
        self.fetches = fetches or []
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        if not self.fetchrows:
            return None
        return self.fetchrows.pop(0)

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        if not self.fetches:
            return []
        return self.fetches.pop(0)

    async def execute(self, query: str, *args: Any) -> None:
        self.executed.append((query, args))


def make_service(tmp_path: Path, pool: FakePool | None = None) -> WorkSessionService:
    service = object.__new__(WorkSessionService)
    service.db_url = "postgresql://example/db"
    service.pool = pool
    service.zero_email = "zero@balizero.com"
    service.data_dir = tmp_path
    service.log_file = tmp_path / "work_sessions_log.jsonl"
    return service


def read_log_events(log_file: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log_file.read_text().splitlines()]


@pytest.mark.asyncio
async def test_start_session_returns_existing_active_session(tmp_path: Path) -> None:
    started_at = datetime(2026, 7, 5, 9, 0, tzinfo=timezone.utc)
    service = make_service(
        tmp_path,
        FakePool(fetchrows=[{"id": "session-1", "session_start": started_at}]),
    )

    result = await service.start_session("user-1", "Ari", "ari@example.com")

    assert result == {
        "status": "already_active",
        "session_id": "session-1",
        "started_at": "2026-07-05T09:00:00+00:00",
    }
    assert not service.log_file.exists()


@pytest.mark.asyncio
async def test_start_session_inserts_logs_and_notifies_zero(tmp_path: Path) -> None:
    started_at = datetime(2026, 7, 5, 9, 30, tzinfo=timezone.utc)
    pool = FakePool(fetchrows=[None, {"id": "session-2", "session_start": started_at}])
    service = make_service(tmp_path, pool)
    notifications: list[tuple[str, str]] = []

    async def fake_notify(subject: str, message: str) -> None:
        notifications.append((subject, message))

    service._notify_zero = fake_notify

    result = await service.start_session("user-2", "Subhi", "subhi@example.com")

    assert result == {
        "status": "started",
        "session_id": "session-2",
        "started_at": "2026-07-05T09:30:00+00:00",
        "user": "Subhi",
    }
    assert notifications[0][0] == "\U0001f7e2 Subhi started work"
    events = read_log_events(service.log_file)
    assert events[0]["event_type"] == "session_start"
    assert events[0]["session_id"] == "session-2"
    assert events[0]["user_email"] == "subhi@example.com"


@pytest.mark.asyncio
async def test_start_session_reports_database_errors(tmp_path: Path) -> None:
    class BrokenPool(FakePool):
        async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
            raise RuntimeError("insert failed")

    service = make_service(tmp_path, BrokenPool())

    assert await service.start_session("user-1", "Ari", "ari@example.com") == {
        "error": "insert failed",
    }


@pytest.mark.asyncio
async def test_update_activity_and_increment_conversations_are_noops_without_pool(
    tmp_path: Path,
) -> None:
    service = make_service(tmp_path, None)

    await service.update_activity("user-1")
    await service.increment_conversations("user-1")

    assert service.pool is None


@pytest.mark.asyncio
async def test_update_activity_and_increment_conversations_execute_updates(tmp_path: Path) -> None:
    pool = FakePool()
    service = make_service(tmp_path, pool)

    await service.update_activity("user-1")
    await service.increment_conversations("user-1")

    assert len(pool.executed) == 2
    assert "activities_count = activities_count + 1" in pool.executed[0][0]
    assert "conversations_count = conversations_count + 1" in pool.executed[1][0]


@pytest.mark.asyncio
async def test_end_session_returns_no_active_session(tmp_path: Path) -> None:
    service = make_service(tmp_path, FakePool(fetchrows=[None]))

    result = await service.end_session("user-1")

    assert result == {"status": "no_active_session", "message": "No active session found"}
    assert not service.log_file.exists()


@pytest.mark.asyncio
async def test_end_session_completes_session_logs_and_notifies_zero(tmp_path: Path) -> None:
    started_at = datetime.now(tz=timezone.utc) - timedelta(minutes=90)
    pool = FakePool(
        fetchrows=[
            {
                "id": "session-3",
                "session_start": started_at,
                "user_name": "Ari",
                "user_email": "ari@example.com",
                "activities_count": 8,
                "conversations_count": 3,
            },
        ],
    )
    service = make_service(tmp_path, pool)
    session_end_notifications: list[dict[str, Any]] = []

    async def fake_notify_session_end(**kwargs: Any) -> None:
        session_end_notifications.append(kwargs)

    service._notify_zero_session_end = fake_notify_session_end

    result = await service.end_session("user-1", notes="handoff complete")

    assert result["status"] == "completed"
    assert result["session_id"] == "session-3"
    assert result["duration_minutes"] in {89, 90, 91}
    assert result["activities"] == 8
    assert result["conversations"] == 3
    assert pool.executed[0][1][1] in {89, 90, 91}
    assert session_end_notifications[0]["notes"] == "handoff complete"
    events = read_log_events(service.log_file)
    assert events[0]["event_type"] == "session_end"
    assert events[0]["duration_minutes"] in {89, 90, 91}


@pytest.mark.asyncio
async def test_get_today_sessions_returns_plain_dicts(tmp_path: Path) -> None:
    pool = FakePool(
        fetches=[
            [
                {
                    "user_name": "Ari",
                    "status": "active",
                    "duration_minutes": None,
                },
            ],
        ],
    )
    service = make_service(tmp_path, pool)

    assert await service.get_today_sessions() == [
        {"user_name": "Ari", "status": "active", "duration_minutes": None},
    ]


@pytest.mark.asyncio
async def test_get_week_summary_aggregates_by_user_and_unique_day(tmp_path: Path) -> None:
    day_one = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
    day_two = datetime(2026, 7, 2, 9, 0, tzinfo=timezone.utc)
    pool = FakePool(
        fetches=[
            [
                {
                    "user_name": "Ari",
                    "user_email": "ari@example.com",
                    "session_start": day_one,
                    "duration_minutes": 120,
                    "conversations_count": 4,
                    "activities_count": 10,
                },
                {
                    "user_name": "Ari",
                    "user_email": "ari@example.com",
                    "session_start": day_two,
                    "duration_minutes": 60,
                    "conversations_count": None,
                    "activities_count": 5,
                },
            ],
        ],
    )
    service = make_service(tmp_path, pool)

    summary = await service.get_week_summary()

    assert summary["total_team_hours"] == 3
    assert len(summary["team_stats"]) == 1
    assert summary["team_stats"][0]["days_worked"] == 2
    assert summary["team_stats"][0]["avg_hours_per_day"] == 1.5
    assert summary["team_stats"][0]["total_conversations"] == 4
    assert summary["team_stats"][0]["total_activities"] == 15


@pytest.mark.asyncio
async def test_generate_daily_report_summarizes_and_persists_report(tmp_path: Path) -> None:
    report_date = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
    pool = FakePool(
        fetches=[
            [
                {
                    "user_name": "Ari",
                    "user_email": "ari@example.com",
                    "session_start": datetime(2026, 7, 5, 9, 0, tzinfo=timezone.utc),
                    "session_end": datetime(2026, 7, 5, 11, 0, tzinfo=timezone.utc),
                    "duration_minutes": 120,
                    "activities_count": 12,
                    "conversations_count": 4,
                    "status": "completed",
                    "notes": "Done",
                },
                {
                    "user_name": "Subhi",
                    "user_email": "subhi@example.com",
                    "session_start": datetime(2026, 7, 5, 10, 0, tzinfo=timezone.utc),
                    "session_end": None,
                    "duration_minutes": None,
                    "activities_count": None,
                    "conversations_count": None,
                    "status": "active",
                    "notes": None,
                },
            ],
        ],
    )
    service = make_service(tmp_path, pool)

    report = await service.generate_daily_report(report_date)

    assert report == {
        "date": "2026-07-05",
        "total_hours": 2.0,
        "total_conversations": 4,
        "team_members_active": 2,
        "team_summary": [
            {
                "name": "Ari",
                "email": "ari@example.com",
                "start": "09:00",
                "end": "11:00",
                "hours": 2.0,
                "conversations": 4,
                "activities": 12,
                "status": "completed",
                "notes": "Done",
            },
            {
                "name": "Subhi",
                "email": "subhi@example.com",
                "start": "10:00",
                "end": "In corso",
                "hours": 0.0,
                "conversations": 0,
                "activities": 0,
                "status": "active",
                "notes": None,
            },
        ],
    }
    assert pool.executed[0][1][0] == report_date.date()
    assert pool.executed[0][1][1] == report
