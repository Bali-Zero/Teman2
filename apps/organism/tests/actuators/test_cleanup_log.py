import os
import time

import pytest

from organism.actuators.cleanup_log import CleanupLog


@pytest.mark.asyncio
async def test_deletes_files_older_than_threshold(
    fake_redis, tmp_path, monkeypatch,
):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    logs = tmp_path / "logs"
    logs.mkdir()
    old = logs / "old.log"
    old.write_text("old")
    # Set mtime to 45 days ago
    ts = time.time() - 45 * 86400
    os.utime(old, (ts, ts))
    new = logs / "new.log"
    new.write_text("new")

    result = await CleanupLog(search_dirs=[logs]).run(
        params={"min_age_days": 30},
        correlation_id="c",
    )
    assert result["success"] is True
    assert result["deleted_count"] >= 1
    assert not old.exists()
    assert new.exists()


@pytest.mark.asyncio
async def test_dry_run_lists_without_deleting(fake_redis, tmp_path, monkeypatch):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    logs = tmp_path / "logs"
    logs.mkdir()
    old = logs / "old.log"
    old.write_text("x")
    ts = time.time() - 45 * 86400
    os.utime(old, (ts, ts))

    result = await CleanupLog(search_dirs=[logs]).run(
        params={"min_age_days": 30},
        correlation_id="c",
        dry_run=True,
    )
    assert result["success"] is True
    assert result["would_delete_count"] >= 1
    assert old.exists()  # NOT deleted


@pytest.mark.asyncio
async def test_reports_bytes_freed(fake_redis, tmp_path, monkeypatch):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    logs = tmp_path / "logs"
    logs.mkdir()
    old = logs / "big.log"
    old.write_text("X" * 500)
    ts = time.time() - 45 * 86400
    os.utime(old, (ts, ts))

    result = await CleanupLog(search_dirs=[logs]).run(
        params={"min_age_days": 30},
        correlation_id="c",
    )
    assert result["bytes_freed"] >= 500


@pytest.mark.asyncio
async def test_missing_directory_handled_gracefully(
    fake_redis, tmp_path, monkeypatch,
):
    from organism.redis_bus import EventBus

    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    result = await CleanupLog(search_dirs=[tmp_path / "nonexistent"]).run(
        params={"min_age_days": 30},
        correlation_id="c",
    )
    assert result["success"] is True
    assert result["deleted_count"] == 0
