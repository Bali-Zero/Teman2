"""host_boundary_reminder_sessionstart.sh — SessionStart reminder while
host_boundary is DISARMED (Zero ruling, 2026-09-09).

host_boundary stays off on Pro/M5/Mini today (HOST_BOUNDARY_OFF=1 in each
machine's ~/.claude/settings.json env block) until Zero decides otherwise.
Nobody wired a reminder into a session that it is off — this receptor
(sibling of escalations_alert_sessionstart.sh) closes that: if the env
var is set, print ONE short Italian block naming the ruling, what the
guard protects, and the re-arm route; otherwise stay silent.

These tests drive the real bash script via subprocess (never mutate a
real settings.json), verifying:
  - guilt: HOST_BOUNDARY_OFF=1 -> valid JSON SessionStart payload whose
    additionalContext contains "DISARMATO" and the `! python3` re-arm
    route, under the 400-byte budget.
  - innocence: HOST_BOUNDARY_OFF unset, or set to "0"/"false"/"" -> empty
    stdout, exit 0.
  - the printed one-liner itself, run against a fixture settings.json,
    removes the HOST_BOUNDARY_OFF key, writes a .bak backup of the
    original content, and leaves every other env key, hooks block, and
    JSON validity untouched.

Run:
    cd ~/nuzantara/.worktrees/<this-lane>
    bash -n scripts/hooks/host_boundary_reminder_sessionstart.sh   # syntax check
    apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_host_boundary_reminder.py -v
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "hooks" / "host_boundary_reminder_sessionstart.sh"


def _run_hook(extra_env: dict | None = None) -> tuple[int, str, str]:
    env = dict(os.environ)
    env.pop("HOST_BOUNDARY_OFF", None)
    env["HOST_BOUNDARY_REMINDER_ENABLED"] = "true"
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        ["bash", str(_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.returncode, result.stdout.strip(), result.stderr


def _extract_one_liner(ctx: str) -> str:
    """Pull the `python3 -c "..."` one-liner out of the printed block."""
    m = re.search(r'! (python3 -c ".*")\s*$', ctx)
    assert m, f"could not find the `! python3` one-liner in: {ctx!r}"
    return m.group(1)


# ── script exists and is syntactically valid ────────────────────────────────

def test_script_exists_and_is_syntactically_valid():
    assert _SCRIPT.is_file(), f"hook script missing at {_SCRIPT}"
    r = subprocess.run(["bash", "-n", str(_SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, f"bash -n failed: {r.stderr}"


# ── guilt: HOST_BOUNDARY_OFF=1 -> reminder block ────────────────────────────

def test_host_boundary_off_1_prints_reminder():
    rc, out, err = _run_hook({"HOST_BOUNDARY_OFF": "1"})
    assert rc == 0, f"hook must always exit 0 (fail-open); stderr={err}"
    assert out, "HOST_BOUNDARY_OFF=1 must print a reminder block"
    payload = json.loads(out)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "DISARMATO" in ctx
    assert "HOST_BOUNDARY_OFF" in ctx
    assert "! python3 -c" in ctx, "the re-arm one-liner must be printed verbatim"
    assert len(ctx.encode("utf-8")) <= 400, (
        f"additionalContext must stay <=400 bytes, got {len(ctx.encode('utf-8'))}"
    )


# ── innocence: anything else -> silence ─────────────────────────────────────

@pytest.mark.parametrize("value", [None, "0", "false", "", "yes"])
def test_host_boundary_off_anything_else_is_silent(value):
    extra_env = {} if value is None else {"HOST_BOUNDARY_OFF": value}
    rc, out, err = _run_hook(extra_env)
    assert rc == 0, f"hook must always exit 0 (fail-open); stderr={err}"
    assert out == "", f"non-'1' HOST_BOUNDARY_OFF must stay silent, got: {out!r}"


def test_kill_switch_disables_even_when_disarmed():
    rc, out, err = _run_hook({
        "HOST_BOUNDARY_OFF": "1",
        "HOST_BOUNDARY_REMINDER_ENABLED": "false",
    })
    assert rc == 0
    assert out == "", "kill switch must silence the receptor even when the guard is off"


# ── the printed one-liner actually re-arms cleanly ──────────────────────────

def test_printed_one_liner_removes_key_and_backs_up(tmp_path, monkeypatch):
    fixture = {
        "env": {
            "HOST_BOUNDARY_OFF": "1",
            "SOME_OTHER_KEY": "keep-me",
        },
        "hooks": {"SessionStart": [{"hooks": []}]},
    }
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps(fixture, indent=2))
    original_text = settings_path.read_text()

    rc, out, _ = _run_hook({"HOST_BOUNDARY_OFF": "1"})
    assert rc == 0 and out
    payload = json.loads(out)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    one_liner = _extract_one_liner(ctx)

    # Run the one-liner with HOME pointed at a fixture dir so it operates on
    # our throwaway settings.json, never the real one.
    home = tmp_path
    (home / ".claude").mkdir(exist_ok=True)
    live = home / ".claude" / "settings.json"
    live.write_text(original_text)

    env = dict(os.environ)
    env["HOME"] = str(home)
    r = subprocess.run(one_liner, shell=True, env=env, capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"one-liner must succeed: {r.stderr}"

    backup = home / ".claude" / "settings.json.bak"
    assert backup.is_file(), "one-liner must write a .bak backup before mutating"
    assert backup.read_text() == original_text, "backup must be byte-identical to the pre-mutation file"

    mutated = json.loads(live.read_text())
    assert "HOST_BOUNDARY_OFF" not in mutated.get("env", {}), "HOST_BOUNDARY_OFF must be removed"
    assert mutated["env"]["SOME_OTHER_KEY"] == "keep-me", "other env keys must survive untouched"
    assert mutated["hooks"] == fixture["hooks"], "hooks block must survive untouched"


def test_printed_one_liner_is_idempotent_when_key_already_absent(tmp_path):
    fixture = {"env": {"SOME_OTHER_KEY": "keep-me"}, "hooks": {}}
    home = tmp_path
    (home / ".claude").mkdir(exist_ok=True)
    live = home / ".claude" / "settings.json"
    live.write_text(json.dumps(fixture, indent=2))

    rc, out, _ = _run_hook({"HOST_BOUNDARY_OFF": "1"})
    payload = json.loads(out)
    one_liner = _extract_one_liner(payload["hookSpecificOutput"]["additionalContext"])

    env = dict(os.environ)
    env["HOME"] = str(home)
    r = subprocess.run(one_liner, shell=True, env=env, capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"one-liner must be a no-op, not an error, when the key is absent: {r.stderr}"
    mutated = json.loads(live.read_text())
    assert mutated["env"] == {"SOME_OTHER_KEY": "keep-me"}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
