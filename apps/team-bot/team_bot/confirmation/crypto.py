"""ArgsCipher — F6's "canonical args encrypted, args_sha256".

Encrypts a mutation's arguments before they ever reach the sqlite row
(``PendingAction.encrypted_args`` is ciphertext-only — see models.py), and
verifies integrity on the way back out: ``args_sha256`` is computed over the
CANONICAL plaintext serialization at encrypt time and re-checked after every
decrypt, so a corrupted/tampered ciphertext is rejected rather than handed
to the executor.

"Canonical" here means one deterministic JSON serialization (sorted keys,
no whitespace) — required for ``args_sha256`` and the idempotency key
(``idempotency.py``) to be stable regardless of the dict's insertion order.

Uses ``cryptography.fernet.Fernet`` (already a repo dependency — see
``backend/services/visa_engine/bundle.py``'s Ed25519 usage from the same
``cryptography`` package family): authenticated symmetric encryption,
simple encrypt(bytes)/decrypt(bytes) API, no key-management scheme this
module needs to invent.

Golden Rule #6 (no hardcoded secrets): the key is never defaulted in code.
``load_cipher_from_env`` reads it from an env var and raises if absent —
callers wanting a throwaway key (tests) must generate one explicitly via
``Fernet.generate_key()``.

Author: Claude Sonnet 5 (lane B3 — team-bot confirmation state machine)
"""

from __future__ import annotations

import hashlib
import json
import os

from cryptography.fernet import Fernet, InvalidToken

__all__ = [
    "ArgsCipher",
    "ArgsIntegrityError",
    "canonicalize_args",
    "load_cipher_from_env",
    "sha256_hex",
]


class ArgsIntegrityError(ValueError):
    """Raised when a decrypted payload's hash does not match the stored
    ``args_sha256`` — corruption or tampering, never silently accepted."""


def canonicalize_args(args: dict[str, object]) -> bytes:
    """Deterministic JSON serialization — sorted keys, no extraneous
    whitespace — so the same logical args always hash/encrypt identically
    regardless of dict construction order."""
    return json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class ArgsCipher:
    """Stateless wrapper around one Fernet key. Safe to share/reuse across
    requests — Fernet itself holds no mutable state."""

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt_canonical_args(self, args: dict[str, object]) -> tuple[bytes, str]:
        """Returns (ciphertext, args_sha256_hex). The hash is computed over
        the CANONICAL plaintext, before encryption — this is what
        ``PendingAction.args_sha256`` stores."""
        canonical = canonicalize_args(args)
        digest = sha256_hex(canonical)
        ciphertext = self._fernet.encrypt(canonical)
        return ciphertext, digest

    def decrypt_args(self, ciphertext: bytes, *, expected_sha256: str) -> dict[str, object]:
        """Decrypts and re-verifies against ``expected_sha256``. Raises
        ``ArgsIntegrityError`` on mismatch (never returns a payload that
        does not match its recorded hash) and propagates
        ``cryptography.fernet.InvalidToken`` unchanged for a ciphertext the
        key cannot even decrypt (wrong key, corrupted bytes)."""
        try:
            canonical = self._fernet.decrypt(ciphertext)
        except InvalidToken:
            raise
        actual = sha256_hex(canonical)
        if actual != expected_sha256:
            raise ArgsIntegrityError(
                f"decrypted args hash {actual} does not match stored args_sha256 {expected_sha256}"
            )
        decoded = json.loads(canonical)
        if not isinstance(decoded, dict):
            raise ArgsIntegrityError("decrypted payload is not a JSON object")
        return decoded


def load_cipher_from_env(env_var: str = "TEAM_BOT_PENDING_ACTION_KEY") -> ArgsCipher:
    """The ONLY sanctioned way to get a production ``ArgsCipher`` — reads a
    base64 urlsafe Fernet key from the environment. Raises ``RuntimeError``
    (not a silent default) when the key is absent, per Golden Rule #6: no
    hardcoded secrets, and no hardcoded FALLBACK that would quietly encrypt
    every environment with the same key."""
    raw = os.environ.get(env_var)
    if not raw:
        raise RuntimeError(
            f"{env_var} is not set — refuse to run the confirmation store without a real key "
            "(never defaults to a hardcoded value)"
        )
    return ArgsCipher(raw.encode("utf-8"))
