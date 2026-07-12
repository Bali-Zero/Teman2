"""Tests for the IG long-lived token watchdog (Task 30).

All Graph API traffic is mocked via httpx.MockTransport — no real token is
ever used, no network call is ever made. The fake token values below are
synthetic markers, chosen to be greppable so the redaction tests can assert
they never leak into logs or reprs.
"""

from __future__ import annotations

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
    refresh_long_lived_token,
    run_watchdog,
)

FAKE_TOKEN = "FAKE-OLD-TOKEN-a1b2c3"
FAKE_NEW_TOKEN = "FAKE-NEW-TOKEN-d4e5f6"
APP_ID = "123456"
APP_SECRET = "FAKE-APP-SECRET-x9y8"

NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


def _epoch(dt: datetime) -> int:
    return int(dt.timestamp())


class GraphHandler:
    """Programmable fake Graph API. Counts calls per endpoint."""

    def __init__(
        self,
        *,
        expires_at: int | None = None,
        is_valid: bool = True,
        debug_error: dict | None = None,
        refresh_error: dict | None = None,
        refresh_expires_in: int = 60 * 86400,
    ) -> None:
        self.expires_at = expires_at
        self.is_valid = is_valid
        self.debug_error = debug_error
        self.refresh_error = refresh_error
        self.refresh_expires_in = refresh_expires_in
        self.debug_calls = 0
        self.refresh_calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/debug_token"):
            self.debug_calls += 1
            if self.debug_error is not None:
                return httpx.Response(400, json={"error": self.debug_error})
            data: dict = {"is_valid": self.is_valid, "type": "USER"}
            if self.expires_at is not None:
                data["expires_at"] = self.expires_at
            return httpx.Response(200, json={"data": data})
        if request.url.path.endswith("/oauth/access_token"):
            self.refresh_calls += 1
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
        raise AssertionError(f"unexpected Graph call: {request.url.path}")


def _client(handler: GraphHandler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ── inspect_token ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_inspect_valid_token_reports_expiry():
    handler = GraphHandler(expires_at=_epoch(NOW + timedelta(days=30)))
    async with _client(handler) as client:
        status = await inspect_token(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
    assert status.is_valid is True
    assert status.expires_at == NOW + timedelta(days=30)
    assert status.days_remaining == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_inspect_never_expiring_token():
    # expires_at=0 is Meta's marker for a non-expiring token.
    handler = GraphHandler(expires_at=0)
    async with _client(handler) as client:
        status = await inspect_token(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
    assert status.is_valid is True
    assert status.expires_at is None
    assert status.days_remaining is None


@pytest.mark.asyncio
async def test_inspect_invalid_token_error_190():
    handler = GraphHandler(
        debug_error={"message": "Cannot parse access token", "code": 190}
    )
    async with _client(handler) as client:
        status = await inspect_token(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
    assert status.is_valid is False
    assert "Cannot parse access token" in (status.error or "")


# ── refresh_long_lived_token ──────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_returns_new_token_and_expiry():
    handler = GraphHandler()
    async with _client(handler) as client:
        refreshed = await refresh_long_lived_token(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
    assert refreshed.token == FAKE_NEW_TOKEN
    assert refreshed.expires_at == NOW + timedelta(days=60)
    assert handler.refresh_calls == 1


@pytest.mark.asyncio
async def test_refresh_error_raises_without_token_in_message():
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


# ── run_watchdog: the durability gate ─────────────────────────


@pytest.mark.asyncio
async def test_watchdog_refreshes_near_expired_token(caplog):
    """GUILT: token expiring inside the threshold → refresh happens."""
    handler = GraphHandler(expires_at=_epoch(NOW + timedelta(days=3)))
    async with _client(handler) as client:
        with caplog.at_level("INFO"):
            outcome = await run_watchdog(
                FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
            )
    assert outcome.action == "refreshed"
    assert outcome.new_token == FAKE_NEW_TOKEN
    assert handler.refresh_calls == 1
    # Provenance line present, token value absent.
    assert any("[ig-token-watchdog] refreshed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_watchdog_skips_fresh_token(caplog):
    """INNOCENCE: token with plenty of life left → NO refresh call."""
    handler = GraphHandler(expires_at=_epoch(NOW + timedelta(days=45)))
    async with _client(handler) as client:
        with caplog.at_level("INFO"):
            outcome = await run_watchdog(
                FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
            )
    assert outcome.action == "fresh"
    assert outcome.new_token is None
    assert handler.refresh_calls == 0


@pytest.mark.asyncio
async def test_watchdog_skips_never_expiring_token():
    handler = GraphHandler(expires_at=0)
    async with _client(handler) as client:
        outcome = await run_watchdog(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
    assert outcome.action == "fresh"
    assert handler.refresh_calls == 0


@pytest.mark.asyncio
async def test_watchdog_invalid_token_no_refresh_attempt():
    handler = GraphHandler(
        debug_error={"message": "Cannot parse access token", "code": 190}
    )
    async with _client(handler) as client:
        outcome = await run_watchdog(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
    assert outcome.action == "invalid"
    assert outcome.new_token is None
    assert handler.refresh_calls == 0


@pytest.mark.asyncio
async def test_watchdog_refresh_failure_reports_error():
    handler = GraphHandler(
        expires_at=_epoch(NOW + timedelta(days=2)),
        refresh_error={"message": "transient", "code": 2},
    )
    async with _client(handler) as client:
        outcome = await run_watchdog(
            FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
        )
    assert outcome.action == "error"
    assert outcome.new_token is None


@pytest.mark.asyncio
async def test_watchdog_custom_threshold():
    # 10 days left, threshold 14 → must refresh.
    handler = GraphHandler(expires_at=_epoch(NOW + timedelta(days=10)))
    async with _client(handler) as client:
        outcome = await run_watchdog(
            FAKE_TOKEN,
            APP_ID,
            APP_SECRET,
            http_client=client,
            now=NOW,
            threshold_days=14,
        )
    assert outcome.action == "refreshed"
    assert handler.refresh_calls == 1


# ── redaction (scar #4: no secret in cleartext) ───────────────


@pytest.mark.asyncio
async def test_no_token_value_in_any_log_record(caplog):
    handler = GraphHandler(expires_at=_epoch(NOW + timedelta(days=1)))
    async with _client(handler) as client:
        with caplog.at_level("DEBUG"):
            await run_watchdog(
                FAKE_TOKEN, APP_ID, APP_SECRET, http_client=client, now=NOW
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
    # TokenStatus never carries the token — just sanity that repr works.
    assert "TokenStatus" in repr(status)


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
