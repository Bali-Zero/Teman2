"""Unit tests for EmailHealthMonitor.

We mock the db_pool and the Brevo HTTP call; the tests exercise the
phase orchestration logic rather than the actual SQL. The SQL is covered
by the migration 126 schema which ships with its own rollback section.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def monitor(fake_pool):
    from backend.services.notifications.email_health_monitor import EmailHealthMonitor

    return EmailHealthMonitor(fake_pool)


@pytest.fixture
def fake_pool():
    """A pool whose ``acquire()`` returns a connection with stub fetch/execute.

    Each test sets ``conn.fetch.return_value`` / ``conn.fetchval.return_value``
    before calling the monitor method.
    """
    conn = MagicMock()
    conn.fetch = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.execute = AsyncMock()

    class _Acquire:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *a):
            return None

    pool = MagicMock()
    pool.acquire.return_value = _Acquire()
    pool._conn = conn  # expose for assertions
    return pool


# ----------------------------------------------------------------------
# 1. Retry logic
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_skips_when_no_failed_rows(monitor, fake_pool):
    fake_pool._conn.fetch.return_value = []

    stats = await monitor.check_and_retry_failed_emails()

    assert stats == {
        "considered": 0,
        "retried": 0,
        "succeeded": 0,
        "failed_again": 0,
    }


@pytest.mark.asyncio
async def test_retry_claims_row_and_succeeds(monitor, fake_pool):
    """A failed row with retry_after<NOW() and attempt_number<3 is
    claimed, re-sent via Brevo, and marked 'sent' on 200."""
    failed_row = {
        "id": 42,
        "email_type": "waiting_docs_client",
        "to_email": "client@example.com",
        "subject": "Documents Needed",
        "practice_id": 7,
        "client_id": 99,
        "attempt_number": 1,
    }
    fake_pool._conn.fetch.return_value = [failed_row]
    fake_pool._conn.fetchval.return_value = 43  # new audit row id

    with patch(
        "backend.services.notifications.email_health_monitor.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        stats = await monitor.check_and_retry_failed_emails()

    assert stats["considered"] == 1
    assert stats["retried"] == 1
    assert stats["succeeded"] == 1
    assert stats["failed_again"] == 0

    # Verify the retry UPDATE to 'sent' was executed
    sent_update_calls = [
        call for call in fake_pool._conn.execute.call_args_list
        if "status = 'sent'" in str(call)
    ]
    assert sent_update_calls, "expected UPDATE ... status='sent' to run"


@pytest.mark.asyncio
async def test_retry_marks_failed_again_when_brevo_errors(monitor, fake_pool):
    """A retry that still fails leaves a new 'failed' row with a fresh
    retry_after for the *next* attempt."""
    failed_row = {
        "id": 42,
        "email_type": "hr_bonus",
        "to_email": "asya@balizero.com",
        "subject": "HR Bonus Pending",
        "practice_id": 7,
        "client_id": None,
        "attempt_number": 1,
    }
    fake_pool._conn.fetch.return_value = [failed_row]
    fake_pool._conn.fetchval.return_value = 43

    with patch(
        "backend.services.notifications.email_health_monitor.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=RuntimeError("network"))
        mock_client_cls.return_value = mock_client

        stats = await monitor.check_and_retry_failed_emails()

    assert stats["failed_again"] == 1
    assert stats["succeeded"] == 0

    # The UPDATE setting new status='failed' with error_message must have run
    failed_updates = [
        call for call in fake_pool._conn.execute.call_args_list
        if "status = 'failed'" in str(call) and "error_message" in str(call)
    ]
    assert failed_updates, "expected UPDATE to re-mark row 'failed' on retry error"


# ----------------------------------------------------------------------
# 2. Stale detection
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_sending_unsticks_old_rows(monitor, fake_pool):
    """Rows stuck at 'sending' for 10+ min get flipped to 'failed'
    with retry_after=+1h."""
    fake_pool._conn.fetch.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]

    stats = await monitor.check_stale_sendings()

    assert stats == {"unstuck": 3}
    # Verify the UPDATE ran exactly once with the right WHERE clause
    assert fake_pool._conn.fetch.called
    executed_sql = str(fake_pool._conn.fetch.call_args_list[0])
    assert "status = 'failed'" in executed_sql
    assert "stale_sending" in executed_sql
    assert "INTERVAL '1 hour'" in executed_sql


@pytest.mark.asyncio
async def test_stale_sending_no_rows_no_action(monitor, fake_pool):
    fake_pool._conn.fetch.return_value = []

    stats = await monitor.check_stale_sendings()

    assert stats == {"unstuck": 0}


# ----------------------------------------------------------------------
# 3. Escalation
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalate_pages_telegram_and_marks_escalated(monitor, fake_pool):
    """Rows with attempt_number>=3 get consolidated into one Telegram
    message and marked 'escalated' so they're paged once."""
    fake_pool._conn.fetch.return_value = [
        {
            "id": 100,
            "email_type": "invoice_client",
            "to_email": "client1@example.com",
            "subject": "Invoice INV-001",
            "practice_id": 10,
            "client_id": 1,
            "attempt_number": 3,
            "error_message": "brevo: 429 | zoho: unauthorized",
            "created_at": datetime(2026, 4, 21, 8, 0, tzinfo=timezone.utc),
        },
        {
            "id": 101,
            "email_type": "welcome",
            "to_email": "client2@example.com",
            "subject": "Welcome",
            "practice_id": None,
            "client_id": 2,
            "attempt_number": 3,
            "error_message": "timeout",
            "created_at": datetime(2026, 4, 21, 8, 5, tzinfo=timezone.utc),
        },
    ]

    with patch(
        "backend.services.notifications.email_health_monitor._post_telegram"
    ) as mock_tg:
        stats = await monitor.escalate_unrecoverable()

    assert stats == {"escalated": 2}
    assert mock_tg.called
    tg_text = mock_tg.call_args[0][0]
    assert "2 unrecoverable" in tg_text
    assert "client1@example.com" in tg_text
    assert "client2@example.com" in tg_text
    assert "invoice_client" in tg_text


