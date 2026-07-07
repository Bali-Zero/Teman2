from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

from backend.services.analytics import weekly_email_reporter
from backend.services.analytics.weekly_email_reporter import WeeklyEmailReporter


async def test_start_creates_scheduler_once_and_stop_cancels_it() -> None:
    pool = object()
    reporter = WeeklyEmailReporter(pool)  # type: ignore[arg-type]

    created_tasks: list[Any] = []

    class FakeTask:
        def __init__(self) -> None:
            self.cancelled = False

        def cancel(self) -> None:
            self.cancelled = True

        def __await__(self) -> Any:
            async def _done() -> None:
                return None

            return _done().__await__()

    fake_task = FakeTask()

    def fake_create_task(coro: Any) -> FakeTask:
        created_tasks.append(coro)
        coro.close()
        return fake_task

    with patch("backend.services.analytics.weekly_email_reporter.asyncio.create_task", fake_create_task):
        await reporter.start()
        await reporter.start()

    assert reporter.running is True
    assert reporter.task is fake_task
    assert created_tasks

    await reporter.stop()

    assert reporter.running is False
    assert fake_task.cancelled is True


def test_init_weekly_reporter_sets_singleton() -> None:
    pool = object()

    reporter = weekly_email_reporter.init_weekly_reporter(pool)  # type: ignore[arg-type]

    assert reporter.pool is pool
    assert weekly_email_reporter.get_weekly_reporter() is reporter


def test_build_html_email_includes_summary_activity_and_inactive_warning() -> None:
    reporter = WeeklyEmailReporter(object())  # type: ignore[arg-type]
    team_activities = [
        {
            "email": "active@example.com",
            "full_name": "Active Member",
            "department": "Ops",
            "activity": {
                "sent": 5,
                "received": 9,
                "read": 0,
                "replied": 2,
                "forwarded": 1,
                "deleted": 0,
                "unread": 3,
            },
        },
        {
            "email": "quiet@example.com",
            "full_name": "Quiet Member",
            "department": "Finance",
            "activity": {
                "sent": 0,
                "received": 1,
                "read": 0,
                "replied": 0,
                "forwarded": 0,
                "deleted": 0,
                "unread": 4,
            },
        },
    ]
    summary = {
        "total_sent": 7,
        "total_received": 10,
        "most_active_user": "active@example.com",
        "most_active_count": 8,
    }

    html = reporter._build_html_email(
        team_activities,
        summary,
        datetime(2026, 7, 5, 16, 0),
    )

    assert "Weekly Email Activity Report" in html
    assert "28 June - 05 July 2026" in html
    assert "Active Member" in html
    assert "Quiet Member" in html
    assert "7" in html
    assert "10" in html
    assert "1/2" in html
    assert "Nessuna attivit" in html


async def test_send_now_delegates_to_send_weekly_report() -> None:
    reporter = WeeklyEmailReporter(object())  # type: ignore[arg-type]
    reporter._send_weekly_report = AsyncMock()  # type: ignore[method-assign]

    await reporter.send_now()

    reporter._send_weekly_report.assert_awaited_once()
