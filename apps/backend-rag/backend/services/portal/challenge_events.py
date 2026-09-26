from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from backend.core.redis_manager import RedisManager
from backend.services.portal.challenge_leaderboard import (
    _is_real_staff_row,
    build_goal_sql,
    compute_status,
    member_key_from_email,
)

logger = logging.getLogger(__name__)
STREAM = "portal-champion:goals:v1"
CACHE_KEY = "dashboard:portal_challenge:v2"
MAX_AGE_MS = 90_000
REPLAY_PAGE = 100
PUBLISH_ONCE = """
if redis.call('EXISTS', KEYS[2]) == 1 then return false end
local event_id = redis.call('XADD', KEYS[1], 'MAXLEN', '~', 2000, '*', 'goal', ARGV[1])
redis.call('SET', KEYS[2], '1', 'EX', 604800)
redis.call('EXPIRE', KEYS[1], 604800)
return event_id
"""


def portrait_url(value: Any) -> str | None:
    if isinstance(value, str) and re.fullmatch(
        r"/static/team/[a-zA-Z0-9_-]+\.(jpg|jpeg|png|webp)", value
    ):
        return value
    return None


async def publish_registration_goal(pool: Any, client_id: int) -> None:
    if compute_status(datetime.now(timezone.utc)) != "live":
        return
    try:
        async with asyncio.timeout(3):
            await _publish_registration_goal(pool, client_id)
    except Exception:
        logger.warning("Portal Champion goal delivery failed; registration remains successful")


async def _publish_registration_goal(pool: Any, client_id: int) -> None:
    redis = RedisManager.get_instance().get_async_client()
    if redis is None:
        logger.warning("Portal Champion goal transport unavailable")
        return
    async with pool.acquire() as connection:
        row = await connection.fetchrow(build_goal_sql(), client_id)
    if row is None or not _is_real_staff_row(row["creator_email"], row["role"]):
        return
    member = member_key_from_email(row["creator_email"])
    goal = {
        "member": member,
        "display_name": row["display_name"] or member,
        "avatar_url": portrait_url(row["avatar"]),
        "activations": int(row["activations"]),
        "at": row["at"].isoformat(timespec="milliseconds"),
    }
    digest = hashlib.sha256(f"{client_id}:{member}".encode()).hexdigest()
    await redis.delete(CACHE_KEY)
    await redis.eval(PUBLISH_ONCE, 2, STREAM, f"{STREAM}:scored:{digest}", json.dumps(goal))


class GoalFanout:
    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue] = set()
        self.task: asyncio.Task | None = None

    async def _read(self, redis: Any, cursor: str) -> None:
        try:
            while self.subscribers:
                batches = await redis.xread({STREAM: cursor}, count=100, block=2000)
                for _, events in batches:
                    for event_id, fields in events:
                        cursor = event_id
                        for queue in tuple(self.subscribers):
                            if queue.full():
                                queue.get_nowait()
                                queue.put_nowait(None)
                            else:
                                queue.put_nowait((event_id, fields))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Portal Champion event stream disconnected")
            for queue in self.subscribers:
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(None)

    async def events(self, redis: Any, last_id: str | None) -> AsyncIterator[str]:
        seconds, microseconds = await redis.time()
        now_ms = int(seconds) * 1000 + int(microseconds) // 1000
        valid_last_id = bool(last_id and re.fullmatch(r"\d{1,16}-\d{1,16}", last_id))
        # Both cursors are exclusive, so start one millisecond early: an XADD in the
        # same millisecond as TIME gets id `now_ms-0` and must not fall between them.
        start = f"{now_ms - 1}-0"
        cursor = (
            max(
                last_id,
                f"{now_ms - MAX_AGE_MS}-0",
                key=lambda value: tuple(map(int, value.split("-"))),
            )
            if valid_last_id and int(last_id.split("-")[0]) <= now_ms
            else start
        )
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.subscribers.add(queue)
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._read(redis, start))
        try:
            ready = json.dumps(
                {"server_time": datetime.now(timezone.utc).isoformat(timespec="milliseconds")}
            )
            yield f"retry: 3000\nevent: ready\nid: {cursor}\ndata: {ready}\n\n"
            while True:
                replay = await redis.xrange(STREAM, min=f"({cursor}", max="+", count=REPLAY_PAGE)
                for event_id, fields in replay:
                    cursor = event_id
                    if int(event_id.split("-")[0]) >= now_ms - MAX_AGE_MS:
                        yield f"event: goal\nid: {event_id}\ndata: {fields['goal']}\n\n"
                if len(replay) < REPLAY_PAGE:
                    break
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if item is None:
                    return
                event_id, fields = item
                if tuple(map(int, event_id.split("-"))) <= tuple(map(int, cursor.split("-"))):
                    continue
                cursor = event_id
                yield f"event: goal\nid: {event_id}\ndata: {fields['goal']}\n\n"
        finally:
            self.subscribers.discard(queue)
            if not self.subscribers and self.task:
                task, self.task = self.task, None
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task


goal_fanout = GoalFanout()
