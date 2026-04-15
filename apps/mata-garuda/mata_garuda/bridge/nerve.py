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
    STREAM_BRIDGE_OUTBOUND,
)

logger = logging.getLogger("mata_garuda.bridge.nerve")


# ── Default I/O implementations (replaceable for tests) ────────────────


def _default_http_get(url: str, headers: dict[str, str], timeout: int) -> dict[str, Any]:
    """HTTP GET via curl subprocess. Returns {status_code, json, text}.

    Raises ConnectionError on network failures (no response received).
    """
    # -4: force IPv4. Fly.io publishes AAAA records but this host's IPv6 route
    # to Fly's anycast is unreachable, causing 15s timeouts under launchd's
    # minimal env (no Happy Eyeballs fallback). Discovered 2026-04-16.
    cmd = [
        "curl", "-sS", "-4",
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



# ── Push side ──────────────────────────────────────────────────────────


PUSH_CONSUMER_GROUP = "bridge-push"
PUSH_CONSUMER_NAME = "nerve-1"

# Map envelope type → backend ingest endpoint path
PUSH_ROUTING: dict[str, str] = {
    "intel.article_ready": "/api/bridge/ingest/article",
    "enrichment.kb_entry": "/api/bridge/ingest/enrichment",
}


def _default_http_post(
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    """HTTP POST via curl subprocess. Returns {status_code, json, text}."""
    # -4: force IPv4. See _default_http_get for the full explanation.
    cmd = [
        "curl", "-sS", "-4", "-X", "POST",
        "--max-time", str(timeout),
        "-w", "\\n%{http_code}",
    ]
    for k, v in headers.items():
        cmd.extend(["-H", f"{k}: {v}"])
    cmd.extend(["-H", "Content-Type: application/json"])
    cmd.extend(["-d", json.dumps(json_body, ensure_ascii=False)])
    cmd.append(url)

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout + 5,
    )
    if result.returncode != 0:
        raise ConnectionError(
            f"curl POST exit {result.returncode}: {result.stderr.strip()}"
        )

    output = result.stdout
    nl = output.rfind("\n")
    if nl == -1:
        raise ConnectionError(f"curl POST response missing status line: {output!r}")
    body = output[:nl]
    try:
        status = int(output[nl + 1:].strip())
    except ValueError as e:
        raise ConnectionError(f"curl POST invalid status: {output[nl + 1:]!r}") from e

    parsed: Any = None
    if body:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = None

    return {"status_code": status, "json": parsed, "text": body}


def _default_redis_xreadgroup(
    stream: str,
    group: str,
    consumer: str,
    count: int,
    block_ms: int,
) -> list[dict[str, Any]]:
    """XREADGROUP via redis-cli subprocess. Ensures group exists.

    Returns list of {id: msg_id, envelope: Envelope}. Empty list if no msgs.
    """
    # Ensure group exists (idempotent — fails silently if already exists)
    subprocess.run(
        ["redis-cli", "XGROUP", "CREATE", stream, group, "0", "MKSTREAM"],
        capture_output=True, text=True, timeout=5,
    )

    args = [
        "redis-cli", "XREADGROUP", "GROUP", group, consumer,
        "COUNT", str(count),
    ]
    if block_ms > 0:
        args.extend(["BLOCK", str(block_ms)])
    args.extend(["STREAMS", stream, ">"])

    result = subprocess.run(args, capture_output=True, text=True, timeout=15)
    if result.returncode != 0 or not result.stdout.strip():
        return []

    # Parse redis-cli flat output
    items: list[dict[str, Any]] = []
    lines = [ln.strip() for ln in result.stdout.split("\n") if ln.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if "-" in line and line[0].isdigit():
            msg_id = line
            data: dict[str, str] = {}
            j = i + 1
            while j < len(lines) and not (lines[j][0].isdigit() and "-" in lines[j]):
                if j + 1 < len(lines):
                    data[lines[j]] = lines[j + 1]
                    j += 2
                else:
                    break
            if data:
                try:
                    env = Envelope.from_redis_dict(data)
                    items.append({"id": msg_id, "envelope": env})
                except Exception as e:
                    logger.error("Failed to parse envelope %s: %s", msg_id, e)
            i = j
        else:
            i += 1
    return items


def _default_redis_xack(stream: str, group: str, msg_id: str) -> None:
    """ACK a message in a consumer group."""
    subprocess.run(
        ["redis-cli", "XACK", stream, group, msg_id],
        capture_output=True, text=True, timeout=5,
    )


def push_once(
    backend_url: str,
    api_key: str,
    batch: int = 10,
    timeout: int = BRIDGE_HTTP_TIMEOUT_S,
    http_post: Callable = _default_http_post,
    redis_xreadgroup: Callable = _default_redis_xreadgroup,
    redis_xack: Callable = _default_redis_xack,
) -> dict[str, int]:
    """Run one push cycle. Returns stats {sent, acked, errors}.

    For each message:
      - Lookup type in PUSH_ROUTING
      - Unknown type → ACK + log warning + count as error (no infinite loop)
      - Known type → POST to endpoint
      - 200/202 → ACK + count sent+acked
      - Non-2xx or exception → NOT ACK, count error (redelivered next cycle)
    """
    stats = {"sent": 0, "acked": 0, "errors": 0}

    items = redis_xreadgroup(
        STREAM_BRIDGE_OUTBOUND,
        PUSH_CONSUMER_GROUP,
        PUSH_CONSUMER_NAME,
        batch,
        1000,  # 1s block
    )

    if not items:
        return stats

    headers = {"X-Bridge-Auth": api_key, "Content-Type": "application/json"}

    for item in items:
        msg_id = item["id"]
        env: Envelope = item["envelope"]

        endpoint_path = PUSH_ROUTING.get(env.type)
        if endpoint_path is None:
            logger.warning(
                "Unknown push type %s (msg_id=%s) — ACKing to avoid loop",
                env.type, msg_id,
            )
            redis_xack(STREAM_BRIDGE_OUTBOUND, PUSH_CONSUMER_GROUP, msg_id)
            stats["acked"] += 1
            stats["errors"] += 1
            continue

        url = f"{backend_url.rstrip('/')}{endpoint_path}"
        try:
            resp = http_post(url, headers=headers, json_body=env.payload, timeout=timeout)
            stats["sent"] += 1
            status = resp.get("status_code")
            if status in (200, 202):
                redis_xack(STREAM_BRIDGE_OUTBOUND, PUSH_CONSUMER_GROUP, msg_id)
                stats["acked"] += 1
            else:
                logger.warning(
                    "Push %s non-2xx: status=%s body=%s — NOT acked",
                    env.type, status, (resp.get("text") or "")[:200],
                )
                stats["errors"] += 1
        except Exception as e:
            logger.warning("Push %s HTTP error: %s — NOT acked", env.type, e)
            stats["errors"] += 1

    if stats["sent"] or stats["errors"]:
        logger.info(
            "Bridge push: sent=%d acked=%d errors=%d",
            stats["sent"], stats["acked"], stats["errors"],
        )

    return stats


def push_loop_main() -> None:
    """Entry point for the push worker (single iteration — cron driven)."""
    api_key = os.getenv(BRIDGE_API_KEY_ENV, "")
    if not api_key:
        logger.error("BRIDGE_API_KEY not set — aborting push")
        return
    push_once(backend_url=BRIDGE_BACKEND_URL, api_key=api_key)


def bridge_main() -> None:
    """Entry point: run pull then push in one cycle."""
    api_key = os.getenv(BRIDGE_API_KEY_ENV, "")
    if not api_key:
        logger.error("BRIDGE_API_KEY not set — aborting bridge cycle")
        return

    cursor = BridgeCursor(BRIDGE_CURSOR_PATH)
    pull_once(cursor=cursor, backend_url=BRIDGE_BACKEND_URL, api_key=api_key)
    push_once(backend_url=BRIDGE_BACKEND_URL, api_key=api_key)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    bridge_main()
