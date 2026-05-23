"""W36 stale-event TTL guard tests for ``events_outbox.replay_unconsumed``.

Discovered 2026-05-23: the W27+W31+W33 Cell auto-heal chain wires
``cell_pulse_observed`` events through ``pg-to-organism-bridge.py`` to
the Organism supervisor, which may fire ``fly_machines_restart`` against
machines whose RED-tier state has since recovered. The bridge itself is
LISTEN-only (no replay), but ``EventBus._replay_outbox_on_reconnect``
calls ``replay_unconsumed`` on every reconnect for every PG channel,
dispatching unconsumed rows back into ``_handle_pg_event`` — which
re-enters the live consumer chain (including the bridge).

The pre-W36 row-level filter (``created_at > NOW() - INTERVAL 60m``) is
necessary but not sufficient: a row can be fresh (e.g. committed by a
long PG transaction) while its in-payload ``pulse_timestamp`` is hours
older. This module covers the W36 second-stage TTL on the payload
timestamp.

Test conventions follow ``test_outbox.py`` (AsyncMock for the
asyncpg.Connection surface).
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from backend.services.events.outbox import (
    _DEFAULT_PAYLOAD_TTL_MIN,
    _is_payload_stale,
    _payload_timestamp_seconds,
    _resolve_payload_ttl_minutes,
    replay_unconsumed,
)

# ── helpers ────────────────────────────────────────────────────────────


def _ms(seconds_ago: float) -> int:
    """Return a ms-since-epoch integer offset by ``seconds_ago`` from now."""
    return int((time.time() - seconds_ago) * 1000)


# ── _resolve_payload_ttl_minutes ──────────────────────────────────────


def test_resolve_payload_ttl_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRIDGE_STALE_EVENT_TTL_MIN", raising=False)
    assert _resolve_payload_ttl_minutes() == _DEFAULT_PAYLOAD_TTL_MIN
    assert _resolve_payload_ttl_minutes() == 60


def test_resolve_payload_ttl_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_STALE_EVENT_TTL_MIN", "15")
    assert _resolve_payload_ttl_minutes() == 15
    monkeypatch.setenv("BRIDGE_STALE_EVENT_TTL_MIN", "240")
    assert _resolve_payload_ttl_minutes() == 240


def test_resolve_payload_ttl_explicit_arg_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_STALE_EVENT_TTL_MIN", "999")
    assert _resolve_payload_ttl_minutes(explicit=5) == 5


def test_resolve_payload_ttl_malformed_env_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("BRIDGE_STALE_EVENT_TTL_MIN", "not-a-number")
    with caplog.at_level("WARNING", logger="backend.services.events.outbox"):
        assert _resolve_payload_ttl_minutes() == _DEFAULT_PAYLOAD_TTL_MIN
    assert any("not an integer" in r.message for r in caplog.records)


def test_resolve_payload_ttl_negative_env_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("BRIDGE_STALE_EVENT_TTL_MIN", "-5")
    with caplog.at_level("WARNING", logger="backend.services.events.outbox"):
        assert _resolve_payload_ttl_minutes() == _DEFAULT_PAYLOAD_TTL_MIN
    assert any("negative" in r.message for r in caplog.records)


# ── _payload_timestamp_seconds ────────────────────────────────────────


def test_payload_timestamp_ms_pulse_timestamp() -> None:
    payload = {"cell_id": "cell", "pulse_timestamp": _ms(0)}
    ts = _payload_timestamp_seconds(payload)
    assert ts is not None
    assert abs(ts - time.time()) < 2.0


def test_payload_timestamp_seconds_fallback_key() -> None:
    payload = {"timestamp": time.time() - 30.0}
    ts = _payload_timestamp_seconds(payload)
    assert ts is not None
    assert abs(ts - (time.time() - 30.0)) < 2.0


def test_payload_timestamp_missing_returns_none() -> None:
    assert _payload_timestamp_seconds({"cell_id": "cell"}) is None
    assert _payload_timestamp_seconds({}) is None


def test_payload_timestamp_invalid_value_returns_none() -> None:
    assert _payload_timestamp_seconds({"pulse_timestamp": "not-a-number"}) is None
    assert _payload_timestamp_seconds({"pulse_timestamp": None}) is None
    assert _payload_timestamp_seconds({"pulse_timestamp": -1}) is None
    assert _payload_timestamp_seconds({"pulse_timestamp": 0}) is None


def test_payload_timestamp_non_dict_returns_none() -> None:
    assert _payload_timestamp_seconds("not a dict") is None  # type: ignore[arg-type]
    assert _payload_timestamp_seconds(None) is None  # type: ignore[arg-type]


# ── _is_payload_stale ────────────────────────────────────────────────


def test_is_payload_stale_fresh_event() -> None:
    payload = {"pulse_timestamp": _ms(5)}  # 5s ago
    assert _is_payload_stale(payload, ttl_minutes=60) is False


def test_is_payload_stale_old_event() -> None:
    payload = {"pulse_timestamp": _ms(2 * 3600)}  # 2h ago
    assert _is_payload_stale(payload, ttl_minutes=60) is True


def test_is_payload_stale_no_timestamp_open_by_default() -> None:
    """Events with no recognised timestamp field are NOT considered stale.

    Row-level ``created_at`` is the safety net for those events. Closing
    by default would mass-drop legitimate channels like ``practice_changed``
    that have no pulse timestamp.
    """
    assert _is_payload_stale({"cell_id": "cell"}, ttl_minutes=60) is False
    assert _is_payload_stale({}, ttl_minutes=60) is False


def test_is_payload_stale_ttl_zero_disables_check() -> None:
    payload = {"pulse_timestamp": _ms(7 * 24 * 3600)}  # week-old
    assert _is_payload_stale(payload, ttl_minutes=0) is False
    assert _is_payload_stale(payload, ttl_minutes=-1) is False


# ── replay_unconsumed integration (stale guard) ──────────────────────


@pytest.mark.asyncio
async def test_replay_unconsumed_skips_stale_payload_and_acks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale-payload rows are skipped + acked so they stop replaying."""
    monkeypatch.delenv("BRIDGE_STALE_EVENT_TTL_MIN", raising=False)

    stale_ts = _ms(2 * 3600)  # 2h ago — older than default 60m TTL
    fresh_ts = _ms(10)  # 10s ago

    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"id": 100, "channel": "cell_pulse_observed", "payload": {"pulse_timestamp": stale_ts, "cell_id": "x"}},
            {"id": 101, "channel": "cell_pulse_observed", "payload": {"pulse_timestamp": fresh_ts, "cell_id": "y"}},
        ]
    )
    conn.execute = AsyncMock(return_value="UPDATE 1")

    dispatched: list[dict] = []

    async def dispatch_fn(payload: dict) -> None:
        dispatched.append(payload)

    acked = await replay_unconsumed(
        conn,
        dispatch_fn,
        channel="cell_pulse_observed",
        max_age_minutes=60,
    )

    # Stale row skipped — only the fresh one reached dispatch_fn.
    assert len(dispatched) == 1
    assert dispatched[0]["cell_id"] == "y"
    # Both rows acked (stale skip still acks to suppress further replay).
    assert acked == 2
    assert conn.execute.await_count == 2


