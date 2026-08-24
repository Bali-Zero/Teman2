"""HMAC-SHA256 signer for Meta (WhatsApp/Instagram) webhook payloads.

Meta signs every webhook delivery with the same mechanism —
``X-Hub-Signature-256: sha256=<hex>``, computed over the EXACT raw request
body bytes using the app's App Secret — regardless of product surface. This
module signs over ``bytes``, never over a re-serialized ``dict``, because
re-serializing (key reordering, whitespace, unicode escaping) changes the
byte stream and therefore the signature. That is the single most common way
a hand-rolled webhook signer silently fails against Meta's real verifier,
and it is exactly the failure mode this module exists to make impossible to
introduce by accident: ``sign_payload`` takes ``bytes`` in its signature,
not a ``dict``, so there is no re-serialization step to get wrong.

The production verifier this signer targets is
``backend.app.routers.whatsapp_chat._verify_whatsapp_signature`` (read,
never modified, per the B6a mandate). ``test_webhook_signer.py`` proves a
signature produced here is accepted by that exact function, and that
mutating a single byte of the body is rejected by it — the RED case.

Instagram's webhook POST handler (``backend.app.routers.instagram_chat``)
does not verify ``X-Hub-Signature-256`` today (checked 2026-08-25 — no
verifier of any kind on that router). This module still signs Instagram
payloads: Meta computes the header uniformly across products, and a future
IG verifier only needs to look like the WhatsApp one to be provable here.
That gap is not this lane's to fix — see the B6a report for the pointer.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_PREFIX = "sha256="


def sign_payload(raw_body: bytes, app_secret: str) -> str:
    """Return the ``X-Hub-Signature-256`` header value for ``raw_body``.

    Args:
        raw_body: the EXACT bytes that will be sent as the request body.
            Signing a re-encoded ``json.dumps(payload)`` of logically the
            same content is a DIFFERENT byte stream and will not match what
            a byte-for-byte replay produces — see
            ``test_signature_over_reserialized_json_body_does_not_match``
            in ``test_webhook_signer.py``.
        app_secret: the Meta App Secret (``WHATSAPP_APP_SECRET`` / the
            equivalent Instagram app secret — Meta uses one App Secret per
            App, shared across the products registered under it).

    Returns:
        ``"sha256=<64 lowercase hex chars>"`` — exactly the format Meta
        sends and ``_verify_whatsapp_signature`` parses.

    Raises:
        TypeError: if ``raw_body`` is not ``bytes`` (a ``str`` or ``dict``
            passed here is almost always the re-serialization bug this
            module exists to prevent — fail loudly instead of silently
            encoding it for the caller).
    """
    if not isinstance(raw_body, bytes):
        raise TypeError(
            f"raw_body must be bytes (the exact wire body), got "
            f"{type(raw_body).__name__} — encode it yourself first so the "
            f"encoding step is visible at the call site, not hidden here"
        )
    digest = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def tamper(raw_body: bytes, *, byte_index: int = 0) -> bytes:
    """Flip one bit of ``raw_body`` at ``byte_index``.

    The minimal "byte-different body" fixture: same length, same shape,
    one bit different — used to prove a signature computed for the
    original body is rejected for the tampered one (a naive verifier that
    e.g. compares lengths or does a substring check could pass a
    wholesale-different body by accident; flipping one bit inside the
    original leaves no such escape hatch).

    Args:
        raw_body: the body to mutate. Must be non-empty.
        byte_index: which byte to flip (wrapped modulo length so any int
            is safe to pass).

    Returns:
        A new ``bytes`` object, same length as ``raw_body``, differing in
        exactly one byte.
    """
    if not raw_body:
        raise ValueError("cannot tamper an empty body")
    index = byte_index % len(raw_body)
    mutated = bytearray(raw_body)
    mutated[index] ^= 0x01
    return bytes(mutated)


def malformed_signature_header(raw_body: bytes, app_secret: str) -> str:
    """A correctly-computed digest with the ``sha256=`` prefix stripped —
    the "malformed sha256= value" scenario from the research capture §5.2.
    """
    valid = sign_payload(raw_body, app_secret)
    return valid[len(SIGNATURE_PREFIX) :]
