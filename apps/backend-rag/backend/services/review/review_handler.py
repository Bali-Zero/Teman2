"""ReviewHandler — high-level Review Gate flow (§8).

Responsibilities:
1. send_review_request(draft) — push cover + caption + primary keyboard
2. process_callback(update) — validate chat_id, decode callback, mutate DB,
   send confirmation, answer the callback query.

Idempotency: approving the same draft twice is a no-op. Rejecting twice
also short-circuits. This is critical because Telegram can retry webhooks.

Authorization: only :class:`TELEGRAM_OWNER_CHAT_ID` can act on review
callbacks. Other users get a silent "not authorized" answer.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from backend.services.review.models import (
    ReviewAction,
    ReviewCallback,
    ReviewCallbackError,
    ReviewRequest,
    build_primary_keyboard,
    build_reject_reason_keyboard,
    decode_callback,
)
from backend.services.review.telegram_adapter import (
    SendResult,
    TelegramReviewAdapter,
)
from backend.services.war_room.models import (
    DraftStatus,
    RejectedBy,
    RejectionReason,
)
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


# Design §8.3: only Zero can act on review callbacks.
DEFAULT_OWNER_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")


@dataclass
class ReviewSendResult:
    ok: bool
    message_id: int | None = None
    error: str | None = None


@dataclass
class CallbackProcessingResult:
    ok: bool
    action: ReviewAction | None = None
    draft_id: UUID | None = None
    new_status: DraftStatus | None = None
    reject_reason: RejectionReason | None = None
    idempotent_noop: bool = False
    error: str | None = None
    unauthorized: bool = False
    ack_text: str = ""
    followup: dict | None = None  # e.g. second-step reject-reason keyboard


class ReviewHandler:
    """Orchestrates send + callback for War Room 2.0 Review Gate."""

    def __init__(
        self,
        repo: WarRoomRepository,
        telegram: TelegramReviewAdapter,
        *,
        owner_chat_id: int | str | None = None,
    ) -> None:
        self.repo = repo
        self.telegram = telegram
        owner = owner_chat_id if owner_chat_id is not None else DEFAULT_OWNER_CHAT_ID
        self.owner_chat_id = str(owner)
        self.logger = logger

    # ── Outbound: send review request ─────────────────────────────────

    async def send_review_request(
        self,
        request: ReviewRequest,
    ) -> ReviewSendResult:
        keyboard = build_primary_keyboard(
            request.draft_id,
            canva_edit_url=request.canva_edit_url,
        )
        caption = request.to_caption()
        sr: SendResult = await self.telegram.send_photo_url(
            chat_id=self.owner_chat_id,
            photo_url=request.cover_image_url,
            caption=caption,
            reply_markup=keyboard,
        )
        if not sr.ok:
            self.logger.warning(
                "review request send failed draft=%s err=%s",
                request.draft_id,
                sr.error,
            )
            return ReviewSendResult(ok=False, error=sr.error)
        return ReviewSendResult(ok=True, message_id=sr.message_id)

    # ── Inbound: process callback ─────────────────────────────────────

    async def process_callback(
        self,
        update: dict[str, Any],
    ) -> CallbackProcessingResult:
        """Handle Telegram webhook payload containing a callback_query.

        Returns a :class:`CallbackProcessingResult` that the router can use
        to decide on the HTTP response. This method always answers the
        callback query (user sees spinner disappear).
        """
        cq = update.get("callback_query") or {}
        callback_query_id = cq.get("id", "")
        data = cq.get("data") or ""
        chat = cq.get("message", {}).get("chat", {})
        from_user = cq.get("from", {})
        incoming_chat_id = str(chat.get("id") or from_user.get("id") or "")
        message_id = cq.get("message", {}).get("message_id")
        username = (
            from_user.get("username")
            or str(from_user.get("id") or "unknown")
        )

        # 1. authorization
        if incoming_chat_id != self.owner_chat_id:
            self.logger.warning(
                "unauthorized review callback from chat=%s user=%s",
                incoming_chat_id,
                username,
            )
            await self._try_answer(
                callback_query_id,
                "Non autorizzato.",
                show_alert=False,
            )
            return CallbackProcessingResult(
                ok=False,
                unauthorized=True,
                error="chat_id mismatch",
            )

        # 2. decode
        try:
            parsed: ReviewCallback = decode_callback(data)
        except ReviewCallbackError as exc:
            await self._try_answer(
                callback_query_id,
                "Callback invalido.",
                show_alert=False,
            )
            return CallbackProcessingResult(
                ok=False,
                error=f"decode: {exc}",
            )

        # 3. dispatch by action
        if parsed.action == ReviewAction.APPROVE:
            return await self._handle_approve(
                parsed, callback_query_id, message_id, username,
            )
        if parsed.action == ReviewAction.EDIT:
            return await self._handle_edit(
                parsed, callback_query_id, username,
            )
        if parsed.action == ReviewAction.REJECT:
            return await self._handle_reject(
                parsed, callback_query_id, message_id, username,
            )

        await self._try_answer(callback_query_id, "Azione sconosciuta.")
        return CallbackProcessingResult(
            ok=False,
            error=f"unknown action: {parsed.action}",
        )

    # ── action handlers ──────────────────────────────────────────────

    async def _handle_approve(
        self,
        parsed: ReviewCallback,
        callback_query_id: str,
        message_id: int | None,
        username: str,
    ) -> CallbackProcessingResult:
        draft = await self.repo.get_draft(parsed.draft_id)
        if draft is None:
            await self._try_answer(callback_query_id, "Bozza non trovata.")
            return CallbackProcessingResult(
                ok=False,
                action=ReviewAction.APPROVE,
                draft_id=parsed.draft_id,
                error="draft not found",
            )

        if draft.status == DraftStatus.APPROVED:
            # idempotent: already approved — answer + remove keyboard anyway
            await self._try_answer(
                callback_query_id, "Già approvata.", show_alert=False,
            )
            if message_id is not None:
                await self._try_clear_keyboard(message_id)
            return CallbackProcessingResult(
                ok=True,
                action=ReviewAction.APPROVE,
                draft_id=parsed.draft_id,
                new_status=DraftStatus.APPROVED,
                idempotent_noop=True,
                ack_text="Già approvata.",
            )

        if draft.status not in (
            DraftStatus.PENDING_REVIEW,
            DraftStatus.RENDERED,
            DraftStatus.DRAFTS,
        ):
            await self._try_answer(
                callback_query_id,
                f"Stato attuale {draft.status.value} non approvabile.",
                show_alert=True,
            )
            return CallbackProcessingResult(
                ok=False,
                action=ReviewAction.APPROVE,
                draft_id=parsed.draft_id,
                error=f"invalid transition from {draft.status.value}",
            )

        await self.repo.update_status(
            parsed.draft_id,
            DraftStatus.APPROVED,
            approved_by=username,
        )
        await self._try_answer(callback_query_id, "✅ Approvata.")
        if message_id is not None:
            await self._try_clear_keyboard(message_id)
        return CallbackProcessingResult(
            ok=True,
            action=ReviewAction.APPROVE,
            draft_id=parsed.draft_id,
            new_status=DraftStatus.APPROVED,
            ack_text="✅ Approvata.",
        )

    async def _handle_edit(
        self,
        parsed: ReviewCallback,
        callback_query_id: str,
        username: str,
    ) -> CallbackProcessingResult:
        # Minimal v1: acknowledge + prompt Zero to reply with the edit hint
        # in a follow-up message. The listener for free-text replies is a
        # separate concern (not part of this sprint — tracked in design §8.1).
        await self._try_answer(
            callback_query_id,
            "Scrivi in chat come modificare la bozza.",
        )
        # In v1 we keep the draft in pending_review until user approves/rejects.
        return CallbackProcessingResult(
            ok=True,
            action=ReviewAction.EDIT,
            draft_id=parsed.draft_id,
            ack_text="Edit request acknowledged.",
        )

    async def _handle_reject(
        self,
        parsed: ReviewCallback,
        callback_query_id: str,
        message_id: int | None,
        username: str,
    ) -> CallbackProcessingResult:
        if parsed.reject_reason is None:
            # first-step: show reason picker keyboard (without touching DB)
            await self._try_answer(
                callback_query_id, "Scegli il motivo del rifiuto.",
            )
            keyboard = build_reject_reason_keyboard(parsed.draft_id)
            if message_id is not None:
                await self.telegram.edit_message_reply_markup(
                    chat_id=self.owner_chat_id,
                    message_id=message_id,
                    reply_markup=keyboard,
                )
            return CallbackProcessingResult(
                ok=True,
                action=ReviewAction.REJECT,
                draft_id=parsed.draft_id,
                followup=keyboard,
                ack_text="Motivo?",
            )

        # second-step: we have a reason — commit the rejection
        draft = await self.repo.get_draft(parsed.draft_id)
        if draft is None:
            await self._try_answer(callback_query_id, "Bozza non trovata.")
            return CallbackProcessingResult(
                ok=False,
                action=ReviewAction.REJECT,
                draft_id=parsed.draft_id,
                error="draft not found",
            )
        if draft.status == DraftStatus.REJECTED:
            await self._try_answer(callback_query_id, "Già rifiutata.")
            if message_id is not None:
                await self._try_clear_keyboard(message_id)
            return CallbackProcessingResult(
                ok=True,
                action=ReviewAction.REJECT,
                draft_id=parsed.draft_id,
                new_status=DraftStatus.REJECTED,
                reject_reason=parsed.reject_reason,
                idempotent_noop=True,
                ack_text="Già rifiutata.",
            )

        await self.repo.update_status(
            parsed.draft_id,
            DraftStatus.REJECTED,
            rejection_reason=parsed.reject_reason.value,
        )
        await self.repo.record_rejection(
            parsed.draft_id,
            parsed.reject_reason,
            RejectedBy.ZERO,
            reason_detail=f"telegram_callback by {username}",
        )
        await self._try_answer(
            callback_query_id,
            f"❌ Rifiutata ({parsed.reject_reason.value}).",
        )
        if message_id is not None:
            await self._try_clear_keyboard(message_id)
        return CallbackProcessingResult(
            ok=True,
            action=ReviewAction.REJECT,
            draft_id=parsed.draft_id,
            new_status=DraftStatus.REJECTED,
            reject_reason=parsed.reject_reason,
            ack_text=f"❌ Rifiutata ({parsed.reject_reason.value}).",
        )

    # ── helpers ──────────────────────────────────────────────────────

    async def _try_answer(
        self,
        callback_query_id: str,
        text: str | None = None,
        *,
        show_alert: bool = False,
    ) -> None:
        if not callback_query_id:
            return
        result = await self.telegram.answer_callback_query(
            callback_query_id=callback_query_id,
            text=text,
            show_alert=show_alert,
        )
        if not result.ok:
            self.logger.debug(
                "answerCallbackQuery failed: %s", result.error,
            )

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
