"""ArgsCipher — encrypt/decrypt round-trip, canonicalization, integrity."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet, InvalidToken

from team_bot.confirmation.crypto import ArgsCipher, ArgsIntegrityError, canonicalize_args, sha256_hex


def _cipher() -> ArgsCipher:
    return ArgsCipher(Fernet.generate_key())


def test_canonicalize_args_is_order_independent() -> None:
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert canonicalize_args(a) == canonicalize_args(b)


def test_encrypt_then_decrypt_round_trips() -> None:
    cipher = _cipher()
    args = {"practice_id": "PR-1042", "new_status": "approved", "reason_code": "completed"}
    ciphertext, digest = cipher.encrypt_canonical_args(args)

    decrypted = cipher.decrypt_args(ciphertext, expected_sha256=digest)
    assert decrypted == args


def test_ciphertext_is_not_plaintext() -> None:
    cipher = _cipher()
    args = {"practice_id": "PR-1042"}
    ciphertext, _ = cipher.encrypt_canonical_args(args)
    assert b"PR-1042" not in ciphertext


def test_wrong_key_cannot_decrypt() -> None:
    cipher_a = _cipher()
    cipher_b = _cipher()
    ciphertext, digest = cipher_a.encrypt_canonical_args({"x": 1})
    with pytest.raises(InvalidToken):
        cipher_b.decrypt_args(ciphertext, expected_sha256=digest)


def test_tampered_hash_is_rejected_even_with_the_right_key() -> None:
    cipher = _cipher()
    ciphertext, _real_digest = cipher.encrypt_canonical_args({"x": 1})
    with pytest.raises(ArgsIntegrityError):
        cipher.decrypt_args(ciphertext, expected_sha256=sha256_hex(b'{"x":2}'))


def test_sha256_hex_is_deterministic() -> None:
    # Known digest (not a self-comparison) — a real fixed value, so a
    # regression that changes the hashing scheme is caught, not just
    # internal self-consistency.
    expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    first_call = sha256_hex(b"hello")
    second_call = sha256_hex(b"hello")
    assert first_call == expected
    assert second_call == expected
    assert sha256_hex(b"world") != expected
