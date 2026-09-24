# ruff: noqa: F811
"""The reviewed output-hygiene guard, registered for Codex by the same installer."""

import json
import os
import subprocess
import sys

import pytest

import context_bridge as bridge
import install as installer
from test_context_bridge import setup  # noqa: F401


class FakeRPC:
    """hooks/list as Codex answers it: every configured handler, with its matcher."""

    drop_guard = False

    def call(self, method, params):
        assert method == "hooks/list"
        hooks = bridge.load(bridge.codex_home() / "hooks.json")["hooks"]
        found = [
            dict(h, eventName=event, matcher=group.get("matcher"))
            for event, groups in hooks.items()
            for group in groups
            for h in group["hooks"]
        ]
        if self.drop_guard:
            found = [h for h in found if installer.GUARD_MARK not in h["command"]]
        return {"data": [{"hooks": found}]}

    def close(self):
        pass


def guard_groups(seat):
    return [
        g
        for g in bridge.load(seat / "hooks.json")["hooks"]["PreToolUse"]
        if any(installer.GUARD_MARK in h["command"] for h in g["hooks"])
    ]


def test_installer_registers_guard_once_and_preserves_foreign_hooks(setup, monkeypatch):
    repo, _, _ = setup
    seat = bridge.codex_home()
    foreign = {"matcher": "Bash", "hooks": [{"type": "command", "command": "true"}]}
    bridge.save(seat / "hooks.json", {"hooks": {"PreToolUse": [foreign]}})
    monkeypatch.setattr(installer, "RPC", FakeRPC)
    first = installer.install(seat, [str(repo)])
    second = installer.install(seat, [str(repo)])
    groups = guard_groups(seat)
    assert len(groups) == 1 and groups[0]["matcher"] == "Bash"
    assert foreign in bridge.load(seat / "hooks.json")["hooks"]["PreToolUse"]
    installed = seat / "hooks" / "nuzantara-context" / installer.GUARD_NAME
    assert installed.read_bytes() == installer.GUARD_SOURCE.read_bytes()
    assert installed.stat().st_mode & 0o777 == 0o700
    digest = bridge.digest(installer.GUARD_SOURCE.read_bytes())
    assert first["source_sha256"][installer.GUARD_NAME] == digest
    assert second["source_sha256"] == first["source_sha256"]


def test_installer_refuses_when_codex_does_not_list_the_guard(setup, monkeypatch):
    repo, _, _ = setup
    monkeypatch.setattr(FakeRPC, "drop_guard", True)
    monkeypatch.setattr(installer, "RPC", FakeRPC)
    with pytest.raises(RuntimeError, match="output guard"):
        installer.install(bridge.codex_home(), [str(repo)])


def test_installer_refuses_duplicate_guard_groups(setup, monkeypatch):
    repo, _, _ = setup
    seat = bridge.codex_home()
    handler = {"type": "command", "command": "python3 x/" + installer.GUARD_MARK}
    dup = {"matcher": "Bash", "hooks": [handler]}
    bridge.save(seat / "hooks.json", {"hooks": {"PreToolUse": [dup, dict(dup)]}})
    monkeypatch.setattr(installer, "RPC", FakeRPC)
    with pytest.raises(ValueError, match="duplicate output guard"):
        installer.install(seat, [str(repo)])


def codex_payload(cwd, tool_name, command):
    # Field set observed in Codex PreToolUse payloads, not Claude's.
    return {
        "session_id": "019a0000-0000-7000-8000-000000000001",
        "turn_id": "turn-1",
        "hook_event_name": "PreToolUse",
        "model": "gpt-6-astra",
        "permission_mode": "bypassPermissions",
        "cwd": str(cwd),
        "transcript_path": None,
        "tool_name": tool_name,
        "tool_use_id": "call_1",
        "tool_input": {"command": command},
    }


@pytest.mark.parametrize(
    "tool_name,command,denied",
    [
        ("Bash", "cat big.log", True),
        ("Bash", "head -n 20 big.log", False),
        ("Bash", "cat big.log > /dev/null", False),
        ("Bash", "cat small.txt", False),
        ("Bash", "ls /nonexistent-dir-for-a-real-failure", False),
        ("Bash", "false", False),
        ("apply_patch", "cat big.log", False),
    ],
)
def test_installed_guard_decides_codex_payloads(
    setup, monkeypatch, tool_name, command, denied
):
    repo, _, _ = setup
    (repo / "big.log").write_text("x" * 40 * 1024)
    (repo / "small.txt").write_text("ok\n")
    monkeypatch.setattr(installer, "RPC", FakeRPC)
    installer.install(bridge.codex_home(), [str(repo)])
    guard = bridge.codex_home() / "hooks" / "nuzantara-context" / installer.GUARD_NAME
    env = {k: v for k, v in os.environ.items() if k != "NUZ_OUTPUT_HYGIENE_OFF"}
    run = subprocess.run(
        [sys.executable, str(guard)],
        input=json.dumps(codex_payload(repo, tool_name, command)),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    # The guard only decides; a genuine failure is the tool's own exit code, never a deny.
    assert run.returncode == (2 if denied else 0)
    assert ("BLOCKED (output-hygiene)" in run.stderr) is denied
    assert run.stdout == ""
