"""Tests for infra/claude-hooks/install_hook_diet.py (per-call hook diet).

Coverage:
- dry-run on a fixture settings.json removes nothing on disk and reports the
  right before/after hook-per-Bash-call count
- a real (non-dry-run) run removes exactly the 3 inline PostToolUse loggers
  + the SessionStart repomap-inject inline, and adds ONE PostToolUse
  matcher=Bash registration; backs up the original file first; copies
  bash_call_log.sh + redact_secrets.py into --hooks-dir at mode 0700
- a second run is a no-op: no new backup, settings.json byte-identical,
  hook count unchanged

Never touches the real ~/.claude/settings.json — everything runs against a
fixture file under tmp_path, via --settings/--hooks-dir.
"""
from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "infra" / "claude-hooks" / "install_hook_diet.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("install_hook_diet", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def install_hook_diet():
    return _load_module()


def _fixture_settings() -> dict:
    """A minimal settings.json shaped like the real one on the field it
    matters for: the 3 inline PostToolUse loggers, one unrelated PostToolUse
    '' hook (mailbox_inject.py-shaped, must survive), one unrelated
    Edit|Write hook, two PreToolUse hooks that DO count toward the
    per-Bash-call total, and a SessionStart '' group with the repomap inline
    plus one unrelated hook that must survive."""
    return {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash|Edit", "hooks": [{"type": "command", "command": "echo pre1"}]},
                {"matcher": "*", "hooks": [{"type": "command", "command": "echo pre2"}]},
            ],
            "PostToolUse": [
                {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "ruff check"}]},
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                "echo \"[$(date '+%Y-%m-%d %H:%M:%S')] "
                                "$(echo \"$TOOL_CALL\" | /usr/bin/jq -r "
                                "'.tool_input.command' 2>/dev/null || echo "
                                "'unknown')\" >> ~/.claude/command-history.log"
                            ),
                        },
                        {
                            "type": "command",
                            "command": (
                                "CMD=$(echo \"$TOOL_CALL\" | /usr/bin/jq -r "
                                "'.tool_input.command' 2>/dev/null); /usr/bin/jq -nc "
                                "--arg cmd \"$CMD\" --arg cwd \"$PWD\" '{cmd:$cmd, "
                                "cwd:$cwd}' | bash ~/.claude/scripts/hotfix-notify.sh "
                                "2>/dev/null || true"
                            ),
                        },
                    ],
                },
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                "printf '{\"ts\":\"%s\",\"tool\":\"%s\",\"cwd\":\"%s\","
                                "\"git_branch\":\"%s\"}' \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\" "
                                "\"$(echo \"$TOOL_CALL\" | /usr/bin/jq -r '.name // "
                                "\"unknown\"')\" \"$PWD\" \"$(git branch --show-current "
                                "2>/dev/null || echo n/a)\" > ~/.claude/live-status.json "
                                "2>/dev/null || true"
                            ),
                        }
                    ],
                },
                {"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/mailbox_inject.py"}]},
            ],
            "SessionStart": [
                {
                    "matcher": "",
                    "hooks": [
                        {"type": "command", "command": "bash ~/.claude/scripts/log-rotate.sh"},
                        {
                            "type": "command",
                            "command": (
                                "# repomap-inject SOTA L4 2026-05-24\n"
                                "if [[ -f ~/.nuzantara-repomap.txt ]]; then cat "
                                "~/.nuzantara-repomap.txt; fi"
                            ),
                        },
                    ],
                }
            ],
        }
    }


@pytest.fixture()
def fixture_paths(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(_fixture_settings(), indent=2))
    hooks_dir = tmp_path / "hooks"
    return settings, hooks_dir


# Expected count per the fixture above (matcher '' / '*' / contains 'Bash'):
#   PreToolUse: "Bash|Edit" (1) + "*" (1) = 2
#   PostToolUse: "Bash" (2) + "" live-status (1) + "" mailbox (1) = 4
#   BEFORE = 6
# After: the "Bash" group (both hooks removed) and the live-status "" group
# (its only hook removed) are dropped entirely; mailbox "" group survives;
# one new "Bash" group with 1 hook is added.
#   AFTER = mailbox(1) + new-Bash(1) + PreToolUse(2) = 4
EXPECTED_BEFORE = 6
EXPECTED_AFTER = 4


