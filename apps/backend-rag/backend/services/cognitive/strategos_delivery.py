"""Strategos delivery — Monday morning Telegram send + callback handler.

Flow:
    1. On Monday 09:00 WITA the delivery service picks the latest brief.
    2. Sends HTML message + inline keyboard [Approva][Adjust][Rifiuta].
    3. Callback handler updates ``weekly_strategic_briefs.zero_approval`` +
       ``approved_at`` based on Zero's choice.

Callback format mirrors the Review Gate (Sprint 6) pattern:
    ``strategos:<action>:<brief_id>``

The ``adjust`` action is a lightweight MVP: it just acknowledges the request
so Zero can reply with free-text in the same chat. Wiring the free-text
capture back into the brief is a future sprint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from backend.services.cognitive.models import WeeklyStrategicBrief
from backend.services.cognitive.repository import CognitiveRepository
from backend.services.review.telegram_adapter import (
    SendResult,
    TelegramReviewAdapter,
)

logger = logging.getLogger(__name__)


CALLBACK_PREFIX = "strategos"


class StrategosAction(str, Enum):
    APPROVE = "approve"
    ADJUST = "adjust"
    REJECT = "reject"


class StrategosCallbackError(ValueError):
    pass


@dataclass(frozen=True)
class StrategosCallback:
    action: StrategosAction
    brief_id: UUID


@dataclass
class StrategosDeliverySendResult:
    ok: bool
    brief_id: UUID | None = None
    message_id: int | None = None
    error: str | None = None
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class StrategosCallbackResult:
    ok: bool
    action: StrategosAction | None = None
    brief_id: UUID | None = None
    approved: bool | None = None
    error: str | None = None
    unauthorized: bool = False
    ack_text: str = ""


# ── Encode / decode ───────────────────────────────────────────


def encode_callback(action: StrategosAction, brief_id: UUID) -> str:
    payload = f"{CALLBACK_PREFIX}:{action.value}:{brief_id}"
    if len(payload.encode()) > 64:
        raise StrategosCallbackError(f"callback > 64 bytes: {len(payload)}")
    return payload


def decode_callback(payload: str) -> StrategosCallback:
    if not payload or not isinstance(payload, str):
        raise StrategosCallbackError("empty payload")
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != CALLBACK_PREFIX:
        raise StrategosCallbackError(
            f"not a strategos callback: {payload[:80]}",
        )
    try:
        action = StrategosAction(parts[1])
    except ValueError as exc:
        raise StrategosCallbackError(f"unknown action {parts[1]!r}") from exc
    try:
        brief_id = UUID(parts[2])
    except ValueError as exc:
        raise StrategosCallbackError(f"bad brief_id {parts[2]!r}") from exc
    return StrategosCallback(action=action, brief_id=brief_id)


def build_keyboard(brief_id: UUID) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Approva",
                    "callback_data": encode_callback(
                        StrategosAction.APPROVE, brief_id,
                    ),
                },
                {
                    "text": "✏️ Adjust",
                    "callback_data": encode_callback(
                        StrategosAction.ADJUST, brief_id,
                    ),
                },
                {
                    "text": "❌ Rifiuta",
                    "callback_data": encode_callback(
                        StrategosAction.REJECT, brief_id,
                    ),
                },
            ]
        ]
    }


# ── Rendering ────────────────────────────────────────────────


def render_brief_message(brief: WeeklyStrategicBrief) -> str:
    lines: list[str] = [
        f"🧠 <b>Strategos — settimana {brief.week_of.isoformat()}</b>",
    ]
    if brief.narrative:
        lines.append("")
        lines.append(_escape_html(brief.narrative[:600]))

    if brief.top_themes:
        lines.append("")
        lines.append("<i>Temi:</i>")
        for theme in brief.top_themes[:5]:
            name = str(theme.get("name") or "?")
            weight = theme.get("weight")
            w_str = f" ({float(weight):.2f})" if weight is not None else ""
            lines.append(f"• {_escape_html(name)}{w_str}")

    if brief.proposed_actions:
        lines.append("")
        lines.append("<i>Azioni:</i>")
        for act in brief.proposed_actions[:6]:
            text = str(act.get("action") or "?")
            owner = act.get("owner")
            deadline = act.get("deadline_days")
            extras: list[str] = []
            if owner:
                extras.append(str(owner))
            if deadline:
                extras.append(f"{deadline}gg")
            extras_s = f" [{', '.join(extras)}]" if extras else ""
            lines.append(f"• {_escape_html(text[:200])}{extras_s}")

    if brief.kpi_targets:
        lines.append("")
        lines.append("<i>KPI:</i>")
        for k, v in list(brief.kpi_targets.items())[:5]:
            lines.append(f"• {_escape_html(str(k))}: {_escape_html(str(v))}")

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


# ── Delivery + callback handler ──────────────────────────────


class StrategosDelivery:
    """Sends the weekly brief to Zero and processes callbacks."""

    def __init__(
        self,
        repo: CognitiveRepository,
        telegram: TelegramReviewAdapter,
        owner_chat_id: str | int,
    ) -> None:
        self.repo = repo
        self.telegram = telegram
        self.owner_chat_id = str(owner_chat_id)
        self.logger = logger

    # ── Send ────────────────────────────────────────────────

    async def send_latest_brief(
        self,
    ) -> StrategosDeliverySendResult:
        try:
            brief = await self.repo.latest_brief()
        except Exception as exc:  # noqa: BLE001
            return StrategosDeliverySendResult(
                ok=False,
                error=f"latest_brief: {type(exc).__name__}: {exc}",
            )
        if brief is None:
            return StrategosDeliverySendResult(
                ok=False,
                skipped=True,
                skip_reason="no_brief_available",
            )
        return await self.send_brief(brief)

    async def send_brief(
        self,
        brief: WeeklyStrategicBrief,
    ) -> StrategosDeliverySendResult:
        if brief.zero_approval is not None:
            return StrategosDeliverySendResult(
                ok=True,
                brief_id=brief.id,
                skipped=True,
                skip_reason="already_decided",
            )
        sr: SendResult = await self.telegram.send_message(
            chat_id=self.owner_chat_id,
            text=render_brief_message(brief),
            reply_markup=build_keyboard(brief.id),
        )
        if not sr.ok:
            return StrategosDeliverySendResult(
                ok=False,
                brief_id=brief.id,
                error=sr.error,
            )
        return StrategosDeliverySendResult(
            ok=True,
            brief_id=brief.id,
            message_id=sr.message_id,
        )

    # ── Callback ────────────────────────────────────────────

    async def process_callback(
        self,
        update: dict[str, Any],
    ) -> StrategosCallbackResult:
        cq = update.get("callback_query") or {}
        callback_query_id = cq.get("id", "")
        data = cq.get("data") or ""
        chat_id = str(
            cq.get("message", {}).get("chat", {}).get("id")
            or cq.get("from", {}).get("id")
            or ""
        )
        message_id = cq.get("message", {}).get("message_id")

        if chat_id != self.owner_chat_id:
            await self._try_answer(callback_query_id, "Non autorizzato.")
            return StrategosCallbackResult(
                ok=False, unauthorized=True, error="chat_id mismatch",
            )

        try:
            parsed = decode_callback(data)
        except StrategosCallbackError as exc:
            await self._try_answer(callback_query_id, "Callback invalido.")
            return StrategosCallbackResult(
                ok=False, error=f"decode: {exc}",
            )

        if parsed.action == StrategosAction.ADJUST:
            # MVP: ack + prompt. Wire free-text capture in a future sprint.
            await self._try_answer(
                callback_query_id,
                "Rispondi in chat con le modifiche richieste.",
            )
            return StrategosCallbackResult(
                ok=True,
                action=StrategosAction.ADJUST,
                brief_id=parsed.brief_id,
                ack_text="Adjust ack.",
            )

        approved = parsed.action == StrategosAction.APPROVE
        try:
            updated = await self.repo.update_brief_approval(
                parsed.brief_id, approved=approved,
            )
        except Exception as exc:  # noqa: BLE001
            await self._try_answer(
                callback_query_id, "Errore DB — riprova.",
            )
            return StrategosCallbackResult(
                ok=False,
                action=parsed.action,
                brief_id=parsed.brief_id,
                error=f"update: {type(exc).__name__}: {exc}",
            )
        if updated is None:
            await self._try_answer(
                callback_query_id, "Brief non trovato.",
            )
            return StrategosCallbackResult(
                ok=False,
                action=parsed.action,
                brief_id=parsed.brief_id,
                error="brief_not_found",
            )

        ack = "✅ Approvato." if approved else "❌ Rifiutato."
        await self._try_answer(callback_query_id, ack)
        if message_id is not None:
            await self._try_clear_keyboard(message_id)
        return StrategosCallbackResult(
            ok=True,
            action=parsed.action,
            brief_id=parsed.brief_id,
            approved=approved,
            ack_text=ack,
        )

    # ── Telegram helpers ────────────────────────────────────

    async def _try_answer(
        self, callback_query_id: str, text: str,
    ) -> None:
        if not callback_query_id:
            return
        result = await self.telegram.answer_callback_query(
            callback_query_id=callback_query_id, text=text,
        )
        if not result.ok:
            self.logger.debug("answer_callback_query failed: %s", result.error)

    async def _try_clear_keyboard(self, message_id: int) -> None:
        result = await self.telegram.edit_message_reply_markup(
            chat_id=self.owner_chat_id,
            message_id=message_id,
            reply_markup=None,
        )
        if not result.ok:
            self.logger.debug(
                "clear keyboard failed: %s", result.error,
            )
