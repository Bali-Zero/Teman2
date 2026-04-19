"""AnomalyAlerter — Telegram notifier for high/critical ComplianceAlerts.

Reference: design §17.2 + §24 (Rischi + mitigazioni — alert flood → daily digest).

Triggered by cognitive_event payload ``event_type=alert_INSERT``. We pull
the full alert from the repo (event payload is intentionally thin), check
severity, send Telegram, mark ``notified_zero=TRUE`` to avoid re-alerting.

Severity policy:
    - critical → 🚨 immediate alert, show_alert=True on callback if any
    - high     → ⚠️ alert
    - medium/low → silent (visible only via dashboard)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timezone
from typing import Any
from uuid import UUID

from backend.services.cognitive.models import AlertSeverity, ComplianceAlert
from backend.services.cognitive.repository import CognitiveRepository
from backend.services.review.telegram_adapter import TelegramReviewAdapter

logger = logging.getLogger(__name__)


@dataclass
class AnomalyAlertSendResult:
    alert_id: UUID | None
    severity: AlertSeverity | None
    sent: bool
    skipped: bool = False
    skip_reason: str = ""
    error: str | None = None


ALERT_ICONS: dict[AlertSeverity, str] = {
    AlertSeverity.CRITICAL: "🚨",
    AlertSeverity.HIGH: "⚠️",
    AlertSeverity.MEDIUM: "ℹ️",
    AlertSeverity.LOW: "·",
}


class AnomalyAlerter:
    """Event handler: pg_notify payload → Telegram alert → mark notified."""

    def __init__(
        self,
        repo: CognitiveRepository,
        telegram: TelegramReviewAdapter,
        owner_chat_id: str | int,
        *,
        min_severity: AlertSeverity = AlertSeverity.HIGH,
    ) -> None:
        self.repo = repo
        self.telegram = telegram
        self.owner_chat_id = str(owner_chat_id)
        self.min_severity = min_severity
        self.logger = logger

    # ── Public API (EventBus handler) ──────────────────────────

    async def handle_event(
        self,
        payload: dict[str, Any],
    ) -> AnomalyAlertSendResult:
        if payload.get("event_type") != "alert_INSERT":
            return AnomalyAlertSendResult(
                alert_id=None, severity=None, sent=False,
                skipped=True, skip_reason="not_alert_insert",
            )

        alert_id_raw = payload.get("alert_id")
        if not alert_id_raw:
            return AnomalyAlertSendResult(
                alert_id=None, severity=None, sent=False,
                skipped=True, skip_reason="missing_alert_id",
            )
        try:
            alert_id = UUID(str(alert_id_raw))
        except (TypeError, ValueError):
            return AnomalyAlertSendResult(
                alert_id=None, severity=None, sent=False,
                skipped=True, skip_reason="bad_alert_id",
            )

        alert = await self._load_alert(alert_id)
        if alert is None:
            return AnomalyAlertSendResult(
                alert_id=alert_id, severity=None, sent=False,
                skipped=True, skip_reason="alert_not_found",
            )
        return await self._dispatch(alert)

    # ── Manual drive (used by tests / backfill) ────────────────

    async def send_for_alert(
        self, alert: ComplianceAlert,
    ) -> AnomalyAlertSendResult:
        return await self._dispatch(alert)

    # ── Internals ──────────────────────────────────────────────

    async def _load_alert(
        self, alert_id: UUID,
    ) -> ComplianceAlert | None:
        rows = await self.repo.fetch_safe(
            """
            SELECT * FROM wr_anomaly_alerts WHERE id = $1 LIMIT 1;
            """,
            alert_id,
        )
        if not rows:
            return None
        from backend.services.cognitive.repository import _row_to_alert

        return _row_to_alert(rows[0])

    async def _dispatch(
        self, alert: ComplianceAlert,
    ) -> AnomalyAlertSendResult:
        if alert.notified_zero:
            return AnomalyAlertSendResult(
                alert_id=alert.id,
                severity=alert.severity,
                sent=False,
                skipped=True,
                skip_reason="already_notified",
            )
        if _severity_rank(alert.severity) < _severity_rank(self.min_severity):
            return AnomalyAlertSendResult(
                alert_id=alert.id,
                severity=alert.severity,
                sent=False,
                skipped=True,
                skip_reason="below_min_severity",
            )

        text = _render(alert)
        sr = await self.telegram.send_message(
            chat_id=self.owner_chat_id,
            text=text,
        )
        if not sr.ok:
            return AnomalyAlertSendResult(
                alert_id=alert.id,
                severity=alert.severity,
                sent=False,
                error=sr.error,
            )

        try:
            await self.repo.mark_alert_notified(alert.id)
        except Exception as exc:  # noqa: BLE001
            # Telegram already sent. Log, but don't flip the flag.
            self.logger.warning(
                "mark_alert_notified failed alert=%s: %s", alert.id, exc,
            )
            return AnomalyAlertSendResult(
                alert_id=alert.id,
                severity=alert.severity,
                sent=True,
                error=f"mark_notified: {exc}",
            )
        return AnomalyAlertSendResult(
            alert_id=alert.id,
            severity=alert.severity,
            sent=True,
        )


# ── rendering ──────────────────────────────────────────────────


def _render(alert: ComplianceAlert) -> str:
    icon = ALERT_ICONS.get(alert.severity, "·")
    detected = alert.detected_at.astimezone(timezone.utc).strftime(
        "%Y-%m-%d %H:%M"
    )
    lines = [
        f"{icon} <b>Anomalia compliance — {alert.severity.value}</b>",
        f"<i>Tipo:</i> {_escape_html(alert.contradiction_type)}",
        f"<i>Dossier A:</i> <code>{alert.dossier_a_id}</code>",
        f"<i>Dossier B:</i> <code>{alert.dossier_b_id}</code>",
        f"<i>Rilevata:</i> {detected}Z",
    ]
    if alert.suggested_action:
        lines.append("")
        lines.append(
            f"<i>Azione suggerita:</i> {_escape_html(alert.suggested_action[:400])}"
        )
    if alert.affected_client_query:
        lines.append(
            f"<i>Segmento impattato:</i> {_escape_html(alert.affected_client_query[:200])}"
        )
    return "\n".join(lines)


def _escape_html(value: str) -> str:
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _severity_rank(s: AlertSeverity) -> int:
    from backend.services.cognitive.anomaly_detector import _SEVERITY_ORDER

    return _SEVERITY_ORDER[s]
