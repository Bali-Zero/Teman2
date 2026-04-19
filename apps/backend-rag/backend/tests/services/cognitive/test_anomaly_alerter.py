"""Tests for AnomalyAlerter — severity routing + dedup via notified_zero."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.services.cognitive.anomaly_alerter import AnomalyAlerter, _render
from backend.services.cognitive.models import AlertSeverity, ComplianceAlert
from backend.services.review.telegram_adapter import SendResult


def _alert(
    severity: AlertSeverity = AlertSeverity.HIGH,
    *,
    notified: bool = False,
    suggested: str | None = "Notify PT PMA clients",
) -> ComplianceAlert:
    return ComplianceAlert(
        id=uuid4(),
        detected_at=datetime.now(timezone.utc),
        dossier_a_id=uuid4(),
        dossier_b_id=uuid4(),
        contradiction_type="grace_period_vs_enforcement",
        severity=severity,
        suggested_action=suggested,
        notified_zero=notified,
    )


def _alert_row_from(alert: ComplianceAlert) -> dict:
    return {
        "id": alert.id,
        "detected_at": alert.detected_at,
        "dossier_a_id": alert.dossier_a_id,
        "dossier_b_id": alert.dossier_b_id,
        "contradiction_type": alert.contradiction_type,
        "severity": alert.severity.value,
        "suggested_action": alert.suggested_action,
        "affected_client_query": alert.affected_client_query,
        "notified_zero": alert.notified_zero,
        "resolved": alert.resolved,
        "resolved_at": alert.resolved_at,
    }


@pytest.fixture
def repo_tg():
    repo = AsyncMock()
    repo.fetch_safe = AsyncMock(return_value=[])
    repo.mark_alert_notified = AsyncMock()
    tg = AsyncMock()
    tg.send_message = AsyncMock(
        return_value=SendResult(ok=True, message_id=1),
    )
    return repo, tg


# ── Rendering ──────────────────────────────────────────────


def test_render_critical_alert_has_siren():
    alert = _alert(AlertSeverity.CRITICAL)
    text = _render(alert)
    assert "🚨" in text
    assert "critical" in text
    assert "grace_period_vs_enforcement" in text


def test_render_high_alert_has_warning():
    text = _render(_alert(AlertSeverity.HIGH))
    assert "⚠️" in text


def test_render_includes_suggested_action():
    text = _render(_alert(suggested="Do the thing"))
    assert "Do the thing" in text


def test_render_omits_suggested_when_none():
    text = _render(_alert(suggested=None))
    assert "Azione suggerita" not in text


def test_render_html_escape_contradiction_type():
    alert = _alert()
    alert.contradiction_type = "bad<>&one"
    text = _render(alert)
    assert "&lt;" in text
    assert "&gt;" in text
    assert "&amp;" in text


# ── handle_event routing ───────────────────────────────────


@pytest.mark.asyncio
async def test_handle_ignores_non_alert_event(repo_tg):
    repo, tg = repo_tg
    alerter = AnomalyAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.handle_event({"event_type": "thesis_INSERT"})
    assert result.skipped
    assert result.skip_reason == "not_alert_insert"
    tg.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_handle_missing_alert_id(repo_tg):
    repo, tg = repo_tg
    alerter = AnomalyAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.handle_event({"event_type": "alert_INSERT"})
    assert result.skip_reason == "missing_alert_id"


@pytest.mark.asyncio
async def test_handle_bad_alert_id(repo_tg):
    repo, tg = repo_tg
    alerter = AnomalyAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.handle_event({
        "event_type": "alert_INSERT",
        "alert_id": "not-a-uuid",
    })
    assert result.skip_reason == "bad_alert_id"


@pytest.mark.asyncio
async def test_handle_alert_not_found(repo_tg):
    repo, tg = repo_tg
    repo.fetch_safe = AsyncMock(return_value=[])
    alerter = AnomalyAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.handle_event({
        "event_type": "alert_INSERT",
        "alert_id": str(uuid4()),
    })
    assert result.skip_reason == "alert_not_found"


# ── Severity gating ────────────────────────────────────────


@pytest.mark.asyncio
async def test_below_min_severity_skipped(repo_tg):
    repo, tg = repo_tg
    a = _alert(AlertSeverity.MEDIUM)
    repo.fetch_safe = AsyncMock(return_value=[_alert_row_from(a)])
    alerter = AnomalyAlerter(
        repo=repo, telegram=tg, owner_chat_id="999",
        min_severity=AlertSeverity.HIGH,
    )
    result = await alerter.handle_event({
        "event_type": "alert_INSERT",
        "alert_id": str(a.id),
    })
    assert result.skipped
    assert result.skip_reason == "below_min_severity"
    tg.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_high_severity_sends_telegram_and_marks_notified(repo_tg):
    repo, tg = repo_tg
    a = _alert(AlertSeverity.HIGH)
    repo.fetch_safe = AsyncMock(return_value=[_alert_row_from(a)])
    alerter = AnomalyAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.handle_event({
        "event_type": "alert_INSERT",
        "alert_id": str(a.id),
    })
    assert result.sent is True
    assert result.severity == AlertSeverity.HIGH
    tg.send_message.assert_awaited_once()
    repo.mark_alert_notified.assert_awaited_once_with(a.id)


@pytest.mark.asyncio
async def test_critical_severity_sends_telegram(repo_tg):
    repo, tg = repo_tg
    a = _alert(AlertSeverity.CRITICAL)
    repo.fetch_safe = AsyncMock(return_value=[_alert_row_from(a)])
    alerter = AnomalyAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.handle_event({
        "event_type": "alert_INSERT",
        "alert_id": str(a.id),
    })
    assert result.sent is True
    assert result.severity == AlertSeverity.CRITICAL


# ── Idempotency ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_already_notified_skipped(repo_tg):
    repo, tg = repo_tg
    a = _alert(AlertSeverity.HIGH, notified=True)
    repo.fetch_safe = AsyncMock(return_value=[_alert_row_from(a)])
    alerter = AnomalyAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.handle_event({
        "event_type": "alert_INSERT",
        "alert_id": str(a.id),
    })
    assert result.skipped
    assert result.skip_reason == "already_notified"
    tg.send_message.assert_not_called()
    repo.mark_alert_notified.assert_not_called()


# ── Telegram failures ──────────────────────────────────────


@pytest.mark.asyncio
async def test_telegram_fail_does_not_mark_notified(repo_tg):
    repo, tg = repo_tg
    a = _alert(AlertSeverity.HIGH)
    repo.fetch_safe = AsyncMock(return_value=[_alert_row_from(a)])
    tg.send_message = AsyncMock(
        return_value=SendResult(ok=False, error="chat not found"),
    )
    alerter = AnomalyAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.handle_event({
        "event_type": "alert_INSERT",
        "alert_id": str(a.id),
    })
    assert result.sent is False
    assert "chat not found" in (result.error or "")
    repo.mark_alert_notified.assert_not_called()


@pytest.mark.asyncio
async def test_mark_notified_failure_still_sent(repo_tg):
    repo, tg = repo_tg
    a = _alert(AlertSeverity.HIGH)
    repo.fetch_safe = AsyncMock(return_value=[_alert_row_from(a)])
    repo.mark_alert_notified = AsyncMock(side_effect=RuntimeError("pg"))
    alerter = AnomalyAlerter(repo=repo, telegram=tg, owner_chat_id="999")
    result = await alerter.handle_event({
        "event_type": "alert_INSERT",
        "alert_id": str(a.id),
    })
    assert result.sent is True
    assert "mark_notified" in (result.error or "")
