import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
import yaml
from organism.actuators.consolidate_redundancy import ConsolidateRedundancy
from organism.redis_bus import EventBus


def _setup(fake_redis, tmp_path, monkeypatch):
    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")


def _write_redundancies(tmp_path: Path) -> Path:
    data = {
        "redundancies": [
            {
                "id": "test_merge",
                "description": "merge X and Y",
                "targets": ["a", "b"],
                "strategy": "merge_into_single_cron",
                "severity": "medium",
            },
            {
                "id": "test_remove",
                "description": "remove disabled Z",
                "targets": ["z"],
                "strategy": "remove_disabled_code",
                "severity": "low",
            },
        ]
    }
    path = tmp_path / "redundancies.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _ok_proc(stdout=b"", returncode=0):
    class _P:
        returncode = 0
        async def communicate(self): return (stdout, b"")
        def kill(self): pass
        async def wait(self): return
    _P.returncode = returncode
    return _P()


@pytest.mark.asyncio
async def test_loads_entries_from_yaml(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    path = _write_redundancies(tmp_path)
    act = ConsolidateRedundancy(yaml_path=path)
    assert len(act._load_all()) == 2
    assert act._load_entry("test_merge")["strategy"] == "merge_into_single_cron"
    assert act._load_entry("nonexistent") is None


@pytest.mark.asyncio
async def test_dry_run_lists_all_consolidations(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    path = _write_redundancies(tmp_path)
    act = ConsolidateRedundancy(yaml_path=path)
    result = await act.run(params={}, correlation_id="c", dry_run=True)
    assert result["success"] is True
    assert len(result["available_consolidations"]) == 2


@pytest.mark.asyncio
async def test_dry_run_specific_id(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    path = _write_redundancies(tmp_path)
    act = ConsolidateRedundancy(yaml_path=path)
    result = await act.run(
        params={"redundancy_id": "test_merge"},
        correlation_id="c", dry_run=True,
    )
    assert result["would_open_pr_for"] == "test_merge"
    assert result["strategy"] == "merge_into_single_cron"
    assert result["branch"] == "organism/consolidate-test_merge"


@pytest.mark.asyncio
async def test_unknown_id_returns_error(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    path = _write_redundancies(tmp_path)
    act = ConsolidateRedundancy(yaml_path=path)
    result = await act.run(
        params={"redundancy_id": "does_not_exist"},
        correlation_id="c",
    )
    assert result["success"] is False
    assert "unknown" in result["error"]


@pytest.mark.asyncio
async def test_execute_opens_pr_on_success(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    path = _write_redundancies(tmp_path)
    monkeypatch.chdir(tmp_path)  # so relative docs/organism/consolidations/ is writable

    mock_spawn = AsyncMock(side_effect=[
        _ok_proc(),  # git checkout -b
        _ok_proc(),  # git add
        _ok_proc(),  # git commit
        _ok_proc(),  # git push
        _ok_proc(stdout=b"https://github.com/owner/repo/pull/999\n"),  # gh pr create
    ])
    act = ConsolidateRedundancy(yaml_path=path)
    with patch("asyncio.create_subprocess_exec", mock_spawn):
        result = await act.run(
            params={"redundancy_id": "test_merge"},
            correlation_id="c",
        )
    assert result["success"] is True
    assert result["pr_created"] is True
    assert "pull/999" in result["pr_url"]
    # Verify plan markdown was written
    plan = tmp_path / "docs" / "organism" / "consolidations" / "test_merge.md"
    assert plan.exists()
    assert "merge X and Y" in plan.read_text()


@pytest.mark.asyncio
async def test_execute_fails_on_checkout_error(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    path = _write_redundancies(tmp_path)
    monkeypatch.chdir(tmp_path)

    mock_spawn = AsyncMock(side_effect=[_ok_proc(returncode=1)])  # checkout fails
    act = ConsolidateRedundancy(yaml_path=path)
    with patch("asyncio.create_subprocess_exec", mock_spawn):
        result = await act.run(
            params={"redundancy_id": "test_merge"},
            correlation_id="c",
        )
    assert result["success"] is False
    assert "checkout" in result["error"]


@pytest.mark.asyncio
async def test_plan_markdown_includes_targets(fake_redis, tmp_path, monkeypatch):
    path = _write_redundancies(tmp_path)
    act = ConsolidateRedundancy(yaml_path=path)
    entry = act._load_entry("test_merge")
    md = act._render_plan_md(entry)
    assert "- a" in md
    assert "- b" in md
    assert "merge_into_single_cron" in md


@pytest.mark.asyncio
async def test_plan_markdown_includes_prefer_line_when_present(fake_redis, tmp_path, monkeypatch):
    data = {
        "redundancies": [
            {
                "id": "with_prefer",
                "description": "keep preferred",
                "targets": ["old"],
                "strategy": "remove_duplicate",
                "prefer": "new_version",
                "severity": "low",
            },
        ]
    }
    path = tmp_path / "r.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    act = ConsolidateRedundancy(yaml_path=path)
    entry = act._load_entry("with_prefer")
    md = act._render_plan_md(entry)
    assert "Keep:" in md
    assert "new_version" in md


@pytest.mark.asyncio
async def test_malformed_yaml_returns_empty_list(fake_redis, tmp_path, monkeypatch):
    path = tmp_path / "bad.yaml"
    path.write_text("this is: : not valid\n:yaml", encoding="utf-8")
    act = ConsolidateRedundancy(yaml_path=path)
    # Should not raise — logs and returns empty
    assert act._load_all() == []


@pytest.mark.asyncio
async def test_missing_yaml_returns_empty_list(fake_redis, tmp_path, monkeypatch):
    act = ConsolidateRedundancy(yaml_path=tmp_path / "no_such_file.yaml")
    assert act._load_all() == []
