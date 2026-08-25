"""F7 gate — ``redact_identifier_for_log`` never leaks a raw phone/chat id.

Guilt/innocence per cicatrix-superscar.md family #3: a redaction helper
proves it redacts (guilt: the raw value never survives), AND proves it
stays useful (innocence: the digest is stable for the same input and
distinguishable for a different one — a redaction that collapses every
input to the same placeholder destroys log correlation, which is a
different failure, not a fix).
"""

from __future__ import annotations

import hashlib

import pytest

from backend.utils.pii_log_identifier import (
    MISSING_IDENTIFIER_MARKER,
    redact_identifier_for_log,
)

# Obviously-synthetic numbers only — never a shape that could be mistaken
# for a real client's WhatsApp number.
_SYNTHETIC_PHONE = "+62 000-111-2222"
_SYNTHETIC_PHONE_DIGITS_ONLY = "620001112222"
_SYNTHETIC_PHONE_OTHER = "+62 999-888-7777"
_SYNTHETIC_CHAT_ID = 194920123


class TestRedactIdentifierForLogGuilt:
    """The raw value must NEVER appear in the digest output."""

    def test_phone_digest_does_not_contain_raw_phone(self) -> None:
        digest = redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert _SYNTHETIC_PHONE not in digest
        assert "0001112222" not in digest  # the bare digits, plus-stripped
        assert digest.startswith("id:")

    def test_chat_id_digest_does_not_contain_raw_chat_id(self) -> None:
        digest = redact_identifier_for_log(_SYNTHETIC_CHAT_ID)
        assert str(_SYNTHETIC_CHAT_ID) not in digest
        assert digest.startswith("id:")

    def test_digest_is_not_a_bare_unkeyed_sha256(self) -> None:
        """A bare sha256 of the digits is reversible by brute force over the
        enumerable phone-number space — it must not appear verbatim."""
        bare = hashlib.sha256(b"620001112222").hexdigest()[:12]
        digest = redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert digest != f"id:{bare}"


class TestRedactIdentifierForLogInnocence:
    """The digest must stay USEFUL for cross-line correlation."""

    def test_same_phone_same_digest_regardless_of_formatting(self) -> None:
        assert redact_identifier_for_log(_SYNTHETIC_PHONE) == redact_identifier_for_log(
            _SYNTHETIC_PHONE_DIGITS_ONLY,
        )

    def test_different_phone_different_digest(self) -> None:
        assert redact_identifier_for_log(_SYNTHETIC_PHONE) != redact_identifier_for_log(
            _SYNTHETIC_PHONE_OTHER,
        )

    def test_digest_is_stable_across_calls(self) -> None:
        first = redact_identifier_for_log(_SYNTHETIC_PHONE)
        second = redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert first == second

    def test_phone_and_chat_id_of_same_digits_still_distinguishable_by_value(self) -> None:
        """Not a collision guard, just documents that a phone-shaped and a
        chat-id-shaped input are hashed via the same normalization; if they
        ever carry the same digits they DO collide by design (both reduce
        to the same digit string). This is fine because they are never
        compared against each other in the caller (one call site logs
        phone-or-chat_id, never both together)."""
        digest_phone = redact_identifier_for_log("620001112222")
        digest_chat_id = redact_identifier_for_log(620001112222)
        assert digest_phone == digest_chat_id


class TestRedactIdentifierForLogMissing:
    def test_none_returns_missing_marker(self) -> None:
        assert redact_identifier_for_log(None) == MISSING_IDENTIFIER_MARKER

    def test_empty_string_returns_missing_marker(self) -> None:
        assert redact_identifier_for_log("") == MISSING_IDENTIFIER_MARKER

    def test_whitespace_only_returns_missing_marker(self) -> None:
        assert redact_identifier_for_log("   ") == MISSING_IDENTIFIER_MARKER

    def test_non_digit_garbage_returns_missing_marker(self) -> None:
        assert redact_identifier_for_log("n/a") == MISSING_IDENTIFIER_MARKER


class TestRedactIdentifierForLogSaltConfiguration:
    """LOG_PII_HMAC_SALT changes the digest; unset falls back, never to
    the raw value."""

    def test_configured_salt_changes_the_digest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LOG_PII_HMAC_SALT", raising=False)
        unconfigured = redact_identifier_for_log(_SYNTHETIC_PHONE)

        monkeypatch.setenv("LOG_PII_HMAC_SALT", "a-test-salt-that-is-not-the-fallback")
        configured = redact_identifier_for_log(_SYNTHETIC_PHONE)

        assert configured != unconfigured
        assert configured.startswith("id:")

    def test_same_configured_salt_is_deterministic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_PII_HMAC_SALT", "a-test-salt")
        first = redact_identifier_for_log(_SYNTHETIC_PHONE)
        second = redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert first == second

    def test_unconfigured_salt_still_never_prints_raw_phone(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("LOG_PII_HMAC_SALT", raising=False)
        digest = redact_identifier_for_log(_SYNTHETIC_PHONE)
        assert _SYNTHETIC_PHONE not in digest
        assert "0001112222" not in digest
        assert digest.startswith("id:")
