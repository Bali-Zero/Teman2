"""Unit tests for scripts/wr2_telegram_publish_gate.py.

Phase 2.2 of WR2 autonomous carousel workflow — Telegram approval gate.

Covers (pure / easily mockable functions):
- get_owner_chat_id: env parse / default / fallback on invalid
- get_gate_secret: raises SystemExit when unset, returns bytes when set
- sign_token: HMAC-SHA256 deterministic + input sensitivity
- verify_token: valid / expired / malformed / wrong HMAC / content_hash binding
- compute_content_hash: deterministic, idempotent, file-sensitive, empty-dir
- build_inline_keyboard: Approve/Reject buttons, optional Preview button
- ALLOWED_USER_IDS whitelist

DB / Telegram / asyncpg paths are NOT exercised here (those require integration).
"""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import sys
import time
from pathlib import Path

import pytest

# Load the gate module from scripts/ (it's not on PYTHONPATH and not a package).
GATE_PATH = Path(__file__).resolve().parent.parent / "wr2_telegram_publish_gate.py"


@pytest.fixture
def gate(monkeypatch):
    """Fresh import of wr2_telegram_publish_gate with a default test secret."""
    # Ensure WR2_TG_GATE_SECRET is set BEFORE module load (module-level
    # DEFAULT_PREVIEW_BASE reads env at import time).
    monkeypatch.setenv("WR2_TG_GATE_SECRET", "test-secret-do-not-use")
    monkeypatch.delenv("WR2_PREVIEW_BASE_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)

    sys.modules.pop("wr2_telegram_gate_mod", None)
    spec = importlib.util.spec_from_file_location(
        "wr2_telegram_gate_mod", GATE_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_telegram_gate_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


# ─────────────────────────────────────────────────────────────────────────
# get_owner_chat_id
# ─────────────────────────────────────────────────────────────────────────


def test_get_owner_chat_id_default_when_env_unset(gate, monkeypatch):
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)
    assert gate.get_owner_chat_id() == 1125336968  # Zero per CLAUDE.md §13


def test_get_owner_chat_id_parses_valid_int(gate, monkeypatch):
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "42")
    assert gate.get_owner_chat_id() == 42


def test_get_owner_chat_id_fallback_on_invalid(gate, monkeypatch):
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "not-a-number")
    assert gate.get_owner_chat_id() == 1125336968


# ─────────────────────────────────────────────────────────────────────────
# get_gate_secret
# ─────────────────────────────────────────────────────────────────────────


def test_get_gate_secret_raises_when_unset(gate, monkeypatch):
    monkeypatch.delenv("WR2_TG_GATE_SECRET", raising=False)
    with pytest.raises(SystemExit) as exc:
        gate.get_gate_secret()
    assert "WR2_TG_GATE_SECRET" in str(exc.value)


def test_get_gate_secret_returns_bytes(gate, monkeypatch):
    monkeypatch.setenv("WR2_TG_GATE_SECRET", "abc123")
    secret = gate.get_gate_secret()
    assert isinstance(secret, bytes)
    assert secret == b"abc123"


# ─────────────────────────────────────────────────────────────────────────
# sign_token
# ─────────────────────────────────────────────────────────────────────────


def test_sign_token_deterministic(gate):
    """Same inputs → same output (HMAC determinism)."""
    t1 = gate.sign_token("car-1", "hash-A", "nonce-x", 1700000000)
    t2 = gate.sign_token("car-1", "hash-A", "nonce-x", 1700000000)
    assert t1 == t2
    # Format: nonce.expires_at.sig
    parts = t1.split(".")
    assert len(parts) == 3
    assert parts[0] == "nonce-x"
    assert parts[1] == "1700000000"


