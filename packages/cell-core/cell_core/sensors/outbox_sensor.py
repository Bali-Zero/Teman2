"""OutboxSensor — perceives durable EventBus pressure.

Reads the count of unconsumed rows in the PostgreSQL ``events_outbox``
table (migration 144) so the cell can sense when the bus is backed up.

Status mapping (defaults):
* 0 unconsumed rows → green
* 1..red_threshold-1 → yellow
* ≥ red_threshold → red

Symbiosis Law 4: when the database is unreachable (or no pool is
configured), the sensor returns *yellow* with error metadata. It never
raises; cells must keep pulsing on other sensors.

The constructor takes a ``pool_factory`` callable so the daemon can lazy
connect once asyncpg is available. ``pool_factory()`` may return ``None``
or any object with an ``acquire`` async context manager that yields a
connection exposing ``fetchval(query, *params)``.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from cell_core.types import SensorReading

logger = logging.getLogger("cell_core.sensors.outbox")

# Default count threshold for red severity. Operators can override to
# match their consumer throughput; 100 is a conservative starting point
# matching the EventBus phase-1 lag alert in the fly_watcher script.
_DEFAULT_RED_THRESHOLD = 100

_QUERY_ALL = "SELECT COUNT(*) FROM events_outbox WHERE consumed_at IS NULL"
_QUERY_PER_CHANNEL = (
    "SELECT COUNT(*) FROM events_outbox "
    "WHERE consumed_at IS NULL AND channel = $1"
)


class OutboxSensor:
    """Reads ``events_outbox`` lag from PostgreSQL.

    Args:
        pool_factory: Zero-arg callable returning the asyncpg pool (or
            None when not yet connected). Called on every read so the
            daemon can recover from a transient PG outage between
            pulses without re-instantiating the sensor.
        channel: Optional PG channel name (e.g. ``practice_changed``)
            to scope the count. If None, counts across all channels.
        red_threshold: Lag count at which status escalates to red.
        name: Sensor name (default ``outbox``).
    """

    def __init__(
        self,
        pool_factory: Callable[[], Any | None],
        channel: str | None = None,
        red_threshold: int = _DEFAULT_RED_THRESHOLD,
        name: str = "outbox",
    ) -> None:
        self._pool_factory = pool_factory
        self._channel = channel
        self._red_threshold = red_threshold
        self.name = name

    async def read(self, **_context: Any) -> SensorReading:
        """Read the current lag and return a SensorReading.

        Never raises. PG-down or pool=None → yellow with error metadata.
        """
        pool = self._pool_factory()
        if pool is None:
            return SensorReading(
                sensor_name=self.name,
                status="yellow",
                metadata={
                    "error": "no pool configured (PG unreachable at boot?)",
                    "channel": self._channel,
                },
            )

        try:
            count = await self._fetch_count(pool)
        except Exception as exc:  # noqa: BLE001 - sensor must never crash PulseLoop
            logger.warning(
                "OutboxSensor: PG unreachable, degrading to yellow: %s", exc
            )
            return SensorReading(
                sensor_name=self.name,
                status="yellow",
                metadata={
                    "error": str(exc),
                    "channel": self._channel,
                },
            )

        if count <= 0:
            status = "green"
        elif count >= self._red_threshold:
            status = "red"
        else:
            status = "yellow"

        return SensorReading(
            sensor_name=self.name,
            status=status,
            value=count,
            metadata={
                "unconsumed_count": count,
                "channel": self._channel,
                "red_threshold": self._red_threshold,
            },
        )

    async def _fetch_count(self, pool: Any) -> int:
        """Run COUNT(*) against events_outbox using the supplied pool.

        Accepts either:
        * an ``acquire()`` async context manager yielding a connection
          with ``fetchval(query, *params)`` (asyncpg shape), or
        * a pool exposing ``fetchval`` directly (test fakes).
        """
        if self._channel is not None:
            query = _QUERY_PER_CHANNEL
            params: tuple[Any, ...] = (self._channel,)
        else:
            query = _QUERY_ALL
            params = ()

        # Prefer the acquire-based path because asyncpg recommends it.
        if hasattr(pool, "acquire"):
            async with pool.acquire() as conn:
                result = conn.fetchval(query, *params)
                if isinstance(result, Awaitable):
                    result = await result
                return int(result or 0)

        # Fallback for fakes that expose fetchval directly.
        result = pool.fetchval(query, *params)
        if isinstance(result, Awaitable):
            result = await result
        return int(result or 0)
