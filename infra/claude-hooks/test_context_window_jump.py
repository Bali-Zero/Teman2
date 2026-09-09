"""Guilt + innocence for the WINDOW JUMP half of context_window_guard.py.

Reuses test_context_window_guard.run_gate (temp HOME with verbatim copies of
the two reused HOME hooks). No Ghostty is ever driven here: the spawn is gated
by TERM_PROGRAM=ghostty AND CONTEXT_JUMP_NO_SPAWN!=1, and every test either
runs "headless" (no TERM_PROGRAM) or sets CONTEXT_JUMP_NO_SPAWN=1.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

from test_context_window_guard import HOOK, run_gate

TRIP = 150_000  # 75% of 200K: past the 40% default


def _jump(home: pathlib.Path, session: str):
    p = home / ".organism" / "context-guard" / f"pending-jump-{session}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _plant_link(home: pathlib.Path, *, produced: str, hops: int, mandate: str = "M0"):
    d = home / ".organism" / "context-guard"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"pending-jump-prev-{produced}.json").write_text(json.dumps(
        {"from_session": f"prev-{produced}", "to_session": produced, "hops": hops,
         "mandate": mandate, "ts": time.time()}))


def _run_with_first_user(home: pathlib.Path, session: str, first_user_line: str):
    """Trip the guard on a transcript whose HEAD is a real user record."""
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="warm", home=home)
    tp = home / "transcript.jsonl"
    tp.write_text(first_user_line + "\n" + tp.read_text())
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"},
               "transcript_path": str(tp), "session_id": session, "cwd": str(home)}
    subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True,
                   text=True, env={"HOME": str(home), "PATH": "/usr/bin:/bin"})
    return json.loads((home / ".claude" / "state" / f"precompact-handoff-{session}.json").read_text())


# ---------------- guilt ----------------
def test_first_trip_writes_pending_jump_and_says_so():
    rc, _, err, home = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-one")
    assert rc == 2
    j = _jump(home, "s-one")
    assert j and j["from_session"] == "s-one" and j["to_session"] is None
    assert j["hops"] == 1 and j["seat"] == "headless" and isinstance(j["from_pid"], int)
    assert j["handoff_path"].endswith("precompact-handoff-s-one.json")
    # Headless seat: no gesture was made, so the deny must not claim one.
    assert "Salto REGISTRATO" in err and "nz-jump s-one" in err and "AVVIATO" not in err


def test_second_trip_same_session_does_not_rewrite_the_jump():
    home = pathlib.Path(tempfile.mkdtemp())
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-two", home=home)
    first = _jump(home, "s-two")
    rc, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-two", home=home)
    assert rc == 2 and _jump(home, "s-two")["ts"] == first["ts"]
    assert "Salto non avviato" in err  # already in flight: the deny stays, the gesture is not repeated


def test_two_sessions_in_the_same_home_get_two_files():
    home = pathlib.Path(tempfile.mkdtemp())
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-a", home=home)
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-b", home=home)
    assert _jump(home, "s-a")["from_session"] == "s-a"
    assert _jump(home, "s-b")["from_session"] == "s-b"  # b did not overwrite a


def test_hop_chain_is_counted_and_capped():
    home = pathlib.Path(tempfile.mkdtemp())
    _plant_link(home, produced="s-four", hops=3)  # this session IS hop 3 → no 4th
    rc, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-four", home=home)
    assert rc == 2 and _jump(home, "s-four") is None and "cap salti" in err
    _plant_link(home, produced="s-hop2", hops=1)  # hop 2 still allowed and counted
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-hop2", home=home)
    assert _jump(home, "s-hop2")["hops"] == 2


def test_mandate_is_carried_along_the_chain_not_recomputed():
    home = pathlib.Path(tempfile.mkdtemp())
    _plant_link(home, produced="s-h2", hops=1, mandate="ORIGINAL MANDATE from hop 0")
    stub = json.dumps({"type": "user", "message": {"role": "user", "content":
                       "Sei la finestra successiva della sessione s-prev (salto 1). Continua da lì senza chiedere."}})
    h = _run_with_first_user(home, "s-h2", stub)
    assert h["mandate"] == "ORIGINAL MANDATE from hop 0"
    assert _jump(home, "s-h2")["mandate"] == "ORIGINAL MANDATE from hop 0"


def test_handoff_carries_the_first_user_mandate_in_full_structured():
    home = pathlib.Path(tempfile.mkdtemp())
    mandate = "Ruling Zero: cinque cose in ordine. " + "x" * 700  # > 500 chars, list-of-blocks content
    line = json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": mandate}]}})
    h = _run_with_first_user(home, "s-m", line)
    assert h["mandate"] == mandate  # not truncated at 500, structured block read


def test_handoff_carries_the_first_user_mandate_plain_string():
    # the common shape of a typed first message: content is a plain string
    home = pathlib.Path(tempfile.mkdtemp())
    mandate = "leggi ed esegui il mandato in docs/x.md, poi riporta " + "y" * 600
    line = json.dumps({"type": "user", "message": {"role": "user", "content": mandate}})
    h = _run_with_first_user(home, "s-str", line)
    assert h["mandate"] == mandate


def test_ghostty_seat_is_recorded_but_spawn_is_suppressed_in_tests():
    rc, _, err, home = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-gh",
                                env_extra={"TERM_PROGRAM": "ghostty", "CONTEXT_JUMP_NO_SPAWN": "1"})
    assert rc == 2 and _jump(home, "s-gh")["seat"] == "ghostty"
    assert "Salto REGISTRATO" in err  # spawn suppressed = no gesture = never "started"


def test_ghostty_spawn_is_reported_as_attempted_not_started(tmp_path=None):
    # A real spawn: the script is a stub that exits 1 (the gesture FAILED, as
    # ⌘N did on M5 2026-09-09 17:59). The hook cannot know that — it does not
    # wait — so it must say TENTATO + where the outcome is + the manual gesture,
    # and never AVVIATO.
    home = pathlib.Path(tempfile.mkdtemp())
    hooks = home / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "window_jump.sh").write_text("#!/bin/bash\nexit 1\n")
    rc, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-spawn", home=home,
                             env_extra={"TERM_PROGRAM": "ghostty"})
    assert rc == 2 and _jump(home, "s-spawn")["seat"] == "ghostty"
    if sys.platform == "darwin":
        assert "Salto di finestra TENTATO" in err and "jump.log" in err and "nz-jump s-spawn" in err
    else:
        assert "Salto REGISTRATO" in err
    assert "AVVIATO" not in err


# ---------------- innocence ----------------
def test_kill_switch_stops_the_jump_but_not_the_deny():
    rc, _, err, home = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-off",
                                env_extra={"CONTEXT_JUMP_OFF": "1"})
    assert rc == 2 and _jump(home, "s-off") is None and "Salto non avviato" in err


def test_below_threshold_never_raises_a_jump():
    rc, _, _, home = run_gate("Bash", {"command": "ls"}, tokens=10_000, session_id="s-low")
    assert rc == 0 and _jump(home, "s-low") is None


def test_allowed_call_above_threshold_still_raises_the_jump_once():
    # the gesture is tied to the TRIP, not to the first denied tool
    rc, _, _, home = run_gate("Bash", {"command": "~/.claude/scripts/mem save fact x 5"},
                              tokens=TRIP, session_id="s-mem")
    assert rc == 0 and _jump(home, "s-mem")["from_session"] == "s-mem"


# ---------------- (c) the gesture is retried when it MISSED ----------------
# 2026-09-09, session a60e0124: the jump file existed, to_session was null,
# jump.log said "nothing typed" — and every later trip answered "salto non
# avviato" because the FILE was the rate limit. A human had to type nz-jump.

def _plant_gesture(home: pathlib.Path) -> pathlib.Path:
    """A fake window_jump.sh that records each spawn instead of driving Ghostty.
    No AppleScript, no window: the gesture itself is proven by
    test_window_jump_gesture.sh with a shimmed osascript."""
    hooks = home / ".claude" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "window_jump.sh").write_text(
        '#!/bin/bash\necho "$1" >> "$HOME/spawns.log"\n')
    return home / "spawns.log"


def _spawns(spawn_log: pathlib.Path, want: int, timeout: float = 10.0) -> int:
    """Popen is async: wait for the detached gesture to have written its mark."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        n = len(spawn_log.read_text().splitlines()) if spawn_log.exists() else 0
        if n >= want:
            return n
        time.sleep(0.1)
    return len(spawn_log.read_text().splitlines()) if spawn_log.exists() else 0


