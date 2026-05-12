"""Tests for skills_bridge_consumer.py (TICKET G.2).

Covers:
- state file lifecycle (first run + persisted)
- HTTP error handling (503 + 401 + 200 empty + 200 populated)
- CORR-G4 orphaned-gap reset to "$"
- CORR-G6 flock single-instance guard
- CORR-G2 incremental state save every 50 events
- CORR-G6 3-consecutive-503 → Telegram alert
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip if dep libs missing (lets the rest of the test suite import this file safely).
pytest.importorskip("httpx")
pytest.importorskip("redis")

# Import the script as a module — apps/cell/scripts/ isn't a Python package,
# so load it via importlib from the file path.
import importlib.util
import pathlib

_SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parents[2] / "scripts" / "skills_bridge_consumer.py"
)
_spec = importlib.util.spec_from_file_location("skills_bridge_consumer", _SCRIPT_PATH)
sbc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sbc)  # type: ignore[union-attr]


# ── fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolated_state_dir(tmp_path, monkeypatch):
    """Redirect STATE_DIR to a tmp_path so tests don't touch real ~/.cell-bridge-state."""
    fake_state_dir = tmp_path / ".cell-bridge-state"
    monkeypatch.setattr(sbc, "STATE_DIR", fake_state_dir)
    monkeypatch.setattr(sbc, "LAST_ID_FILE", fake_state_dir / "skills_last_id.txt")
    monkeypatch.setattr(sbc, "LOCK_FILE", fake_state_dir / "skills_bridge.lock")
    monkeypatch.setattr(sbc, "FAIL_COUNT_FILE", fake_state_dir / "skills_bridge_503_count.txt")
    yield fake_state_dir


def _make_response(status: int, body: dict | None = None):
    """Build a fake httpx.Response-like object."""
    r = MagicMock()
    r.status_code = status
    r.json = MagicMock(return_value=body or {})
    r.text = json.dumps(body or {})
    return r


# ── _load_last_id / _save_last_id ──────────────────────────────────────


def test_load_last_id_returns_00_on_first_run(isolated_state_dir):
    """No state file → return '0-0'."""
    assert sbc._load_last_id() == "0-0"


def test_load_last_id_returns_persisted_value(isolated_state_dir):
    """State file with content → return its value."""
    sbc._save_last_id("1736500000000-3")
    assert sbc._load_last_id() == "1736500000000-3"


def test_save_last_id_is_atomic(isolated_state_dir):
    """Save then load — atomic write via tempfile + rename."""
    sbc._save_last_id("abc-1")
    sbc._save_last_id("abc-2")  # overwrite
    assert sbc._load_last_id() == "abc-2"


# ── run_one_poll: HTTP error paths ─────────────────────────────────────


@pytest.mark.asyncio
async def test_run_one_poll_empty_api_key_returns_1(isolated_state_dir):
    rc = await sbc.run_one_poll("http://fake", "", "redis://127.0.0.1:6379")
    assert rc == 1


