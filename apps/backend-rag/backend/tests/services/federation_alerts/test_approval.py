"""Unit tests for FAD approval token primitives + callback parser."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from backend.services.federation_alerts.approval import (
    admin_chat_ids,
    callback_token_prefix,
    generate_approval_token,
    is_admin_chat_id,
    verify_callback_token,
)
from backend.services.federation_alerts.approval_models import (
    decode_callback,
    encode_callback,
)

# ---------------------------------------------------------------------------
# Token generation + HMAC prefix
# ---------------------------------------------------------------------------


def test_generate_approval_token_hex_string() -> None:
    token = generate_approval_token()
    assert isinstance(token, str)
    assert len(token) == 64  # 32 bytes -> 64 hex
    int(token, 16)  # must be valid hex


def test_generate_approval_token_unique() -> None:
    tokens = {generate_approval_token() for _ in range(50)}
    assert len(tokens) == 50  # collision-free


def test_callback_token_prefix_deterministic() -> None:
    p1 = callback_token_prefix("aabb", "pid-1")
    p2 = callback_token_prefix("aabb", "pid-1")
    assert p1 == p2
    assert len(p1) == 8


def test_callback_token_prefix_different_per_proposal() -> None:
    """Same approval_token but different proposal_id → different prefix."""
    token = "secret"
    assert callback_token_prefix(token, "pid-A") != callback_token_prefix(
        token, "pid-B"
    )


def test_callback_token_prefix_different_per_token() -> None:
    """Same proposal_id but different approval_token → different prefix."""
    pid = "pid-X"
    assert callback_token_prefix("token1", pid) != callback_token_prefix(
        "token2", pid
    )


# ---------------------------------------------------------------------------
# verify_callback_token
# ---------------------------------------------------------------------------


def test_verify_callback_token_happy_path() -> None:
    token = "supersecret"
    pid = "pid-XYZ"
    prefix = callback_token_prefix(token, pid)
    assert verify_callback_token(token, pid, prefix) is True


def test_verify_callback_token_none_token_rejected() -> None:
    assert verify_callback_token(None, "pid-X", "deadbeef") is False


def test_verify_callback_token_empty_token_rejected() -> None:
    assert verify_callback_token("", "pid-X", "deadbeef") is False


def test_verify_callback_token_wrong_length_rejected() -> None:
    token = "supersecret"
    pid = "pid-X"
    assert verify_callback_token(token, pid, "short") is False
    assert verify_callback_token(token, pid, "waaytoolongprefix") is False


def test_verify_callback_token_wrong_prefix_rejected() -> None:
    """Bit-flipped prefix must fail."""
    token = "supersecret"
    pid = "pid-X"
    real = callback_token_prefix(token, pid)
    fake = "0" * 8 if real != "0" * 8 else "1" * 8
    assert verify_callback_token(token, pid, fake) is False


def test_verify_callback_token_case_insensitive() -> None:
    """Telegram clients may upcase callback data; we accept both cases."""
    token = "supersecret"
    pid = "pid-X"
    real = callback_token_prefix(token, pid)
    assert verify_callback_token(token, pid, real.upper()) is True


# ---------------------------------------------------------------------------
# Admin chat allow-list
# ---------------------------------------------------------------------------


def test_admin_chat_ids_default_to_owner() -> None:
    with patch.dict(
        os.environ,
        {"TELEGRAM_OWNER_CHAT_ID": "123", "FEDERATION_ALERT_ADMIN_CHAT_IDS": ""},
        clear=False,
    ):
        ids = admin_chat_ids()
    assert "123" in ids


def test_admin_chat_ids_explicit_list_overrides() -> None:
    with patch.dict(
        os.environ,
        {"FEDERATION_ALERT_ADMIN_CHAT_IDS": "111,222, 333"},
        clear=False,
    ):
        ids = admin_chat_ids()
    assert ids == frozenset({"111", "222", "333"})


def test_is_admin_chat_id_normalizes_int() -> None:
    with patch.dict(
        os.environ,
        {"FEDERATION_ALERT_ADMIN_CHAT_IDS": "42"},
        clear=False,
    ):
        assert is_admin_chat_id(42) is True
        assert is_admin_chat_id("42") is True
        assert is_admin_chat_id(99) is False
        assert is_admin_chat_id(None) is False


# ---------------------------------------------------------------------------
# encode_callback / decode_callback
# ---------------------------------------------------------------------------


def test_encode_callback_approve() -> None:
    pid = "550e8400-e29b-41d4-a716-446655440000"
    cb = encode_callback("approve", pid, "deadbeef")
    assert cb == f"fad:approve:{pid}:deadbeef"
    assert len(cb.encode("utf-8")) <= 64


def test_encode_callback_invalid_action() -> None:
    with pytest.raises(ValueError, match="unknown FAD action"):
        encode_callback("nuke", "pid-1", "deadbeef")


def test_encode_callback_invalid_mode() -> None:
    with pytest.raises(ValueError, match="unknown target mode"):
        encode_callback("mode", "garbage", "deadbeef")


def test_encode_callback_invalid_token_length() -> None:
    with pytest.raises(ValueError, match="8 hex chars"):
        encode_callback("approve", "pid-1", "short")


def test_encode_callback_too_long_for_telegram() -> None:
    """Telegram callback_data limit is 64 bytes."""
    long_pid = "x" * 60  # would push total > 64
    with pytest.raises(ValueError, match="64-byte limit"):
        encode_callback("approve", long_pid, "deadbeef")


def test_decode_callback_round_trip() -> None:
    pid = "550e8400-e29b-41d4-a716-446655440000"
    cb = encode_callback("approve", pid, "deadbeef")
    parsed = decode_callback(cb)
    assert parsed is not None
    assert parsed.action == "approve"
    assert parsed.target == pid
    assert parsed.token_prefix == "deadbeef"


def test_decode_callback_mode_round_trip() -> None:
    cb = encode_callback("mode", "dry_action", "abcd1234")
    parsed = decode_callback(cb)
    assert parsed is not None
    assert parsed.is_mode_change()
    assert parsed.target == "dry_action"


def test_decode_callback_wrong_prefix() -> None:
    assert decode_callback("intel:approve:pid:abcd1234") is None
    assert decode_callback("warroom:approve:pid:abcd1234") is None


def test_decode_callback_wrong_part_count() -> None:
    assert decode_callback("fad:approve:pid") is None
    assert decode_callback("fad:approve:pid:abcd1234:extra") is None


def test_decode_callback_unknown_action() -> None:
    assert decode_callback("fad:nuke:pid:deadbeef") is None


def test_decode_callback_empty_target() -> None:
    assert decode_callback("fad:approve::deadbeef") is None


def test_decode_callback_non_hex_token() -> None:
    assert decode_callback("fad:approve:pid:zzzzzzzz") is None


def test_decode_callback_unknown_mode() -> None:
    assert decode_callback("fad:mode:garbage:deadbeef") is None


def test_decode_callback_short_token() -> None:
    assert decode_callback("fad:approve:pid:dead") is None


def test_decode_callback_is_approval() -> None:
    cb = decode_callback("fad:approve:pid:deadbeef")
    assert cb is not None
    assert cb.is_approval() is True
    assert cb.is_mode_change() is False
