"""Smoke tests for the NLM HTTP Bridge.

Why these exist: nlm-bridge runs as a launchd daemon on Pro
(`com.balizero.nlm-bridge.plist`, port 18790) and is a Fly→Pro lifeline
for NotebookLM queries. Before this file there were zero tests in the
app — any change to HMAC, rate-limit, or schema went straight to prod.

Scope: pure-function and FastAPI-app-level smoke tests that DO NOT need
the real `notebooklm_tools` library or live tokens. Anything that hits
NLM is mocked. The `/nlm/health` endpoint is exercised via TestClient so
the lifespan path is covered.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

# nlm-bridge is a flat-layout app (not a package). Make its modules
# importable without depending on a CWD assumption.
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


# ---------------------------------------------------------------------------
# hmac_verify
# ---------------------------------------------------------------------------

class TestHmacVerify:
    """`sign_request` / `verify_signature` are the only thing standing
    between a public Pro daemon and arbitrary RCE-by-NLM-query. They MUST
    be exercised."""

    def test_sign_and_verify_roundtrip(self) -> None:
        from hmac_verify import sign_request, verify_signature

        secret = "test-secret-123"
        payload = '{"notebook_id": "nb-1", "question": "hello"}'
        sig = sign_request(payload, secret)

        assert isinstance(sig, str)
        assert len(sig) == 64  # hex-encoded sha256
        assert verify_signature(payload, sig, secret) is True

    def test_verify_rejects_tampered_payload(self) -> None:
        from hmac_verify import sign_request, verify_signature

        secret = "test-secret-123"
        payload = '{"notebook_id": "nb-1", "question": "hello"}'
        sig = sign_request(payload, secret)

        assert verify_signature(payload + " ", sig, secret) is False
        assert verify_signature(payload.upper(), sig, secret) is False

    def test_verify_rejects_wrong_secret(self) -> None:
        from hmac_verify import sign_request, verify_signature

        payload = "abc"
        sig = sign_request(payload, "secret-A")
        assert verify_signature(payload, sig, "secret-B") is False

    def test_verify_uses_constant_time_compare(self) -> None:
        """Defense against timing oracle: must use hmac.compare_digest.
        We can't time-test it, so we just assert the helper is called by
        importing and reading the module source — a regression where a
        future refactor switches to `==` would break the timing assumption.
        """
        from hmac_verify import verify_signature

        src = (Path(__file__).resolve().parent / "hmac_verify.py").read_text()
        assert "hmac.compare_digest" in src, (
            "verify_signature must use hmac.compare_digest to prevent "
            "timing oracle attacks against the bridge"
        )
        # Also exercise the function so the import is not dead code.
        assert verify_signature("x", "0" * 64, "k") is False

    def test_sign_accepts_bytes_and_str(self) -> None:
        from hmac_verify import sign_request

        s_str = sign_request("payload", "k")
        s_bytes = sign_request(b"payload", "k")
        assert s_str == s_bytes


# ---------------------------------------------------------------------------
# main: rate limiter + health
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_main(monkeypatch):
    """Reset the in-memory rate-limit window between tests.

    `main._rate_window` is module-level state; a previous test's traffic
    would otherwise leak into the next one's quota.
    """
    # Force the bridge into "no NLM library" mode so importing main.py
    # doesn't hit the network. Importing main.py also triggers a
    # `notebooklm_tools` import attempt — that's wrapped in try/except so
    # it doesn't fail collection here.
    monkeypatch.setenv("NLM_BRIDGE_SECRET", "")
    if "main" in sys.modules:
        del sys.modules["main"]
    import main  # noqa: WPS433 — module reload is the point
    main._rate_window.clear()
    main._request_count = 0
    return main


class TestRateLimiter:
    """`_check_rate_limit` is the only protection against a runaway Fly
    machine hammering the bridge. Limit is 10 req/min per IP."""

    def test_allows_under_limit(self, fresh_main) -> None:
        # 9 requests in burst — under the 10-req limit
        for _ in range(9):
            fresh_main._check_rate_limit("10.0.0.1")

    def test_rejects_at_limit(self, fresh_main) -> None:
        from fastapi import HTTPException

        for _ in range(10):
            fresh_main._check_rate_limit("10.0.0.2")
        with pytest.raises(HTTPException) as exc_info:
            fresh_main._check_rate_limit("10.0.0.2")
        assert exc_info.value.status_code == 429

    def test_separate_ips_have_separate_quotas(self, fresh_main) -> None:
        for _ in range(10):
            fresh_main._check_rate_limit("10.0.0.3")
        # Different IP — should still be allowed
        fresh_main._check_rate_limit("10.0.0.4")

    def test_old_entries_pruned(self, fresh_main, monkeypatch) -> None:
        # Backdate 10 timestamps to 2 minutes ago — outside the 60s window
        ip = "10.0.0.5"
        old = time.time() - 120
        fresh_main._rate_window[ip] = [old] * 10

        # New request should succeed because old entries get pruned
        fresh_main._check_rate_limit(ip)
        # Window now contains only the fresh timestamp
        assert len(fresh_main._rate_window[ip]) == 1


class TestHmacVerifyMiddleware:
    """`_verify_hmac` skips when NLM_BRIDGE_SECRET is unset (local dev)
    but enforces when it is set."""

    def test_skips_when_secret_unset(self, fresh_main, monkeypatch) -> None:
        monkeypatch.setenv("NLM_BRIDGE_SECRET", "")
        # Should NOT raise even with no signature header
        fresh_main._verify_hmac(b"any-body", None)

    def test_rejects_missing_signature_when_secret_set(
        self, fresh_main, monkeypatch,
    ) -> None:
        from fastapi import HTTPException
        monkeypatch.setenv("NLM_BRIDGE_SECRET", "live-secret")
        with pytest.raises(HTTPException) as exc_info:
            fresh_main._verify_hmac(b"body", None)
        assert exc_info.value.status_code == 401

    def test_rejects_bad_signature(self, fresh_main, monkeypatch) -> None:
        from fastapi import HTTPException
        monkeypatch.setenv("NLM_BRIDGE_SECRET", "live-secret")
        with pytest.raises(HTTPException) as exc_info:
            fresh_main._verify_hmac(b"body", "deadbeef" * 8)
        assert exc_info.value.status_code == 401

    def test_accepts_valid_signature(self, fresh_main, monkeypatch) -> None:
        monkeypatch.setenv("NLM_BRIDGE_SECRET", "live-secret")
        from hmac_verify import sign_request

        body = b'{"notebook_id":"nb-1","question":"q"}'
        sig = sign_request(body, "live-secret")
        # Should NOT raise
        fresh_main._verify_hmac(body, sig)


class TestHealthEndpoint:
    """The /nlm/health endpoint is the bridge's own liveness probe and is
    polled by the Cell heartbeat aggregator. It must respond without
    requiring a working NLM client."""

    def test_health_returns_200_without_nlm(self, fresh_main) -> None:
        from fastapi.testclient import TestClient

        # `lifespan` tries to load tokens; without the lib installed this
        # is a no-op (HAS_NLM_LIB is False at import time).
        with TestClient(fresh_main.app) as client:
            resp = client.get("/nlm/health")
            assert resp.status_code == 200
            body = resp.json()
            # "degraded" is the expected state when notebooklm_tools is
            # not installed (test env) — the bridge still serves /health
            # so the Cell heartbeat aggregator can distinguish "process
            # alive but lib missing" from "process down".
            assert body["status"] in (
                "ok", "ready", "healthy", "starting", "degraded",
            )
            assert "uptime" in body
            assert "request_count" in body
            assert isinstance(body["uptime"], (int, float))
            assert body["uptime"] >= 0
