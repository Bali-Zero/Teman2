"""Guilt + innocence for the WINDOW JUMP half of context_window_guard.py.

Reuses test_context_window_guard.run_gate (temp HOME with verbatim copies of
the two reused HOME hooks). No Ghostty is ever driven here: the spawn is gated
by TERM_PROGRAM=ghostty AND CONTEXT_JUMP_NO_SPAWN!=1, and every test either
runs "headless" (no TERM_PROGRAM) or sets CONTEXT_JUMP_NO_SPAWN=1.
"""
from __future__ import annotations

import json
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
    assert "Salto di finestra AVVIATO" in err


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
    rc, _, _, home = run_gate("Bash", {"command": "ls"}, tokens=TRIP, session_id="s-gh",
                              env_extra={"TERM_PROGRAM": "ghostty", "CONTEXT_JUMP_NO_SPAWN": "1"})
    assert rc == 2 and _jump(home, "s-gh")["seat"] == "ghostty"


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
