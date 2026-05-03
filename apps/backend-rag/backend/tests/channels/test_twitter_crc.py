"""Twitter CRC re-enablement verification (P0-6 zero-crash audit 2026-04-29).

The X CRC handshake (HMAC SHA-256) was already implemented at
``backend/app/routers/twitter.py``, but the router was DISABLED in
``backend/app/setup/router_registration.py`` (4 places, audit 2026-04-03).

These tests verify:

1. The CRC endpoint signs with TWITTER_CONSUMER_SECRET / x_consumer_secret.
2. The router is now actively registered in router_manifest.py.
3. The consumer-secret env var is read from settings (not hardcoded).
"""
from __future__ import annotations

import base64
import hashlib
import hmac

import pytest


CONSUMER_SECRET = "test_consumer_secret_p0_6_validation"
CRC_TOKEN = "ChallengeFromTwitter_p0_6"


def _expected_response_token(crc_token: str, secret: str) -> str:
    """Independent stdlib computation of the expected HMAC SHA-256 response."""
    digest = hmac.new(
        secret.encode("utf-8"),
        crc_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"sha256={base64.b64encode(digest).decode('ascii')}"


def test_crc_returns_signed_response_token():
    """CRC endpoint computes HMAC SHA-256 with consumer_secret."""
    from backend.app.routers.twitter import _compute_crc_response

    actual = _compute_crc_response(CRC_TOKEN, CONSUMER_SECRET)
    expected = _expected_response_token(CRC_TOKEN, CONSUMER_SECRET)

    assert actual == expected
    assert actual.startswith("sha256=")
    # Decoded must be 32 bytes (SHA-256 output)
    decoded = base64.b64decode(actual.removeprefix("sha256="))
    assert len(decoded) == 32


def test_crc_uses_consumer_secret_from_env(monkeypatch: pytest.MonkeyPatch):
    """The CRC handler reads x_consumer_secret from settings (not hardcoded)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setattr(
        "backend.app.routers.twitter.settings",
        type("S", (), {"x_consumer_secret": CONSUMER_SECRET})(),
    )
    from backend.app.routers.twitter import webhook_router

    app = FastAPI()
    app.include_router(webhook_router)
    client = TestClient(app)

    resp = client.get("/webhook/twitter", params={"crc_token": CRC_TOKEN})
    assert resp.status_code == 200
    assert resp.json()["response_token"] == _expected_response_token(
        CRC_TOKEN, CONSUMER_SECRET,
    )


def test_crc_returns_500_when_secret_unconfigured(monkeypatch: pytest.MonkeyPatch):
    """Misconfiguration produces a clean 500, never a half-signed response."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setattr(
        "backend.app.routers.twitter.settings",
        type("S", (), {"x_consumer_secret": None})(),
    )
    from backend.app.routers.twitter import webhook_router

    app = FastAPI()
    app.include_router(webhook_router)
    client = TestClient(app)

    resp = client.get("/webhook/twitter", params={"crc_token": CRC_TOKEN})
    assert resp.status_code == 500


def test_twitter_router_listed_in_manifest():
    """Twitter routers are registered in router_manifest.py (no longer in
    the disabled section)."""
    from backend.app.setup.router_manifest import ROUTER_MANIFEST

    twitter_entries = [r for r in ROUTER_MANIFEST if r.name == "twitter"]
    assert len(twitter_entries) >= 1, (
        "Twitter router must be re-enabled in router_manifest.py "
        "(P0-6 audit 2026-04-29 — was DISABLED 2026-04-03)"
    )

    # The webhook_router attribute should also be present
    has_webhook = any(
        r.attr == "webhook_router" for r in twitter_entries
    )
    assert has_webhook, (
        "twitter.webhook_router must be registered (CRC + ack-first endpoint)"
    )
