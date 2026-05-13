"""Tests for OutboxSensor — reads from PG events_outbox.

Sensor contract:
- name attribute
- async read(**context) -> SensorReading
- Symbiosis Law 4: graceful degradation when DB unreachable
- Status mapping:
  * 0 unconsumed rows → green
  * 1..N (under threshold) → yellow with count metadata
  * over threshold → red with count metadata
  * DB unreachable → yellow with error metadata (NOT red — Cell still
    senses other things; outbox down is a degraded but not critical state)
"""
from __future__ import annotations

import pytest

from cell_core.types import SensorReading


# ──────────────────────────────────────────────────────────────────
# Fakes
# ──────────────────────────────────────────────────────────────────


class _FakeConn:
    def __init__(self, count: int):
        self._count = count

    async def fetchval(self, _query, *_args):
        return self._count


class _AcquireCM:
    """Mimics asyncpg's ``pool.acquire()`` async context manager."""

    def __init__(self, count: int, raise_on_enter: Exception | None = None):
        self._count = count
        self._raise = raise_on_enter

    async def __aenter__(self) -> _FakeConn:
        if self._raise is not None:
            raise self._raise
        return _FakeConn(self._count)

    async def __aexit__(self, *_args) -> bool:
        return False


class _FakePool:
    """In-memory fake of asyncpg.Pool with deterministic count."""

    def __init__(self, count: int = 0, raise_on_acquire: Exception | None = None):
        self._count = count
        self._raise = raise_on_acquire

    def acquire(self) -> _AcquireCM:
        # asyncpg's pool.acquire() returns an awaitable that is also an
        # async context manager. Tests use the ``async with`` form.
        return _AcquireCM(self._count, raise_on_enter=self._raise)


# ──────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_outbox_sensor_protocol_compliance():
    """OutboxSensor satisfies the Sensor Protocol."""
    from cell_core.protocols import Sensor
    from cell_core.sensors.outbox_sensor import OutboxSensor

    sensor = OutboxSensor(pool_factory=lambda: None)
    assert isinstance(sensor, Sensor)
    assert sensor.name == "outbox"


@pytest.mark.asyncio
async def test_empty_outbox_returns_green():
    from cell_core.sensors.outbox_sensor import OutboxSensor

    pool = _FakePool(count=0)
    sensor = OutboxSensor(pool_factory=lambda: pool)
    reading = await sensor.read()

    assert isinstance(reading, SensorReading)
    assert reading.status == "green"
    assert reading.metadata.get("unconsumed_count") == 0


@pytest.mark.asyncio
async def test_populated_outbox_returns_yellow_with_count():
    from cell_core.sensors.outbox_sensor import OutboxSensor

    pool = _FakePool(count=5)
    sensor = OutboxSensor(pool_factory=lambda: pool)
    reading = await sensor.read()

    assert reading.status == "yellow"
    assert reading.metadata["unconsumed_count"] == 5


@pytest.mark.asyncio
async def test_overflow_outbox_returns_red():
    from cell_core.sensors.outbox_sensor import OutboxSensor

    pool = _FakePool(count=500)
    # threshold defaults to 100
    sensor = OutboxSensor(pool_factory=lambda: pool, red_threshold=100)
    reading = await sensor.read()

    assert reading.status == "red"
    assert reading.metadata["unconsumed_count"] == 500


@pytest.mark.asyncio
async def test_db_unreachable_degrades_to_yellow_no_crash():
    """Symbiosis Law 4 — PG down → yellow with error metadata, never raises."""
    from cell_core.sensors.outbox_sensor import OutboxSensor

    err = ConnectionError("postgres unreachable")
    pool = _FakePool(raise_on_acquire=err)
    sensor = OutboxSensor(pool_factory=lambda: pool)
    reading = await sensor.read()

    assert reading.status == "yellow"
    assert reading.metadata.get("error") is not None
    assert "postgres unreachable" in reading.metadata["error"]


@pytest.mark.asyncio
async def test_pool_factory_returns_none_degrades_yellow():
    """When the daemon couldn't connect at boot the factory returns None."""
    from cell_core.sensors.outbox_sensor import OutboxSensor

    sensor = OutboxSensor(pool_factory=lambda: None)
    reading = await sensor.read()

    assert reading.status == "yellow"
    assert reading.metadata.get("error") is not None
    assert reading.metadata.get("unconsumed_count") is None