def _log_miss(home: pathlib.Path, session: str):
    d = home / ".organism" / "context-guard"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "jump.log").open("a") as fh:
        fh.write(f"[2026-09-09 19:59:00] [{session}] no new window within 8s of ⌘N: nothing typed\n")


def _log_typed(home: pathlib.Path, session: str):
    d = home / ".organism" / "context-guard"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "jump.log").open("a") as fh:
        fh.write(f"[2026-09-09 19:59:00] [{session}] new window '~/nuzantara' opened, "
                 f"'nz-jump {session}' typed\n")


def test_a_missed_gesture_is_retried_on_the_next_trip():
    home = pathlib.Path(tempfile.mkdtemp())
    spawn_log = _plant_gesture(home)
    env = {"TERM_PROGRAM": "ghostty"}
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-retry", home=home, env_extra=env)
    if sys.platform != "darwin":  # no gesture is even possible off macOS
        assert _jump(home, "s-retry")["gesture_attempts"] == 0
        return
    assert _spawns(spawn_log, 1) == 1 and _jump(home, "s-retry")["gesture_attempts"] == 1
    _log_miss(home, "s-retry")
    rc, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-retry",
                             home=home, env_extra=env)
    assert rc == 2
    assert "gesto ritentato (2/3)" in err
    assert _spawns(spawn_log, 2) == 2
    assert _jump(home, "s-retry")["gesture_attempts"] == 2


