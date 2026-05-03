import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from organism.actuators.propose_yaml_rule import (
    ProposeYamlRule,
    REQUIRED_CANDIDATE_KEYS,
    RULE_ID_RE,
)
from organism.redis_bus import EventBus


def _setup(fake_redis, tmp_path, monkeypatch):
    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")


def _valid_candidate(rule_id="my_learned_rule"):
    return {
        "id": rule_id,
        "match": {"kind": "custom_probe_event"},
        "action": {"actuator": "notify_telegram", "params": {"message": "test"}},
        "confidence": 0.85,
    }


def _ok_proc(stdout=b"", returncode=0):
    class _P:
        async def communicate(self): return (stdout, b"")
        def kill(self): pass
        async def wait(self): return
    _P.returncode = returncode
    return _P()


@pytest.mark.asyncio
async def test_validates_candidate_dict(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    act = ProposeYamlRule()
    result = await act.run(
        params={"rule_candidate": "not a dict"},
        correlation_id="c",
    )
    assert result["success"] is False
    assert "must be a dict" in result["error"]


@pytest.mark.asyncio
async def test_validates_required_keys(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    act = ProposeYamlRule()
    for missing_key in REQUIRED_CANDIDATE_KEYS:
        incomplete = _valid_candidate()
        del incomplete[missing_key]
        result = await act.run(
            params={"rule_candidate": incomplete},
            correlation_id="c",
        )
        assert result["success"] is False
        assert missing_key in result["error"]


@pytest.mark.asyncio
async def test_validates_rule_id_format(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    act = ProposeYamlRule()
    bad_ids = ["UPPERCASE", "123starts_with_digit", "has spaces", "ab", "has-hyphen", ""]
    for bad_id in bad_ids:
        candidate = _valid_candidate(rule_id=bad_id)
        result = await act.run(
            params={"rule_candidate": candidate},
            correlation_id="c",
        )
        assert result["success"] is False, f"accepted bad id: {bad_id!r}"


def test_accepts_valid_id():
    good_ids = ["valid_id", "abc", "a12_b34", "rule_for_cron_agent_burst"]
    for gid in good_ids:
        assert RULE_ID_RE.match(gid), f"regex rejected valid id: {gid}"


@pytest.mark.asyncio
async def test_dry_run_returns_paths(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    act = ProposeYamlRule()
    result = await act.run(
        params={"rule_candidate": _valid_candidate("probe_rule")},
        correlation_id="c", dry_run=True,
    )
    assert result["success"] is True
    assert result["would_propose"] is True
    assert result["branch"] == "organism/propose-rule-probe_rule"
    assert "rules/learned/" in result["yaml_path"]
    assert "tests/rules/" in result["test_path"]
    assert result["candidate_summary"]["actuator"] == "notify_telegram"


@pytest.mark.asyncio
async def test_dry_run_invalid_candidate_reports_error(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    act = ProposeYamlRule()
    result = await act.run(
        params={"rule_candidate": {"id": "bad id with spaces"}},
        correlation_id="c", dry_run=True,
    )
    assert result["success"] is True
    assert result["would_propose"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_execute_opens_pr_and_enables_auto_merge(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)

    mock_spawn = AsyncMock(side_effect=[
        _ok_proc(stdout=str(tmp_path).encode() + b"\n"),  # git rev-parse
        _ok_proc(),  # git checkout -b
        _ok_proc(),  # git add
        _ok_proc(),  # git commit
        _ok_proc(),  # git push
        _ok_proc(stdout=b"https://github.com/Balizero1987/Teman2/pull/999\n"),  # gh pr create
        _ok_proc(),  # gh pr merge --auto --squash
    ])

    act = ProposeYamlRule()
    with patch("asyncio.create_subprocess_exec", mock_spawn):
        result = await act.run(
            params={"rule_candidate": _valid_candidate("my_learned_rule")},
            correlation_id="c",
        )
    assert result["success"] is True
    assert result["rule_id"] == "my_learned_rule"
    assert "pull/999" in result["pr_url"]
    assert result["auto_merge_enabled"] is True
    # Verify YAML and test files were written
    yaml_files = list((tmp_path / "apps/organism/organism/rules/learned").glob("*-my_learned_rule.yaml"))
    test_files = list((tmp_path / "apps/organism/tests/rules").glob("test_learned_my_learned_rule.py"))
    assert len(yaml_files) == 1
    assert len(test_files) == 1


@pytest.mark.asyncio
async def test_execute_fails_when_not_in_repo(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    mock_spawn = AsyncMock(side_effect=[
        _ok_proc(returncode=128),  # rev-parse fails
    ])
    act = ProposeYamlRule()
    with patch("asyncio.create_subprocess_exec", mock_spawn):
        result = await act.run(
            params={"rule_candidate": _valid_candidate()},
            correlation_id="c",
        )
    assert result["success"] is False
    assert "git rev-parse" in result["error"]


@pytest.mark.asyncio
async def test_execute_fails_on_branch_exists(fake_redis, tmp_path, monkeypatch):
    _setup(fake_redis, tmp_path, monkeypatch)
    mock_spawn = AsyncMock(side_effect=[
        _ok_proc(stdout=str(tmp_path).encode() + b"\n"),  # rev-parse
        _ok_proc(returncode=128),  # checkout -b fails (branch exists)
    ])
    act = ProposeYamlRule()
    with patch("asyncio.create_subprocess_exec", mock_spawn):
        result = await act.run(
            params={"rule_candidate": _valid_candidate()},
            correlation_id="c",
        )
    assert result["success"] is False
    assert "checkout" in result["error"]


@pytest.mark.asyncio
async def test_render_yaml_produces_valid_single_rule(fake_redis, tmp_path, monkeypatch):
    import yaml
    candidate = _valid_candidate("yaml_shape_test")
    yaml_text = ProposeYamlRule._render_rule_yaml(candidate)
    parsed = yaml.safe_load(yaml_text)
    assert "rules" in parsed
    assert len(parsed["rules"]) == 1
    rule = parsed["rules"][0]
    assert rule["id"] == "yaml_shape_test"
    assert rule["match"] == candidate["match"]


@pytest.mark.asyncio
async def test_render_test_py_imports_rule_matcher(fake_redis, tmp_path, monkeypatch):
    candidate = _valid_candidate("test_shape")
    test_text = ProposeYamlRule._render_test_py(candidate)
    assert "from organism.supervisor.yaml_rules import RuleMatcher" in test_text
    assert "test_learned_rule_test_shape_matches_expected_kind" in test_text
    assert "custom_probe_event" in test_text


@pytest.mark.asyncio
async def test_auto_merge_failure_still_reports_pr_url(fake_redis, tmp_path, monkeypatch):
    """If `gh pr merge --auto` fails (e.g. branch protection rejects), the PR
    still exists and the actuator should report it instead of losing state."""
    _setup(fake_redis, tmp_path, monkeypatch)
    mock_spawn = AsyncMock(side_effect=[
        _ok_proc(stdout=str(tmp_path).encode() + b"\n"),  # rev-parse
        _ok_proc(),  # checkout
        _ok_proc(),  # add
        _ok_proc(),  # commit
        _ok_proc(),  # push
        _ok_proc(stdout=b"https://github.com/x/y/pull/7\n"),  # pr create ok
        _ok_proc(returncode=1),  # pr merge --auto fails
    ])
    act = ProposeYamlRule()
    with patch("asyncio.create_subprocess_exec", mock_spawn):
        result = await act.run(
            params={"rule_candidate": _valid_candidate("partial_flow")},
            correlation_id="c",
        )
    assert result["success"] is True
    assert "pull/7" in result["pr_url"]
    assert result["auto_merge_enabled"] is False


@pytest.mark.asyncio
async def test_execute_emits_failed_event_on_validation_error(fake_redis, tmp_path, monkeypatch):
    """Critical fix: structured errors must emit propose_yaml_rule_failed, not _done."""
    import json
    from organism.redis_bus import EventBus
    bus = EventBus(redis=fake_redis, jsonl_path=tmp_path / "e.jsonl")
    monkeypatch.setattr("organism.emit._get_bus", lambda: bus)
    monkeypatch.setattr("organism.actuators.base.WAL_DIR", tmp_path / "wal")

    act = ProposeYamlRule()
    result = await act.run(
        params={"rule_candidate": "not a dict"},
        correlation_id="c-fail-event",
    )
    assert result["success"] is False

    # Check EventBus — should have ONE `propose_yaml_rule_failed` event, NOT `_done`.
    entries = await fake_redis.xrange("organism:events")
    kinds = []
    for _, fields in entries:
        raw = fields.get(b"data") if isinstance(fields, dict) else fields["data"]
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        if data.get("source") == "actuator.propose_yaml_rule":
            kinds.append(data["kind"])
    assert "propose_yaml_rule_failed" in kinds
    assert "propose_yaml_rule_done" not in kinds
