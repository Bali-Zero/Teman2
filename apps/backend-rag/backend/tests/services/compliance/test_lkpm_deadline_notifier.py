"""
Tests for backend.services.compliance.lkpm_deadline_notifier

27 tests covering:
- _compute_days_until_deadline (6)
- _format_deadline (5)
- _first_name_from_email (5)
- Kill switch (3)
- Scan and classify / email dispatch (5)
- Telegram alert (3)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

import backend.services.compliance.lkpm_deadline_notifier as mod
from backend.services.compliance.lkpm_deadline_notifier import (
    ADMIN_EMAIL,
    KILLSWITCH_KEY,
    TAX_CONSULTANT_MANAGER,
    TAX_CONSULTANTS_NON_MANAGER,
    TELEGRAM_URGENCY_DAYS,
    LKPMDeadlineNotifier,
    _compute_days_until_deadline,
    _first_name_from_email,
    _format_deadline,
)


# =====================================================================
# Helpers
# =====================================================================


def _row(
    rid: int = 1,
    quarter: str = "Q1",
    year: int = 2026,
    status: str = "draft",
    lkpm_assigned_to: str | None = None,
    company_name: str = "PT Test",
    oss_username: str = "test_oss",
) -> dict:
    return {
        "id": rid,
        "client_id": rid * 100,
        "quarter": quarter,
        "year": year,
        "status": status,
        "oss_submitted": False,
        "lkpm_assigned_to": lkpm_assigned_to,
        "company_name": company_name,
        "oss_username": oss_username,
    }


class _FakeRecord(dict):
    """Mimics asyncpg.Record: supports record["key"], dict(record), and iteration."""

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _make_pool(
    killswitch_value: str | None,
    pending_rows: list[dict] | None = None,
) -> AsyncMock:
    """Build a mock pool for LKPMDeadlineNotifier tests."""
    pool = AsyncMock()
    conn = AsyncMock()

    async def fake_fetchval(sql, *args):
        if KILLSWITCH_KEY in sql:
            return killswitch_value
        return None

    async def fake_fetch(sql, *args):
        if "FROM lkpm_reports" in sql:
            return [_FakeRecord(r) for r in (pending_rows or [])]
        return []

    conn.fetchval = fake_fetchval
    conn.fetch = fake_fetch

    acq = AsyncMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acq)

    return pool


# Frozen datetime for deterministic tests
FROZEN_NOW = datetime(2026, 4, 7, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Freeze datetime.now to 2026-04-07 09:00 UTC."""

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return FROZEN_NOW

    monkeypatch.setattr(mod, "datetime", _FrozenDatetime)
    return FROZEN_NOW


async def _async_none(*args, **kwargs):
    return None


# =====================================================================
# TestComputeDaysUntilDeadline
# =====================================================================


class TestComputeDaysUntilDeadline:
    """6 tests for _compute_days_until_deadline."""

    def test_on_deadline_returns_zero(self) -> None:
        # Q1 2026 deadline = April 15
        now = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert _compute_days_until_deadline("Q1", 2026, now) == 0

    def test_eight_days_before(self) -> None:
        now = datetime(2026, 4, 7, 9, 0, 0, tzinfo=timezone.utc)
        assert _compute_days_until_deadline("Q1", 2026, now) == 8

    def test_one_day_after(self) -> None:
        now = datetime(2026, 4, 16, 9, 0, 0, tzinfo=timezone.utc)
        assert _compute_days_until_deadline("Q1", 2026, now) == -1

    def test_q4_next_year(self) -> None:
        # Q4 2025 deadline = January 15, 2026
        now = datetime(2026, 1, 10, 0, 0, 0, tzinfo=timezone.utc)
        assert _compute_days_until_deadline("Q4", 2025, now) == 5

    def test_unknown_quarter_returns_none(self) -> None:
        now = datetime(2026, 4, 7, 0, 0, 0, tzinfo=timezone.utc)
        assert _compute_days_until_deadline("Q5", 2026, now) is None

    def test_day_boundary_hours_dont_matter(self) -> None:
        now_morning = datetime(2026, 4, 7, 1, 0, 0, tzinfo=timezone.utc)
        now_evening = datetime(2026, 4, 7, 23, 59, 0, tzinfo=timezone.utc)
        assert _compute_days_until_deadline("Q1", 2026, now_morning) == \
            _compute_days_until_deadline("Q1", 2026, now_evening)


