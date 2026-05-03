"""FailoverDetector — Pro-down detection via Olympus heartbeat.

Design §11.1 + §11.2.

Pro publishes a heartbeat every N minutes via the Olympus heartbeat service
(``apps/backend-rag/backend/services/olympus/heartbeat.py``). When Air's
cron wakes up, it asks this detector: should I run the Trend-Hunter in
degraded mode?

Inputs come from a ``heartbeat_lookup_fn`` we inject so the detector is
DB-agnostic and trivially testable.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class PeerState(str, Enum):
    UP = "up"
    STALE = "stale"
    DOWN = "down"


@dataclass
class FailoverState:
    peer: str                  # e.g. "Nuzantara" (Pro hostname)
    state: PeerState
    last_beat: datetime | None
    minutes_since_beat: float | None
    should_failover: bool
    reason: str


HeartbeatLookupFn = Callable[[str], Awaitable[datetime | None]]


class FailoverDetector:
    """Pro-down detection. Default thresholds from design §11.1:

    - stale: last_beat older than ``stale_after_min`` (default 15)
    - down:  last_beat older than ``down_after_min`` (default 30)
    - missing beat → treat as DOWN (conservative)
    """

    def __init__(
        self,
        heartbeat_lookup_fn: HeartbeatLookupFn,
        *,
        stale_after_min: int = 15,
        down_after_min: int = 30,
    ) -> None:
        self.heartbeat_lookup_fn = heartbeat_lookup_fn
        self.stale = timedelta(minutes=stale_after_min)
        self.down = timedelta(minutes=down_after_min)

    async def check(
        self,
        peer: str,
        *,
        now: datetime | None = None,
    ) -> FailoverState:
        now = now or datetime.now(timezone.utc)
        try:
            last = await self.heartbeat_lookup_fn(peer)
        except Exception as exc:  # noqa: BLE001
            logger.warning("heartbeat lookup failed for %s: %s", peer, exc)
            return FailoverState(
                peer=peer,
                state=PeerState.DOWN,
                last_beat=None,
                minutes_since_beat=None,
                should_failover=True,
                reason=f"lookup_error: {type(exc).__name__}",
            )

        if last is None:
            return FailoverState(
                peer=peer,
                state=PeerState.DOWN,
                last_beat=None,
                minutes_since_beat=None,
                should_failover=True,
                reason="no_heartbeat_ever",
            )

        age = now - last
        minutes = age.total_seconds() / 60.0

        if age < self.stale:
            return FailoverState(
                peer=peer,
                state=PeerState.UP,
                last_beat=last,
                minutes_since_beat=minutes,
                should_failover=False,
                reason="fresh",
            )
        if age < self.down:
            return FailoverState(
                peer=peer,
                state=PeerState.STALE,
                last_beat=last,
                minutes_since_beat=minutes,
                should_failover=False,     # don't poach yet — Pro may wake
                reason=f"stale {minutes:.0f}min",
            )
        return FailoverState(
            peer=peer,
            state=PeerState.DOWN,
            last_beat=last,
            minutes_since_beat=minutes,
            should_failover=True,
            reason=f"down {minutes:.0f}min",
        )
