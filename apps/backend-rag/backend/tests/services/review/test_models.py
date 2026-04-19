"""Tests for review callback encode/decode + ReviewRequest formatting."""

from __future__ import annotations

from uuid import UUID

import pytest

from backend.services.review.models import (
    CALLBACK_PREFIX,
    ReviewAction,
    ReviewCallbackError,
    ReviewRequest,
    build_primary_keyboard,
    build_reject_reason_keyboard,
    decode_callback,
    encode_callback,
)
from backend.services.war_room.models import RejectionReason

DID = UUID("12345678-1234-1234-1234-123456789abc")


# ── encode / decode ─────────────────────────────────────────────────


def test_encode_approve_format():
    payload = encode_callback(ReviewAction.APPROVE, DID)
    assert payload == f"{CALLBACK_PREFIX}:approve:{DID}"


def test_encode_reject_with_reason_format():
    payload = encode_callback(ReviewAction.REJECT, DID, RejectionReason.TONE)
    assert payload == f"{CALLBACK_PREFIX}:reject:{DID}:tone"


def test_encode_rejects_reason_on_non_reject_action():
    with pytest.raises(ReviewCallbackError):
        encode_callback(ReviewAction.APPROVE, DID, RejectionReason.TONE)


def test_encode_stays_under_64_bytes():
    payload = encode_callback(ReviewAction.REJECT, DID, RejectionReason.CLICKBAIT)
    assert len(payload.encode("utf-8")) <= 64


def test_decode_approve():
    cb = decode_callback(f"{CALLBACK_PREFIX}:approve:{DID}")
    assert cb.action == ReviewAction.APPROVE
    assert cb.draft_id == DID
    assert cb.reject_reason is None


def test_decode_reject_with_reason():
    cb = decode_callback(f"{CALLBACK_PREFIX}:reject:{DID}:fact")
    assert cb.action == ReviewAction.REJECT
    assert cb.reject_reason == RejectionReason.FACT


def test_decode_rejects_wrong_prefix():
    with pytest.raises(ReviewCallbackError):
        decode_callback(f"other:approve:{DID}")


def test_decode_rejects_unknown_action():
    with pytest.raises(ReviewCallbackError):
        decode_callback(f"{CALLBACK_PREFIX}:delete:{DID}")


def test_decode_rejects_invalid_uuid():
    with pytest.raises(ReviewCallbackError):
        decode_callback(f"{CALLBACK_PREFIX}:approve:not-a-uuid")


def test_decode_rejects_unknown_reason():
    with pytest.raises(ReviewCallbackError):
        decode_callback(f"{CALLBACK_PREFIX}:reject:{DID}:whatever")


def test_decode_rejects_reason_on_wrong_action():
    with pytest.raises(ReviewCallbackError):
        decode_callback(f"{CALLBACK_PREFIX}:approve:{DID}:tone")


def test_decode_empty_payload():
    with pytest.raises(ReviewCallbackError):
        decode_callback("")


def test_roundtrip_preserves_reason():
    for reason in RejectionReason:
        if reason == RejectionReason.SLA_EXPIRED:
            # SLA_EXPIRED is set by the system, not via Telegram keyboard
            continue
        payload = encode_callback(ReviewAction.REJECT, DID, reason)
        parsed = decode_callback(payload)
        assert parsed.reject_reason == reason


# ── Keyboards ──────────────────────────────────────────────────────


def test_primary_keyboard_has_three_buttons():
    kb = build_primary_keyboard(DID)
    assert "inline_keyboard" in kb
    row = kb["inline_keyboard"][0]
    assert len(row) == 3
    actions = [btn["callback_data"].split(":")[1] for btn in row]
    assert actions == ["approve", "edit", "reject"]


def test_reject_reason_keyboard_covers_all_reasons():
    kb = build_reject_reason_keyboard(DID)
    data = [
        btn["callback_data"]
        for row in kb["inline_keyboard"]
        for btn in row
    ]
    reasons = [d.split(":")[3] for d in data]
    assert set(reasons) == {"tone", "fact", "visual", "clickbait", "other"}


# ── ReviewRequest caption ────────────────────────────────────────


def test_caption_contains_topic_and_register():
    req = ReviewRequest(
        draft_id=DID,
        topic="B211A estensione",
        tone_register="analitico",
        cover_image_url="https://x/c.jpg",
        first_slide_text="Primo slide del carousel",
    )
    caption = req.to_caption()
    assert "B211A estensione" in caption
    assert "<b>analitico</b>" in caption
    assert "Primo slide" in caption


def test_caption_shows_rejected_registers():
    req = ReviewRequest(
        draft_id=DID,
        topic="t",
        tone_register="tecnico",
        cover_image_url="https://x/c.jpg",
        first_slide_text="body",
        rejected_registers=["ironico", "cinico"],
    )
    caption = req.to_caption()
    assert "ironico" in caption
    assert "cinico" in caption


def test_caption_shows_cost_when_provided():
    req = ReviewRequest(
        draft_id=DID,
        topic="t",
        tone_register="tecnico",
        cover_image_url="https://x/c.jpg",
        first_slide_text="b",
        ultra_cost_usd=0.16,
    )
    caption = req.to_caption()
    assert "$0.16" in caption


def test_caption_truncates_at_max_chars():
    req = ReviewRequest(
        draft_id=DID,
        topic="t" * 5000,  # oversize
        tone_register="tecnico",
        cover_image_url="https://x/c.jpg",
        first_slide_text="b",
    )
    caption = req.to_caption(max_chars=400)
    assert len(caption) <= 400
    assert caption.endswith("…")


def test_caption_escapes_html():
    req = ReviewRequest(
        draft_id=DID,
        topic="<script>alert(1)</script>",
        tone_register="analitico",
        cover_image_url="https://x/c.jpg",
        first_slide_text="safe",
    )
    caption = req.to_caption()
    assert "<script>" not in caption
    assert "&lt;script&gt;" in caption
