# ruff: noqa: F811
"""Native parent compaction, safe migration, and unchanged ownership gates."""

import os
from unittest.mock import patch

import pytest

import context_bridge as bridge
import install as installer
from install import native_compact_config
from installation_status import native_compact_defaults
from test_context_bridge import setup, token  # noqa: F401


def native_policy():
    path = bridge.codex_home() / "nuzantara-context-policy.json"
    policy = bridge.load(path)
    policy["parent_rollover_enabled"] = False
    bridge.save(path, policy)


@pytest.mark.parametrize("used", [600, 999, 1200])
def test_native_parent_never_freezes_or_launches(setup, used):
    _, log, event = setup
    native_policy()
    token(log, used, 1000)
    with patch.object(bridge, "launch", side_effect=AssertionError("no new jump")):
        for name in ("PreToolUse", "PostToolUse", "Stop"):
            result = bridge.hook(
                {**event, "hook_event_name": name, "tool_name": "Read"}
            )
            assert result.get("decision") != "block"
            assert (
                result.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"
            )
    assert "rollover" not in bridge.load(bridge.state_path(event["session_id"]))
    for name in ("SessionStart", "PreCompact", "PostCompact"):
        result = bridge.hook({**event, "hook_event_name": name})
        assert "native automatic compaction" in str(result)
        assert "Stop will open" not in str(result)


@pytest.mark.parametrize("phase", ["requested", "needs_attention"])
def test_native_retires_only_parked_jumps(setup, phase):
    _, _, event = setup
    native_policy()
    path = bridge.state_path(event["session_id"])
    state = bridge.load(path)
    state.update(rollover=phase, failure="checkpoint_missing", launch_nonce="old")
    bridge.save(path, state)
    assert (
        bridge.hook({**event, "hook_event_name": "PreToolUse", "tool_name": "Read"})
        == {}
    )
    state = bridge.load(path)
    assert "rollover" not in state and "launch_nonce" not in state
    assert state["released"]["reason"] == "native_compaction"
    assert state["baseline"]


@pytest.mark.parametrize(
    "phase", ["starting", "accepted", "requested", "needs_attention"]
)
@pytest.mark.parametrize("native", [True, False])
def test_compact_cannot_unfreeze_inflight_writer(setup, phase, native):
    _, _, event = setup
    if native:
        native_policy()
    path = bridge.state_path(event["session_id"])
    state = bridge.load(path)
    state.update(rollover=phase, launch_nonce="owned")
    # starting/accepted remain frozen even after their supervisor exits.
    if phase in ("requested", "needs_attention"):
        state["supervisor_pid"] = os.getpid()
    bridge.save(path, state)
    bridge.hook({**event, "hook_event_name": "PostCompact"})
    result = bridge.hook(
        {**event, "hook_event_name": "PreToolUse", "tool_name": "Read"}
    )
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert bridge.load(path)["launch_nonce"] == "owned"


def test_native_stop_keeps_verification_gate(setup):
    repo, _, event = setup
    native_policy()
    (repo / "changed.py").write_text("changed = True\n")
    result = bridge.hook({**event, "hook_event_name": "Stop"})
    assert result["decision"] == "block"
    assert "verification receipt" in result["reason"]
    assert "Stop will open" not in result["reason"]


@pytest.mark.parametrize("phase", ["requested", "needs_attention"])
def test_native_stop_does_not_retry_live_parked_jump(setup, phase):
    _, _, event = setup
    native_policy()
    path = bridge.state_path(event["session_id"])
    state = bridge.load(path)
    state.update(
        rollover=phase,
        failure="TimeoutError",
        supervisor_pid=os.getpid(),
        checkpoint={"remaining": ["work"]},
    )
    bridge.save(path, state)
    with patch.object(bridge, "launch", side_effect=AssertionError("no retry")):
        bridge.hook({**event, "hook_event_name": "Stop"})
    assert bridge.load(path)["rollover"] == phase
    reason = bridge.frozen_reason(event["session_id"], state, False)
    assert "will not launch or retry" in reason


def test_config_migration_preserves_unrelated_bytes_and_profiles():
    other = '# operator comment\nmodel = "example"\n[profiles.custom]\nmodel_auto_compact_token_limit = 123\n'
    source = (
        "model_auto_compact_token_limit = 200000 # retired\n"
        'model_auto_compact_token_limit_scope = "total"\n' + other
    )
    migrated = native_compact_config(source)
    assert migrated == other
    assert native_compact_config(migrated) == migrated


@pytest.mark.parametrize(
    "source",
    [
        'model_auto_compact_token_limit_scope = """\ntotal\n"""\n',
        '"model_auto_compact_token_limit" = 200000\n',
        'note = """\nmodel_auto_compact_token_limit = 12\n"""\nmodel_auto_compact_token_limit = 200000\n',
    ],
)
def test_config_migration_rejects_ambiguous_edits(source):
    with pytest.raises(ValueError):
        native_compact_config(source)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_installer_migrates_seat_with_backup(setup, monkeypatch, newline):
    repo, _, _ = setup
    seat = bridge.codex_home()
    config = seat / "config.toml"
    original = 'model_auto_compact_token_limit = 200000\nmodel = "example"\n'.replace(
        "\n", newline
    )
    config.write_bytes(original.encode())
    config.chmod(0o600)
    policy_path = seat / "nuzantara-context-policy.json"
    policy = bridge.load(policy_path)
    policy["child_limits"] = {"max_active": 2}
    bridge.save(policy_path, policy)

    class FakeRPC:
        def call(self, method, params):
            assert method == "hooks/list"
            hooks = bridge.load(seat / "hooks.json")["hooks"]
            return {
                "data": [
                    {
                        "hooks": [
                            h
                            for groups in hooks.values()
                            for group in groups
                            for h in group["hooks"]
                        ]
                    }
                ]
            }

        def close(self):
            pass

    monkeypatch.setattr(installer, "RPC", FakeRPC)
    result = installer.install(seat, [str(repo)])
    assert config.read_bytes() == ('model = "example"' + newline).encode()
    assert config.stat().st_mode & 0o777 == 0o600
    assert (
        installer.Path(result["backup"]) / "config.toml"
    ).read_bytes() == original.encode()
    policy = bridge.load(policy_path)
    assert policy["enabled"] and policy["parent_rollover_enabled"] is False
    assert policy["child_limits"] == {"max_active": 2}


def test_installer_refuses_symlink_without_changing_target(setup):
    repo, _, _ = setup
    seat = bridge.codex_home()
    target = seat / "actual-config.toml"
    original = "model_auto_compact_token_limit = 200000\n"
    target.write_text(original)
    config = seat / "config.toml"
    config.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        installer.install(seat, [str(repo)])
    assert config.is_symlink() and target.read_text() == original
    assert not (seat / "state" / "nuzantara-context-backups").exists()
    assert not (seat / "hooks").exists()


@pytest.mark.parametrize(
    "source,expected",
    [
        (None, True),
        ('model = "example"\n', True),
        ("model_auto_compact_token_limit = 123\n", False),
        (
            'profile = "custom"\n[profiles.custom]\nmodel_auto_compact_token_limit = 123\n',
            False,
        ),
        ("[profiles.custom]\nmodel_auto_compact_token_limit = 123\n", True),
    ],
)
def test_status_native_defaults_missing_root_and_profile(tmp_path, source, expected):
    config = tmp_path / "config.toml"
    if source is not None:
        config.write_text(source)
    assert native_compact_defaults(config) is expected
