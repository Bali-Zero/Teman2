"""Tests for the IG long-lived token watchdog (Task 30).

All Graph API traffic is mocked via httpx.MockTransport — no real token is
ever used, no network call is ever made. The fake token values below are
synthetic markers, chosen to be greppable so the redaction tests can assert
they never leak into logs, reprs or exception messages.

Two token families are covered (the adversarial review of the first draft
proved the live Fly token is INSTAGRAM-family — graph.instagram.com — and a
facebook-only watchdog would have classified it invalid forever):
  instagram: refresh_access_token, expiry via state sidecar
  facebook:  /debug_token + fb_exchange_token
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from backend.services.measurer.ig_token_watchdog import (
    DEFAULT_REFRESH_THRESHOLD_DAYS,
    IGTokenWatchdogError,
    RefreshedToken,
    TokenStatus,
    inspect_token,
    persist_token_to_env_file,
    read_state_expiry,
    refresh_instagram_token,
    refresh_long_lived_token,
    run_from_env,
    run_watchdog,
    write_state_expiry,
)

FAKE_TOKEN = "FAKE-OLD-TOKEN-a1b2c3"
FAKE_NEW_TOKEN = "FAKE-NEW-TOKEN-d4e5f6"
APP_ID = "123456"
APP_SECRET = "FAKE-APP-SECRET-x9y8"

NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


def _epoch(dt: datetime) -> int:
    return int(dt.timestamp())


class GraphHandler:
    """Programmable fake Graph API (both hosts). Counts calls per endpoint."""

    def __init__(
        self,
        *,
        expires_at: int | None = None,
        omit_expires_at: bool = False,
        is_valid: bool = True,
        debug_error: dict | None = None,
        refresh_error: dict | None = None,
        refresh_expires_in: int = 60 * 86400,
        network_error: bool = False,
        non_json: bool = False,
    ) -> None:
        self.expires_at = expires_at
        self.omit_expires_at = omit_expires_at
        self.is_valid = is_valid
        self.debug_error = debug_error
        self.refresh_error = refresh_error
        self.refresh_expires_in = refresh_expires_in
        self.network_error = network_error
        self.non_json = non_json
        self.debug_calls = 0
        self.fb_refresh_calls = 0
        self.ig_refresh_calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.network_error:
            raise httpx.ConnectError("boom", request=request)
        if self.non_json:
            return httpx.Response(502, text="<html>bad gateway</html>")
        if request.url.path.endswith("/debug_token"):
            self.debug_calls += 1
            if self.debug_error is not None:
                return httpx.Response(400, json={"error": self.debug_error})
            data: dict = {"is_valid": self.is_valid, "type": "USER"}
            if not self.omit_expires_at and self.expires_at is not None:
                data["expires_at"] = self.expires_at
            return httpx.Response(200, json={"data": data})
        if request.url.path.endswith("/oauth/access_token"):
            self.fb_refresh_calls += 1
            return self._refresh_response()
        if request.url.path.endswith("/refresh_access_token"):
            assert request.url.host == "graph.instagram.com"
            self.ig_refresh_calls += 1
            return self._refresh_response()
        raise AssertionError(f"unexpected Graph call: {request.url.path}")

    def _refresh_response(self) -> httpx.Response:
        if self.refresh_error is not None:
            return httpx.Response(400, json={"error": self.refresh_error})
        return httpx.Response(
            200,
            json={
                "access_token": FAKE_NEW_TOKEN,
                "token_type": "bearer",
                "expires_in": self.refresh_expires_in,
            },
        )


def _client(handler: GraphHandler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _state(tmp_path: Path, days_left: float) -> Path:
    p = tmp_path / "state.json"
    write_state_expiry(p, NOW + timedelta(days=days_left), refreshed_at=NOW)
    return p


# ── instagram family (the DEFAULT — the live token's family) ──


@pytest.mark.asyncio
async def test_ig_refresh_returns_new_token_and_expiry():
    handler = GraphHandler()
    async with _client(handler) as client:
        refreshed = await refresh_instagram_token(
            FAKE_TOKEN, http_client=client, now=NOW
        )
    assert refreshed.token == FAKE_NEW_TOKEN
    assert refreshed.expires_at == NOW + timedelta(days=60)
    assert handler.ig_refresh_calls == 1


@pytest.mark.asyncio
async def test_ig_watchdog_refreshes_near_expired_state(tmp_path, caplog):
    """GUILT: state says 3 days left → refresh fires on graph.instagram.com."""
    handler = GraphHandler()
    state = _state(tmp_path, days_left=3)
    async with _client(handler) as client:
        with caplog.at_level("INFO"):
            outcome = await run_watchdog(
                FAKE_TOKEN,
                family="instagram",
                state_file=state,
                http_client=client,
                now=NOW,
            )
    assert outcome.action == "refreshed"
    assert outcome.new_token == FAKE_NEW_TOKEN
    assert handler.ig_refresh_calls == 1
    assert any("[ig-token-watchdog] refreshed" in r.message for r in caplog.records)
    # State sidecar updated to the NEW expiry, and carries no secret.
    assert read_state_expiry(state) == NOW + timedelta(days=60)
    assert FAKE_NEW_TOKEN not in state.read_text()


@pytest.mark.asyncio
async def test_ig_watchdog_skips_fresh_state(tmp_path):
    """INNOCENCE: state says 45 days left → NO network call at all."""
    handler = GraphHandler()
    state = _state(tmp_path, days_left=45)
    async with _client(handler) as client:
        outcome = await run_watchdog(
            FAKE_TOKEN,
            family="instagram",
            state_file=state,
            http_client=client,
            now=NOW,
        )
    assert outcome.action == "fresh"
    assert handler.ig_refresh_calls == 0


@pytest.mark.asyncio
async def test_ig_watchdog_no_state_refreshes_conservatively(tmp_path):
    """Unknown expiry (no state sidecar) → refresh, never assume immortality."""
    handler = GraphHandler()
    async with _client(handler) as client:
        outcome = await run_watchdog(
            FAKE_TOKEN, family="instagram", http_client=client, now=NOW
        )
    assert outcome.action == "refreshed"
    assert handler.ig_refresh_calls == 1


@pytest.mark.asyncio
async def test_ig_watchdog_refresh_failure_reports_error():
    handler = GraphHandler(
        refresh_error={"message": "Cannot parse access token", "code": 190}
    )
    async with _client(handler) as client:
        outcome = await run_watchdog(
            FAKE_TOKEN, family="instagram", http_client=client, now=NOW
        )
    assert outcome.action == "error"
    assert outcome.new_token is None


# ── facebook family ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_fb_inspect_valid_token_reports_expiry():
    handler = GraphHandler(expires_at=_epoch(NOW + timedelta(days=30)))
    async with _client(handler) as client:
        status = await inspect_token(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
    assert status.is_valid is True
    assert status.expires_at == NOW + timedelta(days=30)
    assert status.days_remaining == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_fb_inspect_explicit_zero_is_never_expiring():
    handler = GraphHandler(expires_at=0)
    async with _client(handler) as client:
        status = await inspect_token(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
    assert status.is_valid and status.never_expires is True


@pytest.mark.asyncio
async def test_fb_inspect_absent_expiry_is_unknown_not_immortal():
    """Field ABSENT != explicit 0: unknown expiry must trigger a refresh."""
    handler = GraphHandler(omit_expires_at=True)
    async with _client(handler) as client:
        status = await inspect_token(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
        assert status.is_valid and status.never_expires is False
        assert status.days_remaining is None
        outcome = await run_watchdog(
            FAKE_TOKEN, APP_ID, APP_SECRET, family="facebook",
            http_client=client, now=NOW,
        )
    assert outcome.action == "refreshed"
    assert handler.fb_refresh_calls == 1


@pytest.mark.asyncio
async def test_fb_inspect_invalid_token_error_190():
    handler = GraphHandler(
        debug_error={"message": "Cannot parse access token", "code": 190}
    )
    async with _client(handler) as client:
        status = await inspect_token(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
    assert status.is_valid is False
    assert "Cannot parse access token" in (status.error or "")


@pytest.mark.asyncio
async def test_fb_refresh_returns_new_token_and_expiry():
    handler = GraphHandler()
    async with _client(handler) as client:
        refreshed = await refresh_long_lived_token(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
    assert refreshed.token == FAKE_NEW_TOKEN
    assert refreshed.expires_at == NOW + timedelta(days=60)
    assert handler.fb_refresh_calls == 1


@pytest.mark.asyncio
async def test_fb_watchdog_refreshes_near_expired_token(caplog):
    """GUILT: token expiring inside the threshold → refresh happens."""
    handler = GraphHandler(expires_at=_epoch(NOW + timedelta(days=3)))
    async with _client(handler) as client:
        with caplog.at_level("INFO"):
            outcome = await run_watchdog(
                FAKE_TOKEN, APP_ID, APP_SECRET, family="facebook",
                http_client=client, now=NOW,
            )
    assert outcome.action == "refreshed"
    assert outcome.new_token == FAKE_NEW_TOKEN
    assert handler.fb_refresh_calls == 1
    assert any("[ig-token-watchdog] refreshed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_fb_watchdog_skips_fresh_token():
    """INNOCENCE: token with plenty of life left → NO refresh call."""
    handler = GraphHandler(expires_at=_epoch(NOW + timedelta(days=45)))
    async with _client(handler) as client:
        outcome = await run_watchdog(
            FAKE_TOKEN, APP_ID, APP_SECRET, family="facebook",
            http_client=client, now=NOW,
        )
    assert outcome.action == "fresh"
    assert outcome.new_token is None
    assert handler.fb_refresh_calls == 0


@pytest.mark.asyncio
async def test_fb_watchdog_invalid_token_no_refresh_attempt():
    handler = GraphHandler(
        debug_error={"message": "Cannot parse access token", "code": 190}
    )
    async with _client(handler) as client:
        outcome = await run_watchdog(
            FAKE_TOKEN, APP_ID, APP_SECRET, family="facebook",
            http_client=client, now=NOW,
        )
    assert outcome.action == "invalid"
    assert handler.fb_refresh_calls == 0


@pytest.mark.asyncio
async def test_fb_watchdog_custom_threshold():
    handler = GraphHandler(expires_at=_epoch(NOW + timedelta(days=10)))
    async with _client(handler) as client:
        outcome = await run_watchdog(
            FAKE_TOKEN, APP_ID, APP_SECRET, family="facebook",
            http_client=client, now=NOW, threshold_days=14,
        )
    assert outcome.action == "refreshed"


@pytest.mark.asyncio
async def test_watchdog_rejects_unknown_family():
    with pytest.raises(ValueError):
        await run_watchdog(FAKE_TOKEN, family="tiktok", now=NOW)


@pytest.mark.asyncio
async def test_fb_watchdog_requires_app_credentials():
    with pytest.raises(ValueError):
        await run_watchdog(FAKE_TOKEN, family="facebook", now=NOW)


# ── error-path contract (network / non-JSON never traceback) ──


@pytest.mark.asyncio
async def test_network_failure_maps_to_error_outcome_not_traceback():
    handler = GraphHandler(network_error=True)
    async with _client(handler) as client:
        fb = await run_watchdog(
            FAKE_TOKEN, APP_ID, APP_SECRET, family="facebook",
            http_client=client, now=NOW,
        )
        ig = await run_watchdog(
            FAKE_TOKEN, family="instagram", http_client=client, now=NOW
        )
    assert fb.action == "error"
    assert ig.action == "error"


@pytest.mark.asyncio
async def test_non_json_response_maps_to_error_outcome():
    handler = GraphHandler(non_json=True)
    async with _client(handler) as client:
        outcome = await run_watchdog(
            FAKE_TOKEN, family="instagram", http_client=client, now=NOW
        )
    assert outcome.action == "error"


# ── redaction (scar #4: no secret in cleartext) ───────────────


@pytest.mark.asyncio
async def test_refresh_error_message_never_contains_secrets():
    handler = GraphHandler(
        refresh_error={"message": "Invalid OAuth access token.", "code": 190}
    )
    async with _client(handler) as client:
        with pytest.raises(IGTokenWatchdogError) as excinfo:
            await refresh_long_lived_token(
                FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
            )
    assert FAKE_TOKEN not in str(excinfo.value)
    assert APP_SECRET not in str(excinfo.value)


@pytest.mark.asyncio
async def test_error_payload_echoing_token_is_redacted():
    """A proxy/WAF may echo the request URL (token inside) into the error
    message — the logged/raised message must scrub it."""
    handler = GraphHandler(
        refresh_error={
            "message": f"upstream rejected access_token={FAKE_TOKEN} for app",
            "code": 368,
        }
    )
    async with _client(handler) as client:
        with pytest.raises(IGTokenWatchdogError) as excinfo:
            await refresh_instagram_token(FAKE_TOKEN, http_client=client, now=NOW)
    assert FAKE_TOKEN not in str(excinfo.value)
    assert "<redacted>" in str(excinfo.value)


@pytest.mark.asyncio
async def test_no_token_value_in_any_log_record(caplog):
    handler = GraphHandler(expires_at=_epoch(NOW + timedelta(days=1)))
    async with _client(handler) as client:
        with caplog.at_level("DEBUG"):
            await run_watchdog(
                FAKE_TOKEN, APP_ID, APP_SECRET, family="facebook",
                http_client=client, now=NOW,
            )
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert FAKE_TOKEN not in joined
    assert FAKE_NEW_TOKEN not in joined
    assert APP_SECRET not in joined


def test_refreshed_token_repr_is_redacted():
    refreshed = RefreshedToken(token=FAKE_NEW_TOKEN, expires_at=NOW)
    assert FAKE_NEW_TOKEN not in repr(refreshed)
    assert FAKE_NEW_TOKEN not in str(refreshed)


def test_token_status_repr_has_no_secret_fields():
    status = TokenStatus(is_valid=True, expires_at=NOW, days_remaining=1.0)
    assert "TokenStatus" in repr(status)


# ── state sidecar ─────────────────────────────────────────────


def test_state_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    write_state_expiry(p, NOW + timedelta(days=42), refreshed_at=NOW)
    assert read_state_expiry(p) == NOW + timedelta(days=42)
    payload = json.loads(p.read_text())
    assert set(payload) == {"expires_at", "refreshed_at"}


def test_state_missing_or_corrupt_reads_none(tmp_path):
    assert read_state_expiry(tmp_path / "absent.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert read_state_expiry(bad) is None
    assert read_state_expiry(None) is None


# ── persist_token_to_env_file ─────────────────────────────────


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


def test_persist_replaces_existing_key(tmp_path: Path):
    env_file = tmp_path / "secrets.env"
    env_file.write_text(
        "OTHER_VAR=keepme\n"
        f"IG_LONG_LIVED_TOKEN={FAKE_TOKEN}\n"
        "TRAILING_VAR=alsokeep\n"
    )
    persist_token_to_env_file(env_file, FAKE_NEW_TOKEN)
    content = env_file.read_text()
    assert f"IG_LONG_LIVED_TOKEN={FAKE_NEW_TOKEN}\n" in content
    assert FAKE_TOKEN not in content
    assert "OTHER_VAR=keepme" in content
    assert "TRAILING_VAR=alsokeep" in content
    assert _mode(env_file) == 0o600


def test_persist_appends_when_key_missing(tmp_path: Path):
    env_file = tmp_path / "secrets.env"
    env_file.write_text("OTHER_VAR=keepme\n")
    persist_token_to_env_file(env_file, FAKE_NEW_TOKEN)
    content = env_file.read_text()
    assert f"IG_LONG_LIVED_TOKEN={FAKE_NEW_TOKEN}\n" in content
    assert "OTHER_VAR=keepme" in content
    assert _mode(env_file) == 0o600


def test_persist_respects_custom_key(tmp_path: Path):
    env_file = tmp_path / "secrets.env"
    env_file.write_text(f"INSTAGRAM_ACCESS_TOKEN={FAKE_TOKEN}\n")
    persist_token_to_env_file(
        env_file, FAKE_NEW_TOKEN, key="INSTAGRAM_ACCESS_TOKEN"
    )
    content = env_file.read_text()
    assert f"INSTAGRAM_ACCESS_TOKEN={FAKE_NEW_TOKEN}\n" in content
    assert FAKE_TOKEN not in content


def test_persist_refuses_missing_file(tmp_path: Path):
    with pytest.raises(IGTokenWatchdogError):
        persist_token_to_env_file(tmp_path / "nope.env", FAKE_NEW_TOKEN)


def test_default_threshold_is_seven_days():
    assert DEFAULT_REFRESH_THRESHOLD_DAYS == 7


# ── run_from_env: the CLI exit-code contract ──────────────────


@pytest.fixture
def clean_env(monkeypatch):
    for k in (
        "IG_LONG_LIVED_TOKEN", "INSTAGRAM_ACCESS_TOKEN", "IG_TOKEN_FAMILY",
        "META_APP_ID", "META_APP_SECRET", "IG_TOKEN_ENV_FILE",
        "IG_TOKEN_STATE_FILE", "IG_TOKEN_REFRESH_THRESHOLD_DAYS",
    ):
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


@pytest.mark.asyncio
async def test_cli_no_token_is_config_error(clean_env):
    assert await run_from_env() == 1


@pytest.mark.asyncio
async def test_cli_bad_family_is_config_error(clean_env):
    clean_env.setenv("IG_LONG_LIVED_TOKEN", FAKE_TOKEN)
    clean_env.setenv("IG_TOKEN_FAMILY", "tiktok")
    assert await run_from_env() == 1


@pytest.mark.asyncio
async def test_cli_facebook_without_app_creds_is_config_error(clean_env):
    clean_env.setenv("IG_LONG_LIVED_TOKEN", FAKE_TOKEN)
    clean_env.setenv("IG_TOKEN_FAMILY", "facebook")
    assert await run_from_env() == 1


@pytest.mark.asyncio
async def test_cli_bad_threshold_is_config_error(clean_env):
    clean_env.setenv("IG_LONG_LIVED_TOKEN", FAKE_TOKEN)
    clean_env.setenv("IG_TOKEN_REFRESH_THRESHOLD_DAYS", "soon")
    assert await run_from_env() == 1


@pytest.mark.asyncio
async def test_cli_refresh_without_persist_target_is_failure(clean_env):
    """Refreshed-but-dropped must NOT exit 0 — a green cron hiding a dropped
    token is famiglia #2 (esiste≠armato)."""
    clean_env.setenv("IG_LONG_LIVED_TOKEN", FAKE_TOKEN)  # instagram default
    handler = GraphHandler()
    async with _client(handler) as client:
        assert await run_from_env(http_client=client) == 2
    assert handler.ig_refresh_calls == 1


