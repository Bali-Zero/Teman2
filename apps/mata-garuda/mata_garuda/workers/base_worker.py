"""
Mata Garuda — Base worker for Redis Stream consumers.

Workers read from garuda:raw, process items, and write to garuda:enriched.
Uses redis-cli subprocess — no redis-py dependency.
"""
from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from datetime import datetime
from typing import Optional

logger = logging.getLogger("mata_garuda.workers")

REDIS_CLI = "redis-cli"


def redis_cmd(*args: str, timeout: int = 10) -> str:
    """Execute a redis-cli command and return output."""
    cmd = [REDIS_CLI] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            return f"[ERROR] redis-cli: {result.stderr.strip()}"
        return result.stdout.strip()
    except FileNotFoundError:
        return "[ERROR] redis-cli not found"
    except subprocess.TimeoutExpired:
        return f"[ERROR] redis-cli timeout after {timeout}s"


def stream_read_new(
    stream: str,
    group: str,
    consumer: str,
    count: int = 10,
    block_ms: int = 0,
) -> list[dict]:
    """Read new items from a Redis Stream consumer group.

    Creates the group if it doesn't exist.
    Returns list of {id, data} dicts.
    """
    # Ensure group exists
    redis_cmd("XGROUP", "CREATE", stream, group, "0", "MKSTREAM")

    args = ["XREADGROUP", "GROUP", group, consumer, "COUNT", str(count)]
    if block_ms > 0:
        args += ["BLOCK", str(block_ms)]
    args += ["STREAMS", stream, ">"]

    result = redis_cmd(*args)
    if not result or result.startswith("[ERROR]"):
        return []

    return _parse_xreadgroup(result, stream)


def stream_ack(stream: str, group: str, msg_id: str) -> None:
    """Acknowledge a message in a consumer group."""
    redis_cmd("XACK", stream, group, msg_id)


def stream_publish(stream: str, data: dict) -> str:
    """Publish data to a Redis Stream. Returns message ID."""
    fields = []
    for k, v in data.items():
        fields.extend([k, str(v) if not isinstance(v, str) else v])

    result = redis_cmd("XADD", stream, "*", *fields)
    return result


def content_hash(text: str) -> str:
    """SHA256 hash for deduplication."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _parse_xreadgroup(raw: str, stream: str) -> list[dict]:
    """Parse XREADGROUP output into list of {id, data} dicts.

    redis-cli output format is not JSON — it's a flat list of alternating
    keys and values. We parse it line by line.
    """
    items = []
    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    # Simple heuristic parse — redis-cli outputs stream name, then entries
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for message IDs (format: timestamp-seq)
        if "-" in line and line[0].isdigit():
            msg_id = line
            data = {}
            # Read key-value pairs that follow
            j = i + 1
            while j < len(lines) and not (lines[j][0].isdigit() and "-" in lines[j]):
                if j + 1 < len(lines):
                    key = lines[j]
                    val = lines[j + 1]
                    data[key] = val
                    j += 2
                else:
                    break
            if data:
                items.append({"id": msg_id, "data": data})
            i = j
        else:
            i += 1

    return items
