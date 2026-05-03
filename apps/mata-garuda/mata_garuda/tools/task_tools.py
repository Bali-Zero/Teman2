"""
Mata Garuda — Task Stream Tools.

Read research/enrichment tasks from Redis Stream and dispatch agents.
The task stream is a generic queue — MG does not know where tasks originate.

Stream: nexus:gaps (configurable via TASK_STREAM env var)
Consumer group: mata-garuda-tasks
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from mata_garuda.registry import register_tool

logger = logging.getLogger("mata_garuda.tools")

TASK_STREAM = os.environ.get("MG_TASK_STREAM", "nexus:gaps")
TASK_GROUP = "mata-garuda-tasks"
TASK_CONSUMER = "mg-worker-1"
REDIS_CLI = "redis-cli"


def _redis_cmd(*args: str, timeout: int = 10) -> str:
    """Execute a redis-cli command and return output."""
    cmd = [REDIS_CLI] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return f"[ERROR] redis-cli: {result.stderr.strip()}"
        return result.stdout.strip()
    except FileNotFoundError:
        return "[ERROR] redis-cli not found"
    except subprocess.TimeoutExpired:
        return f"[ERROR] redis-cli timeout after {timeout}s"


@dataclass
class TaskRequest:
    """A generic research/enrichment task from the task stream."""

    msg_id: str
    request_id: str = ""
    entity_type: str = ""
    entity_name: str = ""
    entity_nip: str = ""
    gap_type: str = ""
    attribute: str = ""
    priority: int = 3
    ttl_seconds: int = 86400
    created_at: str = ""


def _parse_task_entries(raw: str) -> list[TaskRequest]:
    """Parse Redis XREADGROUP output into TaskRequest objects."""
    entries = []
    lines = raw.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line and "-" in line and line[0].isdigit():
            msg_id = line
            fields: dict[str, str] = {}
            i += 1
            while i < len(lines):
                key_line = lines[i].strip()
                if not key_line or (key_line[0].isdigit() and "-" in key_line):
                    break
                if i + 1 < len(lines):
                    fields[key_line] = lines[i + 1].strip()
                    i += 2
                else:
                    i += 1

            task = TaskRequest(
                msg_id=msg_id,
                request_id=fields.get("request_id", ""),
                entity_type=fields.get("entity_type", ""),
                entity_name=fields.get("entity_name", ""),
                entity_nip=fields.get("entity_nip", ""),
                gap_type=fields.get("gap_type", ""),
                attribute=fields.get("attribute", ""),
                priority=int(fields.get("priority", "3")),
                ttl_seconds=int(fields.get("ttl_seconds", "86400")),
                created_at=fields.get("created_at", ""),
            )
            entries.append(task)
        else:
            i += 1
    return entries


def ensure_task_group() -> None:
    """Create consumer group if it doesn't exist."""
    result = _redis_cmd("XGROUP", "CREATE", TASK_STREAM, TASK_GROUP, "0", "MKSTREAM")
    if "[ERROR]" in result and "BUSYGROUP" not in result:
        logger.warning(f"Failed to create task group: {result}")


def ack_task(msg_id: str) -> None:
    """Acknowledge a processed task."""
    _redis_cmd("XACK", TASK_STREAM, TASK_GROUP, msg_id)


@register_tool(name="task_read")
def task_read(
    count: int = 10,
    context_variables: dict | None = None,
) -> str:
    """Read pending research/enrichment tasks from the task stream.

    Args:
        count: Max tasks to read (default: 10)

    Returns:
        JSON list of task objects, sorted by priority (1=urgent first).
    """
    ensure_task_group()

    raw = _redis_cmd(
        "XREADGROUP", "GROUP", TASK_GROUP, TASK_CONSUMER,
        "COUNT", str(count),
        "STREAMS", TASK_STREAM, ">"
    )

    if raw.startswith("[ERROR]"):
        return raw

    if not raw or raw == "(nil)":
        return "[]"

    tasks = _parse_task_entries(raw)
    # Sort by priority (lower = more urgent)
    tasks.sort(key=lambda t: t.priority)

    result = []
    for t in tasks:
        result.append({
            "msg_id": t.msg_id,
            "request_id": t.request_id,
            "entity_type": t.entity_type,
            "entity_name": t.entity_name,
            "entity_nip": t.entity_nip,
            "gap_type": t.gap_type,
            "attribute": t.attribute,
            "priority": t.priority,
        })

    return json.dumps(result, ensure_ascii=False)


@register_tool(name="task_ack")
def task_ack(
    msg_id: str,
    context_variables: dict | None = None,
) -> str:
    """Acknowledge a task as completed.

    Args:
        msg_id: Redis stream message ID to acknowledge.
    """
    ack_task(msg_id)
    return f"[ACK] {msg_id}"


@register_tool(name="task_info")
def task_info(
    context_variables: dict | None = None,
) -> str:
    """Get info about the task stream (length, groups, pending)."""
    length = _redis_cmd("XLEN", TASK_STREAM)
    if length.startswith("[ERROR]") or "no such key" in length.lower():
        return f"Task stream {TASK_STREAM} does not exist yet"

    pending = _redis_cmd("XPENDING", TASK_STREAM, TASK_GROUP)

    return f"Task stream: {TASK_STREAM}\nLength: {length}\nPending:\n{pending}"