@pytest.mark.asyncio
async def test_replay_unconsumed_passes_through_no_timestamp_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Payload without timestamp field is dispatched normally."""
    monkeypatch.delenv("BRIDGE_STALE_EVENT_TTL_MIN", raising=False)

    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"id": 50, "channel": "practice_changed", "payload": {"practice_id": "p1"}},
        ]
    )
    conn.execute = AsyncMock(return_value="UPDATE 1")

    dispatched: list[dict] = []

    async def dispatch_fn(payload: dict) -> None:
        dispatched.append(payload)

    acked = await replay_unconsumed(
        conn,
        dispatch_fn,
        channel="practice_changed",
        max_age_minutes=60,
    )

    assert acked == 1
    assert len(dispatched) == 1
    assert dispatched[0]["practice_id"] == "p1"


@pytest.mark.asyncio
async def test_replay_unconsumed_env_var_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``BRIDGE_STALE_EVENT_TTL_MIN`` env var tightens the payload TTL."""
    monkeypatch.setenv("BRIDGE_STALE_EVENT_TTL_MIN", "5")

    # 10min-old payload: stale under env=5 but fresh under default=60.
    ts = _ms(10 * 60)

    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"id": 200, "channel": "cell_pulse_observed", "payload": {"pulse_timestamp": ts}},
        ]
    )
    conn.execute = AsyncMock(return_value="UPDATE 1")

    dispatched: list[dict] = []

    async def dispatch_fn(payload: dict) -> None:
        dispatched.append(payload)

    acked = await replay_unconsumed(
        conn,
        dispatch_fn,
        channel="cell_pulse_observed",
        max_age_minutes=60,
    )

    # Skipped because env-TTL=5m and payload is 10m old.
    assert dispatched == []
    assert acked == 1  # acked-on-skip


@pytest.mark.asyncio
async def test_replay_unconsumed_explicit_ttl_arg_disables_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``payload_ttl_minutes=0`` disables the payload TTL even with stale events."""
    monkeypatch.setenv("BRIDGE_STALE_EVENT_TTL_MIN", "1")

    week_old = _ms(7 * 24 * 3600)

    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"id": 300, "channel": "cell_pulse_observed", "payload": {"pulse_timestamp": week_old}},
        ]
    )
    conn.execute = AsyncMock(return_value="UPDATE 1")

    dispatched: list[dict] = []

    async def dispatch_fn(payload: dict) -> None:
        dispatched.append(payload)

    acked = await replay_unconsumed(
        conn,
        dispatch_fn,
        channel="cell_pulse_observed",
        max_age_minutes=60,
        payload_ttl_minutes=0,
    )

    # Guard disabled → row dispatched + acked normally.
    assert len(dispatched) == 1
    assert acked == 1


@pytest.mark.asyncio
async def test_replay_unconsumed_stale_skip_emits_warning_log(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Stale skip must surface in WARNING logs for operator visibility."""
    monkeypatch.delenv("BRIDGE_STALE_EVENT_TTL_MIN", raising=False)

    stale_ts = _ms(3 * 3600)

    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"id": 400, "channel": "cell_pulse_observed", "payload": {"pulse_timestamp": stale_ts}},
        ]
    )
    conn.execute = AsyncMock(return_value="UPDATE 1")

    async def dispatch_fn(_: dict) -> None:
        pytest.fail("dispatch_fn must NOT be called for stale payload")

    with caplog.at_level("WARNING", logger="backend.services.events.outbox"):
        await replay_unconsumed(
            conn,
            dispatch_fn,
            channel="cell_pulse_observed",
            max_age_minutes=60,
        )

    assert any("stale-payload" in r.message for r in caplog.records)
    assert any("id=400" in r.message for r in caplog.records)