@pytest.mark.asyncio
async def test_cli_refresh_with_persist_target_succeeds(clean_env, tmp_path):
    env_file = tmp_path / "secrets.env"
    env_file.write_text(f"IG_LONG_LIVED_TOKEN={FAKE_TOKEN}\n")
    state_file = tmp_path / "state.json"
    clean_env.setenv("IG_LONG_LIVED_TOKEN", FAKE_TOKEN)
    clean_env.setenv("IG_TOKEN_ENV_FILE", str(env_file))
    clean_env.setenv("IG_TOKEN_STATE_FILE", str(state_file))
    handler = GraphHandler()
    async with _client(handler) as client:
        assert await run_from_env(http_client=client) == 0
    assert f"IG_LONG_LIVED_TOKEN={FAKE_NEW_TOKEN}" in env_file.read_text()
    assert read_state_expiry(state_file) is not None


@pytest.mark.asyncio
async def test_cli_fresh_state_exits_zero_without_network(clean_env, tmp_path):
    state_file = _state(tmp_path, days_left=50)
    clean_env.setenv("IG_LONG_LIVED_TOKEN", FAKE_TOKEN)
    clean_env.setenv("IG_TOKEN_STATE_FILE", str(state_file))
    handler = GraphHandler()
    async with _client(handler) as client:
        assert await run_from_env(http_client=client) == 0
    assert handler.ig_refresh_calls == 0


@pytest.mark.asyncio
async def test_cli_invalid_token_exits_two(clean_env):
    clean_env.setenv("IG_LONG_LIVED_TOKEN", FAKE_TOKEN)
    clean_env.setenv("IG_TOKEN_FAMILY", "facebook")
    clean_env.setenv("META_APP_ID", APP_ID)
    clean_env.setenv("META_APP_SECRET", APP_SECRET)
    handler = GraphHandler(
        debug_error={"message": "Cannot parse access token", "code": 190}
    )
    async with _client(handler) as client:
        assert await run_from_env(http_client=client) == 2
