#!/usr/bin/env python3
"""Standalone heartbeat bridge loop for the 4 channel webhooks.

Sprint 1.B Task 5 partial (2026-05-02): the originally-planned wire-up
into `cell/main.py` PulseEngine was deferred to Sprint 1.C to avoid
touching the cell/main.py + cell_core/pulse.py hot path concurrently
with the in-flight Cell Pulse Observatory PR-5 organism activation.

This standalone loop bypasses that coordination concern entirely: a
separate LaunchAgent (`com.nuzantara.heartbeat-bridge`) calls
`ChannelSensor.bridge_channels_to_sidecar()` every 60 seconds. Each
iteration writes 4 sidecar files to `~/.organism/last_seen/channel.{name}.json`
which `genome_aggregator_sensor` reads to classify the organi as green.

backend.api is already covered: Cell main loop's `HealthSensor.read()`
calls `bridge_reading_to_sidecar()` post-poll (PR #422), and that emits
`~/.organism/last_seen/backend.api.json`. This script ONLY adds the 4
channel sidecars.

Why standalone instead of wiring into cell/main.py:
- Zero touchpoint with cell_core.observatory / pulse.py (in-flight Sprint
  by another session — see docs/superpowers/specs/2026-05-01-cell-observatory-fase0-design.md)
- Reversible: `launchctl bootout gui/$(id -u)/com.nuzantara.heartbeat-bridge`
  removes the loop with no Cell behavior change
- Survives Cell daemon restart cycles independently

Spec ref: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §3.3.5
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any

from cell.sensors.channel_sensor import ChannelSensor

logger = logging.getLogger("cell.heartbeat_bridge")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DEFAULT_INTERVAL_SECONDS: float = 60.0

_shutdown = asyncio.Event()


def _handle_signal(sig: int, frame: Any) -> None:
    logger.info(f"Received signal {sig}, shutting down...")
    _shutdown.set()


async def run_loop(interval_seconds: float = DEFAULT_INTERVAL_SECONDS) -> None:
    """Loop forever: every interval_seconds, run channel bridge once.

    Args:
        interval_seconds: between consecutive bridge runs.

    The bridge itself swallows per-channel HTTP failures (returns "fail"
    sidecar for that channel only); this loop only catches loop-level
    errors (e.g. KeyboardInterrupt) and logs them.
    """
    sensor = ChannelSensor()
    iteration = 0
    while not _shutdown.is_set():
        iteration += 1
        try:
            results = await sensor.bridge_channels_to_sidecar()
            logger.info(
                f"iter={iteration} bridge results: {results}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"iter={iteration} bridge raised (caught): {exc}")
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


async def main() -> int:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info(
        f"heartbeat-bridge starting; interval={DEFAULT_INTERVAL_SECONDS}s; "
        f"emits sidecar files to ~/.organism/last_seen/channel.*.json"
    )
    await run_loop(DEFAULT_INTERVAL_SECONDS)
    logger.info("heartbeat-bridge stopped cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
