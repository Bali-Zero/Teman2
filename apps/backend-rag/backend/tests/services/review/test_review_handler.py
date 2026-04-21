"""Tests for ReviewHandler — send + callback processing + idempotency + authz."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from backend.services.review.models import (
    ReviewAction,
    ReviewRequest,
    encode_callback,
)
from backend.services.review.review_handler import (
    ReviewHandler,
)
from backend.services.review.telegram_adapter import SendResult
from backend.services.war_room.models import (
    DraftStatus,
    RejectedBy,
    RejectionReason,
    WarRoomDraft,
)

OWNER_CHAT_ID = "1125336968"
DID = UUID("12345678-1234-1234-1234-123456789abc")


def _draft(status: DraftStatus = DraftStatus.PENDING_REVIEW) -> WarRoomDraft:
    now = datetime.now(timezone.utc)
    return WarRoomDraft(
        id=DID,
        topic="B211A extension",
        tone_register=None,
        status=status,
        created_at=now,
        updated_at=now,
    )


def _send_ok(mid: int = 42) -> SendResult:
    return SendResult(ok=True, message_id=mid)


def _update(data: str, chat_id: str = OWNER_CHAT_ID, user: str = "zero",
            message_id: int = 55) -> dict:
    return {
        "callback_query": {
            "id": "cbq-1",
            "data": data,
            "from": {"id": int(chat_id), "username": user},
            "message": {
                "message_id": message_id,
                "chat": {"id": int(chat_id), "type": "private"},
            },
        }
    }


@pytest.fixture
def repo_and_telegram():
    repo = AsyncMock()
    tg = AsyncMock()
    tg.answer_callback_query = AsyncMock(return_value=SendResult(ok=True))
    tg.edit_message_reply_markup = AsyncMock(return_value=SendResult(ok=True))
    tg.send_photo_url = AsyncMock(return_value=_send_ok())
    tg.send_message = AsyncMock(return_value=_send_ok())
    return repo, tg


# ── send_review_request ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_review_request_happy_path(repo_and_telegram):
    repo, tg = repo_and_telegram
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)
    req = ReviewRequest(
        draft_id=DID,
        topic="B211A",
        tone_register="analitico",
        cover_image_url="https://tigris/cover.png",
        first_slide_text="Primo slide",
    )
    result = await handler.send_review_request(req)
    assert result.ok is True
    assert result.message_id == 42
    tg.send_photo_url.assert_awaited_once()
    call_kwargs = tg.send_photo_url.call_args.kwargs
    assert call_kwargs["chat_id"] == OWNER_CHAT_ID
    assert call_kwargs["photo_url"] == "https://tigris/cover.png"
    # primary keyboard
    kb = call_kwargs["reply_markup"]
    assert len(kb["inline_keyboard"][0]) == 3


@pytest.mark.asyncio
async def test_send_review_request_with_canva_url_adds_button(repo_and_telegram):
    """When draft has canva_edit_url, keyboard exposes it as a URL button."""
    repo, tg = repo_and_telegram
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)
    canva_url = "https://www.canva.com/design/DAHE6lx1lf8/edit"
    req = ReviewRequest(
        draft_id=DID,
        topic="B211A",
        tone_register="analitico",
        cover_image_url="https://tigris/cover.png",
        first_slide_text="Primo slide",
        canva_edit_url=canva_url,
    )
    result = await handler.send_review_request(req)
    assert result.ok is True
    kb = tg.send_photo_url.call_args.kwargs["reply_markup"]
    # First row: approve/edit/reject unchanged
    assert len(kb["inline_keyboard"][0]) == 3
    # Second row: Canva URL button
    assert len(kb["inline_keyboard"]) == 2
    canva_btn = kb["inline_keyboard"][1][0]
    assert canva_btn["url"] == canva_url
    assert "Canva" in canva_btn["text"]


@pytest.mark.asyncio
async def test_send_review_request_telegram_fail(repo_and_telegram):
    repo, tg = repo_and_telegram
    tg.send_photo_url = AsyncMock(
        return_value=SendResult(ok=False, error="chat not found"),
    )
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)
    req = ReviewRequest(
        draft_id=DID, topic="t", tone_register="tecnico",
        cover_image_url="https://x/y", first_slide_text="b",
    )
    result = await handler.send_review_request(req)
    assert result.ok is False
    assert "chat not found" in (result.error or "")


# ── process_callback: authorization ─────────────────────────────────

@pytest.mark.asyncio
async def test_callback_rejects_unauthorized_chat(repo_and_telegram):
    repo, tg = repo_and_telegram
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)
    update = _update(
        encode_callback(ReviewAction.APPROVE, DID),
        chat_id="9999",
        user="stranger",
    )
    result = await handler.process_callback(update)
    assert result.ok is False
    assert result.unauthorized is True
    repo.update_status = AsyncMock()  # never called
    repo.update_status.assert_not_called()


@pytest.mark.asyncio
async def test_callback_bad_data_answers_invalid(repo_and_telegram):
    repo, tg = repo_and_telegram
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)
    update = _update("garbage:payload:not-warroom")
    result = await handler.process_callback(update)
    assert result.ok is False
    assert "decode" in (result.error or "")
    tg.answer_callback_query.assert_awaited()


# ── APPROVE ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_callback_approve_happy_path(repo_and_telegram):
    repo, tg = repo_and_telegram
    repo.get_draft = AsyncMock(return_value=_draft(DraftStatus.PENDING_REVIEW))
    repo.update_status = AsyncMock(return_value=_draft(DraftStatus.APPROVED))
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)

    update = _update(encode_callback(ReviewAction.APPROVE, DID))
    result = await handler.process_callback(update)
    assert result.ok is True
    assert result.action == ReviewAction.APPROVE
    assert result.new_status == DraftStatus.APPROVED
    repo.update_status.assert_awaited_once()
    kwargs = repo.update_status.call_args.kwargs
    assert kwargs["approved_by"] == "zero"
    tg.edit_message_reply_markup.assert_awaited()  # keyboard cleared


@pytest.mark.asyncio
async def test_callback_approve_idempotent_on_already_approved(repo_and_telegram):
    repo, tg = repo_and_telegram
    repo.get_draft = AsyncMock(return_value=_draft(DraftStatus.APPROVED))
    repo.update_status = AsyncMock()
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)

    update = _update(encode_callback(ReviewAction.APPROVE, DID))
    result = await handler.process_callback(update)
    assert result.ok is True
    assert result.idempotent_noop is True
    repo.update_status.assert_not_called()


@pytest.mark.asyncio
async def test_callback_approve_missing_draft(repo_and_telegram):
    repo, tg = repo_and_telegram
    repo.get_draft = AsyncMock(return_value=None)
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)

    update = _update(encode_callback(ReviewAction.APPROVE, DID))
    result = await handler.process_callback(update)
    assert result.ok is False
    assert "not found" in (result.error or "")


@pytest.mark.asyncio
async def test_callback_approve_invalid_transition(repo_and_telegram):
    repo, tg = repo_and_telegram
    # cannot approve a published draft
    repo.get_draft = AsyncMock(return_value=_draft(DraftStatus.PUBLISHED))
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)

    update = _update(encode_callback(ReviewAction.APPROVE, DID))
    result = await handler.process_callback(update)
    assert result.ok is False
    assert "invalid transition" in (result.error or "")


# ── EDIT ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_callback_edit_acknowledges_only(repo_and_telegram):
    repo, tg = repo_and_telegram
    repo.update_status = AsyncMock()
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)

    update = _update(encode_callback(ReviewAction.EDIT, DID))
    result = await handler.process_callback(update)
    assert result.ok is True
    assert result.action == ReviewAction.EDIT
    # MVP: edit doesn't mutate status
    repo.update_status.assert_not_called()


# ── REJECT two-step ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_callback_reject_first_step_shows_reason_picker(repo_and_telegram):
    repo, tg = repo_and_telegram
    repo.update_status = AsyncMock()
    repo.record_rejection = AsyncMock()
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)

    update = _update(encode_callback(ReviewAction.REJECT, DID))
    result = await handler.process_callback(update)
    assert result.ok is True
    assert result.followup is not None
    repo.update_status.assert_not_called()
    repo.record_rejection.assert_not_called()
    # reason picker keyboard was sent
    tg.edit_message_reply_markup.assert_awaited()


@pytest.mark.asyncio
async def test_callback_reject_second_step_commits_rejection(repo_and_telegram):
    repo, tg = repo_and_telegram
    repo.get_draft = AsyncMock(return_value=_draft(DraftStatus.PENDING_REVIEW))
    repo.update_status = AsyncMock()
    repo.record_rejection = AsyncMock()
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)

    update = _update(encode_callback(
        ReviewAction.REJECT, DID, RejectionReason.CLICKBAIT,
    ))
    result = await handler.process_callback(update)
    assert result.ok is True
    assert result.new_status == DraftStatus.REJECTED
    assert result.reject_reason == RejectionReason.CLICKBAIT
    repo.update_status.assert_awaited_once()
    repo.record_rejection.assert_awaited_once()
    args = repo.record_rejection.call_args
    assert args.args[1] == RejectionReason.CLICKBAIT
    assert args.args[2] == RejectedBy.ZERO


@pytest.mark.asyncio
async def test_callback_reject_idempotent_on_already_rejected(repo_and_telegram):
    repo, tg = repo_and_telegram
    repo.get_draft = AsyncMock(return_value=_draft(DraftStatus.REJECTED))
    repo.update_status = AsyncMock()
    repo.record_rejection = AsyncMock()
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)

    update = _update(encode_callback(
        ReviewAction.REJECT, DID, RejectionReason.TONE,
    ))
    result = await handler.process_callback(update)
    assert result.idempotent_noop is True
    repo.update_status.assert_not_called()
    repo.record_rejection.assert_not_called()


@pytest.mark.asyncio
async def test_callback_reject_missing_draft(repo_and_telegram):
    repo, tg = repo_and_telegram
    repo.get_draft = AsyncMock(return_value=None)
    handler = ReviewHandler(repo=repo, telegram=tg, owner_chat_id=OWNER_CHAT_ID)

    update = _update(encode_callback(
        ReviewAction.REJECT, DID, RejectionReason.TONE,
    ))
    result = await handler.process_callback(update)
    assert result.ok is False
    assert "not found" in (result.error or "")
