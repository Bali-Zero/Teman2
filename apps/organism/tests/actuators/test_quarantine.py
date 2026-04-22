import pytest

from organism.actuators.quarantine import Quarantine, QUARANTINE_KEY_PREFIX


@pytest.mark.asyncio
async def test_quarantine_writes_redis_key(fake_redis, tmp_path, monkeypatch):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    act = Quarantine(redis=fake_redis)
    result = await act.run(
        params={"target": "core-guardian", "reason": "runaway"},
        correlation_id="c",
    )
    assert result["success"] is True
    ttl = await fake_redis.ttl(QUARANTINE_KEY_PREFIX + "core-guardian")
    assert 86390 <= ttl <= 86400  # ~24h


@pytest.mark.asyncio
async def test_quarantine_dry_run_no_redis_write(
    fake_redis, tmp_path, monkeypatch,
):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    act = Quarantine(redis=fake_redis)
    result = await act.run(
        params={"target": "x", "reason": "test"},
        correlation_id="c",
        dry_run=True,
    )
    assert result["success"] is True
    # No redis key written
    val = await fake_redis.get(QUARANTINE_KEY_PREFIX + "x")
    assert val is None


@pytest.mark.asyncio
async def test_quarantine_custom_ttl(fake_redis, tmp_path, monkeypatch):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    act = Quarantine(redis=fake_redis)
    result = await act.run(
        params={"target": "x", "reason": "test", "ttl_hours": 1},
        correlation_id="c",
    )
    assert result["success"] is True
    ttl = await fake_redis.ttl(QUARANTINE_KEY_PREFIX + "x")
    assert 3590 <= ttl <= 3600
