"""Guilt + innocence for context_jump_resume.py (SessionStart injector).

Runs the hook as a subprocess with HOME pointed at a temp dir (same isolation
as every sibling gate here). Guilt: the jump named by NZ_JUMP_FROM, fresh and
unclaimed, is injected and stamped. Innocence: consumed, stale, kill switch,
the originating session itself, a session with no jump at all — and, since
2026-09-09, a window opened BY HAND (no NZ_JUMP_FROM) with a fresh unclaimed
jump sitting right there in its own cwd: that window is the owner's, it stays
mute and stamps nothing.
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
    rc, out, jump = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is not None
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "SALTO DI FINESTRA" in ctx and "MANDATO IN CATENA" in ctx  # jump-file mandate wins
    assert "gh pr create" in ctx and "scripts/x.py" in ctx and "arm the PR" in ctx
    assert jump["to_session"] == "new" and jump.get("claimed_ts")


def test_missing_handoff_still_injects_a_recovery_context():
    home = _home_with_jump(os.getcwd(), handoff=False)
    rc, out, jump = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and "handoff non leggibile" in out["hookSpecificOutput"]["additionalContext"]
    assert jump["to_session"] == "new"


# ---------------- innocence ----------------
def test_already_claimed_jump_is_mute():
    home = _home_with_jump(os.getcwd(), to_session="someone-else")
    rc, out, jump = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is None and jump["to_session"] == "someone-else"


def test_stale_jump_is_mute():
    home = _home_with_jump(os.getcwd(), age_s=20 * 60)
    rc, out, jump = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is None and jump["to_session"] is None


def test_hand_opened_window_never_claims_a_jump():
    # Zero opens a plain `claude` in ~/nuzantara two minutes after a guard trip:
    # a fresh, unclaimed jump from THIS cwd is sitting there. No NZ_JUMP_FROM
    # -> the window is the owner's, not a continuation: mute, nothing stamped.
    home = _home_with_jump(os.getcwd())
    rc, out, jump = _run(home)
    assert rc == 0 and out is None and jump["to_session"] is None


def test_explicit_from_session_is_honoured_whatever_the_cwd():
    # the launcher already cd'd into the jump's cwd; the id is the evidence
    home = _home_with_jump("/somewhere/else")
    rc, out, jump = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is not None and jump["to_session"] == "new"


def test_originating_session_never_claims_its_own_jump():
    home = _home_with_jump(os.getcwd())
    rc, out, jump = _run(home, session_id="old", env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is None and jump["to_session"] is None


def test_kill_switch_is_mute():
    home = _home_with_jump(os.getcwd())
    rc, out, jump = _run(home, env_extra={"CONTEXT_JUMP_OFF": "1", "NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is None and jump["to_session"] is None


def test_two_fresh_jumps_and_no_launcher_id_stamp_nothing():
    # the 2026-09-09 fallback picked the freshest; now neither is touched
    home = _home_with_jump(os.getcwd(), age_s=120)
    d = home / ".organism" / "context-guard"
    (d / "pending-jump-newer.json").write_text(json.dumps({
        "from_session": "newer", "to_session": None, "cwd": os.getcwd(), "hops": 1,
        "ts": time.time(), "mandate": "NEWER"}))
    rc, out, old = _run(home)
    assert rc == 0 and out is None
    assert old["to_session"] is None
    assert json.loads((d / "pending-jump-newer.json").read_text())["to_session"] is None


def test_no_jump_file_is_mute():
    home = pathlib.Path(tempfile.mkdtemp())
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"session_id": "n", "cwd": os.getcwd()}),
                       capture_output=True, text=True, env={"HOME": str(home), "PATH": "/usr/bin:/bin"})
    assert p.returncode == 0 and p.stdout.strip() == ""



def test_explicit_from_session_wins_over_the_freshest_file():
    # two unclaimed jumps in the same cwd: "newer" is fresher, but the launcher
    # opened us FOR "old" (NZ_JUMP_FROM=old) — old is picked, newer left alone
    home = _home_with_jump(os.getcwd(), age_s=120)
    d = home / ".organism" / "context-guard"
    (d / "pending-jump-newer.json").write_text(json.dumps({
        "from_session": "newer", "to_session": None, "cwd": os.getcwd(), "hops": 1,
        "ts": time.time(), "mandate": "NEWER"}))
    rc, out, old = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert "MANDATO IN CATENA" in out["hookSpecificOutput"]["additionalContext"]
    assert old["to_session"] == "new"
    assert json.loads((d / "pending-jump-newer.json").read_text())["to_session"] is None


def test_explicit_from_session_that_is_claimed_or_missing_is_mute():
    home = _home_with_jump(os.getcwd(), to_session="someone")
    rc, out, old = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is None and old["to_session"] == "someone"
    home = _home_with_jump(os.getcwd())
    rc, out, old = _run(home, env_extra={"NZ_JUMP_FROM": "nope"})
    assert rc == 0 and out is None and old["to_session"] is None
