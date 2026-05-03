"""Tests for Oracle delivery — send pending + callback handling."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from backend.services.cognitive.models import (
    UltraMove,
    UltraMoveDecision,
)
from backend.services.cognitive.oracle_delivery import (
    CALLBACK_PREFIX,
    OracleAction,
    OracleCallbackError,
    OracleDelivery,
    build_keyboard,
    decode_callback,
    encode_callback,
    render_move_message,
)
from backend.services.review.telegram_adapter import SendResult

DID = UUID("12345678-1234-1234-1234-123456789abc")


def _move(**overrides) -> UltraMove:
    base = {
        "id": DID,
        "proposed_at": datetime.now(timezone.utc),
        "thesis": "Pre-flight audit 458 PT PMA",
        "narrative": "DJP lancerà cross-check NPWP+BPJS+OSS. Audit 2gg.",
        "target_query": "PT PMA digital economy",
        "estimated_cost": "2 giorni team",
        "estimated_value": "evitare flag + upsell compliance",
        "recommended_tone_register": "analitico",
        "source_inputs": {},
        "zero_decision": UltraMoveDecision.PENDING,
    }
    base.update(overrides)
    return UltraMove(**base)


# ── Encode / decode ────────────────────────────────────────


def test_encode_callback_shape():
    payload = encode_callback(OracleAction.APPROVE, DID)
    assert payload == f"{CALLBACK_PREFIX}:approve:{DID}"


def test_encode_under_64_bytes():
    payload = encode_callback(OracleAction.DEFER, DID)
    assert len(payload.encode()) <= 64


def test_decode_roundtrip_all_actions():
    for action in OracleAction:
        parsed = decode_callback(encode_callback(action, DID))
        assert parsed.action == action
        assert parsed.move_id == DID


def test_decode_rejects_wrong_prefix():
    with pytest.raises(OracleCallbackError):
        decode_callback(f"warroom:approve:{DID}")


def test_decode_rejects_bad_action():
    with pytest.raises(OracleCallbackError):
        decode_callback(f"{CALLBACK_PREFIX}:delete:{DID}")


def test_decode_rejects_bad_uuid():
    with pytest.raises(OracleCallbackError):
        decode_callback(f"{CALLBACK_PREFIX}:approve:not-a-uuid")


def test_decode_rejects_empty():
    with pytest.raises(OracleCallbackError):
        decode_callback("")


# ── Keyboard ──────────────────────────────────────────────


def test_keyboard_has_three_buttons():
    kb = build_keyboard(DID)
    row = kb["inline_keyboard"][0]
    assert len(row) == 3
    actions = [btn["callback_data"].split(":")[1] for btn in row]
    assert actions == ["approve", "reject", "defer"]


# ── Rendering ─────────────────────────────────────────────


def test_render_includes_thesis_and_narrative():
    text = render_move_message(_move())
    assert "Pre-flight audit 458 PT PMA" in text
    assert "DJP lancerà" in text


def test_render_shows_optional_fields():
    text = render_move_message(_move())
    assert "Target" in text
    assert "Costo stimato" in text
    assert "Valore stimato" in text
    assert "analitico" in text


def test_render_escapes_html_in_thesis():
    move = _move(thesis="<script>alert('xss')</script>")
    text = render_move_message(move)
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_render_omits_missing_fields():
    move = _move(
        target_query=None,
        estimated_cost=None,
        estimated_value=None,
        recommended_tone_register=None,
    )
    text = render_move_message(move)
    assert "Target:" not in text
    assert "Costo stimato:" not in text


# ── Delivery: send_pending ────────────────────────────────


@pytest.fixture
def repo_tg():
    repo = AsyncMock()
    repo.pending_ultra_moves = AsyncMock(return_value=[])
    repo.update_ultra_move_decision = AsyncMock()
    tg = AsyncMock()
    tg.send_message = AsyncMock(
        return_value=SendResult(ok=True, message_id=1),
    )
    tg.answer_callback_query = AsyncMock(return_value=SendResult(ok=True))
    tg.edit_message_reply_markup = AsyncMock(return_value=SendResult(ok=True))
    return repo, tg


@pytest.mark.asyncio
async def test_send_pending_empty(repo_tg):
    repo, tg = repo_tg
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.send_pending()
    assert result.sent_count == 0
    tg.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_pending_single_move(repo_tg):
    repo, tg = repo_tg
    repo.pending_ultra_moves = AsyncMock(return_value=[_move()])
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.send_pending()
    assert result.sent_count == 1
    assert DID in result.move_ids_sent
    tg.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_pending_multiple_moves(repo_tg):
    repo, tg = repo_tg
    m2 = _move(id=uuid4())
    repo.pending_ultra_moves = AsyncMock(return_value=[_move(), m2])
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.send_pending()
    assert result.sent_count == 2


@pytest.mark.asyncio
async def test_send_pending_partial_failure(repo_tg):
    repo, tg = repo_tg
    m2 = _move(id=uuid4())
    repo.pending_ultra_moves = AsyncMock(return_value=[_move(), m2])
    tg.send_message = AsyncMock(side_effect=[
        SendResult(ok=True, message_id=1),
        SendResult(ok=False, error="rate limited"),
    ])
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.send_pending()
    assert result.sent_count == 1
    assert result.failed_count == 1
    assert any("rate limited" in e for e in result.errors)


@pytest.mark.asyncio
async def test_send_pending_fetch_failure(repo_tg):
    repo, tg = repo_tg
    repo.pending_ultra_moves = AsyncMock(side_effect=RuntimeError("pg"))
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.send_pending()
    assert result.sent_count == 0
    assert any("fetch_pending" in e for e in result.errors)


# ── Delivery: callback ────────────────────────────────────


def _update(action: OracleAction, chat_id: str = "999", message_id: int = 100):
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
async def test_callback_rejects_unauthorized(repo_tg):
    repo, tg = repo_tg
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(
        OracleAction.APPROVE, chat_id="777",
    ))
    assert result.unauthorized is True


@pytest.mark.asyncio
async def test_callback_approve_updates_decision(repo_tg):
    repo, tg = repo_tg
    repo.update_ultra_move_decision = AsyncMock(
        return_value=_move(zero_decision=UltraMoveDecision.APPROVED),
    )
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(OracleAction.APPROVE))
    assert result.ok is True
    assert result.decision == UltraMoveDecision.APPROVED
    args = repo.update_ultra_move_decision.await_args
    # positional (move_id, decision) + kwargs (notes)
    assert args.args[1] == UltraMoveDecision.APPROVED


@pytest.mark.asyncio
async def test_callback_reject_updates_decision(repo_tg):
    repo, tg = repo_tg
    repo.update_ultra_move_decision = AsyncMock(
        return_value=_move(zero_decision=UltraMoveDecision.REJECTED),
    )
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(OracleAction.REJECT))
    assert result.decision == UltraMoveDecision.REJECTED


@pytest.mark.asyncio
async def test_callback_defer_updates_decision(repo_tg):
    repo, tg = repo_tg
    repo.update_ultra_move_decision = AsyncMock(
        return_value=_move(zero_decision=UltraMoveDecision.DEFERRED),
    )
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(OracleAction.DEFER))
    assert result.decision == UltraMoveDecision.DEFERRED


@pytest.mark.asyncio
async def test_callback_bad_data(repo_tg):
    repo, tg = repo_tg
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
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
async def test_callback_missing_move(repo_tg):
    repo, tg = repo_tg
    repo.update_ultra_move_decision = AsyncMock(return_value=None)
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(OracleAction.APPROVE))
    assert result.ok is False
    assert "move_not_found" in (result.error or "")


@pytest.mark.asyncio
async def test_callback_db_failure_gracefully(repo_tg):
    repo, tg = repo_tg
    repo.update_ultra_move_decision = AsyncMock(side_effect=RuntimeError("pg"))
    delivery = OracleDelivery(repo=repo, telegram=tg, owner_chat_id="999")
    result = await delivery.process_callback(_update(OracleAction.APPROVE))
    assert result.ok is False
    assert "update" in (result.error or "")
