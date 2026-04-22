import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from organism.actuators.adopt_module import (
    AdoptModule,
    PROBATIONARY_KEY_PREFIX,
    ADOPTED_KEY_PREFIX,
    DEFAULT_PROBATION_SECONDS,
)
from organism.redis_bus import EventBus


def _setup_bus(fake_redis, tmp_path, monkeypatch):
    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")


def _make_mature_module(root: Path, name: str = "example_app") -> Path:
    mod = root / "apps" / name
    mod.mkdir(parents=True)
    (mod / "pyproject.toml").write_text("[project]\nname='x'\n")
    (mod / "README.md").write_text("# X\n")
    return mod


@pytest.mark.asyncio
async def test_adopts_mature_module_as_probationary(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = _make_mature_module(tmp_path)
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="main")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["success"] is True
    assert result["adopted"] is True
    assert result["mode"] == "probationary_7d"
    # Redis key present with ~7d TTL
    ttl = await fake_redis.ttl(PROBATIONARY_KEY_PREFIX + "example_app")
    assert DEFAULT_PROBATION_SECONDS - 10 <= ttl <= DEFAULT_PROBATION_SECONDS


@pytest.mark.asyncio
async def test_rejects_missing_readme(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = tmp_path / "apps" / "no_readme"
    mod.mkdir(parents=True)
    (mod / "pyproject.toml").write_text("[project]\nname='x'\n")
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="main")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["success"] is True
    assert result["adopted"] is False
    assert result["reason"] == "maturity_missing"
    assert "readme" in result["missing"]


@pytest.mark.asyncio
async def test_rejects_missing_manifest(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = tmp_path / "apps" / "no_manifest"
    mod.mkdir(parents=True)
    (mod / "README.md").write_text("# x\n")
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="main")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["adopted"] is False
    assert "manifest" in result["missing"]


@pytest.mark.asyncio
async def test_rejects_recent_module(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = _make_mature_module(tmp_path, name="brand_new")
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3600)):  # 1h
        with patch.object(act, "_current_branch", AsyncMock(return_value="main")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["adopted"] is False
    assert "age_24h" in result["missing"]


@pytest.mark.asyncio
async def test_rejects_feat_branch(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = _make_mature_module(tmp_path, name="wip_app")
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="feat/new-thing")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["adopted"] is False
    assert "branch_main" in result["missing"]


@pytest.mark.asyncio
async def test_rejects_fix_branch(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = _make_mature_module(tmp_path, name="wip_fix")
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="fix/bug")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["adopted"] is False
    assert "branch_main" in result["missing"]


@pytest.mark.asyncio
async def test_rejects_session_branch(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = _make_mature_module(tmp_path, name="wip_sess")
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="session/xyz")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["adopted"] is False


@pytest.mark.asyncio
async def test_rejects_chore_branch(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = _make_mature_module(tmp_path, name="wip_chore")
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="chore/lockfile")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["adopted"] is False
    assert "branch_main" in result["missing"]


@pytest.mark.asyncio
async def test_rejects_organism_ignore_opt_out(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = _make_mature_module(tmp_path, name="opted_out")
    (mod / ".organism_ignore").write_text("")
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="main")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["adopted"] is False
    assert result["reason"] == "organism_ignore_opt_out"


@pytest.mark.asyncio
async def test_idempotent_when_already_adopted(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = _make_mature_module(tmp_path, name="twice")
    await fake_redis.set(ADOPTED_KEY_PREFIX + "twice", "1")
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="main")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["adopted"] is False
    assert result["reason"] == "already_adopted"


@pytest.mark.asyncio
async def test_path_missing(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    act = AdoptModule(redis=fake_redis)
    result = await act.run(
        params={"module_path": str(tmp_path / "does_not_exist")},
        correlation_id="c",
    )
    assert result["adopted"] is False
    assert result["reason"] == "path_missing"


@pytest.mark.asyncio
async def test_dry_run_does_not_write_redis(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = _make_mature_module(tmp_path, name="dry")
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="main")):
            result = await act.run(
                params={"module_path": str(mod)},
                correlation_id="c", dry_run=True,
            )
    assert result["success"] is True
    assert result["would_adopt"] is True
    # No Redis key written
    assert await fake_redis.ttl(PROBATIONARY_KEY_PREFIX + "dry") == -2


@pytest.mark.asyncio
async def test_accepts_package_json_as_manifest(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = tmp_path / "apps" / "js_app"
    mod.mkdir(parents=True)
    (mod / "package.json").write_text('{"name":"x"}')
    (mod / "README.md").write_text("# X\n")
    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="main")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["adopted"] is True


@pytest.mark.asyncio
async def test_dry_run_reflects_already_adopted_state(fake_redis, tmp_path, monkeypatch):
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = _make_mature_module(tmp_path, name="already_adopted_mod")
    await fake_redis.set(ADOPTED_KEY_PREFIX + "already_adopted_mod", "1")
    act = AdoptModule(redis=fake_redis)
    result = await act.run(
        params={"module_path": str(mod)},
        correlation_id="c", dry_run=True,
    )
    assert result["would_adopt"] is False
    assert result["reason"] == "already_adopted"


@pytest.mark.asyncio
async def test_probationary_ttl_not_reset_on_reinvocation(fake_redis, tmp_path, monkeypatch):
    """CRIT: a module in probationary state must NOT get TTL reset on re-emission."""
    import time
    _setup_bus(fake_redis, tmp_path, monkeypatch)
    mod = _make_mature_module(tmp_path, name="probation_mod")
    # Seed probationary with a specific future timestamp
    promote_at = time.time() + 5 * 86400  # 5 days from now (not fresh 7)
    await fake_redis.set(
        PROBATIONARY_KEY_PREFIX + "probation_mod",
        str(promote_at),
        ex=int(5 * 86400),
    )
    original_ttl = await fake_redis.ttl(PROBATIONARY_KEY_PREFIX + "probation_mod")
    assert original_ttl <= 5 * 86400

    act = AdoptModule(redis=fake_redis)
    with patch.object(act, "_git_first_commit_age", AsyncMock(return_value=3 * 86400)):
        with patch.object(act, "_current_branch", AsyncMock(return_value="main")):
            result = await act.run(params={"module_path": str(mod)}, correlation_id="c")
    assert result["adopted"] is False
    assert result["reason"] == "probationary_active"
    # TTL not reset to 7d
    new_ttl = await fake_redis.ttl(PROBATIONARY_KEY_PREFIX + "probation_mod")
    assert new_ttl <= original_ttl + 2  # small clock drift tolerance
