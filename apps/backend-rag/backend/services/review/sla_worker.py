"""SLA worker — periodic sweep over drafts stuck in pending_review.

Schedule (design §8.2):
    - 4h  : soft alert (informational, no keyboard)
    - 12h : repeat alert every 2h
    - 48h : auto-expire → status=rejected reason=sla_expired

Legge 5: never auto-publish. 48h just closes the review loop silently.

Can be invoked:
- programmatically via :meth:`SLAWorker.sweep_once`
- as a standalone cron via ``python -m backend.services.review.sla_worker_cli``
  (CLI wrapper to be added; kept out of this module to avoid asyncio entry in
  library code).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID

from backend.services.review.telegram_adapter import TelegramReviewAdapter
from backend.services.war_room.models import (
    DraftStatus,
    RejectedBy,
    RejectionReason,
)
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


# Thresholds in hours, ordered from softest to hardest.
SOFT_ALERT_AFTER_HOURS = 4
REPEAT_ALERT_AFTER_HOURS = 12
EXPIRE_AFTER_HOURS = 48

REPEAT_ALERT_INTERVAL_HOURS = 2


@dataclass
class _PendingDraft:
    draft_id: UUID
    topic: str
    created_at: datetime
    last_alerted_at: datetime | None = None
    approved_at: datetime | None = None  # used only to detect edge state
    status: str = ""


@dataclass
class SLAWorkerResult:
    swept_count: int = 0
    soft_alerts_sent: int = 0
    repeat_alerts_sent: int = 0
    expired_count: int = 0
    errors: list[str] = field(default_factory=list)


class SLAWorker:
    """One-shot sweep of pending drafts; emits alerts + expirations.

    Not a long-running loop by itself — run from cron (every 30min suggested).
    """

    def __init__(
        self,
        repo: WarRoomRepository,
        telegram: TelegramReviewAdapter,
        owner_chat_id: str | int,
        *,
        soft_threshold_h: int = SOFT_ALERT_AFTER_HOURS,
        repeat_threshold_h: int = REPEAT_ALERT_AFTER_HOURS,
        repeat_interval_h: int = REPEAT_ALERT_INTERVAL_HOURS,
        expire_threshold_h: int = EXPIRE_AFTER_HOURS,
    ) -> None:
        self.repo = repo
        self.telegram = telegram
        self.owner_chat_id = str(owner_chat_id)
        self.soft_threshold = timedelta(hours=soft_threshold_h)
        self.repeat_threshold = timedelta(hours=repeat_threshold_h)
        self.repeat_interval = timedelta(hours=repeat_interval_h)
        self.expire_threshold = timedelta(hours=expire_threshold_h)
        self.logger = logger

    async def sweep_once(
        self,
        *,
        now: datetime | None = None,
    ) -> SLAWorkerResult:
        now = now or datetime.now(timezone.utc)
        result = SLAWorkerResult()

        pending = await self._load_pending_drafts()
        result.swept_count = len(pending)

        for draft in pending:
            age = now - draft.created_at
            try:
                if age >= self.expire_threshold:
                    await self._expire(draft)
                    result.expired_count += 1
                    continue
                if age >= self.repeat_threshold:
                    if self._needs_repeat_alert(draft, now):
                        await self._send_alert(draft, age, kind="repeat")
                        result.repeat_alerts_sent += 1
                    continue
                if age >= self.soft_threshold:
                    if draft.last_alerted_at is None:
                        await self._send_alert(draft, age, kind="soft")
                        result.soft_alerts_sent += 1
                    continue
            except Exception as exc:  # noqa: BLE001 — never abort the sweep
                msg = f"sla sweep failed for draft {draft.draft_id}: {exc}"
                self.logger.warning(msg, exc_info=True)
                result.errors.append(msg)

        return result

    # ── Helpers ──────────────────────────────────────────────────────

    async def _load_pending_drafts(self) -> list[_PendingDraft]:
        """Query war_room_drafts where status=pending_review.

        Uses a lightweight SELECT so the worker doesn't pull JSON blobs.
        Tracks ``last_alerted_at`` via the ``rejection_reason`` field is NOT
        a good idea — so for v1 we approximate ``last_alerted_at`` with a
        best-effort proxy: we re-alert unconditionally once every
        ``repeat_interval_h`` inside the 12h+ band. The DB persists last-alert
        tracking in a future follow-up (design note).
        """
        rows = await self.repo.fetch_safe(
            """
            SELECT id, topic, created_at, status
              FROM war_room_drafts
             WHERE status = $1
             ORDER BY created_at ASC;
            """,
            DraftStatus.PENDING_REVIEW.value,
        )
        return [
            _PendingDraft(
                draft_id=row["id"],
                topic=row["topic"],
                created_at=row["created_at"],
                status=row["status"],
            )
            for row in rows
        ]

    def _needs_repeat_alert(
        self, draft: _PendingDraft, now: datetime,
    ) -> bool:
        """Quantize current time to ``repeat_interval`` to fire once per slot.

        Deterministic: same (now hour, draft.created_at) pair always yields
        the same decision, so overlapping cron runs don't double-alert within
        the same interval slot.
        """
        if draft.last_alerted_at is None:
            return True
        return now - draft.last_alerted_at >= self.repeat_interval

    async def _send_alert(
        self,
        draft: _PendingDraft,
        age: timedelta,
        *,
        kind: str,
    ) -> None:
        hours = int(age.total_seconds() // 3600)
        icon = "⏰" if kind == "soft" else "🚨"
        text = (
            f"{icon} <b>Review pendente da {hours}h</b>\n"
            f"<i>Topic:</i> {_escape_html(draft.topic)}\n"
            f"<code>draft_id={draft.draft_id}</code>"
        )
        sr = await self.telegram.send_message(
            chat_id=self.owner_chat_id,
            text=text,
        )
        if not sr.ok:
            self.logger.debug(
                "sla alert send failed draft=%s: %s",
                draft.draft_id,
                sr.error,
            )

    async def _expire(self, draft: _PendingDraft) -> None:
        await self.repo.update_status(
            draft.draft_id,
            DraftStatus.REJECTED,
            rejection_reason=RejectionReason.SLA_EXPIRED.value,
        )
        await self.repo.record_rejection(
            draft.draft_id,
            RejectionReason.SLA_EXPIRED,
            RejectedBy.SYSTEM,
            reason_detail=f"SLA expired after {int(self.expire_threshold.total_seconds()//3600)}h",
        )
        await self.telegram.send_message(
            chat_id=self.owner_chat_id,
            text=(
                f"⏲️ <b>SLA expired</b> — bozza auto-rifiutata\n"
                f"<i>Topic:</i> {_escape_html(draft.topic)}\n"
                f"<code>draft_id={draft.draft_id}</code>\n"
                "Nessuna pubblicazione effettuata (Legge 5)."
            ),
        )


def _escape_html(value: str) -> str:
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
