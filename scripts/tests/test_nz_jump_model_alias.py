"""nz-jump.sh keeps the `[1m]` window suffix that the hook payload drops.

Measured 2026-09-18 on M5: every one of the 11 pending-jump files written for
Opus sessions carried the bare id `claude-opus-5`, because the PreToolUse
payload names the model that way while the session had been launched through
the settings alias `opus[1m]`. `nz-jump` passed that bare id to the successor,
which therefore restarted on a 200K window.

  GUILT     (the launcher restores the window): a bare id whose family or id
            matches a `[1m]` default gets the suffix back.
  INNOCENCE (nothing is invented): another family, a default without the
            suffix, an id that already carries it, an unreadable settings
            file, or no model at all → the argv is exactly what it was.

Seam: NZ_JUMP_DRY=1 prints `claude` and its arguments one per line and exits
before launching anything. HOME is a temp dir, so both the jump file and the
settings file the script reads are the fixture's.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "claude-hooks" / "nz-jump.sh"


def _argv(tmp_path: Path, pending_model: str, default_model: str, *, settings: bool = True) -> list[str]:
    home = tmp_path / "home"
    (home / ".organism" / "context-guard").mkdir(parents=True)
    (home / ".claude").mkdir()
    cwd = tmp_path / "repo"
    cwd.mkdir()
    pending = {"model": pending_model, "cwd": str(cwd), "hops": 2, "permission_mode": "bypassPermissions"}
    (home / ".organism" / "context-guard" / "pending-jump-sess-1.json").write_text(json.dumps(pending))
    if settings:
        (home / ".claude" / "settings.json").write_text(json.dumps({"model": default_model}))
    env = {k: v for k, v in os.environ.items() if k not in {"CLAUDE_CONFIG_DIR", "NZ_JUMP_FROM"}}
    env.update({"HOME": str(home), "NZ_JUMP_DRY": "1"})
    r = subprocess.run(["bash", str(SCRIPT), "sess-1"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0] == "nz-jump: dry-run argv", r.stdout
    return lines[1:]


def _model(argv: list[str]) -> str | None:
    return argv[argv.index("--model") + 1] if "--model" in argv else None


@pytest.mark.parametrize("pending,default,expected", [
    ("claude-opus-5", "opus[1m]", "claude-opus-5[1m]"),
    ("claude-opus-5", "claude-opus-5[1m]", "claude-opus-5[1m]"),
    ("claude-sonnet-5", "sonnet[1m]", "claude-sonnet-5[1m]"),
])
def test_guilt_the_window_suffix_of_the_default_model_comes_back(tmp_path, pending, default, expected):
    assert _model(_argv(tmp_path, pending, default)) == expected


@pytest.mark.parametrize("pending,default", [
    ("claude-fable-5-1", "opus[1m]"),
    ("claude-opus-5", "opus"),
    ("claude-opus-5[1m]", "opus[1m]"),
    ("claude-opus-4-8", "claude-opus-5[1m]"),
])
def test_innocence_no_suffix_is_invented(tmp_path, pending, default):
    assert _model(_argv(tmp_path, pending, default)) == pending


def test_innocence_an_unreadable_settings_file_leaves_the_model_bare(tmp_path):
    assert _model(_argv(tmp_path, "claude-opus-5", "", settings=False)) == "claude-opus-5"


def test_innocence_no_model_in_the_jump_file_means_no_model_flag(tmp_path):
    argv = _argv(tmp_path, "", "opus[1m]")
    assert argv[0] == "claude" and "--model" not in argv


def test_the_other_launch_arguments_still_pass(tmp_path):
    argv = _argv(tmp_path, "claude-opus-5", "opus[1m]")
    assert argv[argv.index("--permission-mode") + 1] == "bypassPermissions"
