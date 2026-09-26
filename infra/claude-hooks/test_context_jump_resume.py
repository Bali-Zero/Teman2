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


def _home_with_jump(cwd, *, to_session=None, age_s=0, handoff=True, gesture_age_s=None,
                     last_gesture_ts=None):
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
    jump = {
        "from_session": "old", "to_session": to_session, "model": "claude-sonnet-5",
        "cwd": cwd, "handoff_path": str(hp), "hops": 1, "ts": time.time() - age_s,
        "mandate": "MANDATO IN CATENA: cinque cose, in ordine, senza chiedere."}
    if gesture_age_s is not None:
        jump["last_gesture_ts"] = time.time() - gesture_age_s
    elif last_gesture_ts is not None:
        jump["last_gesture_ts"] = last_gesture_ts
    (d / "pending-jump-old.json").write_text(json.dumps(jump))
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


def test_jump_successes_are_timestamped_claims_with_file_drift(tmp_path):
    changed = tmp_path / "changed.py"
    unchanged = tmp_path / "unchanged.py"
    changed.write_text("new")
    unchanged.write_text("old")
    now = time.time()
    os.utime(changed, (now + 30, now + 30))
    os.utime(unchanged, (now - 60, now - 60))
    home = _home_with_jump(str(tmp_path))
    hp = home / ".claude/state/precompact-handoff-old.json"
    data = json.loads(hp.read_text())
    data["successful_file_changes"] = ["changed.py", "unchanged.py", "missing.py"]
    hp.write_text(json.dumps(data))
    _, out, _ = _run(home, cwd=str(tmp_path), env_extra={"NZ_JUMP_FROM": "old"})
    context = out["hookSpecificOutput"]["additionalContext"]
    assert "Previous command claims at " in context
    assert "not a reusable PASS" in context
    section = context.split("## Changed after the jump", 1)[1].split("## Prossima", 1)[0]
    assert "changed.py: changed after the jump" in section
    assert "missing.py: missing now" in section
    assert "unchanged.py:" not in section


def test_jump_unchanged_file_does_not_become_verified(tmp_path):
    file = tmp_path / "stable.py"
    file.write_text("stable")
    os.utime(file, (1, 1))
    home = _home_with_jump(str(tmp_path))
    hp = home / ".claude/state/precompact-handoff-old.json"
    data = json.loads(hp.read_text())
    data["successful_file_changes"] = ["stable.py"]
    hp.write_text(json.dumps(data))
    _, out, _ = _run(home, cwd=str(tmp_path), env_extra={"NZ_JUMP_FROM": "old"})
    assert "None of the inspected files changed" in out["hookSpecificOutput"]["additionalContext"]


def test_jump_drift_annotation_is_bounded_and_uses_fallback_time(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("resume_hook", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handoff = {"successful_commands": ["check"],
               "successful_file_changes": [f"missing-{i}.py" for i in range(50)]}
    context = module.build_context({"cwd": str(tmp_path)}, handoff, jump_mtime=1)
    assert "1970-01-01T00:00:01Z" in context
    section = context.split("## Changed after the jump", 1)[1].split("## Prossima", 1)[0]
    assert section.count("missing now") == 20
    assert "earlier files are unverified" in section
    assert len(section) < 1500


# ---------------- guilt ----------------
def test_fresh_unclaimed_jump_is_injected_and_stamped():
    home = _home_with_jump(os.getcwd())
    rc, out, jump = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is not None
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "SALTO DI FINESTRA" in ctx and "MANDATO IN CATENA" in ctx  # jump-file mandate wins
    assert "gh pr create" in ctx and "scripts/x.py" in ctx and "arm the PR" in ctx
    assert jump["to_session"] == "new" and jump.get("claimed_ts")


def test_retried_gesture_is_fresh_even_when_ts_is_hours_old():
    # 2026-09-26, session cefbda50: ts=14:40, retry (last_gesture_ts)=18:28 —
    # the window that retry opened must not be judged stale off the first ts.
    home = _home_with_jump(os.getcwd(), age_s=3 * 60 * 60, gesture_age_s=60)
    rc, out, jump = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is not None and jump["to_session"] == "new"


def test_garbage_last_gesture_ts_with_fresh_ts_is_still_picked():
    home = _home_with_jump(os.getcwd(), last_gesture_ts="x")
    rc, out, jump = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is not None and jump["to_session"] == "new"


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


def test_stale_ts_with_no_last_gesture_ts_is_still_mute():
    home = _home_with_jump(os.getcwd(), age_s=3 * 60 * 60)
    rc, out, jump = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is None and jump["to_session"] is None


def test_stale_ts_with_stale_last_gesture_ts_is_still_mute():
    home = _home_with_jump(os.getcwd(), age_s=3 * 60 * 60, gesture_age_s=20 * 60)
    rc, out, jump = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is None and jump["to_session"] is None


def test_fresh_ts_but_claimed_stays_mute_regardless_of_gesture():
    home = _home_with_jump(os.getcwd(), to_session="someone-else", gesture_age_s=60)
    rc, out, jump = _run(home, env_extra={"NZ_JUMP_FROM": "old"})
    assert rc == 0 and out is None and jump["to_session"] == "someone-else"


def test_garbage_last_gesture_ts_with_stale_ts_is_mute():
    home = _home_with_jump(os.getcwd(), age_s=3 * 60 * 60, last_gesture_ts="x")
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
