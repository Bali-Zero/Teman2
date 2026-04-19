"""Oracle delivery — send pending UltraMoves to Zero, handle callbacks.

Each pending move is sent as a standalone message with an inline keyboard:
    [✅ Approva] [❌ Rifiuta] [⏸ Defer]

Callback format: ``oracle:<action>:<move_id>``.

Design §17.4: Oracle NEVER executes. Decisions only update the DB row.
Downstream teams (CRM, War Room, Intel) pick up approved moves from the
``ultra_moves`` table via their own cron / dashboard.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from backend.services.cognitive.models import (
    UltraMove,
    UltraMoveDecision,
)
from backend.services.cognitive.repository import CognitiveRepository
from backend.services.review.telegram_adapter import (
    SendResult,
    TelegramReviewAdapter,
)

logger = logging.getLogger(__name__)


CALLBACK_PREFIX = "oracle"


class OracleAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    DEFER = "defer"


class OracleCallbackError(ValueError):
    pass


@dataclass(frozen=True)
class OracleCallback:
    action: OracleAction
    move_id: UUID


@dataclass
class OracleDeliverySendResult:
    sent_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    move_ids_sent: list[UUID] | None = None
    errors: list[str] | None = None


@dataclass
class OracleCallbackResult:
    ok: bool
    action: OracleAction | None = None
    move_id: UUID | None = None
    decision: UltraMoveDecision | None = None
    unauthorized: bool = False
    error: str | None = None
    ack_text: str = ""


# ── Encode / decode ────────────────────────────────────────


_ACTION_TO_DECISION: dict[OracleAction, UltraMoveDecision] = {
    OracleAction.APPROVE: UltraMoveDecision.APPROVED,
    OracleAction.REJECT: UltraMoveDecision.REJECTED,
    OracleAction.DEFER: UltraMoveDecision.DEFERRED,
}


def encode_callback(action: OracleAction, move_id: UUID) -> str:
    payload = f"{CALLBACK_PREFIX}:{action.value}:{move_id}"
    if len(payload.encode()) > 64:
        raise OracleCallbackError(f"callback > 64 bytes: {len(payload)}")
    return payload


def decode_callback(payload: str) -> OracleCallback:
    if not payload or not isinstance(payload, str):
        raise OracleCallbackError("empty payload")
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != CALLBACK_PREFIX:
        raise OracleCallbackError(
            f"not an oracle callback: {payload[:80]}",
        )
    try:
        action = OracleAction(parts[1])
    except ValueError as exc:
        raise OracleCallbackError(f"unknown action {parts[1]!r}") from exc
    try:
        move_id = UUID(parts[2])
    except ValueError as exc:
        raise OracleCallbackError(f"bad move_id {parts[2]!r}") from exc
    return OracleCallback(action=action, move_id=move_id)


def build_keyboard(move_id: UUID) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Approva",
                    "callback_data": encode_callback(
                        OracleAction.APPROVE, move_id,
                    ),
                },
                {
                    "text": "❌ Rifiuta",
                    "callback_data": encode_callback(
                        OracleAction.REJECT, move_id,
                    ),
                },
                {
                    "text": "⏸ Defer",
                    "callback_data": encode_callback(
                        OracleAction.DEFER, move_id,
                    ),
                },
            ]
        ]
    }


# ── Rendering ──────────────────────────────────────────────


def render_move_message(move: UltraMove) -> str:
    lines = [
        "🔮 <b>Oracle — UltraMove</b>",
        "",
        f"<b>{_escape_html(move.thesis[:280])}</b>",
        "",
        _escape_html(move.narrative[:1200]),
    ]
    extras: list[str] = []
    if move.target_query:
        extras.append(f"<i>Target:</i> {_escape_html(move.target_query[:300])}")
    if move.estimated_cost:
        extras.append(f"<i>Costo stimato:</i> {_escape_html(move.estimated_cost[:300])}")
    if move.estimated_value:
        extras.append(f"<i>Valore stimato:</i> {_escape_html(move.estimated_value[:300])}")
    if move.recommended_tone_register:
        extras.append(
            f"<i>Registro suggerito:</i> {_escape_html(move.recommended_tone_register)}"
        )
    if extras:
        lines.append("")
        lines.extend(extras)
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


# ── Delivery + callback handler ────────────────────────────


class OracleDelivery:
    """Send pending UltraMoves; process callbacks."""

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

    # ── Send ─────────────────────────────────────────────

    async def send_pending(
        self,
    ) -> OracleDeliverySendResult:
        result = OracleDeliverySendResult(
            move_ids_sent=[], errors=[],
        )
        try:
            moves = await self.repo.pending_ultra_moves()
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"fetch_pending: {exc}")
            return result

        for move in moves:
            try:
                sr = await self._send_one(move)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"send {move.id}: {exc}")
                result.failed_count += 1
                continue
            if sr.ok:
                result.sent_count += 1
                result.move_ids_sent.append(move.id)
            else:
                result.failed_count += 1
                result.errors.append(sr.error or "unknown")
        return result

    async def _send_one(self, move: UltraMove) -> SendResult:
        return await self.telegram.send_message(
            chat_id=self.owner_chat_id,
            text=render_move_message(move),
            reply_markup=build_keyboard(move.id),
        )

    # ── Callback ─────────────────────────────────────────

    async def process_callback(
        self,
        update: dict[str, Any],
    ) -> OracleCallbackResult:
        cq = update.get("callback_query") or {}
        callback_query_id = cq.get("id", "")
        data = cq.get("data") or ""
        chat_id = str(
            cq.get("message", {}).get("chat", {}).get("id")
            or cq.get("from", {}).get("id")
            or ""
        )
        message_id = cq.get("message", {}).get("message_id")
        from_user = cq.get("from", {})
        username = (
            from_user.get("username")
            or str(from_user.get("id") or "unknown")
        )

        if chat_id != self.owner_chat_id:
            await self._try_answer(callback_query_id, "Non autorizzato.")
            return OracleCallbackResult(
                ok=False, unauthorized=True, error="chat_id mismatch",
            )

        try:
            parsed = decode_callback(data)
        except OracleCallbackError as exc:
            await self._try_answer(callback_query_id, "Callback invalido.")
            return OracleCallbackResult(ok=False, error=f"decode: {exc}")

        decision = _ACTION_TO_DECISION[parsed.action]
        try:
            updated = await self.repo.update_ultra_move_decision(
                parsed.move_id,
                decision,
                notes=f"via_telegram by {username}",
            )
        except Exception as exc:  # noqa: BLE001
            await self._try_answer(
                callback_query_id, "Errore DB — riprova.",
            )
            return OracleCallbackResult(
                ok=False,
                action=parsed.action,
                move_id=parsed.move_id,
                error=f"update: {type(exc).__name__}: {exc}",
            )
        if updated is None:
            await self._try_answer(
                callback_query_id, "Mossa non trovata.",
            )
            return OracleCallbackResult(
                ok=False,
                action=parsed.action,
                move_id=parsed.move_id,
                error="move_not_found",
            )

        ack = {
            OracleAction.APPROVE: "✅ Approvata.",
            OracleAction.REJECT: "❌ Rifiutata.",
            OracleAction.DEFER: "⏸ Rimandata.",
        }[parsed.action]
        await self._try_answer(callback_query_id, ack)
        if message_id is not None:
            await self._try_clear_keyboard(message_id)
        return OracleCallbackResult(
            ok=True,
            action=parsed.action,
            move_id=parsed.move_id,
            decision=decision,
            ack_text=ack,
        )

    # ── Telegram helpers ─────────────────────────────────

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
