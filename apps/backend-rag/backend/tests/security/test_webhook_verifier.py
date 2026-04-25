"""Unit tests for backend.security.webhook_verifier.

The module is pure — no DB, no HTTP, no settings. We exercise every
``reason`` code, both ``require_secret`` modes, and every helper.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from backend.security.webhook_verifier import (
    WebhookVerificationError,
    verify_meta_hmac,
    verify_telegram_secret,
    verify_twitter_hmac,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

META_SECRET = "meta-app-secret-xyz"
TWITTER_SECRET = "twitter-consumer-secret-abc"
TG_SECRET = "tg-shared-secret-123"


def _meta_sig(body: bytes, secret: str = META_SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _twitter_sig(body: bytes, secret: str = TWITTER_SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return f"sha256={base64.b64encode(digest).decode('ascii')}"


# ---------------------------------------------------------------------------
# Meta HMAC (WhatsApp / Instagram)
# ---------------------------------------------------------------------------


class TestVerifyMetaHmac:
    def test_valid_signature_passes(self) -> None:
        body = b'{"object":"whatsapp_business_account"}'
        verify_meta_hmac(body, _meta_sig(body), META_SECRET, provider="whatsapp")

    def test_valid_signature_empty_body_passes(self) -> None:
        # Meta sends empty bodies for some lifecycle pings; HMAC of b"" is
        # a well-defined value so verification must still succeed.
        body = b""
        verify_meta_hmac(body, _meta_sig(body), META_SECRET, provider="whatsapp")

    def test_missing_header_raises(self) -> None:
        with pytest.raises(WebhookVerificationError) as ei:
            verify_meta_hmac(b"x", None, META_SECRET, provider="instagram")
        assert ei.value.reason == "missing_header"
        assert ei.value.provider == "instagram"

    def test_malformed_header_raises(self) -> None:
        with pytest.raises(WebhookVerificationError) as ei:
            verify_meta_hmac(
                b"x",
                "md5=deadbeef",  # wrong algorithm prefix
                META_SECRET,
                provider="whatsapp",
            )
        assert ei.value.reason == "malformed_header"

    def test_wrong_secret_raises_signature_mismatch(self) -> None:
        body = b'{"a":1}'
        sig = _meta_sig(body, secret="wrong-secret")
        with pytest.raises(WebhookVerificationError) as ei:
            verify_meta_hmac(body, sig, META_SECRET, provider="whatsapp")
        assert ei.value.reason == "signature_mismatch"

    def test_replay_with_modified_body_raises(self) -> None:
        # Same secret, but body was mutated in flight — signature no longer
        # matches the new bytes.
        original = b'{"amount":100}'
        sig = _meta_sig(original)
        tampered = b'{"amount":999}'
        with pytest.raises(WebhookVerificationError) as ei:
            verify_meta_hmac(tampered, sig, META_SECRET, provider="whatsapp")
        assert ei.value.reason == "signature_mismatch"

    def test_missing_secret_with_require_raises(self) -> None:
        with pytest.raises(WebhookVerificationError) as ei:
            verify_meta_hmac(
                b"x", "sha256=abc", None, provider="whatsapp", require_secret=True,
            )
        assert ei.value.reason == "missing_secret"

    def test_missing_secret_without_require_skips(self) -> None:
        # dev mode: should not raise even with bogus signature
        verify_meta_hmac(
            b"x",
            "sha256=bogus",
            None,
            provider="whatsapp",
            require_secret=False,
        )

    def test_default_require_secret_is_true(self) -> None:
        # Sanity: the safe default kicks in if caller forgets the kwarg.
        with pytest.raises(WebhookVerificationError):
            verify_meta_hmac(b"x", "sha256=abc", None, provider="whatsapp")


# ---------------------------------------------------------------------------
# Telegram shared-secret header
# ---------------------------------------------------------------------------


class TestVerifyTelegramSecret:
    def test_valid_secret_passes(self) -> None:
        verify_telegram_secret(TG_SECRET, TG_SECRET)

    def test_missing_header_raises(self) -> None:
        with pytest.raises(WebhookVerificationError) as ei:
            verify_telegram_secret(None, TG_SECRET)
        assert ei.value.reason == "missing_header"

    def test_wrong_secret_raises_signature_mismatch(self) -> None:
        with pytest.raises(WebhookVerificationError) as ei:
            verify_telegram_secret("not-the-secret", TG_SECRET)
        assert ei.value.reason == "signature_mismatch"

    def test_missing_expected_secret_with_require_raises(self) -> None:
        with pytest.raises(WebhookVerificationError) as ei:
            verify_telegram_secret(TG_SECRET, None, require_secret=True)
        assert ei.value.reason == "missing_secret"

    def test_missing_expected_secret_without_require_skips(self) -> None:
        verify_telegram_secret(TG_SECRET, None, require_secret=False)


# ---------------------------------------------------------------------------
# Twitter HMAC (base64)
# ---------------------------------------------------------------------------


class TestVerifyTwitterHmac:
    def test_valid_signature_passes(self) -> None:
        body = b'{"direct_message_events":[]}'
        verify_twitter_hmac(body, _twitter_sig(body), TWITTER_SECRET)

    def test_uses_base64_not_hex(self) -> None:
        # Regression guard: if someone refactors and switches to .hexdigest(),
        # this hex-shaped header must NOT be accepted as a valid base64.
        body = b"hello"
        hex_sig = "sha256=" + hmac.new(
            TWITTER_SECRET.encode(), body, hashlib.sha256,
        ).hexdigest()
        with pytest.raises(WebhookVerificationError) as ei:
            verify_twitter_hmac(body, hex_sig, TWITTER_SECRET)
        assert ei.value.reason == "signature_mismatch"

    def test_missing_header_raises(self) -> None:
        with pytest.raises(WebhookVerificationError) as ei:
            verify_twitter_hmac(b"x", None, TWITTER_SECRET)
        assert ei.value.reason == "missing_header"

    def test_malformed_header_raises(self) -> None:
        with pytest.raises(WebhookVerificationError) as ei:
            verify_twitter_hmac(b"x", "junk", TWITTER_SECRET)
        assert ei.value.reason == "malformed_header"

    def test_wrong_secret_raises(self) -> None:
        body = b"x"
        sig = _twitter_sig(body, secret="other")
        with pytest.raises(WebhookVerificationError) as ei:
            verify_twitter_hmac(body, sig, TWITTER_SECRET)
        assert ei.value.reason == "signature_mismatch"

    def test_missing_secret_with_require_raises(self) -> None:
        with pytest.raises(WebhookVerificationError) as ei:
            verify_twitter_hmac(b"x", "sha256=abc", None)
        assert ei.value.reason == "missing_secret"

    def test_missing_secret_without_require_skips(self) -> None:
        verify_twitter_hmac(b"x", "sha256=abc", None, require_secret=False)


# ---------------------------------------------------------------------------
# Exception contract
# ---------------------------------------------------------------------------


class TestWebhookVerificationError:
    def test_unknown_reason_rejected(self) -> None:
        with pytest.raises(ValueError):
            WebhookVerificationError("not_a_reason", "whatsapp")

    def test_known_reasons_carry_provider(self) -> None:
        err = WebhookVerificationError("missing_header", "telegram")
        assert err.reason == "missing_header"
        assert err.provider == "telegram"
        assert "telegram" in str(err)
