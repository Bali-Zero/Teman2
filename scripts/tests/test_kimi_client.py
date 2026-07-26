"""Tests for scripts/kimi_client.py — headless Kimi K3 CLI wrapper.

Module is imported via importlib.util.spec_from_file_location (not a package
import) because scripts/ is a flat bag of standalone tools, not a Python
package (mirrors scripts/tests/test_arsenal_probe.py).

NO real subprocess/network calls anywhere in this file — every subprocess
boundary is monkeypatched.
"""

from __future__ import annotations

import importlib.util
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
