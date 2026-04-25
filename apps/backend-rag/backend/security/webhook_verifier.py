"""Webhook signature/secret verification primitives.

Pure functions that can be reused by every public-channel router
(WhatsApp, Instagram, Telegram, X/Twitter). Each function raises
``WebhookVerificationError`` with a stable ``reason`` code on failure
and returns ``None`` on success — callers decide HTTP status mapping.

Design contract:

* No I/O, no logging side effects in the hot path. Logging happens at the
  call site so per-channel context (correlation ids, headers) stays there.
* Constant-time comparison for every secret/HMAC check via
  :func:`hmac.compare_digest`.
* ``require_secret`` is the only knob that controls fail-open vs fail-closed
  when the configured secret is missing. Production callers pass
  ``require_secret=True``; local/dev may pass ``False``. The default is
  ``True`` so a forgotten flag fails safely.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

__all__ = [
    "WebhookVerificationError",
    "verify_meta_hmac",
    "verify_telegram_secret",
    "verify_twitter_hmac",
]


class WebhookVerificationError(Exception):
    """Raised when a webhook signature/secret check fails.

    Attributes:
        reason: Stable machine-readable code (used for metrics/audit).
                One of: ``missing_secret``, ``missing_header``,
                ``malformed_header``, ``signature_mismatch``,
                ``empty_body``.
        provider: Channel name (``whatsapp``, ``instagram``, ``telegram``,
                  ``twitter``) — populated by the calling helper.
    """

    REASONS = frozenset(
        {
            "missing_secret",
            "missing_header",
            "malformed_header",
            "signature_mismatch",
            "empty_body",
        },
    )

    def __init__(self, reason: str, provider: str, message: str | None = None) -> None:
        if reason not in self.REASONS:
            raise ValueError(f"unknown webhook verification reason: {reason!r}")
        self.reason = reason
        self.provider = provider
        super().__init__(message or f"{provider}: {reason}")


def _strip_sha256_prefix(value: str) -> str | None:
    """Return the hex digest portion of a ``sha256=<hex>`` header.

    Returns ``None`` if the prefix is missing — callers treat that as a
    malformed header.
    """
    prefix = "sha256="
    if not value.startswith(prefix):
        return None
    return value[len(prefix):]


def verify_meta_hmac(
    body: bytes,
    signature_header: str | None,
    app_secret: str | None,
    *,
    provider: str,
    require_secret: bool = True,
) -> None:
    """Verify Meta-style ``X-Hub-Signature-256`` HMAC-SHA256.

    Used by WhatsApp Cloud API and Instagram Graph webhooks. Both providers
    sign the raw POST body with the Meta App Secret.

    Args:
        body: Raw request body bytes (must be the *exact* bytes received,
              before any JSON parsing/normalization).
        signature_header: Value of ``X-Hub-Signature-256`` (format
              ``sha256=<hex>``), or ``None`` if absent.
        app_secret: Meta App Secret, or ``None`` if not configured.
        provider: Channel label for the error (``whatsapp`` or
                  ``instagram``).
        require_secret: When ``True`` (default), missing ``app_secret``
                  is treated as a configuration error and verification
                  fails. When ``False``, verification is *skipped*
                  silently — only acceptable in dev/test contexts.

    Raises:
        WebhookVerificationError: On any verification failure.
    """
    if not app_secret:
        if require_secret:
            raise WebhookVerificationError("missing_secret", provider)
        return  # dev mode: skip verification

    if not signature_header:
        raise WebhookVerificationError("missing_header", provider)

    received_digest = _strip_sha256_prefix(signature_header)
    if received_digest is None:
        raise WebhookVerificationError("malformed_header", provider)

    expected_digest = hmac.new(
        app_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(received_digest, expected_digest):
        raise WebhookVerificationError("signature_mismatch", provider)


def verify_telegram_secret(
    header_value: str | None,
    expected_secret: str | None,
    *,
    require_secret: bool = True,
    provider: str = "telegram",
) -> None:
    """Verify ``X-Telegram-Bot-Api-Secret-Token`` shared-secret header.

    Telegram does not sign the body — instead it echoes back a static
    secret that was registered with ``setWebhook``. Constant-time
    comparison avoids leaking the secret length via timing.

    Args:
        header_value: Value of ``X-Telegram-Bot-Api-Secret-Token``, or
                ``None`` if absent.
        expected_secret: Secret previously sent to ``setWebhook``, or
                ``None`` if not configured.
        require_secret: See :func:`verify_meta_hmac`.
        provider: Channel label (default ``telegram``).

    Raises:
        WebhookVerificationError: On any verification failure.
    """
    if not expected_secret:
        if require_secret:
            raise WebhookVerificationError("missing_secret", provider)
        return

    if not header_value:
        raise WebhookVerificationError("missing_header", provider)

    if not hmac.compare_digest(header_value, expected_secret):
        raise WebhookVerificationError("signature_mismatch", provider)


def verify_twitter_hmac(
    body: bytes,
    signature_header: str | None,
    consumer_secret: str | None,
    *,
    require_secret: bool = True,
    provider: str = "twitter",
) -> None:
    """Verify ``X-Twitter-Webhooks-Signature`` HMAC-SHA256 (base64).

    Twitter Account Activity API signs the raw body with the app's
    consumer secret using HMAC-SHA256, then base64-encodes the digest
    (NOT hex like Meta). The header format is also ``sha256=<base64>``.

    Args:
        body: Raw request body bytes.
        signature_header: Value of ``X-Twitter-Webhooks-Signature``.
        consumer_secret: App consumer secret.
        require_secret: See :func:`verify_meta_hmac`.
        provider: Channel label (default ``twitter``).

    Raises:
        WebhookVerificationError: On any verification failure.
    """
    if not consumer_secret:
        if require_secret:
            raise WebhookVerificationError("missing_secret", provider)
        return

    if not signature_header:
        raise WebhookVerificationError("missing_header", provider)

    received_b64 = _strip_sha256_prefix(signature_header)
    if received_b64 is None:
        raise WebhookVerificationError("malformed_header", provider)

    expected_digest = hmac.new(
        consumer_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected_b64 = base64.b64encode(expected_digest).decode("ascii")

    if not hmac.compare_digest(received_b64, expected_b64):
        raise WebhookVerificationError("signature_mismatch", provider)
