import pytest
from unittest.mock import AsyncMock, patch
from organism.actuators.cleanup_cache import CleanupCache
from organism.redis_bus import EventBus


def _setup(fake_redis, tmp_path, monkeypatch):
    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")


class _OK:
    returncode = 0
    async def communicate(self): return b"cleaned", b""
    def kill(self): pass
    async def wait(self): return


@pytest.mark.asyncio
async def test_runs_all_three_cache_commands(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    mock_spawn = AsyncMock(return_value=_OK())
    with patch("asyncio.create_subprocess_exec", mock_spawn):
        result = await CleanupCache().run(params={}, correlation_id="c")
    assert result["success"] is True
    assert "npm" in result["caches"]
    assert "pip" in result["caches"]
    assert "brew" in result["caches"]
    assert mock_spawn.call_count == 3


@pytest.mark.asyncio
async def test_skips_missing_binary(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    mock_spawn = AsyncMock(side_effect=FileNotFoundError)
    with patch("asyncio.create_subprocess_exec", mock_spawn):
        result = await CleanupCache().run(params={}, correlation_id="c")
    assert result["success"] is True
    assert all(v.get("skipped") == "binary_not_found" for v in result["caches"].values())


@pytest.mark.asyncio
async def test_dry_run_lists_commands(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    result = await CleanupCache().run(params={}, correlation_id="c", dry_run=True)
    assert result["would_run"] == [
        "npm cache clean --force",
        "pip cache purge",
        "brew cleanup --prune=all",
    ]


@pytest.mark.asyncio
async def test_timeout_captured(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)

    class _Hang:
        returncode = None
        async def communicate(self):
            await __import__("asyncio").sleep(3600)
        def kill(self): pass
        async def wait(self): return

    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=_Hang())):
        with patch("asyncio.wait_for", side_effect=__import__("asyncio").TimeoutError):
            result = await CleanupCache().run(params={}, correlation_id="c")
    assert result["success"] is True
    assert all("timeout_60s" in v.get("error", "") for v in result["caches"].values())
