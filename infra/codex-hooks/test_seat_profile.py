"""The reviewed Codex seat profile: install absent items, never overwrite drift."""

import hashlib
import json
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import install_seat_profile as profile  # noqa: E402

TEXT, ROLES = profile.expected()


def version_of(config):
    data = tomllib.loads(config.read_text())
    return (
        "sha256:"
        + hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    )


class FakeRPC:
    """Codex config/read (user layer, semantic version) and version-pinned batchWrite."""

    calls: list = []
    collateral = False
    competitor = None
    tool_names = profile.RESEARCH_READ_TOOLS | {"notebook_create", "runtime_added_write_tool"}

    def call(self, method, params):
        config = profile.Path(profile.os.environ["CODEX_HOME"]) / "config.toml"
        if method == "mcpServerStatus/list":
            data = tomllib.loads(config.read_text())
            disabled = data.get("mcp_servers", {}).get(profile.NOTEBOOKLM, {}).get("disabled_tools", [])
            return {"data": [{"name": profile.NOTEBOOKLM,
                              "tools": {name: {} for name in self.tool_names - set(disabled)}}]}
        if method == "config/read":
            assert params == {"includeLayers": True}
            name = {"type": "user", "file": str(config), "profile": None}
            data = tomllib.loads(config.read_text())
            return {
                "layers": [
                    {"name": name, "version": version_of(config), "config": data}
                ]
            }
        assert method == "config/batchWrite"
        FakeRPC.calls.append(params)
        if FakeRPC.competitor:
            FakeRPC.competitor(config)
        if params["expectedVersion"] != version_of(config):
            raise RuntimeError(
                "{'code': -32600, 'data': {'config_write_error_code': 'configVersionConflict'}}"
            )
        data = tomllib.loads(config.read_text())
        for edit in params["edits"]:
            parts = edit["keyPath"].split(".")
            target = data
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = edit["value"]
        if self.collateral:
            data["approval_policy"] = "never"

        def lines(value, path=()):
            for name, item in value.items():
                key = (*path, name)
                if isinstance(item, dict):
                    yield from lines(item, key)
                else:
                    yield ".".join(map(json.dumps, key)) + " = " + json.dumps(item) + "\n"

        config.write_text("".join(lines(data)))
        return {}

    def close(self):
        pass


@pytest.fixture
def seat(tmp_path, monkeypatch):
    seat = tmp_path / "seat"
    seat.mkdir()
    (seat / "config.toml").write_text('model = "example"\n\n[features]\nhooks = true\n')
    (seat / "config.toml").chmod(0o600)
    FakeRPC.calls = []
    monkeypatch.setattr(FakeRPC, "collateral", False)
    monkeypatch.setattr(FakeRPC, "competitor", None)
    monkeypatch.setattr(profile, "RPC", FakeRPC)
    monkeypatch.setattr(profile, "conditional_write_proven", lambda: True)
    return seat


def notebook_seat(seat):
    config = seat / "config.toml"
    config.write_text(config.read_text() + '\n[mcp_servers.notebooklm-mcp]\ncommand = "fixture"\n')
    return config


def test_loadout_installs_only_absent_skill_bound_without_new_server(seat):
    before = tomllib.loads((seat / "config.toml").read_text())
    result = profile.loadout(seat)
    after = tomllib.loads((seat / "config.toml").read_text())
    assert result["installed"] and result[profile.NOTEBOOKLM] == "not_configured"
    assert after.pop("skills") == {"max_context_tokens": 3000}
    assert after == before and not (seat / "agents").exists()


def test_loadout_discovers_runtime_inventory_and_retains_queries(seat):
    config = notebook_seat(seat)
    before_bytes = config.read_bytes()
    result = profile.loadout(seat)
    data = tomllib.loads(config.read_text())
    assert result["installed"] and result["exposed_tools"] == 10
    assert data["mcp_servers"][profile.NOTEBOOKLM]["disabled_tools"] == ["notebook_create", "runtime_added_write_tool"]
    assert data["mcp_servers"][profile.NOTEBOOKLM]["command"] == "fixture"
    assert Path(result["backup"], "config.toml").read_bytes() == before_bytes
    assert (config.stat().st_mode & 0o777) == 0o600
    assert len(FakeRPC.calls[0]["edits"]) == 2  # one version-pinned batch
    bytes_after = config.read_bytes()
    assert profile.loadout(seat)["installed"]
    assert config.read_bytes() == bytes_after and len(FakeRPC.calls) == 1


