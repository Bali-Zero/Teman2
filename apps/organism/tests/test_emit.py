import pytest
import json
from organism.emit import emit_event
from organism.schemas import Severity


def _test_bus(redis, tmp_path):
    from organism.redis_bus import EventBus
    return EventBus(redis=redis, jsonl_path=tmp_path / "e.jsonl")


@pytest.mark.asyncio
async def test_emit_event_sanitizes_payload(fake_redis, tmp_path, monkeypatch):
    bus = _test_bus(fake_redis, tmp_path)
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    await emit_event(
        severity=Severity.ERROR,
        source="guardian.test",
        kind="probe",
        payload={"msg": "hi; rm"},  # ";" stripped but no deny-list trigger
    )
    length = await fake_redis.xlen("organism:events")
    assert length == 1


@pytest.mark.asyncio
async def test_emit_event_auto_correlation_id(fake_redis, tmp_path, monkeypatch):
    bus = _test_bus(fake_redis, tmp_path)
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    await emit_event(severity=Severity.INFO, source="s", kind="k", payload={})
    entries = await fake_redis.xrange("organism:events")
    data = json.loads(entries[0][1][b"data"])
    assert data["correlation_id"]  # auto-generated, not empty


@pytest.mark.asyncio
async def test_emit_event_respects_passed_correlation_id(fake_redis, tmp_path, monkeypatch):
    bus = _test_bus(fake_redis, tmp_path)
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    await emit_event(
        severity=Severity.INFO, source="s", kind="k", payload={},
        correlation_id="my-explicit-id",
    )
    entries = await fake_redis.xrange("organism:events")
    data = json.loads(entries[0][1][b"data"])
    assert data["correlation_id"] == "my-explicit-id"


@pytest.mark.asyncio
async def test_emit_event_multiple_emits_same_bus(fake_redis, tmp_path, monkeypatch):
    """W0.2 guardian pattern: multiple emits in one test — must hit same bus."""
    bus = _test_bus(fake_redis, tmp_path)
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    await emit_event(severity=Severity.INFO, source="a", kind="k", payload={})
    await emit_event(severity=Severity.INFO, source="b", kind="k", payload={})
    assert await fake_redis.xlen("organism:events") == 2
