"""Audit logger for MCP tool calls — JSONL file for pilot, PostgreSQL later."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("audit")

AUDIT_FILE = Path(__file__).parent / "audit" / "tool_calls.jsonl"


def log_tool_call(
    role: str,
    tool_name: str,
    allowed: bool,
    params: dict | None = None,
) -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "tool": tool_name,
        "allowed": allowed,
        "params_keys": list((params or {}).keys()),
    }
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    if not allowed:
        logger.warning("BLOCKED: role=%s tried tool=%s", role, tool_name)
