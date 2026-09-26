import asyncio
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.portal import challenge_events as events


@pytest.fixture
def transport(monkeypatch):
    redis = AsyncMock()
    manager = MagicMock()
    manager.get_async_client.return_value = redis
    monkeypatch.setattr(events.RedisManager, "get_instance", lambda: manager)
    monkeypatch.setattr(events, "compute_status", lambda now: "live")
    connection = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = connection
    connection.fetchrow.return_value = {
        "creator_email": "contender@balizero.com",
        "role": "team",
        "display_name": "Contender",
        "avatar": "/static/team/sample.jpg",
        "activations": 12,
        "at": datetime.now(timezone.utc),
    }
    return redis, connection, pool


@pytest.mark.asyncio
async def test_publish_invalidates_then_emits_only_staff_projection(transport):
    redis, connection, pool = transport
    await events.publish_registration_goal(pool, 999999)
    redis.delete.assert_awaited_once_with(events.CACHE_KEY)
    redis.eval.assert_awaited_once()
    arguments = redis.eval.await_args.args
    goal = json.loads(arguments[-1])
    assert goal["activations"] == 12
    assert goal["display_name"] == "Contender"
    assert "999999" not in arguments[-2]
    assert "client_id" not in goal and "email" not in goal
    assert connection.fetchrow.await_args.args[1] == 999999


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "row", [None, {"creator_email": "probe@balizero.com", "role": "monitoring"}]
)
async def test_no_goal_for_excluded_registration(transport, row):
    redis, connection, pool = transport
    connection.fetchrow.return_value = row
    await events.publish_registration_goal(pool, 999999)
    redis.eval.assert_not_awaited()


@pytest.mark.asyncio
async def test_closed_window_and_transport_failure_never_fail_registration(transport, monkeypatch):
    redis, _, pool = transport
    monkeypatch.setattr(events, "compute_status", lambda now: "closed")
    await events.publish_registration_goal(pool, 999999)
    redis.eval.assert_not_awaited()
    monkeypatch.setattr(events, "compute_status", lambda now: "live")
    redis.eval.side_effect = ConnectionError("offline")
    await events.publish_registration_goal(pool, 999999)


class FakeStream:
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.replay = []
        self.readers = 0

    async def xread(self, *args, **kwargs):
        self.readers += 1
        try:
            return await self.incoming.get()
        finally:
            self.readers -= 1

    async def xrange(self, *args, **kwargs):
        return self.replay

    async def time(self):
        now = time.time()
        return int(now), int((now % 1) * 1_000_000)


@pytest.mark.asyncio
async def test_two_screens_share_one_reader_and_receive_the_same_goal():
    redis = FakeStream()
    fanout = events.GoalFanout()
    first, second = fanout.events(redis, None), fanout.events(redis, None)
    assert "event: ready" in await anext(first)
    assert "event: ready" in await anext(second)
    deliveries = [asyncio.create_task(anext(first)), asyncio.create_task(anext(second))]
    await asyncio.sleep(0)
    assert redis.readers == 1
    event_id = f"{int(time.time() * 1000) + 1}-0"
    await redis.incoming.put([(events.STREAM, [(event_id, {"goal": '{"member":"contender"}'})])])
    result = await asyncio.wait_for(asyncio.gather(*deliveries), timeout=1)
    assert result[0] == result[1]
    assert "event: goal" in result[0]
    await first.aclose()
    await second.aclose()
    assert fanout.task is None
    assert not fanout.subscribers


@pytest.mark.asyncio
async def test_reconnect_replays_recent_events_after_last_event_id():
    redis = FakeStream()
    now_ms = int(time.time() * 1000)
    redis.replay = [(f"{now_ms}-0", {"goal": '{"member":"contender"}'})]
    fanout = events.GoalFanout()
    stream = fanout.events(redis, f"{now_ms - 1000}-0")
    assert f"id: {now_ms - 1000}-0" in await anext(stream)
    assert f"id: {now_ms}-0" in await anext(stream)
    await stream.aclose()


@pytest.mark.asyncio
async def test_idle_stream_rotation_replays_a_goal_during_the_reconnect_gap():
    redis = FakeStream()
    now_ms = int(time.time() * 1000)
    event_id = f"{now_ms - 1000}-0"
    redis.replay = [(event_id, {"goal": '{"member":"contender"}'})]
    fanout = events.GoalFanout()
    stream = fanout.events(redis, f"{now_ms - 243_000}-0")
    ready = await anext(stream)
    assert f"id: {now_ms - 243_000}-0" not in ready
    assert event_id in await anext(stream)
    await stream.aclose()


def test_portraits_allow_only_local_team_assets():
    assert events.portrait_url("/static/team/sample.jpg")
    for value in [None, "https://external.invalid/photo.jpg", "/static/team/../secret.jpg", {}]:
        assert events.portrait_url(value) is None


@pytest.mark.asyncio
async def test_registration_schedules_delivery_only_after_commit(monkeypatch):
    from fastapi import BackgroundTasks

    from backend.app.routers.portal_invite import CompleteRegistrationRequest, complete_registration

    service = MagicMock()
    service.complete_registration = AsyncMock(
        return_value={"client_id": 999999, "user_id": "fixture", "email": "fixture@example.test"}
    )
    publisher = AsyncMock()
    monkeypatch.setattr(events, "publish_registration_goal", publisher)
    background = BackgroundTasks()
    result = await complete_registration(
        CompleteRegistrationRequest(token="fixture", pin="1234"), background, service
    )
    assert result.success
    publisher.assert_not_awaited()
    assert len(background.tasks) == 1
    await background()
    publisher.assert_awaited_once_with(service.pool, 999999)


@pytest.mark.asyncio
async def test_publish_has_a_deadline_even_when_transport_hangs(transport, monkeypatch):
    _, _, pool = transport
    started = asyncio.Event()

    async def stalled(*args):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(events, "_publish_registration_goal", stalled)
    await asyncio.wait_for(events.publish_registration_goal(pool, 999999), timeout=3.5)
    assert started.is_set()
