import pytest
import json
from pathlib import Path
from organism.schemas import Event, Severity
from organism.redis_bus import EventBus


@pytest.mark.asyncio
async def test_emit_writes_to_redis_stream(fake_redis, tmp_path):
    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "events.jsonl")
    e = Event(
        severity=Severity.WARNING, source="test", kind="probe",
        payload={"x": 1}, correlation_id="c-1", host="Pro",
    )
    await bus.emit(e)
    length = await fake_redis.xlen("organism:events")
    assert length == 1


@pytest.mark.asyncio
async def test_emit_also_writes_jsonl_mirror(fake_redis, tmp_path):
    path = tmp_path / "events.jsonl"
    bus = EventBus(redis=fake_redis, jsonl_path=path)
    e = Event(
        severity=Severity.INFO, source="t", kind="p", payload={},
        correlation_id="c", host="Air",
    )
    await bus.emit(e)
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    decoded = json.loads(lines[0])
    assert decoded["source"] == "t"


@pytest.mark.asyncio
async def test_emit_continues_if_redis_down(tmp_path):
    class BrokenRedis:
        async def xadd(self, *a, **kw):
            raise ConnectionError("redis down")
    path = tmp_path / "events.jsonl"
    bus = EventBus(redis=BrokenRedis(), jsonl_path=path)
    e = Event(
        severity=Severity.CRITICAL, source="t", kind="p", payload={},
        correlation_id="c", host="Pro",
    )
    await bus.emit(e)  # must NOT raise
    assert path.exists()
    assert len(path.read_text().strip().splitlines()) == 1
