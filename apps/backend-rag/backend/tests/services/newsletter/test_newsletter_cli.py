"""Tests for newsletter_cli — recipients default fallback + --daily arg parsing.

2026-07-14: NEWSLETTER_RECIPIENTS was never set in prod, so the cron always
skipped with "no_recipients" (permanent no-op). These tests pin the fix:
a default internal recipient, and the new --daily dispatch flag.

2026-08-07: also covers the daily-digest idempotency guard. Confirmed live
that day: the legacy Pro LaunchAgent (disarmed the same day, but HOME-fork
drift — scar family #1 — can silently reload a plist) and the in-process
``daily_task.py`` loop both call ``_run_daily`` for the same UTC calendar
day, ~5.5h apart, with neither ``build_daily`` nor ``send_daily_digest``
de-duplicating. These tests pin: a second same-day invocation skips
(logged, exit 2, no send attempted); the first invocation of the day still
sends normally.
"""

from __future__ import annotations

import os
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.newsletter.newsletter_cli import (
    DEFAULT_RECIPIENT,
    _already_sent_today,
    _mark_sent_today,
    _parse_args,
    _recipients_from_env,
    _run_daily,
)


@pytest.fixture(autouse=True)
def _clean_env():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("NEWSLETTER_RECIPIENTS", None)
        os.environ.pop("NEWSLETTER_SUBJECT_PREFIX", None)
        yield


def test_recipients_default_to_internal_owner_when_unset():
    assert _recipients_from_env() == [DEFAULT_RECIPIENT]


def test_recipients_default_is_balizero_domain():
    assert DEFAULT_RECIPIENT.endswith("@balizero.com")


def test_recipients_env_overrides_default():
    os.environ["NEWSLETTER_RECIPIENTS"] = "a@balizero.com,b@balizero.com"
    assert _recipients_from_env() == ["a@balizero.com", "b@balizero.com"]


def test_recipients_env_whitespace_only_falls_back_to_default():
    os.environ["NEWSLETTER_RECIPIENTS"] = "   ,  ,"
    assert _recipients_from_env() == [DEFAULT_RECIPIENT]


def test_recipients_env_trims_whitespace():
    os.environ["NEWSLETTER_RECIPIENTS"] = " a@balizero.com , b@balizero.com "
    assert _recipients_from_env() == ["a@balizero.com", "b@balizero.com"]


# ── --daily flag ─────────────────────────────────────────────────


def test_parse_args_defaults_to_weekly():
    args = _parse_args([])
    assert args.daily is False
    assert args.subject_prefix == ""


def test_parse_args_daily_flag():
    args = _parse_args(["--daily"])
    assert args.daily is True


def test_parse_args_subject_prefix_flag():
    args = _parse_args(["--daily", "--subject-prefix", "[TEST] "])
    assert args.subject_prefix == "[TEST] "


def test_parse_args_subject_prefix_from_env():
    os.environ["NEWSLETTER_SUBJECT_PREFIX"] = "[TEST] "
    args = _parse_args(["--daily"])
    assert args.subject_prefix == "[TEST] "


# ── idempotency guard (2026-08-07) ──────────────────────────────────


def _fetchrow_pool(row: dict | None) -> AsyncMock:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=row)
    return pool


@pytest.mark.asyncio
async def test_already_sent_today_true_when_stored_day_matches():
    pool = _fetchrow_pool({"value": '{"day": "2026-08-07"}'})
    assert await _already_sent_today(pool, date(2026, 8, 7)) is True


@pytest.mark.asyncio
async def test_already_sent_today_false_when_stored_day_differs():
    # Innocence: yesterday's claim must not block today's send.
    pool = _fetchrow_pool({"value": '{"day": "2026-08-06"}'})
    assert await _already_sent_today(pool, date(2026, 8, 7)) is False


@pytest.mark.asyncio
async def test_already_sent_today_false_when_no_row():
    pool = _fetchrow_pool(None)
    assert await _already_sent_today(pool, date(2026, 8, 7)) is False


@pytest.mark.asyncio
async def test_already_sent_today_false_on_malformed_value():
    pool = _fetchrow_pool({"value": "not-json"})
    assert await _already_sent_today(pool, date(2026, 8, 7)) is False


@pytest.mark.asyncio
async def test_already_sent_today_fails_open_on_db_error():
    # Scar family #8: a transient read failure must not starve a real send.
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(side_effect=RuntimeError("connection lost"))
    assert await _already_sent_today(pool, date(2026, 8, 7)) is False


@pytest.mark.asyncio
async def test_mark_sent_today_wins_claim_when_row_returned():
    # First claim of the day: UPDATE/INSERT affects a row, RETURNING yields it.
    pool = _fetchrow_pool({"value": '{"day": "2026-08-07"}'})
    assert await _mark_sent_today(pool, date(2026, 8, 7)) is True


@pytest.mark.asyncio
async def test_mark_sent_today_loses_claim_when_no_row_returned():
    # Guilt: a second claim for the same already-stored day hits the WHERE
    # guard (value IS DISTINCT FROM EXCLUDED.value is false) — no row back.
    pool = _fetchrow_pool(None)
    assert await _mark_sent_today(pool, date(2026, 8, 7)) is False