def test_sign_token_different_inputs_differ(gate):
    """Changing any single input changes the signature."""
    base = gate.sign_token("car-1", "hash-A", "nonce-x", 1700000000)
    diff_carousel = gate.sign_token("car-2", "hash-A", "nonce-x", 1700000000)
    diff_hash = gate.sign_token("car-1", "hash-B", "nonce-x", 1700000000)
    diff_nonce = gate.sign_token("car-1", "hash-A", "nonce-y", 1700000000)
    diff_exp = gate.sign_token("car-1", "hash-A", "nonce-x", 1700000001)
    assert base != diff_carousel
    assert base != diff_hash
    assert base != diff_nonce
    assert base != diff_exp


# ─────────────────────────────────────────────────────────────────────────
# verify_token
# ─────────────────────────────────────────────────────────────────────────


def test_verify_token_valid(gate):
    expires_at = int(time.time()) + 3600  # 1 hour ahead
    token = gate.sign_token("car-1", "hash-A", "n1", expires_at)
    valid, reason = gate.verify_token(token, "car-1", "hash-A")
    assert valid is True
    assert reason == "ok"


def test_verify_token_expired(gate):
    expires_at = int(time.time()) - 60  # 1 min ago
    token = gate.sign_token("car-1", "hash-A", "n1", expires_at)
    valid, reason = gate.verify_token(token, "car-1", "hash-A")
    assert valid is False
    assert reason == "token_expired"


def test_verify_token_malformed(gate):
    # Token missing dot-separators
    valid, reason = gate.verify_token("not-a-valid-token", "car-1", "hash-A")
    assert valid is False
    assert reason == "token_malformed"


def test_verify_token_malformed_non_int_expires(gate):
    # nonce.notanint.sig → ValueError on int() cast
    bogus = "nonce.abc.deadbeef"
    valid, reason = gate.verify_token(bogus, "car-1", "hash-A")
    assert valid is False
    assert reason == "token_malformed"


def test_verify_token_wrong_hmac(gate):
    """Tampering with sig segment → token_mismatch."""
    expires_at = int(time.time()) + 3600
    token = gate.sign_token("car-1", "hash-A", "n1", expires_at)
    # Replace sig with all zeros
    nonce, exp, _sig = token.split(".")
    tampered = f"{nonce}.{exp}.{'0' * 64}"
    valid, reason = gate.verify_token(tampered, "car-1", "hash-A")
    assert valid is False
    assert reason == "token_mismatch"


def test_verify_token_bound_to_content_hash(gate):
    """Token signed with hash-A must NOT verify against hash-B."""
    expires_at = int(time.time()) + 3600
    token = gate.sign_token("car-1", "hash-A", "n1", expires_at)
    valid, reason = gate.verify_token(token, "car-1", "hash-B")
    assert valid is False
    assert reason == "token_mismatch"


# ─────────────────────────────────────────────────────────────────────────
# compute_content_hash
# ─────────────────────────────────────────────────────────────────────────


def test_compute_content_hash_deterministic_64char_hex(gate, tmp_path):
    (tmp_path / "brief_interpreter.json").write_bytes(b'{"a":1}')
    (tmp_path / "storyboarder.json").write_bytes(b'{"b":2}')
    h = gate.compute_content_hash(tmp_path)
    assert isinstance(h, str)
    assert len(h) == 64
    int(h, 16)  # must parse as hex


def test_compute_content_hash_idempotent(gate, tmp_path):
    (tmp_path / "brief_interpreter.json").write_bytes(b'{"a":1}')
    (tmp_path / "storyboarder.json").write_bytes(b'{"b":2}')
    (tmp_path / "layout_composer.json").write_bytes(b'{"c":3}')
    (tmp_path / "rendered.json").write_bytes(b'{"d":4}')
    h1 = gate.compute_content_hash(tmp_path)
    h2 = gate.compute_content_hash(tmp_path)
    assert h1 == h2


def test_compute_content_hash_changes_when_input_changes(gate, tmp_path):
    (tmp_path / "brief_interpreter.json").write_bytes(b'{"a":1}')
    h_before = gate.compute_content_hash(tmp_path)
    # Mutate one file
    (tmp_path / "brief_interpreter.json").write_bytes(b'{"a":2}')
    h_after = gate.compute_content_hash(tmp_path)
    assert h_before != h_after


