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
import importlib.util
import logging
import signal
import sys
from pathlib import Path
from typing import Any

from cell.sensors.channel_sensor import ChannelSensor

logger = logging.getLogger("cell.heartbeat_bridge")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    # ops-hardening fix 2026-05-19: explicit sys.stdout.
    # Default basicConfig routes to sys.stderr, which sent 4 INFO
    # "HTTP Request: GET .../api/channels/.../health 200 OK" lines
    # per minute to stderr.log (15 MB after ~140 iterations).
    stream=sys.stdout,
)

DEFAULT_INTERVAL_SECONDS: float = 60.0

_shutdown = asyncio.Event()


def _load_organism_heartbeat():
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "scripts" / "lib" / "heartbeat.py"
        if not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location("nuzantara_heartbeat", candidate)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.organism_heartbeat
    return None


def organism_heartbeat(organ_id: str, status: str = "ok", note: str = "") -> None:
    heartbeat = _load_organism_heartbeat()
    if heartbeat:
        heartbeat(organ_id, status, note)


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
            organism_heartbeat("pro.heartbeat_bridge", "ok", f"iter={iteration}")
            logger.info(
                f"iter={iteration} bridge results: {results}",
            )
        except Exception as exc:  # noqa: BLE001
            organism_heartbeat("pro.heartbeat_bridge", "error", f"iter={iteration}: {exc}")
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
    organism_heartbeat("pro.heartbeat_bridge", "starting", "heartbeat bridge starting")
    await run_loop(DEFAULT_INTERVAL_SECONDS)
    organism_heartbeat("pro.heartbeat_bridge", "degraded", "heartbeat bridge stopped")
    logger.info("heartbeat-bridge stopped cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
