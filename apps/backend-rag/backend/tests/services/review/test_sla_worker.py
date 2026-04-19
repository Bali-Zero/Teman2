"""Tests for SLAWorker — threshold math, never-auto-publish, alert cadence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from backend.services.review.sla_worker import (
    EXPIRE_AFTER_HOURS,
    REPEAT_ALERT_AFTER_HOURS,
    SOFT_ALERT_AFTER_HOURS,
    SLAWorker,
)
from backend.services.review.telegram_adapter import SendResult
from backend.services.war_room.models import (
    DraftStatus,
    RejectedBy,
    RejectionReason,
)

OWNER = "1125336968"


def _draft_row(hours_ago: float, draft_id: UUID | None = None) -> dict:
    return {
        "id": draft_id or uuid4(),
        "topic": "B211A extension",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        "status": DraftStatus.PENDING_REVIEW.value,
    }


@pytest.fixture
def repo_and_tg():
    repo = AsyncMock()
    repo.fetch_safe = AsyncMock(return_value=[])
    repo.update_status = AsyncMock()
    repo.record_rejection = AsyncMock()

    tg = AsyncMock()
    tg.send_message = AsyncMock(return_value=SendResult(ok=True, message_id=1))
    return repo, tg


def _worker(repo, tg) -> SLAWorker:
    return SLAWorker(repo=repo, telegram=tg, owner_chat_id=OWNER)


# ── Thresholds ────────────────────────────────────────────────────


def test_design_thresholds_are_four_twelve_fortyeight():
    assert SOFT_ALERT_AFTER_HOURS == 4
    assert REPEAT_ALERT_AFTER_HOURS == 12
    assert EXPIRE_AFTER_HOURS == 48


# ── Sweep behaviour ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sweep_empty_list_nothing_happens(repo_and_tg):
    repo, tg = repo_and_tg
    worker = _worker(repo, tg)
    result = await worker.sweep_once()
    assert result.swept_count == 0
    assert result.soft_alerts_sent == 0
    assert result.expired_count == 0
    tg.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_ignores_drafts_younger_than_soft(repo_and_tg):
    repo, tg = repo_and_tg
    repo.fetch_safe = AsyncMock(return_value=[_draft_row(hours_ago=2.0)])
    worker = _worker(repo, tg)
    result = await worker.sweep_once()
    assert result.swept_count == 1
    assert result.soft_alerts_sent == 0
    assert result.expired_count == 0
    tg.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_sweep_emits_soft_alert_between_4h_and_12h(repo_and_tg):
    repo, tg = repo_and_tg
    repo.fetch_safe = AsyncMock(return_value=[_draft_row(hours_ago=6.0)])
    worker = _worker(repo, tg)
    result = await worker.sweep_once()
    assert result.soft_alerts_sent == 1
    tg.send_message.assert_awaited_once()
    text = tg.send_message.call_args.kwargs["text"]
    assert "Review pendente" in text
    assert "⏰" in text


@pytest.mark.asyncio
async def test_sweep_repeat_alert_above_12h(repo_and_tg):
    repo, tg = repo_and_tg
    repo.fetch_safe = AsyncMock(return_value=[_draft_row(hours_ago=14.0)])
    worker = _worker(repo, tg)
    result = await worker.sweep_once()
    assert result.repeat_alerts_sent == 1
    text = tg.send_message.call_args.kwargs["text"]
    assert "🚨" in text


@pytest.mark.asyncio
async def test_sweep_auto_expires_above_48h_never_publishes(repo_and_tg):
    repo, tg = repo_and_tg
    repo.fetch_safe = AsyncMock(return_value=[_draft_row(hours_ago=50.0)])
    worker = _worker(repo, tg)
    result = await worker.sweep_once()

    assert result.expired_count == 1
    # update_status called with REJECTED (not APPROVED → Legge 5 respected)
    repo.update_status.assert_awaited_once()
    args = repo.update_status.call_args
    assert args.args[1] == DraftStatus.REJECTED
    assert args.kwargs["rejection_reason"] == RejectionReason.SLA_EXPIRED.value
    # rejection recorded with RejectedBy.SYSTEM
    repo.record_rejection.assert_awaited_once()
    rej_args = repo.record_rejection.call_args
    assert rej_args.args[1] == RejectionReason.SLA_EXPIRED
    assert rej_args.args[2] == RejectedBy.SYSTEM
    # Telegram notification of expiration was sent
    tg.send_message.assert_awaited_once()
    text = tg.send_message.call_args.kwargs["text"]
    assert "SLA expired" in text
    assert "Legge 5" in text


@pytest.mark.asyncio
async def test_sweep_handles_mixed_bucket(repo_and_tg):
    repo, tg = repo_and_tg
    repo.fetch_safe = AsyncMock(return_value=[
        _draft_row(hours_ago=1.0),     # ignored
        _draft_row(hours_ago=5.0),     # soft
        _draft_row(hours_ago=15.0),    # repeat
        _draft_row(hours_ago=60.0),    # expired
    ])
    worker = _worker(repo, tg)
    result = await worker.sweep_once()
    assert result.swept_count == 4
    assert result.soft_alerts_sent == 1
    assert result.repeat_alerts_sent == 1
    assert result.expired_count == 1


@pytest.mark.asyncio
async def test_sweep_error_on_one_draft_does_not_abort(repo_and_tg):
    repo, tg = repo_and_tg
    repo.fetch_safe = AsyncMock(return_value=[
        _draft_row(hours_ago=50.0),
        _draft_row(hours_ago=55.0),
    ])
    repo.update_status = AsyncMock(
        side_effect=[Exception("boom"), None],
    )
    worker = _worker(repo, tg)
    result = await worker.sweep_once()
    assert result.swept_count == 2
    # one errored, one expired
    assert result.expired_count == 1
    assert len(result.errors) == 1


@pytest.mark.asyncio
async def test_sweep_handles_telegram_failure_gracefully(repo_and_tg):
    repo, tg = repo_and_tg
    repo.fetch_safe = AsyncMock(return_value=[_draft_row(hours_ago=6.0)])
    tg.send_message = AsyncMock(
        return_value=SendResult(ok=False, error="chat not found"),
    )
    worker = _worker(repo, tg)
    result = await worker.sweep_once()
    # sweep still counts soft_alerts_sent=1; telegram failure is logged but
    # does not fail the sweep (Law 4 Graceful degradation).
    assert result.soft_alerts_sent == 1
    assert result.errors == []
