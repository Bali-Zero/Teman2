import pytest

from organism.actuators.base import ActuatorBase


class _FakeActuator(ActuatorBase):
    name = "fake"
    calls: list = []

    async def _execute(self, params):
        _FakeActuator.calls.append(("execute", params))
        return {"did": "work", "echo": params.get("x")}

    async def _dry_run(self, params):
        _FakeActuator.calls.append(("dry", params))
        return {"would_do": "work"}


@pytest.mark.asyncio
async def test_run_executes_and_emits_done(fake_redis, tmp_path, monkeypatch):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")
    _FakeActuator.calls = []

    a = _FakeActuator()
    result = await a.run(params={"x": 1}, correlation_id="c-1")

    assert result["success"] is True
    assert result["did"] == "work"
    assert _FakeActuator.calls == [("execute", {"x": 1})]
    # Done event emitted
    assert await fake_redis.xlen("organism:events") == 1


@pytest.mark.asyncio
async def test_dry_run_skips_execute(fake_redis, tmp_path, monkeypatch):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")
    _FakeActuator.calls = []

    a = _FakeActuator()
    result = await a.run(params={"x": 2}, correlation_id="c-2", dry_run=True)

    assert result["success"] is True
    assert result["dry_run"] is True
    assert _FakeActuator.calls == [("dry", {"x": 2})]


@pytest.mark.asyncio
async def test_run_captures_exception_and_emits_failed(
    fake_redis, tmp_path, monkeypatch,
):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    class _Broken(ActuatorBase):
        name = "broken"

        async def _execute(self, params):
            raise RuntimeError("boom")

        async def _dry_run(self, params):
            return {}

    result = await _Broken().run(params={}, correlation_id="c-3")
    assert result["success"] is False
    assert "boom" in result["error"]


@pytest.mark.asyncio
async def test_wal_entry_written(fake_redis, tmp_path, monkeypatch):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    wal = tmp_path / "wal"
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", wal)

    a = _FakeActuator()
    await a.run(params={"x": 9}, correlation_id="c-wal")

    entries = list(wal.glob("fake-*.json"))
    assert len(entries) == 1
    import json

    data = json.loads(entries[0].read_text())
    assert data["actuator"] == "fake"
    assert data["correlation_id"] == "c-wal"
    assert data["params"] == {"x": 9}
