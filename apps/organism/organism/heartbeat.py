"""Supervisor heartbeat check for guardian local_emergency_mode fallback.

Guardians call supervisor_heartbeat_check() every cycle. If lag >5min
(or no heartbeat ever), they revert to pre-organism autonomous behavior.
MANDATORY to prevent the organism becoming a SPOF worse than the blind
guardians of today.

Used by: scripts/system_doctor.py, scripts/sentinel_lib/zombie_hunter.py,
and any future guardian wired into the event bus.
"""
import time
from dataclasses import dataclass


SUPERVISOR_HB_KEY = "organism:supervisor:heartbeat"
DEFAULT_MAX_LAG_SECONDS = 300  # 5 minutes — covers 1 missed Supervisor cycle + margin


@dataclass(frozen=True)
class HeartbeatStatus:
    """Result of a supervisor heartbeat check.

    Attributes:
        supervisor_alive: True if Supervisor heartbeat is fresh enough.
        last_heartbeat_ts: unix timestamp of last observed heartbeat, or
            None if no heartbeat was ever written.
        lag_seconds: seconds since last heartbeat, or None if never observed.
    """
    supervisor_alive: bool
    last_heartbeat_ts: float | None
    lag_seconds: float | None

    @property
    def should_enter_emergency_mode(self) -> bool:
        """Guardian should fall back to autonomous pre-organism behavior."""
        return not self.supervisor_alive


async def supervisor_heartbeat_check(
    *, redis, max_lag_seconds: int = DEFAULT_MAX_LAG_SECONDS,
) -> HeartbeatStatus:
    """Query Redis for the Supervisor heartbeat and compute status.

    Args:
        redis: async Redis client (from redis.asyncio or fakeredis.aioredis).
        max_lag_seconds: heartbeat older than this -> emergency mode.

    Returns:
        HeartbeatStatus dataclass. Guardians should check
        .should_enter_emergency_mode to decide their behavior.
    """
    raw = await redis.get(SUPERVISOR_HB_KEY)
    if raw is None:
        return HeartbeatStatus(
            supervisor_alive=False, last_heartbeat_ts=None, lag_seconds=None,
        )
    try:
        ts = float(raw)
    except (ValueError, TypeError):
        return HeartbeatStatus(
            supervisor_alive=False, last_heartbeat_ts=None, lag_seconds=None,
        )
    lag = time.time() - ts
    return HeartbeatStatus(
        supervisor_alive=lag <= max_lag_seconds,
        last_heartbeat_ts=ts,
        lag_seconds=lag,
    )
