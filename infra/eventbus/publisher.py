"""Bali Zero event publisher (Redis Streams via redis-py).

Usage:
    from eventbus import publish
    eid = publish("intel.collected", {"source": "regulatory-watcher", ...})

REFACTORED 2026-05-09 per Gemini W1 review (P0): replaced redis-cli subprocess
with native redis-py to fix ARG_MAX limit, parser fragility, throughput ceiling.
"""
from __future__ import annotations
import os
import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis

from .schema import EVENT_TYPES, MAXLEN, validate_payload, generate_event_id

REDIS_HOST = os.environ.get("BZ_REDIS_HOST", "100.93.236.6")
REDIS_PORT = int(os.environ.get("BZ_REDIS_PORT", "6379"))
STREAM_PREFIX = "bz:"

log = logging.getLogger("eventbus.publisher")

# Singleton connection pool, reused across publish() calls
_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
    socket_timeout=65,
    socket_connect_timeout=5,
    max_connections=10,
)


def _client() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


def publish(
    event_type: str,
    payload: dict[str, Any],
    *,
    emitted_by: str | None = None,
    trace_id: str | None = None,
) -> str:
    """Publish event to Redis Stream `bz:<event_type>`.

    Returns event_id. Raises ValueError on schema violation, RedisError on infra failure.
    """
    validate_payload(event_type, payload)

    event_id = generate_event_id()
    if trace_id is None:
        trace_id = event_id

    if emitted_by is None:
        emitted_by = os.environ.get("BZ_AGENT_NAME", "unknown-agent")

    envelope = {
        "event_id": event_id,
        "event_type": event_type,
        "version": "1",
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "emitted_by": emitted_by,
        "trace_id": trace_id,
        "payload": json.dumps(payload, default=str),
    }

    stream = f"{STREAM_PREFIX}{event_type}"
    maxlen = MAXLEN.get(event_type, 10000)

    try:
        redis_id = _client().xadd(stream, envelope, maxlen=maxlen, approximate=True)
        log.info(
            "published %s event_id=%s stream=%s redis_id=%s",
            event_type, event_id, stream, redis_id,
        )
        return event_id
    except redis.RedisError as e:
        log.error("publish failed: %s", e)
        raise


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("usage: python -m eventbus.publisher <event_type> '<json_payload>'", file=sys.stderr)
        sys.exit(2)
    print(publish(sys.argv[1], json.loads(sys.argv[2])))
