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
    member_key_from_email,
)

logger = logging.getLogger(__name__)
STREAM = "portal-champion:goals:v1"
CACHE_KEY = "dashboard:portal_challenge:v3"
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


def compute_status(now: datetime) -> str:
    """upcoming | live | closed for whichever round is active at `now` — a
    thin wrapper kept as a module-level name (rather than inlined) so tests
    can keep monkeypatching `events.compute_status` as the single seam that
    gates goal delivery, unchanged across the Round 1 -> Round 2 boundary."""
    from backend.services.portal import challenge_round2 as r2

    return r2.compute_round_status(now, r2.active_round(now))


async def publish_registration_goal(pool: Any, client_id: int) -> None:
    if compute_status(datetime.now(timezone.utc)) != "live":
        return
    try:
        async with asyncio.timeout(3):
            await _publish_registration_goal(pool, client_id)
    except Exception:
        logger.warning("Portal Champion goal delivery failed; registration remains successful")


async def _publish_registration_goal(pool: Any, client_id: int) -> None:
    from backend.services.portal import challenge_round2 as r2

    redis = RedisManager.get_instance().get_async_client()
    if redis is None:
        logger.warning("Portal Champion goal transport unavailable")
        return
    now = datetime.now(timezone.utc)
    round_number = r2.active_round(now)
    lookup_sql = build_goal_sql() if round_number == 1 else r2.build_goal_lookup_sql()
    async with pool.acquire() as connection:
        row = await connection.fetchrow(lookup_sql, client_id)
    if row is None or not _is_real_staff_row(row["creator_email"], row["role"]):
        return
    member = member_key_from_email(row["creator_email"])
    if round_number == 1:
        activations = int(row["activations"])
    else:
        activations = await _round2_points_for_creator(pool, row["creator_email"], now)
        if activations is None:
            return  # creator has no scored R2 entry (e.g. Asya) — skip the goal
    goal = {
        "member": member,
        "display_name": row["display_name"] or member,
        "avatar_url": portrait_url(row["avatar"]),
        "activations": activations,
        "at": row["at"].isoformat(timespec="milliseconds"),
    }
    digest = hashlib.sha256(f"{client_id}:{member}".encode()).hexdigest()
    await redis.delete(CACHE_KEY)
    await redis.eval(PUBLISH_ONCE, 2, STREAM, f"{STREAM}:scored:{digest}", json.dumps(goal))


async def _round2_points_for_creator(pool: Any, creator_email: str, now: datetime) -> int | None:
    """Full R2 scoring pipeline for one creator, used only for the live
    goal celebration's `activations` field (which in Round 2 means the
    scorer's `points`, not a raw registration count). Returns None when the
    creator has no scored entry (e.g. Asya, excluded from the general
    ranking) so the caller skips the goal rather than publish a bogus 0.
    """
    from backend.services.portal import challenge_round2 as r2
    from backend.services.portal.challenge_leaderboard import (
        ROSTER_SQL,
        build_aggregates_sql,
        compute_awards,
        merge_roster_and_activity,
    )

    async with pool.acquire() as connection:
        roster_records = await connection.fetch(ROSTER_SQL)
        r1_activity_records = await connection.fetch(build_aggregates_sql())
        registration_records = await connection.fetch(r2.build_registration_aggregates_sql())
        first_document_records = await connection.fetch(r2.build_first_documents_sql())
        request_records = await connection.fetch(r2.build_client_requests_sql())
        review_records = await connection.fetch(r2.build_required_document_reviews_sql())
        asya_request_records = await connection.fetch(r2.build_asya_requests_sql())
        asya_client_event_records = await connection.fetch(r2.build_asya_client_events_sql())

    roster_dicts = [dict(r) for r in roster_records]
    r1_awarded = compute_awards(
        merge_roster_and_activity(roster_dicts, [dict(r) for r in r1_activity_records])
    )
    snapshot = r2.score_round2(
        roster_dicts,
        r1_awarded,
        [dict(r) for r in registration_records],
        [dict(r) for r in first_document_records],
        [dict(r) for r in request_records],
        [dict(r) for r in review_records],
        [dict(r) for r in asya_request_records],
        [dict(r) for r in asya_client_event_records],
        now,
    )
    for entry in snapshot.entries:
        if entry.email == creator_email:
            return entry.points
    return None


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