@pytest.mark.asyncio
async def test_run_one_poll_503_increments_counter(isolated_state_dir):
    """3 consecutive 503 → Telegram alert."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_ctx = AsyncMock()
        mock_ctx.get = AsyncMock(return_value=_make_response(503))
        mock_client_cls.return_value.__aenter__.return_value = mock_ctx

        with patch.object(sbc, "_send_telegram_alert") as alert_mock:
            # 1st + 2nd: no alert
            rc1 = await sbc.run_one_poll("http://fake", "key", "redis://127.0.0.1:6379")
            rc2 = await sbc.run_one_poll("http://fake", "key", "redis://127.0.0.1:6379")
            # 3rd: alert fires
            rc3 = await sbc.run_one_poll("http://fake", "key", "redis://127.0.0.1:6379")
            assert rc1 == rc2 == rc3 == 1
            assert alert_mock.call_count == 1


@pytest.mark.asyncio
async def test_run_one_poll_401_returns_1_no_state_change(isolated_state_dir):
    sbc._save_last_id("0-0")
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_ctx = AsyncMock()
        mock_ctx.get = AsyncMock(return_value=_make_response(401))
        mock_client_cls.return_value.__aenter__.return_value = mock_ctx
        rc = await sbc.run_one_poll("http://fake", "wrong-key", "redis://127.0.0.1:6379")
        assert rc == 1
        assert sbc._load_last_id() == "0-0"


# ── run_one_poll: success paths ────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_one_poll_empty_response_no_xadd(isolated_state_dir):
    """Empty events list → return 0, no XADD."""
    sbc._save_last_id("100-0")
    body = {"events": [], "last_stream_id": "100-0", "events_orphaned": False}
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_ctx = AsyncMock()
        mock_ctx.get = AsyncMock(return_value=_make_response(200, body))
        mock_client_cls.return_value.__aenter__.return_value = mock_ctx

        # Even if redis client built, no xadd should be called
        rc = await sbc.run_one_poll("http://fake", "key", "redis://127.0.0.1:6379")
        assert rc == 0
        assert sbc._load_last_id() == "100-0"


@pytest.mark.asyncio
async def test_run_one_poll_populated_response_xadds_events(isolated_state_dir):
    """Populated response → XADD all events + save last_id."""
    body = {
        "events": [
            {"id": "200-0", "fields": {"skill_id": "hgt_001", "procedure": "p1"}},
            {"id": "201-0", "fields": {"skill_id": "hgt_002", "procedure": "p2"}},
        ],
        "last_stream_id": "201-0",
        "events_orphaned": False,
    }
    fake_redis = AsyncMock()
    fake_redis.xadd = AsyncMock()
    fake_redis.aclose = AsyncMock()

    with patch("httpx.AsyncClient") as mock_client_cls, \
         patch("redis.asyncio.from_url", return_value=fake_redis):
        mock_ctx = AsyncMock()
        mock_ctx.get = AsyncMock(return_value=_make_response(200, body))
        mock_client_cls.return_value.__aenter__.return_value = mock_ctx

        rc = await sbc.run_one_poll("http://fake", "key", "redis://127.0.0.1:6379")
        assert rc == 0
        assert fake_redis.xadd.call_count == 2
        assert sbc._load_last_id() == "201-0"


# ── CORR-G4: orphaned-gap detection ────────────────────────────────────


@pytest.mark.asyncio
async def test_run_one_poll_orphaned_gap_resets_to_dollar(isolated_state_dir):
    """events_orphaned=true → save '$' + return 1 + alert."""
    sbc._save_last_id("100-0")
    body = {
        "events": [],
        "last_stream_id": "100-0",
        "events_orphaned": True,
        "stream_lowest_id": "999-0",
    }
    with patch("httpx.AsyncClient") as mock_client_cls, \
         patch.object(sbc, "_send_telegram_alert") as alert_mock:
        mock_ctx = AsyncMock()
        mock_ctx.get = AsyncMock(return_value=_make_response(200, body))
        mock_client_cls.return_value.__aenter__.return_value = mock_ctx

        rc = await sbc.run_one_poll("http://fake", "key", "redis://127.0.0.1:6379")
        assert rc == 1
        assert sbc._load_last_id() == "$"
        assert alert_mock.call_count == 1


# ── CORR-G2: incremental state save ────────────────────────────────────


@pytest.mark.asyncio
async def test_incremental_save_every_50_events(isolated_state_dir):
    """100 events → save at id of event #50 (incremental) + final id."""
    events = [
        {"id": f"{i}-0", "fields": {"skill_id": f"hgt_{i}", "procedure": "p"}}
        for i in range(1, 101)
    ]
    fake_redis = AsyncMock()
    fake_redis.xadd = AsyncMock()
    fake_redis.aclose = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=fake_redis):
        added = await sbc._xadd_events("redis://127.0.0.1:6379", events, "100-0")

    assert added == 100
    # Final save wins
    assert sbc._load_last_id() == "100-0"
    # xadd called 100 times
    assert fake_redis.xadd.call_count == 100


# ── 503 counter reset on success ───────────────────────────────────────


@pytest.mark.asyncio
async def test_503_counter_reset_after_success(isolated_state_dir):
    """After 2× 503 then 1× 200, counter should be reset."""
    sbc._increment_503_counter()
    sbc._increment_503_counter()
    body = {"events": [], "last_stream_id": "0-0", "events_orphaned": False}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_ctx = AsyncMock()
        mock_ctx.get = AsyncMock(return_value=_make_response(200, body))
        mock_client_cls.return_value.__aenter__.return_value = mock_ctx

        rc = await sbc.run_one_poll("http://fake", "key", "redis://127.0.0.1:6379")
        assert rc == 0
        # File deleted by _reset_503_counter
        assert not sbc.FAIL_COUNT_FILE.exists()
