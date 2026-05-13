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
            to scope the count. If None and ``channels`` is None,
            counts across all channels. Mutually exclusive with
            ``channels``.
        channels: Optional list of PG channel names (e.g.
            ``["cell_pulse_observed"]``). Combined with ``exclude`` to
            filter the count. LEVA 3 use case: exclude
            ``cell_pulse_observed`` so CELL doesn't self-flood the
            metric.
        exclude: When ``channels`` is non-empty, ``True`` counts rows
            whose channel is NOT in the list, ``False`` counts rows
            whose channel IS in the list. Ignored if ``channels`` is
            None.
        lookback_seconds: Optional lookback window. When set, counts
            only rows whose ``created_at > NOW() - INTERVAL N second``.
            Prevents an abandoned consumer's lag from growing
            unbounded.
        red_threshold: Lag count at which status escalates to red.
        name: Sensor name (default ``outbox``).
    """

    def __init__(
        self,
        pool_factory: Callable[[], Any | None],
        channel: str | None = None,
        channels: list[str] | None = None,
        exclude: bool = False,
        lookback_seconds: int | None = None,
        red_threshold: int = _DEFAULT_RED_THRESHOLD,
        name: str = "outbox",
    ) -> None:
        # LEVA 3 (2026-05-13): `channels` and `channel` are mutually
        # exclusive. `exclude=True` flips the channel-list filter from
        # IN to NOT-IN. `lookback_seconds` caps the window so an
        # abandoned consumer doesn't make the count grow unbounded.
        if channel is not None and channels is not None:
            raise ValueError(
                "OutboxSensor: pass either `channel` (single) or "
                "`channels` (list), not both"
            )
        self._pool_factory = pool_factory
        self._channel = channel
        self._channels = list(channels) if channels else None
        self._exclude = bool(exclude)
        self._lookback_seconds = (
            int(lookback_seconds)
            if lookback_seconds and lookback_seconds > 0
            else None
        )
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
                    "channels": list(self._channels) if self._channels else None,
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
                    "channels": list(self._channels) if self._channels else None,
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
                "channels": list(self._channels) if self._channels else None,
                "exclude": self._exclude if self._channels else None,
                "lookback_seconds": self._lookback_seconds,
                "red_threshold": self._red_threshold,
            },
        )

    def _build_query(self) -> tuple[str, tuple[Any, ...]]:
        """Build the COUNT query + parameter tuple for the current config.

        Returns a literal SQL string with positional placeholders ($1, $2,
        ...) and the parameter tuple. The query always starts with
        ``SELECT COUNT(*) FROM events_outbox WHERE consumed_at IS NULL``;
        optional clauses are added in this order:
        - single channel:    AND channel = $N
        - channels include:  AND channel = ANY($N::text[])
        - channels exclude:  AND NOT (channel = ANY($N::text[]))
        - lookback:          AND created_at > NOW() - INTERVAL '$N seconds'
                             (literal-substituted; ``__init__`` validates
                             the value to int so injection is impossible)
        """
        clauses: list[str] = []
        params: list[Any] = []
        next_idx = 1

        if self._channel is not None:
            clauses.append(f"channel = ${next_idx}")
            params.append(self._channel)
            next_idx += 1
        elif self._channels:
            if self._exclude:
                clauses.append(f"NOT (channel = ANY(${next_idx}::text[]))")
            else:
                clauses.append(f"channel = ANY(${next_idx}::text[])")
            params.append(self._channels)
            next_idx += 1

        if self._lookback_seconds is not None:
            clauses.append(
                f"created_at > NOW() - INTERVAL '{self._lookback_seconds} seconds'"
            )

        query = "SELECT COUNT(*) FROM events_outbox WHERE consumed_at IS NULL"
        if clauses:
            query += " AND " + " AND ".join(clauses)
        return query, tuple(params)

    async def _fetch_count(self, pool: Any) -> int:
        """Run COUNT(*) against events_outbox using the supplied pool.

        Accepts either:
        * an ``acquire()`` async context manager yielding a connection
          with ``fetchval(query, *params)`` (asyncpg shape), or
        * a pool exposing ``fetchval`` directly (test fakes).
        """
        query, params = self._build_query()

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