@pytest.mark.asyncio
async def test_mark_sent_today_fails_open_on_db_error():
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(side_effect=RuntimeError("connection lost"))
    assert await _mark_sent_today(pool, date(2026, 8, 7)) is True


# ── _run_daily end-to-end: second-same-day skip vs first-of-day pass ──


def _content(*, day: date, empty: bool = False):
    content = MagicMock()
    content.day = day
    content.is_empty = empty
    content.items = [] if empty else [MagicMock()]
    content.scarce = False
    return content


def _send_result(*, day: date, sent: int = 1, skipped: bool = False, reason: str = ""):
    result = MagicMock()
    result.day = day
    result.recipients_attempted = sent
    result.recipients_sent = sent
    result.recipients_failed = 0
    result.subject = "Bali Zero Daily · test"
    result.skipped = skipped
    result.skip_reason = reason
    return result


@pytest.mark.asyncio
async def test_run_daily_second_invocation_same_day_skips_without_sending():
    """Guilt case: already_sent_today=True → _run_daily must not build/send."""
    pool = AsyncMock()
    with (
        patch(
            "backend.services.newsletter.newsletter_cli._already_sent_today",
            AsyncMock(return_value=True),
        ),
        patch("backend.services.newsletter.newsletter_cli.DailyDigestBuilder") as MockBuilder,
        patch("backend.services.newsletter.newsletter_cli.NewsletterPublisher") as MockPublisher,
    ):
        rc = await _run_daily(pool, ["zero@balizero.com"], "")

    assert rc == 2
    MockBuilder.return_value.build_daily.assert_not_called()
    MockPublisher.return_value.send_daily_digest.assert_not_called()


@pytest.mark.asyncio
async def test_run_daily_first_invocation_of_day_sends_normally():
    """Innocence case: already_sent_today=False → _run_daily builds, claims, sends."""
    today = date(2026, 8, 7)
    pool = AsyncMock()
    content = _content(day=today)
    result = _send_result(day=today)

    with (
        patch(
            "backend.services.newsletter.newsletter_cli._already_sent_today",
            AsyncMock(return_value=False),
        ),
        patch(
            "backend.services.newsletter.newsletter_cli._mark_sent_today",
            AsyncMock(return_value=True),
        ) as mock_claim,
        patch("backend.services.newsletter.newsletter_cli.DailyDigestBuilder") as MockBuilder,
        patch("backend.services.newsletter.newsletter_cli.NewsletterPublisher") as MockPublisher,
    ):
        MockBuilder.return_value.build_daily = AsyncMock(return_value=content)
        MockPublisher.return_value.send_daily_digest = AsyncMock(return_value=result)

        rc = await _run_daily(pool, ["zero@balizero.com"], "")

    assert rc == 0
    mock_claim.assert_awaited_once_with(pool, today)
    MockPublisher.return_value.send_daily_digest.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_daily_loses_race_on_claim_skips_send():
    """A concurrent invocation claims the day between the check and the
    claim — _run_daily must still not send (closes the narrower race)."""
    today = date(2026, 8, 7)
    pool = AsyncMock()
    content = _content(day=today)

    with (
        patch(
            "backend.services.newsletter.newsletter_cli._already_sent_today",
            AsyncMock(return_value=False),
        ),
        patch(
            "backend.services.newsletter.newsletter_cli._mark_sent_today",
            AsyncMock(return_value=False),
        ),
        patch("backend.services.newsletter.newsletter_cli.DailyDigestBuilder") as MockBuilder,
        patch("backend.services.newsletter.newsletter_cli.NewsletterPublisher") as MockPublisher,
    ):
        MockBuilder.return_value.build_daily = AsyncMock(return_value=content)

        rc = await _run_daily(pool, ["zero@balizero.com"], "")

    assert rc == 2
    MockPublisher.return_value.send_daily_digest.assert_not_called()


@pytest.mark.asyncio
async def test_run_daily_empty_digest_does_not_claim_the_day():
    """An empty-digest run must not burn the day for a later real attempt."""
    today = date(2026, 8, 7)
    pool = AsyncMock()
    content = _content(day=today, empty=True)
    result = _send_result(day=today, sent=0, skipped=True, reason="empty_digest")

    with (
        patch(
            "backend.services.newsletter.newsletter_cli._already_sent_today",
            AsyncMock(return_value=False),
        ),
        patch(
            "backend.services.newsletter.newsletter_cli._mark_sent_today",
            AsyncMock(return_value=True),
        ) as mock_claim,
        patch("backend.services.newsletter.newsletter_cli.DailyDigestBuilder") as MockBuilder,
        patch("backend.services.newsletter.newsletter_cli.NewsletterPublisher") as MockPublisher,
    ):
        MockBuilder.return_value.build_daily = AsyncMock(return_value=content)
        MockPublisher.return_value.send_daily_digest = AsyncMock(return_value=result)

        rc = await _run_daily(pool, ["zero@balizero.com"], "")

    assert rc == 2
    mock_claim.assert_not_called()