def test_compute_content_hash_empty_dir_is_empty_sha256(gate, tmp_path):
    """Missing files → hash of nothing = sha256 of empty bytes."""
    h = gate.compute_content_hash(tmp_path)
    # sha256() with no updates returns sha256 of b""
    assert h == hashlib.sha256(b"").hexdigest()


def test_compute_content_hash_matches_manual_concat(gate, tmp_path):
    """Verify hash equals sha256 of concatenated file bytes in fixed order."""
    files = {
        "brief_interpreter.json": b"alpha",
        "storyboarder.json": b"beta",
        "layout_composer.json": b"gamma",
        "rendered.json": b"delta",
    }
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    actual = gate.compute_content_hash(tmp_path)
    expected = hashlib.sha256(b"alpha" + b"beta" + b"gamma" + b"delta").hexdigest()
    assert actual == expected


# ─────────────────────────────────────────────────────────────────────────
# build_inline_keyboard
# ─────────────────────────────────────────────────────────────────────────


def test_build_inline_keyboard_approve_reject_only_when_preview_unset(gate):
    """Without WR2_PREVIEW_BASE_URL set at module-import time, no Preview button."""
    kb = gate.build_inline_keyboard("abcdef1234567890", 42)
    assert "inline_keyboard" in kb
    rows = kb["inline_keyboard"]
    # First row = approve + reject; preview row only if env was set at import
    assert len(rows[0]) == 2
    assert rows[0][0]["text"] == "✅ Approve"
    assert rows[0][1]["text"] == "❌ Reject"
    # No preview row (env unset in fixture)
    assert len(rows) == 1


def test_build_inline_keyboard_callback_data_format(gate):
    """callback_data: 'a:<short_id>:<attempt_id>' and 'r:<short_id>:<attempt_id>'.

    short_id = carousel_id[:8].
    """
    kb = gate.build_inline_keyboard("abcdef1234567890", 42)
    approve = kb["inline_keyboard"][0][0]
    reject = kb["inline_keyboard"][0][1]
    assert approve["callback_data"] == "a:abcdef12:42"
    assert reject["callback_data"] == "r:abcdef12:42"


def test_build_inline_keyboard_preview_button_when_env_set(monkeypatch):
    """Preview button appears when WR2_PREVIEW_BASE_URL is set at module import."""
    monkeypatch.setenv("WR2_TG_GATE_SECRET", "x")
    monkeypatch.setenv("WR2_PREVIEW_BASE_URL", "https://preview.example.com")
    sys.modules.pop("wr2_telegram_gate_mod_p", None)
    spec = importlib.util.spec_from_file_location(
        "wr2_telegram_gate_mod_p", GATE_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_telegram_gate_mod_p"] = mod
    spec.loader.exec_module(mod)

    kb = mod.build_inline_keyboard("xyz12345abcdef", 7)
    rows = kb["inline_keyboard"]
    assert len(rows) == 2  # approve+reject row, preview row
    preview = rows[1][0]
    assert preview["text"] == "👀 Preview"
    assert preview["url"] == "https://preview.example.com/xyz12345abcdef"


# ─────────────────────────────────────────────────────────────────────────
# ALLOWED_USER_IDS whitelist
# ─────────────────────────────────────────────────────────────────────────


def test_allowed_user_ids_contains_zero(gate):
    """Zero (1125336968) is in the whitelist."""
    assert 1125336968 in gate.ALLOWED_USER_IDS


def test_allowed_user_ids_rejects_random(gate):
    """Arbitrary user_ids are NOT in the whitelist."""
    assert 0 not in gate.ALLOWED_USER_IDS
    assert 99999 not in gate.ALLOWED_USER_IDS
    assert -1 not in gate.ALLOWED_USER_IDS