def test_loadout_check_is_config_read_only(seat):
    config = notebook_seat(seat)
    before = config.read_bytes()
    result = profile.loadout(seat, check=True)
    assert not result["installed"] and result["backup"] is None
    assert config.read_bytes() == before and not FakeRPC.calls


def test_loadout_preserves_operator_values_and_profiles(seat):
    config = notebook_seat(seat)
    config.write_text(config.read_text() + 'disabled_tools = []\n\n[skills]\nmax_context_tokens = 7000\n\n[profiles.research]\nmodel = "assigned"\n')
    before = config.read_bytes()
    result = profile.loadout(seat)
    assert result["skills.max_context_tokens"] == result[profile.NOTEBOOKLM] == "drift"
    assert config.read_bytes() == before and not FakeRPC.calls


def test_loadout_rejects_config_change_during_tool_discovery(seat, monkeypatch):
    config = notebook_seat(seat)
    original = profile.notebook_tools
    concurrent = None

    def discover(path):
        nonlocal concurrent
        tools = original(path)
        config.write_text(config.read_text() + '\n[profiles.concurrent]\nmodel = "other"\n')
        concurrent = config.read_bytes()
        return tools

    monkeypatch.setattr(profile, "notebook_tools", discover)
    with pytest.raises(RuntimeError, match="configVersionConflict"):
        profile.loadout(seat)
    assert config.read_bytes() == concurrent


def test_loadout_discovery_failure_never_writes_config(seat, monkeypatch):
    config = notebook_seat(seat)
    before = config.read_bytes()
    monkeypatch.setattr(FakeRPC, "tool_names", set())
    with pytest.raises(RuntimeError, match="discovery unavailable"):
        profile.loadout(seat)
    assert config.read_bytes() == before and not FakeRPC.calls


def test_loadout_does_not_override_operator_allowlist(seat):
    config = notebook_seat(seat)
    config.write_text(config.read_text() + 'enabled_tools = ["notebook_list"]\n\n[skills]\nmax_context_tokens = 3000\n')
    before = config.read_bytes()
    result = profile.loadout(seat)
    assert result[profile.NOTEBOOKLM] == "drift"
    assert config.read_bytes() == before and not FakeRPC.calls


def test_loadout_does_not_start_operator_disabled_server(seat, monkeypatch):
    config = notebook_seat(seat)
    config.write_text(config.read_text() + 'enabled = false\n')
    monkeypatch.setattr(FakeRPC, "tool_names", set())  # discovery would fail if called
    result = profile.loadout(seat)
    assert result["installed"] and result[profile.NOTEBOOKLM] == "disabled_by_operator"
    assert tomllib.loads(config.read_text())["mcp_servers"][profile.NOTEBOOKLM]["enabled"] is False


