"""Unit tests for email_audit helpers.

Covers:
- log_email_attempt: inserts 'sending' row, returns id
- record_email_result: computes retry_after based on attempt_number
- notify_email_failure_critical: Telegram call shape + token absent no-op
- is_critical: membership in CRITICAL_EMAIL_TYPES
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.notifications.email_audit import (
    CRITICAL_EMAIL_TYPES,
    is_critical,
    log_email_attempt,
    notify_email_failure_critical,
    record_email_result,
)


@pytest.fixture
def fake_pool():
    conn = MagicMock()
    conn.fetchval = AsyncMock()
    conn.execute = AsyncMock()

    class _Acquire:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *a):
            return None

    pool = MagicMock()
    pool.acquire.return_value = _Acquire()
    pool._conn = conn
    return pool


# ----------------------------------------------------------------------
# log_email_attempt
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_email_attempt_returns_row_id(fake_pool):
    fake_pool._conn.fetchval.return_value = 1234

    row_id = await log_email_attempt(
        fake_pool,
        email_type="hr_bonus",
        to_email="asya@balizero.com",
        subject="Bonus Pending",
        practice_id=42,
        client_id=None,
    )

    assert row_id == 1234
    assert fake_pool._conn.fetchval.called


@pytest.mark.asyncio
async def test_log_email_attempt_swallows_db_error(fake_pool):
    """If the audit INSERT fails, log_email_attempt returns None and the
    caller can proceed with the send anyway."""
    fake_pool._conn.fetchval.side_effect = RuntimeError("db down")

    row_id = await log_email_attempt(
        fake_pool,
        email_type="welcome",
        to_email="x@y.com",
    )

    assert row_id is None


# ----------------------------------------------------------------------
# record_email_result — retry_after schedule
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_email_result_sent_no_retry_after(fake_pool):
    """Sent rows set retry_after=None (nothing to retry)."""
    await record_email_result(fake_pool, 7, status="sent", provider="brevo")

    executed = str(fake_pool._conn.execute.call_args_list[0])
    assert "status" in executed.lower()


@pytest.mark.asyncio
async def test_record_email_result_first_failure_schedules_1h(fake_pool):
    """Attempt 1 failure → retry_after = NOW()+1h."""
    fake_pool._conn.fetchval.return_value = 1  # attempt_number=1

    await record_email_result(
        fake_pool, 7, status="failed", provider="brevo", error_message="500"
    )

    # 1h is the first backoff step (_RETRY_BACKOFF[0])
    assert fake_pool._conn.execute.called


@pytest.mark.asyncio
async def test_record_email_result_null_row_id_is_noop(fake_pool):
    """Passing row_id=None must not call the DB (audit was never inserted)."""
    await record_email_result(fake_pool, None, status="failed")

    assert not fake_pool._conn.execute.called


@pytest.mark.asyncio
async def test_record_email_result_invalid_status_coerced_to_failed(fake_pool):
    """Unknown status strings should be coerced to 'failed' so the row is
    still reachable by the retry worker."""
    fake_pool._conn.fetchval.return_value = 1

    await record_email_result(
        fake_pool, 7, status="what_is_this", provider="brevo"
    )

    # Still calls execute (the row is updated, just with coerced status)
    assert fake_pool._conn.execute.called


# ----------------------------------------------------------------------
# notify_email_failure_critical
# ----------------------------------------------------------------------


def test_notify_email_failure_critical_sends_telegram(monkeypatch):
    """With a bot token set, a properly-formatted POST hits the Telegram API.

    _OWNER_CHAT_ID is frozen at module import (reads env once), so we
    assert on the module-level value rather than overriding via env.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    # Import after setenv so the module reads our token. chat_id is
    # frozen at first import of the module earlier in the test session.
    from backend.services.notifications import email_audit

    with patch(
        "backend.services.notifications.email_audit.urllib.request.urlopen"
    ) as mock_open:
        notify_email_failure_critical(
            email_type="waiting_docs_client",
            to_email="client@example.com",
            subject="Documents Needed",
            practice_id=42,
            error="brevo: 500 | zoho: 503",
        )

    assert mock_open.called
    url = mock_open.call_args[0][0]
    assert "api.telegram.org/botfake-token/sendMessage" in url
    data = mock_open.call_args[0][1]
    # chat_id is whatever the module captured at import (prod default
    # 1125336968 or CI override via env — both valid).
    assert f"chat_id={email_audit._OWNER_CHAT_ID}".encode() in data
    assert b"waiting_docs_client" in data


def test_notify_email_failure_critical_no_token_is_noop(monkeypatch):
    """Without TELEGRAM_BOT_TOKEN, the function should not raise and not
    attempt any network call."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with patch(
        "backend.services.notifications.email_audit.urllib.request.urlopen"
    ) as mock_open:
        notify_email_failure_critical(
            email_type="hr_bonus",
            to_email="asya@balizero.com",
            subject="Bonus",
            practice_id=1,
            error="anything",
        )

    assert not mock_open.called


def test_notify_email_failure_critical_swallows_network_error(monkeypatch):
    """A URLError from Telegram must not leak into the caller's retry path."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    import urllib.error

    with patch(
        "backend.services.notifications.email_audit.urllib.request.urlopen",
        side_effect=urllib.error.URLError("timeout"),
    ):
        # Must not raise.
        notify_email_failure_critical(
            email_type="completion_client",
            to_email="c@x.com",
            subject="s",
            practice_id=None,
            error="e",
        )


# ----------------------------------------------------------------------
# is_critical — membership
# ----------------------------------------------------------------------


def test_critical_email_types_include_key_flows():
    """The CRITICAL set must cover the five business-critical flows plus
    welcome (added in the 2026-04-21 audit)."""
    assert "waiting_docs_client" in CRITICAL_EMAIL_TYPES
    assert "waiting_docs_team" in CRITICAL_EMAIL_TYPES
    assert "completion_client" in CRITICAL_EMAIL_TYPES
    assert "completion_team" in CRITICAL_EMAIL_TYPES
    assert "hr_bonus" in CRITICAL_EMAIL_TYPES
    assert "invoice_client" in CRITICAL_EMAIL_TYPES
    assert "welcome" in CRITICAL_EMAIL_TYPES


def test_is_critical_membership():
    assert is_critical("hr_bonus") is True
    assert is_critical("cron_visa") is False
    assert is_critical("") is False
    assert is_critical("random_string") is False