def test_the_retry_stops_at_three_gestures_and_says_so():
    if sys.platform != "darwin":
        return
    home = pathlib.Path(tempfile.mkdtemp())
    spawn_log = _plant_gesture(home)
    env = {"TERM_PROGRAM": "ghostty"}
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-cap", home=home, env_extra=env)
    _spawns(spawn_log, 1)
    for expected in (2, 3):
        _log_miss(home, "s-cap")
        _, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-cap",
                                home=home, env_extra=env)
        assert f"gesto ritentato ({expected}/3)" in err
        assert _spawns(spawn_log, expected) == expected
    _log_miss(home, "s-cap")  # a fourth trip after three misses is a human problem
    _, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-cap",
                            home=home, env_extra=env)
    assert "Salto non avviato" in err and "cap salti" in err
    assert _spawns(spawn_log, 4, timeout=2.0) == 3
    assert _jump(home, "s-cap")["gesture_attempts"] == 3


def test_a_gesture_that_landed_is_never_retried():
    if sys.platform != "darwin":
        return
    home = pathlib.Path(tempfile.mkdtemp())
    spawn_log = _plant_gesture(home)
    env = {"TERM_PROGRAM": "ghostty"}
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-ok", home=home, env_extra=env)
    _spawns(spawn_log, 1)
    _log_typed(home, "s-ok")  # the keystroke landed; the new session is just slow
    _, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-ok",
                            home=home, env_extra=env)
    assert "Salto non avviato" in err and "ritentato" not in err
    assert _spawns(spawn_log, 2, timeout=2.0) == 1
    assert _jump(home, "s-ok")["gesture_attempts"] == 1


def test_a_reported_new_session_is_never_retried_even_after_a_miss():
    if sys.platform != "darwin":
        return
    home = pathlib.Path(tempfile.mkdtemp())
    spawn_log = _plant_gesture(home)
    env = {"TERM_PROGRAM": "ghostty"}
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-done", home=home, env_extra=env)
    _spawns(spawn_log, 1)
    p = home / ".organism" / "context-guard" / "pending-jump-s-done.json"
    j = json.loads(p.read_text()); j["to_session"] = "s-next"; p.write_text(json.dumps(j))
    _log_miss(home, "s-done")  # a stale miss line must not outvote to_session
    _, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-done",
                            home=home, env_extra=env)
    assert "Salto non avviato" in err
    assert _spawns(spawn_log, 2, timeout=2.0) == 1


def test_a_headless_jump_is_never_retried():
    # gesture_attempts == 0: nothing was ever gestured, so nothing is owed.
    home = pathlib.Path(tempfile.mkdtemp())
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-head", home=home)
    _log_miss(home, "s-head")
    _, _, err, _ = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-head", home=home)
    assert "Salto non avviato" in err and _jump(home, "s-head")["gesture_attempts"] == 0


# ---------------- (d) from_pid is the claude process, not a shell ----------
# Outside the hook (manual invocation, probe) the parent is a shell, and
# window_jump.sh's SIGINT×2 fallback would interrupt THAT instead of claude.

def _fake_ps(home: pathlib.Path, answers: list[str]) -> str:
    """PATH shim for `ps -o ppid=,comm= -p <pid>`: answers the Nth call with the
    Nth line. Returns the PATH the hook must run with. Nothing else is shimmed."""
    d = home / "shim"
    d.mkdir(parents=True, exist_ok=True)
    for i, a in enumerate(answers, 1):
        (d / f"ps.{i}").write_text(a + "\n")
    ps = d / "ps"
    ps.write_text('#!/bin/bash\n'
                  'd="$(cd "$(dirname "$0")" && pwd)"\n'
                  'n=$(cat "$d/n" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$d/n"\n'
                  'f="$d/ps.$n"; [ -f "$f" ] && cat "$f"\n'
                  'exit 0\n')
    ps.chmod(0o755)
    return f"{d}:/usr/bin:/bin"


def test_from_pid_walks_up_the_chain_to_the_claude_process():
    home = pathlib.Path(tempfile.mkdtemp())
    # hook's parent is a shell (4145), whose parent is the installed CLI —
    # whose basename is a VERSION, so the match is on the path component.
    path = _fake_ps(home, ["4145 /bin/zsh",
                           "77 /Users/x/.local/share/claude/versions/2.1.266"])
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-pid", home=home,
             env_extra={"PATH": path})
    assert _jump(home, "s-pid")["from_pid"] == 4145


def test_from_pid_falls_back_to_the_direct_parent_when_no_claude_on_the_chain():
    home = pathlib.Path(tempfile.mkdtemp())
    path = _fake_ps(home, ["4145 /bin/zsh", "1 /sbin/launchd"])
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-pid2", home=home,
             env_extra={"PATH": path})
    # the hook's real parent is THIS process (run_gate spawns it directly)
    assert _jump(home, "s-pid2")["from_pid"] == os.getpid()


def test_from_pid_survives_a_ps_that_says_nothing():
    home = pathlib.Path(tempfile.mkdtemp())
    path = _fake_ps(home, [])  # every call returns empty: unknowable chain
    run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-pid3", home=home,
             env_extra={"PATH": path})
    assert _jump(home, "s-pid3")["from_pid"] == os.getpid()