def test_dry_run_writes_nothing(install_hook_diet, fixture_paths, capsys):
    settings, hooks_dir = fixture_paths
    original_bytes = settings.read_bytes()

    import sys as _sys

    argv = _sys.argv
    _sys.argv = ["install_hook_diet.py", "--dry-run", "--settings", str(settings), "--hooks-dir", str(hooks_dir)]
    try:
        install_hook_diet.main()
    finally:
        _sys.argv = argv

    out = capsys.readouterr().out
    assert f"{EXPECTED_BEFORE} -> {EXPECTED_AFTER}" in out
    assert "dry-run" in out
    assert settings.read_bytes() == original_bytes, "dry-run must not touch the settings file"
    assert not hooks_dir.exists(), "dry-run must not create the hooks dir"
    assert not list(settings.parent.glob("*.bak-hookdiet-*")), "dry-run must not create a backup"


def test_apply_removes_loggers_and_registers_one(install_hook_diet, fixture_paths, capsys):
    settings, hooks_dir = fixture_paths

    import sys as _sys

    argv = _sys.argv
    _sys.argv = ["install_hook_diet.py", "--settings", str(settings), "--hooks-dir", str(hooks_dir)]
    try:
        install_hook_diet.main()
    finally:
        _sys.argv = argv

    out = capsys.readouterr().out
    assert f"{EXPECTED_BEFORE} -> {EXPECTED_AFTER}" in out

    data = json.loads(settings.read_text())
    hooks = data["hooks"]

    all_post_commands = [
        h.get("command", "") for g in hooks["PostToolUse"] for h in g.get("hooks", [])
    ]
    assert not any("command-history.log" in c and ">>" in c for c in all_post_commands)
    assert not any("hotfix-notify.sh" in c for c in all_post_commands)
    assert not any("live-status.json" in c and "printf" in c for c in all_post_commands)
    # survivors
    assert any("mailbox_inject.py" in c for c in all_post_commands)
    assert any(c.strip() == "bash ~/.claude/hooks/bash_call_log.sh" for c in all_post_commands)
    # the new registration is its own matcher=Bash group
    new_groups = [g for g in hooks["PostToolUse"] if g.get("matcher") == "Bash"]
    assert len(new_groups) == 1
    assert len(new_groups[0]["hooks"]) == 1

    all_session_commands = [
        h.get("command", "") for g in hooks["SessionStart"] for h in g.get("hooks", [])
    ]
    assert not any("repomap-inject" in c for c in all_session_commands)
    assert any("log-rotate.sh" in c for c in all_session_commands)

    # backup created with the ORIGINAL content
    backups = list(settings.parent.glob("*.bak-hookdiet-*"))
    assert len(backups) == 1
    backup_data = json.loads(backups[0].read_text())
    assert any(
        "command-history.log" in h.get("command", "")
        for g in backup_data["hooks"]["PostToolUse"]
        for h in g.get("hooks", [])
    ), "backup must carry the PRE-install content"

    # hook files installed at 0700
    for name in ("bash_call_log.sh", "redact_secrets.py"):
        dst = hooks_dir / name
        assert dst.exists(), f"{name} not installed"
        mode = stat.S_IMODE(dst.stat().st_mode)
        assert mode == 0o700, f"{name} mode {oct(mode)} != 0700"


def test_second_run_is_a_noop(install_hook_diet, fixture_paths, capsys):
    settings, hooks_dir = fixture_paths

    import sys as _sys

    argv = _sys.argv
    _sys.argv = ["install_hook_diet.py", "--settings", str(settings), "--hooks-dir", str(hooks_dir)]
    try:
        install_hook_diet.main()
        capsys.readouterr()  # drain first-run output
        after_first = settings.read_bytes()

        install_hook_diet.main()
    finally:
        _sys.argv = argv

    out = capsys.readouterr().out
    assert "no-op" in out
    assert f"{EXPECTED_AFTER} -> {EXPECTED_AFTER}" in out
    assert settings.read_bytes() == after_first, "second run must not rewrite settings.json"

    backups = list(settings.parent.glob("*.bak-hookdiet-*"))
    assert len(backups) == 1, "second run must not create a second backup"
