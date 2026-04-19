"""Tests for Strategos Telegram delivery + callback handler."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from backend.services.cognitive.models import WeeklyStrategicBrief
from backend.services.cognitive.strategos_delivery import (
    CALLBACK_PREFIX,
    StrategosAction,
    StrategosCallbackError,
    StrategosDelivery,
    build_keyboard,
    decode_callback,
    encode_callback,
    render_brief_message,
)
from backend.services.review.telegram_adapter import SendResult

DID = UUID("12345678-1234-1234-1234-123456789abc")


def _brief(
    *,
    approved: bool | None = None,
    themes: list | None = None,
    actions: list | None = None,
) -> WeeklyStrategicBrief:
    now = datetime.now(timezone.utc)
    return WeeklyStrategicBrief(
        id=DID,
        week_of=date(2026, 4, 20),
        top_themes=themes or [{"name": "Balance", "weight": 0.5}],
        proposed_actions=actions or [
            {"action": "commissiona 3 analitici", "owner": "war_room", "deadline_days": 5}
        ],
        kpi_targets={"reach_uplift_pct": 20},
        team_assignments={"war_room": "Damar"},
        narrative="Settimana di ribilanciamento",
        generated_at=now,
        zero_approval=approved,
        approved_at=now if approved is not None else None,
    )


# ── Encode / decode ──────────────────────────────────────────


def test_encode_approve():
    payload = encode_callback(StrategosAction.APPROVE, DID)
    assert payload == f"{CALLBACK_PREFIX}:approve:{DID}"


def test_encode_under_64_bytes():
    payload = encode_callback(StrategosAction.ADJUST, DID)
    assert len(payload.encode()) <= 64


def test_decode_roundtrip():
    for action in StrategosAction:
        payload = encode_callback(action, DID)
        parsed = decode_callback(payload)
        assert parsed.action == action
        assert parsed.brief_id == DID


def test_decode_rejects_wrong_prefix():
    with pytest.raises(StrategosCallbackError):
        decode_callback(f"warroom:approve:{DID}")


def test_decode_rejects_bad_action():
    with pytest.raises(StrategosCallbackError):
        decode_callback(f"{CALLBACK_PREFIX}:delete:{DID}")


def test_decode_rejects_bad_uuid():
    with pytest.raises(StrategosCallbackError):
        decode_callback(f"{CALLBACK_PREFIX}:approve:not-a-uuid")


def test_decode_rejects_empty():
    with pytest.raises(StrategosCallbackError):
        decode_callback("")


# ── Keyboard ─────────────────────────────────────────────────


def test_keyboard_has_three_buttons():
    kb = build_keyboard(DID)
    row = kb["inline_keyboard"][0]
    assert len(row) == 3
    actions = [btn["callback_data"].split(":")[1] for btn in row]
    assert actions == ["approve", "adjust", "reject"]


# ── Rendering ────────────────────────────────────────────────


def test_render_includes_week_and_narrative():
    text = render_brief_message(_brief())
    assert "2026-04-20" in text
    assert "ribilanciamento" in text


def test_render_includes_themes_and_actions():
    text = render_brief_message(_brief())
    assert "Balance" in text
    assert "commissiona 3 analitici" in text


def test_render_escapes_html_in_theme_names():
    brief = _brief(themes=[{"name": "<script>alert()</script>"}])
    text = render_brief_message(brief)
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_render_handles_empty_sections():
    brief = _brief(themes=[], actions=[])
    text = render_brief_message(brief)
    # still has header + narrative + kpi
    assert "Strategos" in text


# ── Delivery: send ───────────────────────────────────────────


@pytest.fixture
def repo_tg():
    repo = AsyncMock()
    tg = AsyncMock()
    tg.send_message = AsyncMock(
        return_value=SendResult(ok=True, message_id=42),
    )
    tg.answer_callback_query = AsyncMock(return_value=SendResult(ok=True))
    tg.edit_message_reply_markup = AsyncMock(return_value=SendResult(ok=True))
    return repo, tg


@pytest.mark.asyncio
async def test_send_latest_happy_path(repo_tg):
    repo, tg = repo_tg
    repo.latest_brief = AsyncMock(return_value=_brief())
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.send_latest_brief()
    assert result.ok is True
    assert result.brief_id == DID
    assert result.message_id == 42
    tg.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_latest_skips_when_no_brief(repo_tg):
    repo, tg = repo_tg
    repo.latest_brief = AsyncMock(return_value=None)
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.send_latest_brief()
    assert result.skipped
    assert result.skip_reason == "no_brief_available"


@pytest.mark.asyncio
async def test_send_skips_already_decided_brief(repo_tg):
    repo, tg = repo_tg
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.send_brief(_brief(approved=True))
    assert result.skipped
    assert result.skip_reason == "already_decided"
    tg.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_telegram_failure(repo_tg):
    repo, tg = repo_tg
    tg.send_message = AsyncMock(
        return_value=SendResult(ok=False, error="chat not found"),
    )
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.send_brief(_brief())
    assert result.ok is False
    assert "chat not found" in (result.error or "")


@pytest.mark.asyncio
async def test_send_latest_brief_fetch_failure(repo_tg):
    repo, tg = repo_tg
    repo.latest_brief = AsyncMock(side_effect=RuntimeError("pg down"))
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.send_latest_brief()
    assert result.ok is False
    assert "latest_brief" in (result.error or "")


# ── Delivery: callback ───────────────────────────────────────


def _update(action: StrategosAction, chat_id: str = "999", message_id: int = 100):
    return {
        "callback_query": {
            "id": "cbq-1",
            "data": encode_callback(action, DID),
            "from": {"id": int(chat_id), "username": "zero"},
            "message": {
                "message_id": message_id,
                "chat": {"id": int(chat_id), "type": "private"},
            },
        }
    }


@pytest.mark.asyncio
async def test_callback_rejects_unauthorized_chat(repo_tg):
    repo, tg = repo_tg
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(
        StrategosAction.APPROVE, chat_id="777",
    ))
    assert result.unauthorized is True
    tg.answer_callback_query.assert_awaited()


@pytest.mark.asyncio
async def test_callback_approve_updates_brief(repo_tg):
    repo, tg = repo_tg
    repo.update_brief_approval = AsyncMock(return_value=_brief(approved=True))
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(StrategosAction.APPROVE))
    assert result.ok is True
    assert result.approved is True
    repo.update_brief_approval.assert_awaited_once()
    tg.edit_message_reply_markup.assert_awaited()


@pytest.mark.asyncio
async def test_callback_reject_updates_brief_with_false(repo_tg):
    repo, tg = repo_tg
    repo.update_brief_approval = AsyncMock(return_value=_brief(approved=False))
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(StrategosAction.REJECT))
    assert result.ok is True
    assert result.approved is False
    args = repo.update_brief_approval.await_args
    assert args.kwargs["approved"] is False


@pytest.mark.asyncio
async def test_callback_adjust_is_ack_only(repo_tg):
    repo, tg = repo_tg
    repo.update_brief_approval = AsyncMock()
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(StrategosAction.ADJUST))
    assert result.ok is True
    assert result.action == StrategosAction.ADJUST
    repo.update_brief_approval.assert_not_called()


@pytest.mark.asyncio
async def test_callback_bad_data(repo_tg):
    repo, tg = repo_tg
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    update = {
        "callback_query": {
            "id": "x",
            "data": "garbage:payload",
            "from": {"id": 999},
            "message": {"message_id": 1, "chat": {"id": 999}},
        }
    }
    result = await delivery.process_callback(update)
    assert result.ok is False
    assert "decode" in (result.error or "")


@pytest.mark.asyncio
async def test_callback_missing_brief(repo_tg):
    repo, tg = repo_tg
    repo.update_brief_approval = AsyncMock(return_value=None)
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(StrategosAction.APPROVE))
    assert result.ok is False
    assert "brief_not_found" in (result.error or "")


@pytest.mark.asyncio
async def test_callback_db_failure_gracefully(repo_tg):
    repo, tg = repo_tg
    repo.update_brief_approval = AsyncMock(side_effect=RuntimeError("pg"))
    delivery = StrategosDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(StrategosAction.APPROVE))
    assert result.ok is False
    assert "update" in (result.error or "")
