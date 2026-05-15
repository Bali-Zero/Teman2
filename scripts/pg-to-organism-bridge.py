#!/usr/bin/env python3
"""pg-to-organism-bridge.py — bridge PG LISTEN/NOTIFY → organism Redis stream.

Subscribes to all 13 PG_CHANNEL_MAP channels via asyncpg LISTEN. For every
notification received, builds an organism Event and emits it onto:
  1. Redis stream `organism:events` (best-effort)
  2. ~/.organism/events/pg-bridge.jsonl (durable mirror)

This closes Layer 1 of the "totale interattività" audit: until this
bridge existed, the backend PG bus and the Pro-side Supervisor stream
were two universes — events on `compliance_alert` / `intel_event` /
`war_room_event` etc. never reached the Supervisor's actuator pipeline.

Schedule: continuous daemon under launchd
  ~/Library/LaunchAgents/com.nuzantara.pg-organism-bridge.plist
  KeepAlive=true, RunAtLoad=true.

Connection: uses local pg-proxy at 127.0.0.1:15432 (DATABASE_URL_LOCAL).
Reconnects on disconnect with exponential backoff (cap 60s).
Heartbeat written each 60s tick to ~/.organism/last_seen/pro.pg_organism_bridge.json.

Severity mapping per channel (organism schema requires Severity enum):
  compliance_alert, federation_alert, war_room_event → warning (or payload.severity)
  intel_event, cognitive_event, cell_pulse_observed → info
  practice_changed, client_changed, partner_commission_changed → info
  measurer_event, asset_provenance, crm_welcome_completed → info
  lkpm_ingest_completed, wr2_status_change → info

Each emitted Event:
  source = "pg_bus.<channel>"
  kind = channel name
  payload = parsed JSON of NOTIFY payload (truncated to 2KB per schema)

Exit codes:
  0  graceful shutdown via SIGTERM
  1  fatal config (missing DATABASE_URL etc.)
  2  fatal asyncpg error not recoverable
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

logger = logging.getLogger("pg-organism-bridge")

# ─────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────

CHANNELS = [
    "practice_changed",
    "client_changed",
    "compliance_alert",
    "lkpm_ingest_completed",
    "war_room_event",
    "intel_event",
    "cognitive_event",
    "partner_commission_changed",
    "federation_alert",
    "cell_pulse_observed",
    "measurer_event",
    "crm_welcome_completed",
    "asset_provenance",
    "wr2_status_change",
]

WARNING_CHANNELS = {"compliance_alert", "federation_alert"}

EVENTS_JSONL = Path.home() / ".organism" / "events" / "pg-bridge.jsonl"
HEARTBEAT_PATH = Path.home() / ".organism" / "last_seen" / "pro.pg_organism_bridge.json"
ORGANISM_STREAM_KEY = "organism:events"

_RECONNECT_DELAY_S = 1.0
_RECONNECT_DELAY_CAP = 60.0
_HEARTBEAT_INTERVAL_S = 60

_shutdown = asyncio.Event()


def _load_secrets() -> None:
    secrets_path = os.path.expanduser("~/.nuzantara-secrets.env")
    if not os.path.isfile(secrets_path):
        return
    try:
        with open(secrets_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    except Exception as exc:
        logger.warning("could not source secrets: %s", exc)


# ─────────────────────────────────────────────────────────────────────────
# Heartbeat
# ─────────────────────────────────────────────────────────────────────────

def _write_heartbeat(status: str = "ok", note: str = "") -> None:
    try:
        HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {"ts": ts, "status": status, "note": str(note)[:500]}
        tmp = HEARTBEAT_PATH.with_suffix(HEARTBEAT_PATH.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(tmp, HEARTBEAT_PATH)
    except Exception:
        pass


async def _heartbeat_loop() -> None:
    while not _shutdown.is_set():
        _write_heartbeat("ok", "tick")
        try:
            await asyncio.wait_for(_shutdown.wait(), timeout=_HEARTBEAT_INTERVAL_S)
        except asyncio.TimeoutError:
            pass


# ─────────────────────────────────────────────────────────────────────────
# Event emission
# ─────────────────────────────────────────────────────────────────────────

def _truncate_payload(payload: dict) -> dict:
    """Honour organism Event 2KB payload limit. If too big, keep keys but
    truncate string values and drop oversized nested dicts."""
    serialised = json.dumps(payload, separators=(",", ":"), default=str)
    if len(serialised) <= 2000:
        return payload
    truncated: dict = {}
    for k, v in payload.items():
        if isinstance(v, str) and len(v) > 256:
            truncated[k] = v[:256] + "...(truncated)"
        elif isinstance(v, (dict, list)):
            truncated[k] = "(nested-truncated)"
        else:
            truncated[k] = v
    truncated["_pg_bridge_truncated"] = True
    return truncated


def _build_event(channel: str, payload_str: str) -> dict:
    try:
        payload = json.loads(payload_str)
        if not isinstance(payload, dict):
            payload = {"raw": payload_str[:512]}
    except json.JSONDecodeError:
        payload = {"raw": payload_str[:512], "_parse_error": True}

    payload = _truncate_payload(payload)

    severity = "warning" if channel in WARNING_CHANNELS else "info"
    # Honour explicit payload.severity if present and valid.
    explicit = payload.get("severity")
    if isinstance(explicit, str) and explicit.lower() in ("critical", "error", "warning", "info"):
        severity = explicit.lower()

    correlation_id = (
        payload.get("_outbox_id")
        or payload.get("correlation_id")
        or f"pg-{channel}-{datetime.now(timezone.utc).timestamp()}"
    )

    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "severity": severity,
        "source": f"pg_bus.{channel}",
        "kind": channel,
        "payload": payload,
        "correlation_id": str(correlation_id),
        "is_actuation": False,
        "host": "Pro",
    }


def _emit_event(event: dict) -> None:
    """JSONL first (durable), Redis XADD second (best-effort)."""
    try:
        EVENTS_JSONL.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, separators=(",", ":"), default=str)
        with EVENTS_JSONL.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as exc:
        logger.warning("JSONL write failed: %s", exc)
        return

    try:
        subprocess.run(
            [
                "redis-cli", "XADD", ORGANISM_STREAM_KEY, "*",
                "data", json.dumps(event, separators=(",", ":"), default=str),
            ],
            capture_output=True, timeout=2, check=False,
        )
    except Exception as exc:
        logger.debug("redis XADD failed (non-fatal): %s", exc)


# ─────────────────────────────────────────────────────────────────────────
# Listener
# ─────────────────────────────────────────────────────────────────────────

def _on_notification(_conn, _pid, channel: str, payload: str) -> None:
    """asyncpg sync callback. Build + emit Event."""
    try:
        event = _build_event(channel, payload)
        _emit_event(event)
        logger.debug("emitted %s (corr=%s)", channel, event["correlation_id"])
    except Exception:
        logger.exception("emit failed for channel=%s", channel)


async def _run_listener(dsn: str) -> None:
    backoff = _RECONNECT_DELAY_S
    while not _shutdown.is_set():
        conn = None
        try:
            logger.info("connecting to PG: %s", dsn.split("@")[-1] if "@" in dsn else dsn)
            conn = await asyncpg.connect(dsn=dsn, command_timeout=30)
            for ch in CHANNELS:
                await conn.add_listener(ch, _on_notification)
            logger.info("LISTEN on %d channels active", len(CHANNELS))
            backoff = _RECONNECT_DELAY_S

            # Keep-alive SELECT every 5s — stops idle Fly proxy from dropping.
            while not _shutdown.is_set():
                try:
                    await asyncio.wait_for(_shutdown.wait(), timeout=5.0)
                    break
                except asyncio.TimeoutError:
                    await conn.execute("SELECT 1")
        except (asyncpg.PostgresError, OSError, asyncio.TimeoutError) as exc:
            logger.warning("connection lost: %s — reconnecting in %.1fs", exc, backoff)
            _write_heartbeat("warning", f"disconnected: {type(exc).__name__}")
        finally:
            if conn is not None:
                try:
                    await asyncio.wait_for(conn.close(), timeout=5)
                except (asyncio.TimeoutError, Exception):
                    try:
                        conn.terminate()
                    except Exception:
                        pass

        if _shutdown.is_set():
            break
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, _RECONNECT_DELAY_CAP)


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def _setup_signals(loop: asyncio.AbstractEventLoop) -> None:
    def _stop():
        logger.info("shutdown signal received")
        _shutdown.set()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass


async def _amain() -> int:
    _load_secrets()
    dsn = os.environ.get("DATABASE_URL_LOCAL") or os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL[_LOCAL] not set — cannot connect")
        return 1
    # Rewrite flycast/.internal hosts to local pg-proxy if needed.
    if ".flycast" in dsn or ".internal" in dsn:
        # quick check pg-proxy reachability
        try:
            r = subprocess.run(["nc", "-z", "127.0.0.1", "15432"], timeout=2, capture_output=True)
            if r.returncode == 0:
                import re
                dsn = re.sub(r"@[^:/]+:[0-9]+", "@127.0.0.1:15432", dsn)
                logger.info("rewrote DSN to local pg-proxy")
            else:
                logger.error("DSN points to flycast but pg-proxy :15432 unreachable")
                return 2
        except Exception as exc:
            logger.error("nc check failed: %s", exc)
            return 2

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    loop = asyncio.get_running_loop()
    _setup_signals(loop)
    _write_heartbeat("starting", f"channels={len(CHANNELS)}")

    listener_task = asyncio.create_task(_run_listener(dsn))
    heartbeat_task = asyncio.create_task(_heartbeat_loop())

    await _shutdown.wait()
    listener_task.cancel()
    heartbeat_task.cancel()
    for t in (listener_task, heartbeat_task):
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass
    _write_heartbeat("ok", "stopped clean")
    return 0


def main() -> int:
    try:
        return asyncio.run(_amain())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
