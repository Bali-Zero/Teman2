import pytest
from unittest.mock import AsyncMock, patch

from organism.actuators.restart_agent import RestartAgent


@pytest.mark.asyncio
async def test_dry_run_returns_plan(fake_redis, tmp_path, monkeypatch):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    result = await RestartAgent().run(
        params={"agent_ref": "core-guardian"},
        correlation_id="c",
        dry_run=True,
    )
    assert result["success"] is True
    assert "com.balizero.core-guardian" in result.get("would_kickstart", "")


@pytest.mark.asyncio
async def test_execute_shells_out_to_launchctl(fake_redis, tmp_path, monkeypatch):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"ok\n", b""))
    mock_proc.returncode = 0
    with patch(
        "asyncio.create_subprocess_exec", AsyncMock(return_value=mock_proc)
    ) as m:
        result = await RestartAgent().run(
            params={"agent_ref": "core-guardian"},
            correlation_id="c",
        )

    assert result["success"] is True
    assert result["returncode"] == 0
    # launchctl was called
    assert m.called
    args = m.call_args.args
    assert args[0] == "launchctl"
    assert args[1] == "kickstart"
    assert args[2] == "-k"


@pytest.mark.asyncio
async def test_execute_full_label_passthrough(fake_redis, tmp_path, monkeypatch):
    """If agent_ref already contains dots (e.g. com.foo.bar), pass through as-is."""
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    result = await RestartAgent().run(
        params={"agent_ref": "com.third.party.agent"},
        correlation_id="c",
        dry_run=True,
    )
    assert "com.third.party.agent" in result["would_kickstart"]
    assert "com.balizero" not in result["would_kickstart"]
