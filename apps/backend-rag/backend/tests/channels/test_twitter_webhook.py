"""Tests for X/Twitter webhook CRC challenge and signature verification."""

import base64
import hashlib
import hmac

import pytest

from backend.app.routers.twitter import _compute_crc_response, _verify_webhook_signature


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONSUMER_SECRET = "test_consumer_secret_abc123"
CRC_TOKEN = "test_crc_token_xyz789"


def _expected_response_token(crc_token: str, secret: str) -> str:
    """Compute the expected CRC response using stdlib directly."""
    digest = hmac.new(
        secret.encode("utf-8"),
        crc_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"sha256={base64.b64encode(digest).decode('ascii')}"


# ---------------------------------------------------------------------------
# _compute_crc_response
# ---------------------------------------------------------------------------


class TestComputeCrcResponse:
    def test_returns_sha256_prefixed_token(self) -> None:
        result = _compute_crc_response(CRC_TOKEN, CONSUMER_SECRET)
        assert result.startswith("sha256=")

    def test_matches_manual_hmac(self) -> None:
        result = _compute_crc_response(CRC_TOKEN, CONSUMER_SECRET)
        expected = _expected_response_token(CRC_TOKEN, CONSUMER_SECRET)
        assert result == expected

    def test_different_secrets_produce_different_tokens(self) -> None:
        token_a = _compute_crc_response(CRC_TOKEN, "secret_a")
        token_b = _compute_crc_response(CRC_TOKEN, "secret_b")
        assert token_a != token_b

    def test_different_crc_tokens_produce_different_results(self) -> None:
        token_a = _compute_crc_response("token_a", CONSUMER_SECRET)
        token_b = _compute_crc_response("token_b", CONSUMER_SECRET)
        assert token_a != token_b

    def test_base64_output_is_valid(self) -> None:
        result = _compute_crc_response(CRC_TOKEN, CONSUMER_SECRET)
        b64_part = result.removeprefix("sha256=")
        # Should not raise
        decoded = base64.b64decode(b64_part)
        assert len(decoded) == 32  # SHA-256 = 32 bytes


# ---------------------------------------------------------------------------
# _verify_webhook_signature
# ---------------------------------------------------------------------------


class TestVerifyWebhookSignature:
    def _make_signature(self, body: str, secret: str) -> str:
        digest = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return f"sha256={base64.b64encode(digest).decode('ascii')}"

    def test_valid_signature_returns_true(self) -> None:
        body = '{"events": []}'
        sig = self._make_signature(body, CONSUMER_SECRET)
        assert _verify_webhook_signature(body.encode(), sig, CONSUMER_SECRET) is True

    def test_invalid_signature_returns_false(self) -> None:
        body = '{"events": []}'
        assert (
            _verify_webhook_signature(body.encode(), "sha256=AAAA", CONSUMER_SECRET)
            is False
        )

    def test_missing_signature_returns_false(self) -> None:
        assert _verify_webhook_signature(b"body", None, CONSUMER_SECRET) is False

    def test_empty_signature_returns_false(self) -> None:
        assert _verify_webhook_signature(b"body", "", CONSUMER_SECRET) is False

    def test_tampered_body_returns_false(self) -> None:
        body_original = '{"events": []}'
        sig = self._make_signature(body_original, CONSUMER_SECRET)
        body_tampered = '{"events": ["malicious"]}'
        assert (
            _verify_webhook_signature(body_tampered.encode(), sig, CONSUMER_SECRET)
            is False
        )


# ---------------------------------------------------------------------------
# CRC endpoint (via FastAPI TestClient)
# ---------------------------------------------------------------------------


class TestCrcEndpoint:
    @pytest.fixture()
    def client(self, monkeypatch: pytest.MonkeyPatch):
        """Create a test client with mocked settings."""
        monkeypatch.setattr(
            "backend.app.routers.twitter.settings",
            type("S", (), {"x_consumer_secret": CONSUMER_SECRET})(),
        )
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.app.routers.twitter import webhook_router

        app = FastAPI()
        app.include_router(webhook_router)
        return TestClient(app)

    def test_crc_success(self, client) -> None:  # type: ignore[no-untyped-def]
        resp = client.get("/webhook/twitter", params={"crc_token": CRC_TOKEN})
        assert resp.status_code == 200
        data = resp.json()
        assert "response_token" in data
        expected = _expected_response_token(CRC_TOKEN, CONSUMER_SECRET)
        assert data["response_token"] == expected

    def test_crc_missing_token_returns_400(self, client) -> None:  # type: ignore[no-untyped-def]
        resp = client.get("/webhook/twitter")
        assert resp.status_code == 400

    def test_crc_content_type_is_json(self, client) -> None:  # type: ignore[no-untyped-def]
        resp = client.get("/webhook/twitter", params={"crc_token": CRC_TOKEN})
        assert "application/json" in resp.headers["content-type"]

    def test_crc_no_secret_returns_500(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "backend.app.routers.twitter.settings",
            type("S", (), {"x_consumer_secret": None})(),
        )
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.app.routers.twitter import webhook_router

        app = FastAPI()
        app.include_router(webhook_router)
        c = TestClient(app)
        resp = c.get("/webhook/twitter", params={"crc_token": CRC_TOKEN})
        assert resp.status_code == 500
