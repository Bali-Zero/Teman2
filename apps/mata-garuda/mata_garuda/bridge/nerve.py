"""
Mata Garuda — Bridge Nerve.

Bidirectional bridge worker between Pro (local) and Fly.io (cloud).

Pull side (this file): GET /api/bridge/events?after_id={cursor} → wrap each
event in an Envelope and XADD to bridge:inbound.

Push side: see push_once() (Task 10, appended later).

Transport: subprocess + curl + redis-cli (no httpx — Mata Garuda only allows
pydantic + pytest as runtime deps).

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §4
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any, Callable

from mata_garuda.bridge.cursor import BridgeCursor
from mata_garuda.bridge.envelope import Envelope
from mata_garuda.config import (
    BRIDGE_API_KEY_ENV,
    BRIDGE_BACKEND_URL,
    BRIDGE_CURSOR_PATH,
    BRIDGE_HTTP_TIMEOUT_S,
    BRIDGE_PULL_LIMIT,
    STREAM_BRIDGE_INBOUND,
)

logger = logging.getLogger("mata_garuda.bridge.nerve")


# ── Default I/O implementations (replaceable for tests) ────────────────


def _default_http_get(url: str, headers: dict[str, str], timeout: int) -> dict[str, Any]:
    """HTTP GET via curl subprocess. Returns {status_code, json, text}.

    Raises ConnectionError on network failures (no response received).
    """
    cmd = [
        "curl", "-sS",
        "--max-time", str(timeout),
        "-w", "\\n%{http_code}",  # Append status code on a new line
    ]
    for k, v in headers.items():
        cmd.extend(["-H", f"{k}: {v}"])
    cmd.append(url)

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout + 5,
    )
    if result.returncode != 0:
        raise ConnectionError(
            f"curl exit {result.returncode}: {result.stderr.strip()}"
        )

    output = result.stdout
    # Last line is the status code; everything before is the body.
    nl = output.rfind("\n")
    if nl == -1:
        raise ConnectionError(f"curl response missing status line: {output!r}")
    body = output[:nl]
    try:
        status = int(output[nl + 1:].strip())
    except ValueError as e:
        raise ConnectionError(f"curl invalid status: {output[nl + 1:]!r}") from e

    parsed: Any = None
    if body:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = None  # leave as None; caller will check

    return {"status_code": status, "json": parsed, "text": body}


def _default_redis_xadd(stream: str, fields: dict[str, str]) -> str:
    """XADD via redis-cli subprocess (matches existing MG pattern)."""
    args = ["redis-cli", "XADD", stream, "*"]
    for k, v in fields.items():
        args.extend([k, v])
    result = subprocess.run(args, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(f"redis-cli XADD failed: {result.stderr.strip()}")
    return result.stdout.strip()


# ── Pull side ──────────────────────────────────────────────────────────


def pull_once(
    cursor: BridgeCursor,
    backend_url: str,
    api_key: str,
    http_get: Callable = _default_http_get,
    redis_xadd: Callable = _default_redis_xadd,
    limit: int = BRIDGE_PULL_LIMIT,
    timeout: int = BRIDGE_HTTP_TIMEOUT_S,
) -> dict[str, int]:
    """Run one pull cycle. Returns stats {fetched, published, errors}.

    Cursor only advances if ALL events in the batch published successfully.
    If any event fails, cursor stays put — next cycle replays everything
    (at-least-once semantics, which matches Redis Streams + Envelope.id dedup
    downstream).
    """
    stats = {"fetched": 0, "published": 0, "errors": 0}

    after_id = cursor.read()
    url = (
        f"{backend_url.rstrip('/')}/api/bridge/events"
        f"?after_id={after_id}&limit={limit}"
    )
    headers = {"X-Bridge-Auth": api_key}

    try:
        resp = http_get(url, headers=headers, timeout=timeout)
    except Exception as e:
        logger.warning("Bridge pull HTTP error: %s — cursor unchanged", e)
        stats["errors"] = 1
        return stats

    status = resp.get("status_code")
    if status != 200:
        logger.warning(
            "Bridge pull non-200: status=%s body=%s",
            status,
            (resp.get("text") or "")[:200],
        )
        stats["errors"] = 1
        return stats

    body = resp.get("json")
    if not isinstance(body, dict):
        logger.error("Bridge pull JSON parse error or empty body")
        stats["errors"] = 1
        return stats

    events = body.get("events", [])
    last_id = int(body.get("last_id", after_id))
    stats["fetched"] = len(events)

    if not events:
        return stats

    # Publish each event. If ANY fails, do NOT advance cursor.
    for event in events:
        try:
            env = Envelope(
                type=event["type"],
                source="bridge",
                priority=3,  # default; payload-specific priority is Phase 2
                payload={
                    **event.get("payload", {}),
                    "_outbox_id": event["id"],
                    "_outbox_created_at": event.get("created_at"),
                },
            )
            redis_xadd(STREAM_BRIDGE_INBOUND, env.to_redis_dict())
            stats["published"] += 1
        except Exception as e:
            logger.error(
                "Failed to publish event id=%s: %s",
                event.get("id"), e,
            )
            stats["errors"] += 1

    # Advance cursor ONLY if zero errors during publish (all-or-nothing semantics)
    if stats["errors"] == 0:
        cursor.write(last_id)
        logger.info(
            "Bridge pull: fetched=%d published=%d cursor=%d",
            stats["fetched"], stats["published"], last_id,
        )
    else:
        logger.warning(
            "Bridge pull: fetched=%d published=%d errors=%d — cursor NOT advanced",
            stats["fetched"], stats["published"], stats["errors"],
        )

    return stats


def pull_loop_main() -> None:
    """Entry point for the pull worker (single iteration — cron driven)."""
    api_key = os.getenv(BRIDGE_API_KEY_ENV, "")
    if not api_key:
        logger.error("BRIDGE_API_KEY not set — aborting pull")
        return

    cursor = BridgeCursor(BRIDGE_CURSOR_PATH)
    pull_once(cursor=cursor, backend_url=BRIDGE_BACKEND_URL, api_key=api_key)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    pull_loop_main()
