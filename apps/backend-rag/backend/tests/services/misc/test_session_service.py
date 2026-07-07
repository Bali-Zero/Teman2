from __future__ import annotations

import json
from datetime import timedelta

from backend.services.misc.session_service import SessionService


class FakeRedis:
    def __init__(self, *, ping_ok: bool = True) -> None:
        self.ping_ok = ping_ok
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.closed = False

    async def ping(self) -> bool:
        if not self.ping_ok:
            raise RuntimeError("down")
        return True

    async def setex(self, key: str, ttl: timedelta, value: str) -> None:
        self.store[key] = value
        self.ttls[key] = int(ttl.total_seconds())

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, key: str) -> int:
        existed = key in self.store
        self.store.pop(key, None)
        self.ttls.pop(key, None)
        return 1 if existed else 0

    async def expire(self, key: str, ttl: timedelta) -> bool:
        if key not in self.store:
            return False
        self.ttls[key] = int(ttl.total_seconds())
        return True

    async def ttl(self, key: str) -> int:
        return self.ttls.get(key, -2)

    async def scan_iter(self, pattern: str):
        prefix = pattern.removesuffix("*")
        for key in sorted(self.store):
            if key.startswith(prefix):
                yield key

    async def close(self) -> None:
        self.closed = True


def build_service(redis_client: FakeRedis | None = None) -> SessionService:
    return SessionService(redis_client=redis_client or FakeRedis(), ttl_hours=2)


async def test_health_check_reports_redis_status() -> None:
    assert await build_service(FakeRedis()).health_check() is True
    assert await build_service(FakeRedis(ping_ok=False)).health_check() is False


async def test_create_update_get_and_delete_session_roundtrip() -> None:
    redis_client = FakeRedis()
    service = build_service(redis_client)

    session_id = await service.create_session()
    history = [{"role": "user", "content": "hello"}]

    assert session_id
    assert await service.get_history(session_id) == []
    assert await service.update_history(session_id, history) is True
    assert await service.get_history(session_id) == history
    assert await service.delete_session(session_id) is True
    assert await service.get_history(session_id) is None


async def test_update_history_rejects_invalid_payload() -> None:
    service = build_service()

    assert await service.update_history("session-1", {"role": "user"}) is False  # type: ignore[arg-type]
    assert await service.update_history_with_ttl("session-1", "bad") is False  # type: ignore[arg-type]


async def test_ttl_and_session_info_use_default_and_custom_durations() -> None:
    redis_client = FakeRedis()
    service = build_service(redis_client)
    history = [{"role": "user", "content": "hello"}]

    assert await service.update_history("session-1", history) is True
    assert redis_client.ttls["session:session-1"] == 7200
    assert await service.extend_ttl_custom("session-1", ttl_hours=3) is True
    assert redis_client.ttls["session:session-1"] == 10800

    info = await service.get_session_info("session-1")

    assert info == {
        "session_id": "session-1",
        "message_count": 1,
        "ttl_seconds": 10800,
        "ttl_hours": 3.0,
    }


async def test_analytics_counts_sessions_and_ignores_invalid_json() -> None:
    redis_client = FakeRedis()
    service = build_service(redis_client)
    await redis_client.setex("session:empty", timedelta(hours=2), json.dumps([]))
    await redis_client.setex(
        "session:active",
        timedelta(hours=2),
        json.dumps([{"role": "user", "content": str(i)} for i in range(12)]),
    )
    await redis_client.setex("session:bad", timedelta(hours=2), "not-json")

    analytics = await service.get_analytics()

    assert analytics["total_sessions"] == 3
    assert analytics["active_sessions"] == 1
    assert analytics["avg_messages_per_session"] == 6.0
    assert analytics["top_session"] == {"id": "active", "messages": 12}
    assert analytics["sessions_by_range"] == {"0-10": 1, "11-20": 1, "21-50": 0, "51+": 0}


async def test_export_session_as_json_or_markdown_and_close() -> None:
    redis_client = FakeRedis()
    service = build_service(redis_client)
    await service.update_history(
        "session-1",
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
    )

    exported_json = await service.export_session("session-1")
    exported_markdown = await service.export_session("session-1", format="markdown")

    assert json.loads(exported_json)["message_count"] == 2
    assert "# Conversation Export - session-1" in exported_markdown
    assert "User (Message 1)" in exported_markdown

    await service.close()
    assert redis_client.closed is True