def test_rpc_initialization_failure_restores_selected_seat(seat, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", "prior-seat")

    def unavailable():
        raise RuntimeError("unavailable")

    monkeypatch.setattr(profile, "RPC", unavailable)
    with pytest.raises(RuntimeError, match="unavailable"):
        profile.rpc_call(seat, "config/read", {})
    assert profile.os.environ["CODEX_HOME"] == "prior-seat"


def test_skills_only_preserves_mcp_and_does_not_discover_tools(seat, monkeypatch, capsys):
    config = notebook_seat(seat)
    before = tomllib.loads(config.read_text())["mcp_servers"]
    monkeypatch.setattr(FakeRPC, "tool_names", set())  # discovery would raise
    monkeypatch.setattr(sys, "argv", ["installer", "--seat", str(seat), "--skills-only"])
    profile.main()
    result = json.loads(capsys.readouterr().out)
    assert result["installed"] and result[profile.NOTEBOOKLM] == "unchanged"
    assert tomllib.loads(config.read_text())["mcp_servers"] == before
    assert FakeRPC.calls[0]["edits"] == [{"keyPath": "skills.max_context_tokens", "value": 3000, "mergeStrategy": "replace"}]


def test_fresh_seat_gets_exact_profile_with_backup(seat):
    original = (seat / "config.toml").read_bytes()
    result = profile.install(seat)
    assert (
        result["installed"] and result["before"]["developer_instructions"] == "absent"
    )
    config = tomllib.loads((seat / "config.toml").read_text())
    assert config["developer_instructions"] == TEXT and config["model"] == "example"
    assert (seat / "config.toml").stat().st_mode & 0o777 == 0o600
    for role, data in ROLES.items():
        path = seat / "agents" / f"{role}.toml"
        assert path.read_bytes() == data and path.stat().st_mode & 0o777 == 0o600
    assert (profile.Path(result["backup"]) / "config.toml").read_bytes() == original


def test_matching_seat_is_untouched(seat):
    profile.install(seat)
    FakeRPC.calls = []
    before = (seat / "config.toml").read_bytes()
    result = profile.install(seat)
    assert result["installed"] and result["backup"] is None and FakeRPC.calls == []
    assert (seat / "config.toml").read_bytes() == before


def test_drift_is_reported_and_never_overwritten(seat):
    (seat / "config.toml").write_text('developer_instructions = "operator text"\n')
    (seat / "agents").mkdir()
    (seat / "agents" / "mechanical.toml").write_text('model = "operator"\n')
    result = profile.install(seat)
    assert result["developer_instructions"] == "drift" and not result["installed"]
    assert result["roles"]["mechanical"] == "drift"
    assert (seat / "agents" / "mechanical.toml").read_text() == 'model = "operator"\n'
    assert (
        tomllib.loads((seat / "config.toml").read_text())["developer_instructions"]
        == "operator text"
    )
    assert FakeRPC.calls == []
    assert result["roles"]["routine-explorer"] == "match"


def test_collateral_config_change_is_refused(seat, monkeypatch):
    monkeypatch.setattr(FakeRPC, "collateral", True)
    with pytest.raises(RuntimeError, match="not exact"):
        profile.install(seat)


def test_symlinked_config_is_refused_before_any_write(seat):
    target = seat / "real.toml"
    (seat / "config.toml").rename(target)
    (seat / "config.toml").symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        profile.install(seat)
    assert not (seat / "agents").exists() and not (seat / "state").exists()


# Routing contract: which seat does which routine work, and that none widens scope.
@pytest.mark.parametrize(
    "role,model,effort,read_only",
    [
        ("mechanical", "gpt-5.6-luna", "low", True),
        ("routine-explorer", "gpt-5.6-terra", "medium", True),
        ("routine-worker", "gpt-5.6-terra", "medium", False),
        ("code-reviewer", "gpt-5.6-sol", "high", True),
    ],
)
def test_role_pins_model_effort_and_sandbox(role, model, effort, read_only):
    spec = tomllib.loads(ROLES[role].decode())
    assert (spec["name"], spec["model"], spec["model_reasoning_effort"]) == (
        role,
        model,
        effort,
    )
    assert (spec.get("sandbox_mode") == "read-only") is read_only
    assert spec["agents"]["enabled"] is False
    assert role in TEXT


def test_instructions_keep_reviews_and_explicit_assignments_binding():
    assert (
        "never replace required cross-family reviews or mission-colour final gates"
        in TEXT
    )
    assert (
        "Honor required independent reviews and explicit model or effort assignments"
        in TEXT
    )
    for cap in (
        "mechanical 500",
        "routine-explorer and routine-worker 1000",
        "code-reviewer 1500",
    ):
        assert cap in TEXT


def test_role_created_concurrently_is_never_overwritten(seat, monkeypatch):
    real_backup = profile.backup_seat

    def racing_backup(seat_dir, config_file):
        backup = real_backup(seat_dir, config_file)
        (seat_dir / "agents").mkdir(exist_ok=True)
        (seat_dir / "agents" / "mechanical.toml").write_text('model = "operator"\n')
        return backup

    monkeypatch.setattr(profile, "backup_seat", racing_backup)
    result = profile.install(seat)
    assert (seat / "agents" / "mechanical.toml").read_text() == 'model = "operator"\n'
    assert result["roles"]["mechanical"] == "drift" and not result["installed"]
    assert not list((seat / "agents").glob("*.tmp"))


def test_mode_is_restored_when_the_write_is_refused(seat, monkeypatch):
    monkeypatch.setattr(FakeRPC, "collateral", True)
    real_call = FakeRPC.call

    def loosening_call(self, method, params):
        out = real_call(self, method, params)
        (profile.Path(profile.os.environ["CODEX_HOME"]) / "config.toml").chmod(0o644)
        return out

    monkeypatch.setattr(FakeRPC, "call", loosening_call)
    with pytest.raises(RuntimeError, match="not exact"):
        profile.install(seat)
    assert (seat / "config.toml").stat().st_mode & 0o777 == 0o600


def test_competitor_at_the_create_instant_keeps_its_bytes(seat, monkeypatch):
    real_link = profile.os.link

    def racing_link(src, dst):
        profile.Path(dst).write_text('model = "competitor"\n')
        return real_link(src, dst)

    monkeypatch.setattr(profile.os, "link", racing_link)
    result = profile.install(seat)
    for role in ROLES:
        assert (
            seat / "agents" / f"{role}.toml"
        ).read_text() == 'model = "competitor"\n'
        assert result["roles"][role] == "drift"
    assert not list((seat / "agents").glob("*.tmp"))


def test_there_is_no_automatic_removal(monkeypatch, seat):
    monkeypatch.setattr(profile.sys, "argv", ["x", "--seat", str(seat), "--remove"])
    with pytest.raises(SystemExit):
        profile.main()


def test_symlink_or_directory_at_a_role_path_is_drift(seat):
    (seat / "agents").mkdir()
    (seat / "agents" / "mechanical.toml").symlink_to(seat / "missing-target")
    (seat / "agents" / "routine-worker.toml").mkdir()
    result = profile.install(seat)
    assert result["roles"]["mechanical"] == "drift"
    assert result["roles"]["routine-worker"] == "drift"
    assert (seat / "agents" / "mechanical.toml").is_symlink()
    assert (seat / "agents" / "routine-worker.toml").is_dir()
    assert result["roles"]["routine-explorer"] == "match"


def test_a_change_after_the_validated_snapshot_is_never_overwritten(seat, monkeypatch):
    def competing_edit(config):
        config.write_text('approval_policy = "on-request"\n' + config.read_text())

    monkeypatch.setattr(FakeRPC, "competitor", staticmethod(competing_edit))
    with pytest.raises(RuntimeError, match="changed since it was validated"):
        profile.install(seat)
    config = tomllib.loads((seat / "config.toml").read_text())
    assert config["approval_policy"] == "on-request"
    assert "developer_instructions" not in config
    assert FakeRPC.calls[0]["expectedVersion"].startswith("sha256:")


def test_a_codex_that_accepts_a_stale_version_writes_nothing(seat, monkeypatch):
    monkeypatch.setattr(profile, "conditional_write_proven", lambda: False)
    original = (seat / "config.toml").read_bytes()
    with pytest.raises(RuntimeError, match="does not refuse a stale config version"):
        profile.install(seat)
    assert (seat / "config.toml").read_bytes() == original
    assert not (seat / "agents").exists() and FakeRPC.calls == []


def test_the_real_codex_refuses_a_stale_version_on_a_scratch_seat():
    binary = profile.Path("/Applications/ChatGPT.app/Contents/Resources/codex")
    if not binary.is_file() and not profile.shutil.which("codex"):
        pytest.skip("no Codex binary on this host")
    assert profile.conditional_write_proven() is True
