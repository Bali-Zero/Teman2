import pytest
from unittest.mock import AsyncMock, patch
from organism.actuators.cleanup_branches import CleanupBranches
from organism.redis_bus import EventBus


def _setup(fake_redis, tmp_path, monkeypatch):
    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")


BRANCH_LIST_OUTPUT = b"""\
* main                   abc1234 [origin/main] latest
  feat/done               def5678 [origin/feat/done: gone] old work
  feat/active             abc9999 [origin/feat/active] in progress
  fix/stale               abc8888 [origin/fix/stale: gone] stale
"""


def _proc(stdout=b"", returncode=0):
    class _P:
        returncode = 0
        async def communicate(self): return (stdout, b"")
        def kill(self): pass
        async def wait(self): return
    _P.returncode = returncode
    return _P()


@pytest.mark.asyncio
async def test_detects_and_deletes_gone_branches(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    calls = []

    async def _fake_spawn(*cmd, **_):
        calls.append(cmd)
        if cmd[:2] == ("git", "fetch"):
            return _proc()
        if cmd[:3] == ("git", "branch", "-vv"):
            return _proc(stdout=BRANCH_LIST_OUTPUT)
        if cmd[:2] == ("git", "branch"):
            return _proc()
        return _proc()

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_spawn):
        result = await CleanupBranches().run(params={}, correlation_id="c")
    assert result["success"] is True
    assert result["deleted_count"] == 2
    assert set(result["deleted"]) == {"feat/done", "fix/stale"}


@pytest.mark.asyncio
async def test_dry_run_lists_gone(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)

    async def _fake_spawn(*cmd, **_):
        if cmd[:3] == ("git", "branch", "-vv"):
            return _proc(stdout=BRANCH_LIST_OUTPUT)
        return _proc()

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_spawn):
        result = await CleanupBranches().run(params={}, correlation_id="c", dry_run=True)
    assert result["success"] is True
    assert result["would_delete_count"] == 2


@pytest.mark.asyncio
async def test_no_gone_branches(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    clean_output = b"* main abc1234 [origin/main] latest\n"

    async def _fake_spawn(*cmd, **_):
        if cmd[:3] == ("git", "branch", "-vv"):
            return _proc(stdout=clean_output)
        return _proc()

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_spawn):
        result = await CleanupBranches().run(params={}, correlation_id="c")
    assert result["deleted_count"] == 0


@pytest.mark.asyncio
async def test_delete_failure_recorded(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)

    async def _fake_spawn(*cmd, **_):
        if cmd[:3] == ("git", "branch", "-vv"):
            return _proc(stdout=BRANCH_LIST_OUTPUT)
        if cmd[:2] == ("git", "branch") and "-D" in cmd:
            return _proc(returncode=1)
        return _proc()

    with patch("asyncio.create_subprocess_exec", side_effect=_fake_spawn):
        result = await CleanupBranches().run(params={}, correlation_id="c")
    assert result["deleted_count"] == 0
    assert len(result["failed"]) == 2
