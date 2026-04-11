"""Tests for backend.services.compliance.lkpm_deadline_notifier"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.compliance.lkpm_deadline_notifier import (
    KILLSWITCH_KEY,
    LKPM_DASHBOARD_URL,
    LKPMDeadlineNotifier,
    _compute_days_until_deadline,
    _first_name_from_email,
    _format_deadline,
    _row_color,
    _ROW_COLORS,
    run_lkpm_deadline_notifier_task,
)


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------

class TestComputeDaysUntilDeadline:
    def test_q1_same_year(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=timezone.utc)
        days = _compute_days_until_deadline("Q1", 2026, now)
        # Q1 deadline = April 15 2026, diff = 31 days
        assert days == 31

    def test_q4_next_year(self) -> None:
        now = datetime(2026, 12, 1, tzinfo=timezone.utc)
        days = _compute_days_until_deadline("Q4", 2026, now)
        # Q4 deadline = Jan 15 2027, diff = 45 days
        assert days == 45

    def test_past_deadline(self) -> None:
        now = datetime(2026, 5, 1, tzinfo=timezone.utc)
        days = _compute_days_until_deadline("Q1", 2026, now)
        # Q1 deadline April 15 already past → negative
        assert days is not None
        assert days < 0

    def test_unknown_quarter(self) -> None:
        assert _compute_days_until_deadline("Q5", 2026) is None

    def test_same_day(self) -> None:
        now = datetime(2026, 4, 15, tzinfo=timezone.utc)
        days = _compute_days_until_deadline("Q1", 2026, now)
        assert days == 0

    def test_defaults_to_now(self) -> None:
        # Should not raise when now=None (uses datetime.now)
        result = _compute_days_until_deadline("Q1", 2099)
        assert result is not None


class TestFormatDeadline:
    def test_q1(self) -> None:
        assert _format_deadline("Q1", 2026) == "15/04/2026"

    def test_q2(self) -> None:
        assert _format_deadline("Q2", 2026) == "15/07/2026"

    def test_q3(self) -> None:
        assert _format_deadline("Q3", 2026) == "15/10/2026"

    def test_q4_next_year(self) -> None:
        assert _format_deadline("Q4", 2026) == "15/01/2027"

    def test_unknown_quarter(self) -> None:
        result = _format_deadline("Q5", 2026)
        assert result == "\u2014"  # em dash


class TestFirstNameFromEmail:
    def test_simple(self) -> None:
        assert _first_name_from_email("kadek.tax@balizero.com") == "Kadek"

    def test_dewaayu_special_case(self) -> None:
        assert _first_name_from_email("dewaayu.tax@balizero.com") == "Dewa Ayu"

    def test_single_part(self) -> None:
        assert _first_name_from_email("admin@balizero.com") == "Admin"


class TestRowColor:
    def test_critical(self) -> None:
        assert _row_color(0) == _ROW_COLORS["critical"]
        assert _row_color(1) == _ROW_COLORS["critical"]

    def test_urgent(self) -> None:
        assert _row_color(2) == _ROW_COLORS["urgent"]
        assert _row_color(3) == _ROW_COLORS["urgent"]

    def test_warning(self) -> None:
        assert _row_color(5) == _ROW_COLORS["warning"]
        assert _row_color(7) == _ROW_COLORS["warning"]

    def test_ok(self) -> None:
        assert _row_color(8) == _ROW_COLORS["ok"]
        assert _row_color(30) == _ROW_COLORS["ok"]


# ---------------------------------------------------------------------------
# LKPMDeadlineNotifier — HTML builders
# ---------------------------------------------------------------------------

class TestBuildTableRow:
    def test_basic_row(self) -> None:
        row = {
            "company_name": "PT Acme",
            "oss_username": "acme_oss",
            "status": "draft",
            "days_until_deadline": 5,
        }
        html = LKPMDeadlineNotifier._build_table_row(row)
        assert "PT Acme" in html
        assert "acme_oss" in html
        assert "draft" in html
        assert "5 hari" in html
        # 5 days → warning color
        assert _ROW_COLORS["warning"] in html

    def test_critical_row(self) -> None:
        row = {
            "company_name": "PT Urgent",
            "status": "pending",
            "days_until_deadline": 1,
        }
        html = LKPMDeadlineNotifier._build_table_row(row)
        assert _ROW_COLORS["critical"] in html

    def test_ok_row(self) -> None:
        row = {
            "company_name": "PT Healthy",
            "status": "in_progress",
            "days_until_deadline": 20,
        }
        html = LKPMDeadlineNotifier._build_table_row(row)
        assert _ROW_COLORS["ok"] in html


class TestBuildEmailBody:
    def test_contains_name_and_count(self) -> None:
        notifier = LKPMDeadlineNotifier(db_pool=MagicMock())
        rows = [
            {
                "company_name": "PT A",
                "oss_username": "a",
                "status": "draft",
                "days_until_deadline": 10,
            },
            {
                "company_name": "PT B",
                "oss_username": "b",
                "status": "pending",
                "days_until_deadline": 3,
            },
        ]
        html = notifier._build_email_body("Kadek", rows)
        assert "Kadek" in html
        assert "<strong>2</strong>" in html
        assert "PT A" in html
        assert "PT B" in html
        assert LKPM_DASHBOARD_URL in html


# ---------------------------------------------------------------------------
# LKPMDeadlineNotifier — check_and_notify
# ---------------------------------------------------------------------------

def _make_db_pool(
    killswitch: str = "true",
    pending_rows: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Create a mock db_pool that supports `acquire()` context manager."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=killswitch)
    conn.fetch = AsyncMock(return_value=[MagicMock(**{
        "__iter__": lambda self: iter(pending_rows or []),
        "keys.return_value": [],
    })])
    # Make rows iterable as dicts
    if pending_rows:
        conn.fetch.return_value = [MagicMock(**{k: v for k, v in row.items()}) for row in pending_rows]
        # Simpler: just return the rows directly via side_effect
        async def _fetch_side_effect(query, *args):
            return pending_rows
        conn.fetch.side_effect = _fetch_side_effect

    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


class TestCheckAndNotify:
    @pytest.mark.asyncio
    async def test_blocked_when_killswitch_off(self) -> None:
        pool = _make_db_pool(killswitch="false")
        notifier = LKPMDeadlineNotifier(pool)
        result = await notifier.check_and_notify()
        assert result["status"] == "blocked"
        assert result["reason"] == "awaiting_owner_approval"

    @pytest.mark.asyncio
    async def test_blocked_when_killswitch_none(self) -> None:
        pool = _make_db_pool(killswitch=None)
        notifier = LKPMDeadlineNotifier(pool)
        result = await notifier.check_and_notify()
        assert result["status"] == "blocked"

    @pytest.mark.asyncio
    async def test_ok_when_no_pending(self) -> None:
        pool = _make_db_pool(killswitch="true", pending_rows=[])
        notifier = LKPMDeadlineNotifier(pool)
        with patch.object(notifier, "_get_pending_reports", new_callable=AsyncMock, return_value=[]):
            result = await notifier.check_and_notify()
        assert result["status"] == "ok"
        assert result["emails_sent"] == 0

    @pytest.mark.asyncio
    @patch("backend.services.compliance.lkpm_deadline_notifier.httpx.AsyncClient")
    async def test_sends_assignee_and_unassigned_emails(
        self, mock_client_cls: MagicMock,
    ) -> None:
        now = datetime(2026, 4, 1, tzinfo=timezone.utc)
        rows = [
            {
                "id": 1,
                "client_id": 10,
                "quarter": "Q1",
                "year": 2026,
                "status": "draft",
                "oss_submitted": False,
                "lkpm_assigned_to": "kadek.tax@balizero.com",
                "company_name": "PT Assigned",
                "oss_username": "assigned_oss",
            },
            {
                "id": 2,
                "client_id": 20,
                "quarter": "Q2",
                "year": 2026,
                "status": "pending",
                "oss_submitted": False,
                "lkpm_assigned_to": None,
                "company_name": "PT Unassigned",
                "oss_username": "unassigned_oss",
            },
        ]

        pool = _make_db_pool(killswitch="true", pending_rows=rows)

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_http

        notifier = LKPMDeadlineNotifier(pool)

        with patch.object(notifier, "_maybe_send_telegram", new_callable=AsyncMock, return_value=False):
            with patch("backend.services.compliance.lkpm_deadline_notifier.datetime") as mock_dt:
                mock_dt.now.return_value = now
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                result = await notifier.check_and_notify()

        assert result["status"] == "ok"
        assert result["emails_sent"] >= 1


# ---------------------------------------------------------------------------
# _maybe_send_telegram
# ---------------------------------------------------------------------------

class TestMaybeSendTelegram:
    @pytest.mark.asyncio
    async def test_no_urgent_rows(self) -> None:
        notifier = LKPMDeadlineNotifier(db_pool=MagicMock())
        rows = [{"days_until_deadline": 10, "status": "draft"}]
        result = await notifier._maybe_send_telegram(rows, datetime.now(timezone.utc))
        assert result is False

    @pytest.mark.asyncio
    async def test_urgent_non_draft_skipped(self) -> None:
        notifier = LKPMDeadlineNotifier(db_pool=MagicMock())
        rows = [{"days_until_deadline": 2, "status": "pending"}]
        result = await notifier._maybe_send_telegram(rows, datetime.now(timezone.utc))
        assert result is False

    @pytest.mark.asyncio
    @patch("backend.services.compliance.lkpm_deadline_notifier.LKPMDeadlineNotifier._send_telegram_alert")
    async def test_sends_for_urgent_drafts(self, mock_send: AsyncMock) -> None:
        mock_send.return_value = None
        notifier = LKPMDeadlineNotifier(db_pool=MagicMock())
        rows = [
            {
                "days_until_deadline": 2,
                "status": "draft",
                "company_name": "PT Urgent",
                "quarter": "Q1",
                "year": 2026,
            },
        ]
        result = await notifier._maybe_send_telegram(rows, datetime.now(timezone.utc))
        assert result is True
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("backend.services.compliance.lkpm_deadline_notifier.LKPMDeadlineNotifier._send_telegram_alert")
    async def test_returns_false_on_telegram_error(self, mock_send: AsyncMock) -> None:
        mock_send.side_effect = RuntimeError("Telegram down")
        notifier = LKPMDeadlineNotifier(db_pool=MagicMock())
        rows = [{"days_until_deadline": 1, "status": "draft", "company_name": "X", "quarter": "Q1", "year": 2026}]
        result = await notifier._maybe_send_telegram(rows, datetime.now(timezone.utc))
        assert result is False


# ---------------------------------------------------------------------------
# _post_email
# ---------------------------------------------------------------------------

class TestPostEmail:
    @pytest.mark.asyncio
    async def test_raises_without_client(self) -> None:
        notifier = LKPMDeadlineNotifier(db_pool=MagicMock())
        notifier._client = None
        with pytest.raises(RuntimeError, match="outside HTTP client context"):
            await notifier._post_email(to="a@b.com", subject="test", html_body="<p>hi</p>")

    @pytest.mark.asyncio
    async def test_posts_with_cc(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        notifier = LKPMDeadlineNotifier(db_pool=MagicMock())
        notifier._client = mock_client

        await notifier._post_email(
            to="a@b.com", subject="test", html_body="<p>hi</p>", cc="cc@b.com",
        )
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["cc"] == "cc@b.com"

    @pytest.mark.asyncio
    async def test_posts_without_cc(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        notifier = LKPMDeadlineNotifier(db_pool=MagicMock())
        notifier._client = mock_client

        await notifier._post_email(to="a@b.com", subject="test", html_body="<p>hi</p>")
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "cc" not in payload


# ---------------------------------------------------------------------------
# run_lkpm_deadline_notifier_task (module-level entry point)
# ---------------------------------------------------------------------------

class TestEntryPoint:
    @pytest.mark.asyncio
    @patch(
        "backend.services.compliance.lkpm_deadline_notifier.LKPMDeadlineNotifier.check_and_notify",
        new_callable=AsyncMock,
        return_value={"status": "ok", "emails_sent": 0, "telegram_sent": False},
    )
    async def test_run_task(self, mock_check: AsyncMock) -> None:
        result = await run_lkpm_deadline_notifier_task(db_pool=MagicMock())
        assert result["status"] == "ok"
        mock_check.assert_awaited_once()
