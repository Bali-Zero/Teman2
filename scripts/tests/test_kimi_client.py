"""Tests for scripts/kimi_client.py — headless Kimi K3 CLI wrapper.

Module is imported via importlib.util.spec_from_file_location (not a package
import) because scripts/ is a flat bag of standalone tools, not a Python
package (mirrors scripts/tests/test_arsenal_probe.py).

NO real subprocess/network calls anywhere in this file — every subprocess
boundary is monkeypatched.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "kimi_client.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("kimi_client", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


kc = _load_module()


# ---------------------------------------------------------------------------
# Default model — guilt test (the cascade wiring elsewhere assumes this slug)
# ---------------------------------------------------------------------------


def test_default_model_is_kimi_code_k3():
    assert kc.DEFAULT_MODEL == "kimi-code/k3"


# ---------------------------------------------------------------------------
# _resolve_kimi_bin — KIMI_BIN env override
# ---------------------------------------------------------------------------


def test_resolve_kimi_bin_env_override_respected(monkeypatch, tmp_path):
    custom = tmp_path / "kimi-custom"
    custom.write_text("#!/bin/sh\n")
    monkeypatch.setenv("KIMI_BIN", str(custom))
    assert kc._resolve_kimi_bin() == str(custom)


def test_resolve_kimi_bin_dangling_env_override_falls_through(monkeypatch, tmp_path):
    # GLM R1 2026-07-19: a dangling override must not shadow a working install.
    monkeypatch.setenv("KIMI_BIN", "/custom/path/that/does/not/exist")
    fake_default = tmp_path / "kimi"
    fake_default.write_text("#!/bin/sh\n")
    monkeypatch.setattr(kc, "_KIMI_BIN_DEFAULT", str(fake_default))
    assert kc._resolve_kimi_bin() == str(fake_default)


def test_resolve_kimi_bin_falls_back_to_default_path(monkeypatch, tmp_path):
    monkeypatch.delenv("KIMI_BIN", raising=False)
    fake_default = tmp_path / "kimi"
    fake_default.write_text("#!/bin/sh\n")
    monkeypatch.setattr(kc, "_KIMI_BIN_DEFAULT", str(fake_default))
    assert kc._resolve_kimi_bin() == str(fake_default)


def test_resolve_kimi_bin_falls_back_to_path_lookup(monkeypatch):
    monkeypatch.delenv("KIMI_BIN", raising=False)
    monkeypatch.setattr(kc, "_KIMI_BIN_DEFAULT", "/does/not/exist/kimi")
    monkeypatch.setattr(kc.shutil, "which", lambda name: "/opt/homebrew/bin/kimi" if name == "kimi" else None)
    assert kc._resolve_kimi_bin() == "/opt/homebrew/bin/kimi"


def test_resolve_kimi_bin_none_when_nothing_found(monkeypatch):
    monkeypatch.delenv("KIMI_BIN", raising=False)
    monkeypatch.setattr(kc, "_KIMI_BIN_DEFAULT", "/does/not/exist/kimi")
    monkeypatch.setattr(kc.shutil, "which", lambda name: None)
    assert kc._resolve_kimi_bin() is None


# ---------------------------------------------------------------------------
# probe() — success / failure, never raises
# ---------------------------------------------------------------------------


class _FakeCompleted:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_probe_success_returns_true(monkeypatch):
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", lambda cmd, **kwargs: _FakeCompleted(0, "PONG\n", ""))
    assert kc.probe() is True


def test_probe_missing_binary_returns_false(monkeypatch):
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: None)
    assert kc.probe() is False


def test_probe_non_pong_output_returns_false(monkeypatch):
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", lambda cmd, **kwargs: _FakeCompleted(1, "No providers configured.\n", ""))
    assert kc.probe() is False


def test_probe_timeout_returns_false_never_raises(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 60))

    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    assert kc.probe() is False


def test_probe_oserror_returns_false_never_raises(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("no such file")

    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    assert kc.probe() is False


def test_probe_uses_devnull_stdin(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return _FakeCompleted(0, "PONG\n", "")

    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    kc.probe()
    assert captured.get("stdin") == kc.subprocess.DEVNULL


# ---------------------------------------------------------------------------
# run() — success, non-zero exit raises, timeout raises
# ---------------------------------------------------------------------------


def test_run_success_returns_stdout(monkeypatch):
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", lambda cmd, **kwargs: _FakeCompleted(0, "review output\n", ""))
    out = kc.run("review this diff")
    assert out == "review output\n"


def test_run_passes_prompt_and_model_to_cli(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeCompleted(0, "ok\n", "")

    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    kc.run("hello world", model="kimi-code/kimi-for-coding")
    cmd = captured["cmd"]
    assert cmd[0] == "/fake/kimi"
    assert "-m" in cmd and cmd[cmd.index("-m") + 1] == "kimi-code/kimi-for-coding"
    assert "-p" in cmd and cmd[cmd.index("-p") + 1] == "hello world"


def test_run_missing_binary_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: None)
    with pytest.raises(RuntimeError, match="kimi binary not found"):
        kc.run("prompt")


def test_run_non_zero_exit_raises_runtime_error_with_stderr_excerpt(monkeypatch):
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", lambda cmd, **kwargs: _FakeCompleted(1, "", "boom: bad prompt"))
    with pytest.raises(RuntimeError, match="boom: bad prompt"):
        kc.run("prompt")


def test_run_timeout_raises_runtime_error(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 300))

    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="timed out"):
        kc.run("prompt")


def test_run_oserror_raises_runtime_error(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="failed to start"):
        kc.run("prompt")


def test_run_uses_devnull_stdin(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return _FakeCompleted(0, "ok\n", "")

    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    kc.run("prompt")
    assert captured.get("stdin") == kc.subprocess.DEVNULL


def test_run_passes_cwd_through(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return _FakeCompleted(0, "ok\n", "")

    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    kc.run("prompt", cwd="/some/worktree")
    assert captured.get("cwd") == "/some/worktree"


# ---------------------------------------------------------------------------
# CLI main() — --probe and prompt paths
# ---------------------------------------------------------------------------


def test_main_probe_flag_live_exits_0(monkeypatch, capsys):
    monkeypatch.setattr(kc, "probe", lambda: True)
    code = kc.main(["--probe"])
    assert code == 0
    assert "LIVE" in capsys.readouterr().out


def test_main_probe_flag_dead_exits_1(monkeypatch, capsys):
    monkeypatch.setattr(kc, "probe", lambda: False)
    code = kc.main(["--probe"])
    assert code == 1
    assert "DEAD" in capsys.readouterr().out


def test_main_no_prompt_no_probe_exits_2(capsys):
    code = kc.main([])
    assert code == 2
    assert "prompt is required" in capsys.readouterr().err


def test_main_prompt_runs_and_prints_output(monkeypatch, capsys):
    monkeypatch.setattr(kc, "run", lambda prompt, model=kc.DEFAULT_MODEL: "the answer\n")
    code = kc.main(["hello"])
    assert code == 0
    assert "the answer" in capsys.readouterr().out


def test_main_run_failure_exits_1(monkeypatch, capsys):
    def fake_run(prompt, model=kc.DEFAULT_MODEL):
        raise RuntimeError("kimi exploded")

    monkeypatch.setattr(kc, "run", fake_run)
    code = kc.main(["hello"])
    assert code == 1
    assert "kimi exploded" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# v2 hardening — env scrub, PII gate, model guard, durable perms
# (standard: qwen-cloud-code.sh v3 — "a prompt instruction is NOT a control")
# ---------------------------------------------------------------------------


def test_scrubbed_env_drops_credential_markers(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok")
    monkeypatch.setenv("FLY_API_TOKEN", "fly")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_x")
    env = kc._scrubbed_env()
    for leaked in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "FLY_API_TOKEN", "DATABASE_URL", "GITHUB_TOKEN"):
        assert leaked not in env
    assert env.get("PATH") == os.environ.get("PATH")


def test_scrubbed_env_keeps_kimi_code_knobs_and_kimi_bin(monkeypatch):
    monkeypatch.setenv("KIMI_CODE_EXPERIMENTAL_FLAG", "1")
    monkeypatch.setenv("KIMI_BIN", "/custom/kimi")
    env = kc._scrubbed_env()
    assert env.get("KIMI_CODE_EXPERIMENTAL_FLAG") == "1"
    assert env.get("KIMI_BIN") == "/custom/kimi"


def test_run_child_gets_scrubbed_env(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return _FakeCompleted(0, "ok\n", "")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    kc.run("prompt")
    assert "env" in captured
    assert "OPENAI_API_KEY" not in captured["env"]


def test_probe_child_gets_scrubbed_env(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return _FakeCompleted(0, "PONG\n", "")

    monkeypatch.setenv("JWT_SECRET", "jwt")
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    kc.probe()
    assert "env" in captured
    assert "JWT_SECRET" not in captured["env"]


def test_model_guard_refuses_flag_smuggling():
    with pytest.raises(ValueError, match="must not start with"):
        kc._check_model("--yolo")
    kc._check_model("kimi-code/k3")


def test_assert_credential_perms_chmods_0600(monkeypatch, tmp_path):
    state = tmp_path / "credentials"
    state.mkdir()
    secret = state / "kimi-code.json"
    secret.write_text("{}")
    secret.chmod(0o644)
    monkeypatch.setattr(kc, "_KIMI_STATE_DIRS", (state,))
    kc._assert_credential_perms()
    assert (secret.stat().st_mode & 0o777) == 0o600


def test_assert_credential_perms_missing_dir_never_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(kc, "_KIMI_STATE_DIRS", (tmp_path / "absent",))
    kc._assert_credential_perms()


# ---------------------------------------------------------------------------
# v2.1 — REWORK-BUILD cures from the Opus-5 Gear-2 verdict on 182c82d069
# ---------------------------------------------------------------------------


def test_no_tools_agent_file_exists_and_disables_all_tools():
    # C1/C2: the pinned profile must exist next to the wrapper and carry
    # an empty tools allowlist (tools: [] = all tools disabled)
    assert kc._AGENT_FILE.is_file()
    text = kc._AGENT_FILE.read_text()
    assert "tools: []" in text


def test_run_binds_no_tools_agent_file(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeCompleted(0, "ok\n", "")

    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    kc.run("hello")
    cmd = captured["cmd"]
    assert "--agent-file" in cmd
    assert cmd[cmd.index("--agent-file") + 1] == str(kc._AGENT_FILE)


def test_probe_binds_no_tools_agent_file(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeCompleted(0, "PONG\n", "")

    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc.subprocess, "run", fake_run)
    assert kc.probe() is True
    assert "--agent-file" in captured["cmd"]


def test_run_missing_agent_file_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc, "_AGENT_FILE", Path("/does/not/exist/agent.md"))
    with pytest.raises(RuntimeError, match="agent file missing"):
        kc.run("prompt")


def test_probe_missing_agent_file_returns_false(monkeypatch):
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    monkeypatch.setattr(kc, "_AGENT_FILE", Path("/does/not/exist/agent.md"))
    assert kc.probe() is False


def test_assert_credential_perms_chmods_dir_0700(monkeypatch, tmp_path):
    # P1 from the review: the directory itself must not stay enumerable
    state = tmp_path / "oauth"
    state.mkdir()
    state.chmod(0o755)
    (state / "kimi-code").write_text("x")
    monkeypatch.setattr(kc, "_KIMI_STATE_DIRS", (state,))
    kc._assert_credential_perms()
    assert (state.stat().st_mode & 0o777) == 0o700
    assert ((state / "kimi-code").stat().st_mode & 0o777) == 0o600


# ---------------------------------------------------------------------------
# v2.2 — PASS-WITH-CONDITIONS cures (Opus-5 re-verdict on 87f315f185):
# structural PII gate (over-match killed, evasions closed), runtime pin
# of the no-tools profile
# ---------------------------------------------------------------------------


def test_run_refuses_when_profile_loses_no_tools_pin(monkeypatch, tmp_path):
    # the "pin not armed" cure: a profile edit that drops `tools: []` must
    # turn the seat dead, not silently re-arm the exfil channel
    bad = tmp_path / "agent.md"
    bad.write_text("---\nname: kimi-client-headless\ndescription: x\n---\nbody\n")
    monkeypatch.setattr(kc, "_AGENT_FILE", bad)
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    with pytest.raises(RuntimeError, match="no longer disables all tools"):
        kc.run("prompt")


def test_probe_dead_when_profile_loses_no_tools_pin(monkeypatch, tmp_path):
    bad = tmp_path / "agent.md"
    bad.write_text("---\nname: kimi-client-headless\ndescription: x\ntools: [Read]\n---\nbody\n")
    monkeypatch.setattr(kc, "_AGENT_FILE", bad)
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    assert kc.probe() is False


def test_no_tools_pin_reads_frontmatter_not_body(monkeypatch, tmp_path):
    # F3 (cycle-2 verdict): a `tools: []` line in the prose BODY must not
    # satisfy the guard — only the frontmatter block counts
    sneaky = tmp_path / "agent.md"
    sneaky.write_text(
        "---\nname: kimi-client-headless\ndescription: x\ntools: [Read]\n---\n"
        "This profile keeps tools: [] as its safety contract.\n"
    )
    monkeypatch.setattr(kc, "_AGENT_FILE", sneaky)
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    with pytest.raises(RuntimeError, match="no longer disables all tools"):
        kc.run("prompt")


# ---------------------------------------------------------------------------
# v2.3.1 — the two one-line cures prescribed by the owner-resolved review
# (N1 unicode separator artifacts, N2 frontmatter anchored at byte 0)
# ---------------------------------------------------------------------------


def test_no_tools_pin_requires_frontmatter_at_byte_zero(monkeypatch, tmp_path):
    # N2: prose followed by a decoy --- block must NOT parse as frontmatter
    decoy = tmp_path / "agent.md"
    decoy.write_text(
        "Some prose first.\n---\ntools: []\n---\nname: x\ntools: [Read, Bash]\n"
    )
    monkeypatch.setattr(kc, "_AGENT_FILE", decoy)
    monkeypatch.setattr(kc, "_resolve_kimi_bin", lambda: "/fake/kimi")
    with pytest.raises(RuntimeError, match="no longer disables all tools"):
        kc.run("prompt")
