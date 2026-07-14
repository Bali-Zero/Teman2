"""Tests for the in-process newsletter daily-digest trigger.

Covers the pure wall-clock scheduling math (before/at/after the target
minute — the recurring off-by-one class of bug for "next occurrence of
HH:MM" logic) and the kill switch, without needing a live DB pool or event
loop lifetime.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.newsletter.daily_task import (
    _persist_state,
    _seconds_until_next_utc_target,
    start_newsletter_daily_task,
)


def test_seconds_until_next_utc_target_before_target_today() -> None:
    now = datetime(2026, 7, 15, 5, 0, 0, tzinfo=timezone.utc)  # 05:00 UTC
    seconds = _seconds_until_next_utc_target(8, 0, now=now)
    assert seconds == 3 * 3600  # 08:00 UTC same day, 3h away


def test_seconds_until_next_utc_target_after_target_today_rolls_to_tomorrow() -> None:
    now = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)  # 12:00 UTC
    seconds = _seconds_until_next_utc_target(8, 0, now=now)
    assert seconds == 20 * 3600  # 08:00 UTC tomorrow, 20h away


def test_seconds_until_next_utc_target_exactly_at_target_rolls_to_tomorrow() -> None:
    # `<=` in the implementation: firing exactly at boundary should not
    # re-fire immediately (would double-send on a same-second restart).
    now = datetime(2026, 7, 15, 0, 0, 0, tzinfo=timezone.utc)
    seconds = _seconds_until_next_utc_target(0, 0, now=now)
    assert seconds == 24 * 3600


def test_seconds_until_next_utc_target_default_08_wita_is_midnight_utc() -> None:
    now = datetime(2026, 7, 15, 23, 59, 0, tzinfo=timezone.utc)
    seconds = _seconds_until_next_utc_target(0, 0, now=now)
    assert seconds == 60  # 1 minute to midnight UTC == 08:00 WITA


def test_start_newsletter_daily_task_respects_kill_switch() -> None:
    with patch.dict("os.environ", {"NEWSLETTER_DAILY_TASK_ENABLED": "false"}):
        task = start_newsletter_daily_task(db_pool=None)
    assert task is None


@pytest.mark.asyncio
async def test_persist_state_noop_without_db_pool() -> None:
    # Must not raise when db_pool is None (boot-time race / degraded start),
    # and must not attempt any query.
    db_pool = AsyncMock()
    await _persist_state(None, {"ok": True})
    db_pool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_persist_state_swallows_db_errors() -> None:
    # The loop must survive a broken pool (scar family #8) — persistence
    # failures are logged, never raised.
    db_pool = AsyncMock()
    db_pool.execute.side_effect = RuntimeError("connection lost")
    await _persist_state(db_pool, {"ok": True})
    db_pool.execute.assert_awaited_once()
