"""High-level emit_event() helper — used by guardians directly.

Sanitizes payload, generates correlation_id if absent, auto-detects host
Pro vs Air, writes to Redis + JSONL via EventBus singleton.
"""
import os
import socket
import uuid
from pathlib import Path
from typing import Any
import redis.asyncio as redis
from organism.schemas import Event, Severity
from organism.sanitize import sanitize_payload
from organism.redis_bus import EventBus


ORGANISM_JSONL_DEFAULT = Path(
    os.getenv("ORGANISM_JSONL_PATH", str(Path.home() / "logs" / "organism" / "events.jsonl"))
)
_REDIS_URL = os.getenv("ORGANISM_REDIS_URL", "redis://127.0.0.1:6379/0")
_bus_singleton: EventBus | None = None


def _get_bus() -> EventBus:
    """Lazy-init EventBus singleton. Overridable in tests via monkeypatch."""
    global _bus_singleton
    if _bus_singleton is None:
        r = redis.from_url(_REDIS_URL, decode_responses=False)
        _bus_singleton = EventBus(redis=r, jsonl_path=ORGANISM_JSONL_DEFAULT)
    return _bus_singleton


def _reset_bus_for_tests() -> None:
    """Test-only: reset singleton so the next _get_bus() creates fresh."""
    global _bus_singleton
    _bus_singleton = None


def _detect_host() -> str:
    """Detect Pro vs Air from hostname."""
    h = socket.gethostname()
    if "Nuzantara-9" in h or "Air" in h:
        return "Air"
    return "Pro"


_HOST: str = _detect_host()


async def emit_event(
    *,
    severity: Severity,
    source: str,
    kind: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    is_actuation: bool = False,
) -> None:
    """Emit an event from anywhere (guardian, actuator, hook, script).

    Sanitizes payload via sanitize_payload(), generates correlation_id if
    absent (uuid4), writes to Redis stream + JSONL mirror via singleton bus.
    """
    safe = sanitize_payload(payload)
    ev = Event(
        severity=severity,
        source=source,
        kind=kind,
        payload=safe,
        correlation_id=correlation_id or str(uuid.uuid4()),
        is_actuation=is_actuation,
        host=_HOST,
    )
    await _get_bus().emit(ev)
