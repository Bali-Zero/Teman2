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