# =====================================================================
# TestFormatDeadline
# =====================================================================


class TestFormatDeadline:
    """5 tests for _format_deadline."""

    def test_q1(self) -> None:
        assert _format_deadline("Q1", 2026) == "15/04/2026"

    def test_q2(self) -> None:
        assert _format_deadline("Q2", 2026) == "15/07/2026"

    def test_q3(self) -> None:
        assert _format_deadline("Q3", 2026) == "15/10/2026"

    def test_q4_uses_next_year(self) -> None:
        assert _format_deadline("Q4", 2025) == "15/01/2026"

    def test_unknown_quarter(self) -> None:
        assert _format_deadline("Q5", 2026) == "\u2014"


# =====================================================================
# TestFirstNameFromEmail
# =====================================================================


class TestFirstNameFromEmail:
    """5 tests for _first_name_from_email."""

    def test_veronika(self) -> None:
        assert _first_name_from_email("veronika.tax@balizero.com") == "Veronika"

    def test_kadek(self) -> None:
        assert _first_name_from_email("kadek.tax@balizero.com") == "Kadek"

    def test_dewaayu(self) -> None:
        assert _first_name_from_email("dewaayu.tax@balizero.com") == "Dewa Ayu"

    def test_angel(self) -> None:
        assert _first_name_from_email("angel.tax@balizero.com") == "Angel"

    def test_faisha(self) -> None:
        assert _first_name_from_email("faisha.tax@balizero.com") == "Faisha"


# =====================================================================
# TestKillSwitch
# =====================================================================


class TestKillSwitch:
    """3 tests for kill switch behavior."""

    async def test_null_blocks(self, frozen_now: datetime) -> None:
        pool = _make_pool(killswitch_value=None)
        notifier = LKPMDeadlineNotifier(pool)
        result = await notifier.check_and_notify()
        assert result["status"] == "blocked"
        assert result["reason"] == "awaiting_owner_approval"

    async def test_false_blocks(self, frozen_now: datetime) -> None:
        pool = _make_pool(killswitch_value="false")
        notifier = LKPMDeadlineNotifier(pool)
        result = await notifier.check_and_notify()
        assert result["status"] == "blocked"

    async def test_true_runs_scan(self, frozen_now: datetime, monkeypatch: pytest.MonkeyPatch) -> None:
        pool = _make_pool(killswitch_value="true", pending_rows=[])
        notifier = LKPMDeadlineNotifier(pool)
        result = await notifier.check_and_notify()
        assert result["status"] == "ok"
        assert result["emails_sent"] == 0


# =====================================================================
# TestScanAndClassify
# =====================================================================


class TestScanAndClassify:
    """5 tests for scan, classify, and email dispatch."""

    async def test_single_assigned_draft_sends_email(
        self, frozen_now: datetime, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [_row(1, "Q1", 2026, "draft", "kadek.tax@balizero.com", "PT Tes")]
        pool = _make_pool("true", rows)
        notifier = LKPMDeadlineNotifier(pool)

        sent_emails: list[dict] = []

        async def fake_post_email(self_, to, subject, html_body, cc=None):
            sent_emails.append({"to": to, "cc": cc, "subject": subject})

        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_post_email", fake_post_email
        )
        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_send_telegram_alert",
            lambda *a, **kw: _async_none(),
        )

        result = await notifier.check_and_notify()
        assert result["emails_sent"] == 1
        assert sent_emails[0]["to"] == "kadek.tax@balizero.com"
        assert sent_emails[0]["cc"] == ADMIN_EMAIL

    async def test_overdue_silently_skipped(
        self, frozen_now: datetime, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Q4 2024 deadline was Jan 15 2025 -- well past frozen_now (2026-04-07)
        rows = [_row(2, "Q4", 2024, "draft", "kadek.tax@balizero.com")]
        pool = _make_pool("true", rows)
        notifier = LKPMDeadlineNotifier(pool)

        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_post_email",
            lambda *a, **kw: _async_none(),
        )

        result = await notifier.check_and_notify()
        assert result["emails_sent"] == 0

    async def test_unassigned_mass_email(
        self, frozen_now: datetime, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [_row(3, "Q1", 2026, "draft", None, "PT Unassigned")]
        pool = _make_pool("true", rows)
        notifier = LKPMDeadlineNotifier(pool)

        sent_emails: list[dict] = []

        async def fake_post_email(self_, to, subject, html_body, cc=None):
            sent_emails.append({"to": to, "cc": cc, "subject": subject})

        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_post_email", fake_post_email
        )
        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_send_telegram_alert",
            lambda *a, **kw: _async_none(),
        )

        result = await notifier.check_and_notify()
        assert result["emails_sent"] == 1
        # TO = 4 non-manager consultants
        to = sent_emails[0]["to"]
        for consultant in TAX_CONSULTANTS_NON_MANAGER:
            assert consultant in to
        # CC = manager + admin
        cc = sent_emails[0]["cc"]
        assert TAX_CONSULTANT_MANAGER in cc
        assert ADMIN_EMAIL in cc

    async def test_grouping_by_assignee(
        self, frozen_now: datetime, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [
            _row(4, "Q1", 2026, "draft", "kadek.tax@balizero.com", "PT A"),
            _row(5, "Q1", 2026, "draft", "angel.tax@balizero.com", "PT B"),
            _row(6, "Q1", 2026, "draft", "kadek.tax@balizero.com", "PT C"),
        ]
        pool = _make_pool("true", rows)
        notifier = LKPMDeadlineNotifier(pool)

        sent_emails: list[dict] = []

        async def fake_post_email(self_, to, subject, html_body, cc=None):
            sent_emails.append({"to": to, "cc": cc})

        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_post_email", fake_post_email
        )
        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_send_telegram_alert",
            lambda *a, **kw: _async_none(),
        )

        result = await notifier.check_and_notify()
        # 2 emails: one for kadek (2 reports), one for angel (1 report)
        assert result["emails_sent"] == 2

    async def test_query_filters_deleted_clients(self) -> None:
        """Verify the SQL query includes c.deleted_at IS NULL."""
        assert "c.deleted_at IS NULL" in mod._PENDING_QUERY


