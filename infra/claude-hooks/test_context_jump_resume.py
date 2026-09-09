"""Guilt + innocence for context_jump_resume.py (SessionStart injector).

Runs the hook as a subprocess with HOME pointed at a temp dir (same isolation
as every sibling gate here). Guilt: a fresh unclaimed jump from this cwd is
injected and stamped. Innocence: consumed, stale, foreign-cwd, kill switch,
the originating session itself, and a session with no jump at all stay mute.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

HOOK = pathlib.Path(__file__).resolve().parent / "context_jump_resume.py"


def _home_with_jump(cwd, *, to_session=None, age_s=0, handoff=True):
    home = pathlib.Path(tempfile.mkdtemp())
    d = home / ".organism" / "context-guard"
    d.mkdir(parents=True)
    hp = home / ".claude" / "state" / "precompact-handoff-old.json"
    hp.parent.mkdir(parents=True)
    if handoff:
        hp.write_text(json.dumps({
            "mandate": "Ruling Zero 2026-09-09: cinque cose, in ordine, senza chiedere.",
            "objective": [], "successful_commands": ["gh pr create ...", "pytest -q"],
            "successful_file_changes": ["scripts/x.py"], "risks": [], "next_action": "arm the PR"}))
    (d / "pending-jump-old.json").write_text(json.dumps({
        "from_session": "old", "to_session": to_session, "model": "claude-sonnet-5",
        "cwd": cwd, "handoff_path": str(hp), "hops": 1, "ts": time.time() - age_s,
        "mandate": "MANDATO IN CATENA: cinque cose, in ordine, senza chiedere."}))
    return home


def _run(home, session_id="new", cwd=None, env_extra=None):
    payload = {"session_id": session_id, "cwd": cwd or os.getcwd(), "hook_event_name": "SessionStart",
               "source": "startup"}
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    out = json.loads(p.stdout) if p.stdout.strip() else None
    jump = json.loads((home / ".organism" / "context-guard" / "pending-jump-old.json").read_text())
    return p.returncode, out, jump


# ---------------- guilt ----------------
def test_fresh_unclaimed_jump_is_injected_and_stamped():
    home = _home_with_jump(os.getcwd())
    rc, out, jump = _run(home)
    assert rc == 0 and out is not None
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "SALTO DI FINESTRA" in ctx and "MANDATO IN CATENA" in ctx  # jump-file mandate wins
    assert "gh pr create" in ctx and "scripts/x.py" in ctx and "arm the PR" in ctx
    assert jump["to_session"] == "new" and jump.get("claimed_ts")


def test_missing_handoff_still_injects_a_recovery_context():
    home = _home_with_jump(os.getcwd(), handoff=False)
    rc, out, jump = _run(home)
    assert rc == 0 and "handoff non leggibile" in out["hookSpecificOutput"]["additionalContext"]
    assert jump["to_session"] == "new"


# ---------------- innocence ----------------
def test_already_claimed_jump_is_mute():
    home = _home_with_jump(os.getcwd(), to_session="someone-else")
    rc, out, jump = _run(home)
    assert rc == 0 and out is None and jump["to_session"] == "someone-else"


def test_stale_jump_is_mute():
    home = _home_with_jump(os.getcwd(), age_s=20 * 60)
    rc, out, jump = _run(home)
    assert rc == 0 and out is None and jump["to_session"] is None


def test_foreign_cwd_is_mute():
    home = _home_with_jump("/somewhere/else")
    rc, out, jump = _run(home)
    assert rc == 0 and out is None and jump["to_session"] is None


def test_originating_session_never_claims_its_own_jump():
    home = _home_with_jump(os.getcwd())
    rc, out, jump = _run(home, session_id="old")
    assert rc == 0 and out is None and jump["to_session"] is None


def test_kill_switch_is_mute():
    home = _home_with_jump(os.getcwd())
    rc, out, jump = _run(home, env_extra={"CONTEXT_JUMP_OFF": "1"})
    assert rc == 0 and out is None and jump["to_session"] is None


def test_freshest_unclaimed_jump_wins_and_only_it_is_stamped():
    home = _home_with_jump(os.getcwd(), age_s=120)
    d = home / ".organism" / "context-guard"
    (d / "pending-jump-newer.json").write_text(json.dumps({
        "from_session": "newer", "to_session": None, "cwd": os.getcwd(), "hops": 1,
        "ts": time.time(), "mandate": "NEWER"}))
    rc, out, old = _run(home)
    assert "NEWER" in out["hookSpecificOutput"]["additionalContext"]
    assert old["to_session"] is None
    assert json.loads((d / "pending-jump-newer.json").read_text())["to_session"] == "new"


def test_no_jump_file_is_mute():
    home = pathlib.Path(tempfile.mkdtemp())
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"session_id": "n", "cwd": os.getcwd()}),
                       capture_output=True, text=True, env={"HOME": str(home), "PATH": "/usr/bin:/bin"})
    assert p.returncode == 0 and p.stdout.strip() == ""
