"""
Mata Garuda — Base worker for Redis Stream consumers.

Workers read from garuda:raw, process items, and write to garuda:enriched.
Uses redis-cli subprocess — no redis-py dependency.

Cross-host topology (2026-05-06): when GARUDA_REDIS_HOST is set, every
redis-cli call is routed to that host (with optional GARUDA_REDIS_PORT).
This lets the feeder running on Pro consume the alerts stream produced
by the sentinel running on Mini, without standing up a redis-py client.
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess

logger = logging.getLogger("mata_garuda.workers")

REDIS_CLI = "redis-cli"


def _redis_host_args() -> list[str]:
    """Return ['-h', host] (and optional ['-p', port]) from env vars.

    GARUDA_REDIS_HOST empty/unset → no -h/-p (redis-cli defaults to 127.0.0.1).
    GARUDA_REDIS_PORT without HOST → ignored (avoid surprising localhost:port).
    """
    host = (os.environ.get("GARUDA_REDIS_HOST") or "").strip()
    if not host:
        return []
    args = ["-h", host]
    port = (os.environ.get("GARUDA_REDIS_PORT") or "").strip()
    if port:
        args += ["-p", port]
    return args


def redis_cmd(*args: str, timeout: int = 10) -> str:
    """Execute a redis-cli command and return output."""
    cmd = [REDIS_CLI] + _redis_host_args() + list(args)
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


def stream_ack(stream: str, group: str, msg_id: str) -> bool:
    """Acknowledge a message in a consumer group.

    Returns True if XACK confirmed the message was in PEL and got acked,
    False if Redis returned 0 (msg not in PEL — silent failure, e.g. the
    cleaner already drained it, or msg_id was wrong) or the redis-cli
    invocation errored.

    Callers that don't care about ack failure can ignore the return value;
    backward-compatible. Callers that DO care (e.g. graceful PEL-overflow
    detection) can act on False.

    W14 (2026-05-22): added return value + WARNING log on silent ack-zero
    to make PEL stuck-orphan issues visible from worker logs without
    requiring a separate XPENDING audit. See W13 cicatrix for the
    accumulation pattern this catches.
    """
    result = redis_cmd("XACK", stream, group, msg_id)
    if result.startswith("[ERROR]"):
        logger.warning(
            "[stream_ack] redis-cli error acking %s/%s/%s: %s",
            stream, group, msg_id, result,
        )
        return False
    try:
        acked = int(result.strip())
    except ValueError:
        logger.warning(
            "[stream_ack] unparseable XACK reply for %s/%s/%s: %r",
            stream, group, msg_id, result,
        )
        return False
    if acked == 0:
        logger.warning(
            "[stream_ack] XACK returned 0 for %s/%s/%s — msg not in PEL "
            "(already drained, wrong id, or race)",
            stream, group, msg_id,
        )
        return False
    return True


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


def _is_msg_id(line: str) -> bool:
    """True if `line` looks like a Redis Stream message ID (timestamp-seq).

    Empty/whitespace lines return False (so they are NOT mistaken for IDs
    and can flow through as legitimate empty values in the field stream).
    """
    if not line:
        return False
    if not line[0].isdigit():
        return False
    if "-" not in line:
        return False
    # Defensive: confirm timestamp-seq shape (digits-digits)
    parts = line.split("-", 1)
    return len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()


def _parse_xreadgroup(raw: str, stream: str) -> list[dict]:
    """Parse XREADGROUP output into list of {id, data} dicts.

    redis-cli output format is not JSON — it's a flat list of alternating
    keys and values. We parse it line by line.

    Empty values (e.g. ``entity_nip`` blank for an Organization gap) are
    PRESERVED as empty strings, not silently dropped. The previous
    implementation stripped empty lines wholesale, which shifted every
    key/value pair after the first empty value and silently corrupted
    `gap_type`, `attribute`, etc. Discovered 2026-05-16 during Pilastro 1
    reflection regression debug — see research/symbiosis/.../dispatch-alias.
    """
    items = []
    # Preserve empty lines (they may be empty values); only rstrip the
    # trailing whitespace + \r introduced by redis-cli line-buffering.
    lines = [line.rstrip() for line in raw.split("\n")]

    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_msg_id(line):
            msg_id = line
            data = {}
            # Read key-value pairs until the next message ID. Empty lines
            # between two non-ID lines are real values, not separators.
            j = i + 1
            while j < len(lines) and not _is_msg_id(lines[j]):
                if j + 1 < len(lines):
                    key = lines[j]
                    val = lines[j + 1]
                    if key:  # field names are always non-empty
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
