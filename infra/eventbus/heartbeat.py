"""Daemon heartbeat helpers.

Each long-running eventbus daemon should call:
    from eventbus.heartbeat import beat
    beat("meta-dispatcher")  # in main loop, every iteration

Stores a Redis SET key `bz:heartbeat:<daemon>` with TTL 120s. If absent
for >5 min, daemon-watchdog (separate process) detects and Telegrams.
"""
from __future__ import annotations
import os
import time
import logging

import redis

from .publisher import _client, REDIS_HOST, REDIS_PORT

log = logging.getLogger("eventbus.heartbeat")

HEARTBEAT_PREFIX = "bz:heartbeat:"
HEARTBEAT_TTL = 120  # seconds — daemon dead if no beat for 2x the TTL

# Throttle: don't beat more than once per 30s per daemon
_last_beat_at: dict[str, float] = {}
_BEAT_THROTTLE = 30.0


def beat(daemon_name: str, *, force: bool = False) -> None:
    """Mark daemon alive. Throttled to 1/30s. Idempotent on Redis failure."""
    now = time.time()
    last = _last_beat_at.get(daemon_name, 0)
    if not force and (now - last) < _BEAT_THROTTLE:
        return
    try:
        _client().setex(f"{HEARTBEAT_PREFIX}{daemon_name}", HEARTBEAT_TTL, str(int(now)))
        _last_beat_at[daemon_name] = now
    except redis.RedisError as e:
        log.warning("heartbeat failed for %s: %s", daemon_name, e)


def is_alive(daemon_name: str) -> bool:
    """Return True if daemon emitted heartbeat in the last HEARTBEAT_TTL seconds."""
    try:
        return _client().exists(f"{HEARTBEAT_PREFIX}{daemon_name}") == 1
    except redis.RedisError:
        return True  # fail-open: assume alive when Redis itself is down


def start_background_beater(daemon_name: str, interval: int = 30) -> None:
    """Spawn a background thread that emits heartbeat every `interval` seconds.

    Solves the case where the main loop blocks (XREADGROUP BLOCK) for longer than
    the heartbeat TTL — without this thread, idle daemons appear dead.
    Idempotent: calling twice for same daemon_name spawns 2 threads (avoid).
    """
    import threading

    def _loop():
        while True:
            try:
                beat(daemon_name, force=True)
            except Exception as e:
                log.warning("background beat failed for %s: %s", daemon_name, e)
            time.sleep(interval)

    t = threading.Thread(target=_loop, daemon=True, name=f"heartbeat-{daemon_name}")
    t.start()
    log.info("background heartbeat started for %s (interval=%ds)", daemon_name, interval)


def list_all_heartbeats() -> dict[str, int]:
    """Return {daemon_name: timestamp_int} for all currently-alive daemons."""
    try:
        keys = _client().keys(f"{HEARTBEAT_PREFIX}*")
        out = {}
        for k in keys:
            ts_raw = _client().get(k)
            try:
                ts = int(ts_raw) if ts_raw else 0
            except (TypeError, ValueError):
                ts = 0
            out[k.replace(HEARTBEAT_PREFIX, "")] = ts
        return out
    except redis.RedisError:
        return {}