# =====================================================================
# TestTelegramAlert
# =====================================================================


class TestTelegramAlert:
    """3 tests for Telegram alert logic."""

    async def test_eight_days_no_trigger(
        self, frozen_now: datetime, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Q1 2026 deadline is April 15, frozen_now is April 7 -> 8 days
        rows = [_row(7, "Q1", 2026, "draft", "kadek.tax@balizero.com")]
        pool = _make_pool("true", rows)
        notifier = LKPMDeadlineNotifier(pool)

        telegram_calls: list[Any] = []

        async def fake_send_telegram(self_, urgent):
            telegram_calls.append(urgent)

        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_post_email",
            lambda *a, **kw: _async_none(),
        )
        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_send_telegram_alert", fake_send_telegram
        )

        result = await notifier.check_and_notify()
        assert result["telegram_sent"] is False
        assert len(telegram_calls) == 0

    async def test_three_days_triggers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Freeze time to April 12 -> 3 days until deadline
        close_now = datetime(2026, 4, 12, 9, 0, 0, tzinfo=timezone.utc)

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return close_now

        monkeypatch.setattr(mod, "datetime", _FrozenDatetime)

        rows = [_row(8, "Q1", 2026, "draft", "kadek.tax@balizero.com")]
        pool = _make_pool("true", rows)
        notifier = LKPMDeadlineNotifier(pool)

        telegram_calls: list[Any] = []

        async def fake_send_telegram(self_, urgent):
            telegram_calls.append(urgent)

        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_post_email",
            lambda *a, **kw: _async_none(),
        )
        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_send_telegram_alert", fake_send_telegram
        )

        result = await notifier.check_and_notify()
        assert result["telegram_sent"] is True
        assert len(telegram_calls) == 1

    async def test_validated_status_never_triggers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Even close to deadline, status='validated' (not 'draft') shouldn't trigger TG
        close_now = datetime(2026, 4, 12, 9, 0, 0, tzinfo=timezone.utc)

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return close_now

        monkeypatch.setattr(mod, "datetime", _FrozenDatetime)

        rows = [_row(9, "Q1", 2026, "validated", "kadek.tax@balizero.com")]
        pool = _make_pool("true", rows)
        notifier = LKPMDeadlineNotifier(pool)

        telegram_calls: list[Any] = []

        async def fake_send_telegram(self_, urgent):
            telegram_calls.append(urgent)

        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_post_email",
            lambda *a, **kw: _async_none(),
        )
        monkeypatch.setattr(
            mod.LKPMDeadlineNotifier, "_send_telegram_alert", fake_send_telegram
        )

        result = await notifier.check_and_notify()
        assert result["telegram_sent"] is False