@pytest.mark.asyncio
async def test_per_channel_filtering():
    """When channel argument is provided, sensor scopes the count query."""
    from cell_core.sensors.outbox_sensor import OutboxSensor

    pool = _FakePool(count=2)
    sensor = OutboxSensor(pool_factory=lambda: pool, channel="practice_changed")
    reading = await sensor.read()

    assert reading.status == "yellow"
    assert reading.metadata["channel"] == "practice_changed"


# ──────────────────────────────────────────────────────────────────
# LEVA 3 extensions (2026-05-13): channels list, exclude, lookback
# ──────────────────────────────────────────────────────────────────


def test_channel_and_channels_are_mutex():
    """Constructor rejects both single-channel and list-channel at once."""
    from cell_core.sensors.outbox_sensor import OutboxSensor

    with pytest.raises(ValueError):
        OutboxSensor(
            pool_factory=lambda: None,
            channel="practice_changed",
            channels=["client_changed"],
        )


@pytest.mark.asyncio
async def test_channels_include_emits_ANY_query():
    """channels=[a,b] + exclude=False -> WHERE channel = ANY(...)."""
    from cell_core.sensors.outbox_sensor import OutboxSensor

    pool = _FakePool(count=7)
    sensor = OutboxSensor(
        pool_factory=lambda: pool,
        channels=["practice_changed", "client_changed"],
        exclude=False,
    )
    query, params = sensor._build_query()
    assert "= ANY($1::text[])" in query
    assert "NOT " not in query
    assert params == (["practice_changed", "client_changed"],)
    reading = await sensor.read()
    assert reading.status == "yellow"
    assert reading.metadata["channels"] == ["practice_changed", "client_changed"]
    assert reading.metadata["exclude"] is False


@pytest.mark.asyncio
async def test_channels_exclude_emits_NOT_ANY_query():
    """channels=[x] + exclude=True -> WHERE NOT (channel = ANY(...))."""
    from cell_core.sensors.outbox_sensor import OutboxSensor

    pool = _FakePool(count=4)
    sensor = OutboxSensor(
        pool_factory=lambda: pool,
        channels=["cell_pulse_observed"],
        exclude=True,
    )
    query, params = sensor._build_query()
    assert "NOT (channel = ANY($1::text[]))" in query
    assert params == (["cell_pulse_observed"],)
    reading = await sensor.read()
    assert reading.metadata["exclude"] is True


def test_lookback_seconds_appended_to_query():
    """lookback_seconds=3600 -> INTERVAL '3600 seconds' clause."""
    from cell_core.sensors.outbox_sensor import OutboxSensor

    sensor = OutboxSensor(
        pool_factory=lambda: None,
        lookback_seconds=3600,
    )
    query, _ = sensor._build_query()
    assert "INTERVAL '3600 seconds'" in query
    assert "created_at > NOW() -" in query


def test_lookback_zero_or_negative_ignored():
    """lookback_seconds=0/negative is normalised to None (no clause)."""
    from cell_core.sensors.outbox_sensor import OutboxSensor

    s1 = OutboxSensor(pool_factory=lambda: None, lookback_seconds=0)
    s2 = OutboxSensor(pool_factory=lambda: None, lookback_seconds=-10)
    q1, _ = s1._build_query()
    q2, _ = s2._build_query()
    assert "INTERVAL" not in q1
    assert "INTERVAL" not in q2


@pytest.mark.asyncio
async def test_channels_exclude_with_lookback_combined():
    """Combined query: exclude + lookback both active."""
    from cell_core.sensors.outbox_sensor import OutboxSensor

    pool = _FakePool(count=12)
    sensor = OutboxSensor(
        pool_factory=lambda: pool,
        channels=["cell_pulse_observed"],
        exclude=True,
        lookback_seconds=3600,
        red_threshold=200,
    )
    query, params = sensor._build_query()
    assert "NOT (channel = ANY($1::text[]))" in query
    assert "INTERVAL '3600 seconds'" in query
    assert params == (["cell_pulse_observed"],)
    reading = await sensor.read()
    assert reading.status == "yellow"  # 12 < 200
    assert reading.metadata["lookback_seconds"] == 3600
    assert reading.metadata["red_threshold"] == 200
