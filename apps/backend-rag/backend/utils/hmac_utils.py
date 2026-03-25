"""HMAC utilities for NLM bridge request signing and verification."""

import hashlib
import hmac
import os


_BRIDGE_SECRET = os.getenv("NLM_BRIDGE_SECRET", "")


def sign_request(payload: str | bytes, secret: str = "") -> str:
    """Generate HMAC-SHA256 signature for a payload.

    Args:
        payload: The request body to sign
        secret: Shared secret (defaults to NLM_BRIDGE_SECRET env var)

    Returns:
        Hex-encoded HMAC-SHA256 signature
    """
    key = (secret or _BRIDGE_SECRET).encode()
    data = payload.encode() if isinstance(payload, str) else payload
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def verify_signature(payload: str | bytes, signature: str, secret: str = "") -> bool:
    """Verify an HMAC-SHA256 signature.

    Args:
        payload: The original request body
        signature: The signature to verify
        secret: Shared secret (defaults to NLM_BRIDGE_SECRET env var)

    Returns:
        True if signature matches
    """
    expected = sign_request(payload, secret)
    return hmac.compare_digest(expected, signature)
