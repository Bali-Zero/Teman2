"""MissedRunsAlerter — Telegram notifications for unannounced skipped runs.

Design §11.3: if the pipeline was skipped (pro_offline, hard_failure,
no_trend, quota_exceeded) and Zero hasn't been notified, surface a
summary message. Dedup via ``notified_zero`` boolean on the row.

If total pending runs > threshold, we send one aggregate message (avoids
Telegram flood). Each notified row is flipped to ``notified_zero=TRUE``
in a single UPDATE after the send succeeds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.services.review.telegram_adapter import TelegramReviewAdapter
from backend.services.war_room.models import WarRoomMissedRun
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


DEFAULT_LOOKBACK_DAYS = 2
MAX_DETAIL_LINES = 8
AGGREGATE_THRESHOLD = 3


@dataclass
class MissedRunsAlertResult:
    ran_at: datetime
    pending_count: int
    notified_count: int
    message_sent: bool
    error: str | None = None


class MissedRunsAlerter:
    """Send one aggregate Telegram message per sweep, then mark as notified."""

    def __init__(
        self,
        repo: WarRoomRepository,
        telegram: TelegramReviewAdapter,
        owner_chat_id: str | int,
        *,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> None:
        self.repo = repo
        self.telegram = telegram
        self.owner_chat_id = str(owner_chat_id)
        self.lookback_days = lookback_days

    async def sweep_once(
        self,
        *,
        now: datetime | None = None,
    ) -> MissedRunsAlertResult:
        now = now or datetime.now(timezone.utc)
        try:
            pending = await self.repo.pending_missed_runs(days=self.lookback_days)
        except Exception as exc:  # noqa: BLE001
            return MissedRunsAlertResult(
                ran_at=now,
                pending_count=0,
                notified_count=0,
                message_sent=False,
                error=f"fetch: {type(exc).__name__}: {exc}",
            )

        if not pending:
            return MissedRunsAlertResult(
                ran_at=now,
                pending_count=0,
                notified_count=0,
                message_sent=False,
            )

        text = _render(pending)
        sr = await self.telegram.send_message(
            chat_id=self.owner_chat_id,
            text=text,
        )
        if not sr.ok:
            return MissedRunsAlertResult(
                ran_at=now,
                pending_count=len(pending),
                notified_count=0,
                message_sent=False,
                error=sr.error,
            )

        ids = [r.id for r in pending]
        try:
            await self.repo.mark_missed_runs_notified(ids)
        except Exception as exc:  # noqa: BLE001
            # Telegram already sent — next sweep might re-alert for the same
            # ids. Flag the error but count as notified for this run.
            return MissedRunsAlertResult(
                ran_at=now,
                pending_count=len(pending),
                notified_count=0,
                message_sent=True,
                error=f"mark_notified: {type(exc).__name__}: {exc}",
            )

        return MissedRunsAlertResult(
            ran_at=now,
            pending_count=len(pending),
            notified_count=len(ids),
            message_sent=True,
        )


def _render(pending: list[WarRoomMissedRun]) -> str:
    total = len(pending)
    by_reason: dict[str, int] = {}
    for r in pending:
        by_reason[r.skipped_reason.value] = by_reason.get(r.skipped_reason.value, 0) + 1

    lines: list[str] = [
        f"⚠️ <b>War Room — {total} run saltati</b>",
    ]
    for reason, count in sorted(by_reason.items(), key=lambda kv: -kv[1]):
        lines.append(f"• {reason}: {count}")

    # Show up to MAX_DETAIL_LINES individual entries (most recent first).
    lines.append("")
    lines.append("<i>Ultime occorrenze:</i>")
    for run in pending[:MAX_DETAIL_LINES]:
        ts = run.scheduled_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"• <code>{ts}Z</code> — {_escape_html(run.skipped_reason.value)}"
        )
    if total > MAX_DETAIL_LINES:
        lines.append(f"• … e altri {total - MAX_DETAIL_LINES}")

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
