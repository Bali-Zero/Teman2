import pytest
import plistlib
from pathlib import Path
from unittest.mock import AsyncMock, patch
from organism.actuators.cleanup_zombie_plist import CleanupZombiePlist
from organism.redis_bus import EventBus


def _setup(fake_redis, tmp_path, monkeypatch):
    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")


def _write_plist(dir: Path, label: str, program: str = "/tmp/nonexistent") -> Path:
    path = dir / f"{label}.plist"
    with path.open("wb") as f:
        plistlib.dump({"Label": label, "ProgramArguments": [program]}, f)
    return path


class _OK:
    returncode = 0
    def __init__(self, stdout=b""):
        self._stdout = stdout
    async def communicate(self): return (self._stdout, b"")
    def kill(self): pass
    async def wait(self): return


@pytest.mark.asyncio
async def test_detects_zombie_plist(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    la_dir = tmp_path / "launchagents"
    la_dir.mkdir()
    _write_plist(la_dir, "com.balizero.dead_agent", program="/tmp/ghost_missing_xxxxxxxx")

    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_OK(stdout=b"PID\tStatus\tLabel\n-\t0\tcom.balizero.live\n")),
    ):
        result = await CleanupZombiePlist(launchagents_dir=la_dir).run(
            params={}, correlation_id="c",
        )
    assert result["success"] is True
    assert result["removed_count"] == 1


@pytest.mark.asyncio
async def test_keeps_loaded_plist(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    la_dir = tmp_path / "launchagents"
    la_dir.mkdir()
    _write_plist(la_dir, "com.balizero.live_agent", program="/tmp/ghost")

    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_OK(stdout=b"PID\tStatus\tLabel\n1234\t0\tcom.balizero.live_agent\n")),
    ):
        result = await CleanupZombiePlist(launchagents_dir=la_dir).run(
            params={}, correlation_id="c",
        )
    assert result["removed_count"] == 0


@pytest.mark.asyncio
async def test_keeps_plist_with_existing_program(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    la_dir = tmp_path / "launchagents"
    la_dir.mkdir()
    existing_prog = tmp_path / "real_prog.sh"
    existing_prog.write_text("#!/bin/sh\n")
    _write_plist(la_dir, "com.balizero.has_program", program=str(existing_prog))

    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_OK(stdout=b"PID\tStatus\tLabel\n")),
    ):
        result = await CleanupZombiePlist(launchagents_dir=la_dir).run(
            params={}, correlation_id="c",
        )
    assert result["removed_count"] == 0


@pytest.mark.asyncio
async def test_dry_run_lists_without_deleting(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    la_dir = tmp_path / "launchagents"
    la_dir.mkdir()
    plist_path = _write_plist(la_dir, "com.balizero.zombie", program="/tmp/gone")

    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_OK(stdout=b"PID\tStatus\tLabel\n")),
    ):
        result = await CleanupZombiePlist(launchagents_dir=la_dir).run(
            params={}, correlation_id="c", dry_run=True,
        )
    assert result["would_remove_count"] == 1
    assert plist_path.exists()  # NOT deleted


@pytest.mark.asyncio
async def test_handles_missing_launchagents_dir(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    result = await CleanupZombiePlist(launchagents_dir=tmp_path / "nope").run(
        params={}, correlation_id="c",
    )
    assert result["success"] is True
    assert result["removed_count"] == 0


@pytest.mark.asyncio
async def test_skips_malformed_plist(fake_redis, tmp_path, monkeypatch):
    """Unreadable/corrupted plist must NOT be deleted — safe default is skip."""
    _setup(fake_redis, tmp_path, monkeypatch)
    la_dir = tmp_path / "launchagents"
    la_dir.mkdir()
    # Write garbage that plistlib cannot parse
    plist_path = la_dir / "com.balizero.broken.plist"
    plist_path.write_bytes(b"<not a valid plist>")

    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=_OK(stdout=b"PID\tStatus\tLabel\n")),
    ):
        result = await CleanupZombiePlist(launchagents_dir=la_dir).run(
            params={}, correlation_id="c",
        )
    assert result["success"] is True
    assert result["removed_count"] == 0
    # File NOT deleted
    assert plist_path.exists()