@pytest.mark.asyncio
async def test_escalate_no_unrecoverable_rows_skips_telegram(monitor, fake_pool):
    fake_pool._conn.fetch.return_value = []

    with patch(
        "backend.services.notifications.email_health_monitor._post_telegram"
    ) as mock_tg:
        stats = await monitor.escalate_unrecoverable()

    assert stats == {"escalated": 0}
    assert not mock_tg.called


@pytest.mark.asyncio
async def test_escalate_truncates_to_15_items_in_telegram(monitor, fake_pool):
    """Telegram Markdown messages must stay under the byte cap;
    beyond 15 rows we append a '...and N more' suffix."""
    big_batch = [
        {
            "id": i,
            "email_type": "welcome",
            "to_email": f"c{i}@example.com",
            "subject": "s",
            "practice_id": None,
            "client_id": i,
            "attempt_number": 3,
            "error_message": "e",
            "created_at": datetime(2026, 4, 21, 8, i % 60, tzinfo=timezone.utc),
        }
        for i in range(20)
    ]
    fake_pool._conn.fetch.return_value = big_batch

    with patch(
        "backend.services.notifications.email_health_monitor._post_telegram"
    ) as mock_tg:
        await monitor.escalate_unrecoverable()

    tg_text = mock_tg.call_args[0][0]
    assert "and 5 more" in tg_text


# ----------------------------------------------------------------------
# 4. Daily report — 24h rate-limit
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_report_skips_if_fired_within_24h(monitor, fake_pool):
    """If last_report_utc is 5h ago, skip with reason='fired_within_24h'."""
    recent = (datetime.now(tz=timezone.utc) - timedelta(hours=5)).isoformat()
    fake_pool._conn.fetchval.return_value = recent

    result = await monitor.generate_daily_report()

    assert result == {"report": "skipped", "reason": "fired_within_24h"}


@pytest.mark.asyncio
async def test_daily_report_fires_when_last_report_is_old(monitor, fake_pool):
    """If last_report_utc is 25h ago, the report fires and state is updated."""
    old = (datetime.now(tz=timezone.utc) - timedelta(hours=25)).isoformat()
    fake_pool._conn.fetchval.return_value = old
    fake_pool._conn.fetch.return_value = [
        {"email_type": "welcome", "status": "sent", "n": 12},
        {"email_type": "welcome", "status": "failed", "n": 1},
        {"email_type": "hr_bonus", "status": "sent", "n": 5},
    ]

    with patch(
        "backend.services.notifications.email_health_monitor._post_telegram"
    ) as mock_tg:
        result = await monitor.generate_daily_report()

    assert result["report"] == "sent"
    assert mock_tg.called
    tg_text = mock_tg.call_args[0][0]
    assert "welcome" in tg_text
    assert "sent=12" in tg_text
    assert "failed=1" in tg_text
    assert "🚨" in tg_text  # welcome has failures → alert flag

    # State upsert must have executed
    upsert_calls = [
        call for call in fake_pool._conn.execute.call_args_list
        if "INSERT INTO system_settings" in str(call)
    ]
    assert upsert_calls


@pytest.mark.asyncio
async def test_daily_report_corrupt_state_still_fires(monitor, fake_pool):
    """A malformed last_report_utc value should not prevent the report."""
    fake_pool._conn.fetchval.return_value = "not-an-iso-timestamp"
    fake_pool._conn.fetch.return_value = []

    result = await monitor.generate_daily_report()

    assert result["report"] == "empty_window"


@pytest.mark.asyncio
async def test_daily_report_empty_window_still_marks_state(monitor, fake_pool):
    """When there are no rows, the state still gets stamped so we don't
    re-query on the next cron tick."""
    fake_pool._conn.fetchval.return_value = None
    fake_pool._conn.fetch.return_value = []

    result = await monitor.generate_daily_report()

    assert result == {"report": "empty_window"}
    upsert_calls = [
        call for call in fake_pool._conn.execute.call_args_list
        if "INSERT INTO system_settings" in str(call)
    ]
    assert upsert_calls
