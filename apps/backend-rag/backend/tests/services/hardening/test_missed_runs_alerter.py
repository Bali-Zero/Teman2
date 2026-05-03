"""Tests for MissedRunsAlerter — send once + mark_notified dedup."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.hardening.missed_runs_alerter import (
    MissedRunsAlerter,
    _render,
)
from backend.services.review.telegram_adapter import SendResult
from backend.services.war_room.models import (
    MissedRunReason,
    WarRoomMissedRun,
)


def _run(reason: MissedRunReason, hours_ago: float = 5) -> WarRoomMissedRun:
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    return WarRoomMissedRun(
        id=uuid4(),
        scheduled_at=now - timedelta(hours=hours_ago),
        skipped_reason=reason,
        details_json=None,
        notified_zero=False,
        created_at=now - timedelta(hours=hours_ago),
    )


@pytest.fixture
def repo_tg():
    repo = AsyncMock()
    repo.pending_missed_runs = AsyncMock(return_value=[])
    repo.mark_missed_runs_notified = AsyncMock()
    tg = AsyncMock()
    tg.send_message = AsyncMock(return_value=SendResult(ok=True, message_id=1))
    return repo, tg


@pytest.mark.asyncio
async def test_no_pending_no_alert(repo_tg):
    repo, tg = repo_tg
    alerter = MissedRunsAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.sweep_once()
    assert result.pending_count == 0
    assert result.message_sent is False
    tg.send_message.assert_not_called()
    repo.mark_missed_runs_notified.assert_not_called()


@pytest.mark.asyncio
async def test_single_pending_sends_alert_and_marks(repo_tg):
    repo, tg = repo_tg
    repo.pending_missed_runs = AsyncMock(return_value=[
        _run(MissedRunReason.PRO_OFFLINE),
    ])
    alerter = MissedRunsAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.sweep_once()
    assert result.pending_count == 1
    assert result.message_sent is True
    assert result.notified_count == 1
    repo.mark_missed_runs_notified.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_failure_leaves_rows_unmarked(repo_tg):
    repo, tg = repo_tg
    repo.pending_missed_runs = AsyncMock(return_value=[
        _run(MissedRunReason.HARD_FAILURE),
    ])
    tg.send_message = AsyncMock(return_value=SendResult(
        ok=False, error="chat not found",
    ))
    alerter = MissedRunsAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.sweep_once()
    assert result.message_sent is False
    # marking skipped — we'll retry next sweep
    repo.mark_missed_runs_notified.assert_not_called()
    assert "chat not found" in (result.error or "")


@pytest.mark.asyncio
async def test_mark_notified_failure_still_counted_as_message_sent(repo_tg):
    repo, tg = repo_tg
    repo.pending_missed_runs = AsyncMock(return_value=[
        _run(MissedRunReason.QUOTA_EXCEEDED),
    ])
    repo.mark_missed_runs_notified = AsyncMock(side_effect=RuntimeError("pg"))
    alerter = MissedRunsAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.sweep_once()
    assert result.message_sent is True
    assert result.notified_count == 0
    assert "mark_notified" in (result.error or "")


@pytest.mark.asyncio
async def test_fetch_failure_no_alert(repo_tg):
    repo, tg = repo_tg
    repo.pending_missed_runs = AsyncMock(side_effect=RuntimeError("pg down"))
    alerter = MissedRunsAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.sweep_once()
    assert result.message_sent is False
    assert "fetch" in (result.error or "")
    tg.send_message.assert_not_called()


# ── _render ──────────────────────────────────────────────────


def test_render_groups_by_reason():
    runs = [
        _run(MissedRunReason.PRO_OFFLINE),
        _run(MissedRunReason.PRO_OFFLINE),
        _run(MissedRunReason.HARD_FAILURE),
    ]
    text = _render(runs)
    assert "3 run saltati" in text
    assert "pro_offline: 2" in text
    assert "hard_failure: 1" in text


def test_render_truncates_detail_lines_at_threshold():
    runs = [_run(MissedRunReason.NO_TREND) for _ in range(20)]
    text = _render(runs)
    assert "20 run saltati" in text
    assert "e altri 12" in text  # 20 - 8 shown
