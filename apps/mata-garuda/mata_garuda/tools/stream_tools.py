"""
Mata Garuda — Redis Stream Tools.

Publish to and consume from Redis Streams via redis-cli subprocess.
No redis-py dependency — CLI-only per vincolo Mata Garuda.

Stream: garuda:raw — raw harvested data from Layer 1 agents.
"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime

from mata_garuda.registry import register_tool

logger = logging.getLogger("mata_garuda.tools")

DEFAULT_STREAM = "garuda:raw"
REDIS_CLI = "redis-cli"


def _redis_cmd(*args: str, timeout: int = 10) -> str:
    """Execute a redis-cli command and return output.

    Delegates to base_worker.redis_cmd (the SSOT), which carries REDISCLI_AUTH
    (cicatrix #4 — never -a on argv), the canonical-host resolution, and the
    absolute redis-cli path. This module's harvester (run_sentinel_py →
    stream_publish) was previously running BARE `redis-cli` here with NO auth, so
    every XADD silently failed (NOAUTH) and garuda:raw froze for days while the
    harvester reported success (cicatrix #1 partial-fix drift + #2 green-but-dead).
    Fixed 2026-06-30 by routing through the already-cured base_worker path.
    base_worker does NOT import stream_tools → no circular import; redis_cmd is a
    generic passthrough so the MAXLEN/* this module supplies still applies.
    """
    from mata_garuda.workers.base_worker import redis_cmd as _bw_redis_cmd
    return _bw_redis_cmd(*args, timeout=timeout)


@register_tool(name="stream_publish")
def stream_publish(
    title: str,
    url: str,
    source: str,
    content: str = "",
    stream: str = DEFAULT_STREAM,
    context_variables: dict | None = None,
) -> str:
    """Publish a harvested item to Redis Stream.

    Args:
        title: Document/regulation title
        url: Source URL
        source: Source identifier (e.g., "peraturan.go.id")
        content: Content text or summary
        stream: Redis stream name (default: garuda:raw)
    """
    ts = datetime.now().isoformat(timespec="seconds")

    # XADD stream * field value field value ...
    # MAXLEN ~ N approximate trim (council fix — bounded RAM, O(1)).
    from mata_garuda.config import STREAM_MAXLEN
    result = _redis_cmd(
        "XADD", stream, "MAXLEN", "~", str(STREAM_MAXLEN), "*",
        "title", title,
        "url", url,
        "source", source,
        "content", content[:2000],  # Cap content to avoid Redis issues
        "timestamp", ts,
        "agent", context_variables.get("agent_name", "unknown") if context_variables else "unknown",
    )

    if result.startswith("[ERROR]"):
        return result

    logger.info(f"[stream] Published to {stream}: {title[:60]}")
    return f"[SUCCESS] Published to {stream} (id: {result})"


@register_tool(name="stream_read")
def stream_read(
    count: int = 5,
    stream: str = DEFAULT_STREAM,
    context_variables: dict | None = None,
) -> str:
    """Read latest items from Redis Stream.

    Args:
        count: Number of items to read (default: 5)
        stream: Redis stream name (default: garuda:raw)
    """
    # XREVRANGE stream + - COUNT n
    result = _redis_cmd(
        "XREVRANGE", stream, "+", "-", "COUNT", str(count)
    )

    if result.startswith("[ERROR]"):
        return result

    if not result:
        return f"No items in {stream}"

    return f"Latest {count} items from {stream}:\n{result}"


@register_tool(name="stream_info")
def stream_info(
    stream: str = DEFAULT_STREAM,
    context_variables: dict | None = None,
) -> str:
    """Get info about a Redis Stream.

    Args:
        stream: Redis stream name (default: garuda:raw)
    """
    result = _redis_cmd("XINFO", "STREAM", stream)

    if result.startswith("[ERROR]") or "ERR" in result or "no such key" in result.lower():
        return f"Stream {stream} does not exist yet"

    return f"Stream {stream} info:\n{result}"


@register_tool(name="stream_length")
def stream_length(
    stream: str = DEFAULT_STREAM,
    context_variables: dict | None = None,
) -> str:
    """Get the number of items in a Redis Stream.

    Args:
        stream: Redis stream name (default: garuda:raw)
    """
    result = _redis_cmd("XLEN", stream)

    if result.startswith("[ERROR]"):
        return result

    return f"Stream {stream} has {result} items"
