"""window_jump.sh — the gesture, exercised with a stubbed `osascript`.

The script drives Ghostty through AppleScript; no CI runner has a GUI, so the
seam is OSASCRIPT=<stub>. The stub records every call (action + argv) and
answers per MODE, and the test asserts the ORDER of gestures, what is typed
where, and the log line for every miss — the contract that failed live on
2026-09-09 (Pro 15:36, M5 17:59: ⌘N without a new front window, and the
guard already claiming "AVVIATO").

Since v2.1 both routes stand on the SAME pre-gesture snapshot (`window-names`
is the first call either way) and only a window whose name was ABSENT from it
may be typed into — the native route cross-checks the name of the window its
own API handed back. The name-level guilt/innocence lives in
infra/claude-hooks/test_window_jump_gesture.sh; what this file pins is the
ORDER of the two routes and the ending of the old session.

v2.2 (2026-09-17): the OLD window is never the front window. It is resolved
AFTER the new session claimed the jump, by an OSC title stamped on the tty of
`from_pid` (seam: JUMP_TTY=<file>) — only the old claude's own terminal can show
it — and `/exit` goes to the ONE window whose name carries the session id, or
nowhere. On 2026-09-17 01:35 the front window was Zero's fresh Sonnet session.

Portable since 2026-09-19: the script gates on the OSASCRIPT binary, not on
uname, and this corpus supplies that binary, so it runs on ubuntu CI too. It
used to carry a file-level Darwin-only skip written when the script still
exited 0 off macOS; after #6788 wired it into guard-conformance.yml the runner
collected 11 skips and the corpus could never go red on a PR (gate notice on
#6788). Every macOS-only call (ps -o tty=, osascript) is behind a seam here.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(os.environ.get("WINDOW_JUMP_SH")
              or Path(__file__).resolve().parents[2] / "infra" / "claude-hooks" / "window_jump.sh")

STUB = r'''#!/bin/bash
# osascript stub: $1 = script path, $2 = action, rest = args. MODE from env.
echo "$(basename "$1") $2 ${3:-} ${4:-}" >> "$STUB_LOG"
d="$(dirname "$STUB_LOG")"
case "$(basename "$1")|$2|$STUB_MODE" in
  *native*"|"*"|native-disabled"|*native*"|"*"|keys-"*) echo "execution error: AppleScript is disabled by the macos-applescript configuration. (-1743)" >&2; exit 1 ;;
  *native*"|window-names|"*)           echo "old title"; exit 0 ;;
  *native*"|old-id|native-no-old")     echo ""; exit 0 ;;
  *native*"|old-id|"*)                 echo "win-OLD"; exit 0 ;;
  *native*"|new-window|"*)             echo "win-NEW"; exit 0 ;;
  *native*"|name-of-id|"*)             if [ "${3:-}" = "win-NEW" ]; then echo "new title"; else echo "old title"; fi; exit 0 ;;
  *native*"|type-into|"*)              echo "ok"; exit 0 ;;
  *native*"|close-window|"*)           echo "ok"; exit 0 ;;
  window_jump.applescript"|window-names|keys-front-stuck") echo "old title"; exit 0 ;;
  window_jump.applescript"|window-names|keys-stamped")
    # snapshot = front is Zero's other session; later lists carry OUR stamped
    # old window too, which must never be taken for the birth of the new one
    n=$(cat "$d/wn" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$d/wn"
    if [ "$n" = 1 ]; then echo "old title"; else printf 'old title\n⏩ nz-jump sess-123\nnew title\n'; fi; exit 0 ;;
  window_jump.applescript"|window-names|"*)
    # first call = the snapshot; every later one also shows the new window
    n=$(cat "$d/wn" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$d/wn"
    if [ "$n" = 1 ]; then echo "old title"; else printf 'old title\nnew title\n'; fi; exit 0 ;;
  window_jump.applescript"|front-name|"*)  echo "old title"; exit 0 ;;
  window_jump.applescript"|cmd-n|"*)       echo "ok"; exit 0 ;;
  window_jump.applescript"|type-here|"*)   echo "ok"; exit 0 ;;
  window_jump.applescript"|raise-type|"*)  echo "ok"; exit 0 ;;
esac
exit 1
'''


def _home(tmp_path: Path, from_pid: int, *, cwd: str = "/tmp/wd") -> tuple[Path, Path]:
    home = tmp_path / "home"
    state = home / ".organism" / "context-guard"
    state.mkdir(parents=True)
    pending = state / "pending-jump-sess-1234-abcd.json"
    pending.write_text(json.dumps({"from_session": "sess-1234-abcd", "from_pid": from_pid,
                                   "to_session": None, "cwd": cwd, "hops": 1, "ts": time.time(),
                                   "seat": "ghostty", "model": "claude-sonnet-5"}))
    stub = tmp_path / "osascript"
    stub.write_text(STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    (home / "stamp.tty").write_bytes(b"")   # the seam for the old claude's tty
    return home, pending


STAMP = "\x1b]0;⏩ nz-jump sess-123\x07"


def _stamp(home: Path) -> str:
    return (home / "stamp.tty").read_bytes().decode("utf-8")


def _run(home: Path, mode: str, *, claim_after: float | None = 0.5, from_pid: int | None = None,
         tty_seam: bool = True):
    """Run the script; optionally stamp to_session after `claim_after` seconds
    (the SessionStart hook of the new window would)."""
    pending = home / ".organism" / "context-guard" / "pending-jump-sess-1234-abcd.json"
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "OSASCRIPT": str(home.parent / "osascript"),
           "STUB_MODE": mode, "STUB_LOG": str(home / "calls.log"),
           "JUMP_WAIT_S": "6", "EXIT_WAIT_S": "1", "JUMP_POLL_MAX_S": "2",
           **({"JUMP_TTY": str(home / "stamp.tty")} if tty_seam else {})}
    p = subprocess.Popen(["bash", str(SCRIPT), "sess-1234-abcd"], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if claim_after is not None:
        time.sleep(claim_after)
        d = json.loads(pending.read_text())
        d["to_session"] = "sess-NEW"
        pending.write_text(json.dumps(d))
    rc = p.wait(timeout=30)
    calls = (home / "calls.log").read_text().splitlines() if (home / "calls.log").exists() else []
    log = (home / ".organism" / "context-guard" / "jump.log").read_text()
    return rc, calls, log


def _sleeper() -> subprocess.Popen:
    # A stand-in for the old claude: dies on SIGINT, like the measured fallback.
    return subprocess.Popen([sys.executable, "-c", "import time\nwhile True: time.sleep(0.2)"])


# ---------------- native route ----------------
def test_native_route_opens_by_id_types_into_new_then_exits_and_closes_old(tmp_path):
    old = _sleeper()
    try:
        home, _ = _home(tmp_path, old.pid)
        rc, calls, log = _run(home, "native-ok")
    finally:
        old.kill()
    assert rc == 0, log
    assert calls[:4] == ["window_jump_native.applescript window-names  ",
                         "window_jump_native.applescript new-window /tmp/wd ",
                         "window_jump_native.applescript name-of-id win-NEW ",
                         "window_jump_native.applescript type-into win-NEW nz-jump sess-1234-abcd"]
    assert "name='new title' (absent from the snapshot)" in log, "the id is a handle; the NAME authorises the keystroke"
    # the old window is asked for only AFTER the claim, and only by the stamp
    assert calls.index("window_jump_native.applescript old-id sess-123 ") > 3
    assert _stamp(home) == STAMP, "the stamp goes to the tty of from_pid, nowhere else"
    assert "window_jump_native.applescript type-into win-OLD /exit" in calls
    assert "/exit typed into old window id=win-OLD (proven ours by stamp)" in log
    assert calls[-1] == "window_jump_native.applescript close-window win-OLD "
    assert not any(c.startswith("window_jump.applescript") for c in calls), "native route must never touch System Events"
    assert "new session sess-NEW is up" in log and "old window id=win-OLD closed" in log
    assert "SIGINT" in log  # the sleeper ignores /exit, so the fallback ended it


def test_native_unknown_old_window_never_types_exit_and_leaves_it_open(tmp_path):
    old = _sleeper()
    try:
        home, _ = _home(tmp_path, old.pid)
        rc, calls, log = _run(home, "native-no-old")
    finally:
        old.kill()
    assert rc == 0
    assert not any("type-into win-OLD" in c or "close-window" in c for c in calls)
    assert "old window id unknown: /exit NOT typed" in log and "window left open" in log


def test_native_old_window_not_closed_while_old_claude_alive(tmp_path):
    # from_pid that ignores SIGINT: the window must stay (Ghostty would prompt).
    old = subprocess.Popen([sys.executable, "-c",
                            "import signal,time\nsignal.signal(signal.SIGINT, signal.SIG_IGN)\nwhile True: time.sleep(0.2)"])
    try:
        home, _ = _home(tmp_path, old.pid)
        rc, calls, log = _run(home, "native-ok")
    finally:
        old.kill()
    assert rc == 0
    assert not any("close-window" in c for c in calls)
    assert "STILL alive" in log and "NOT closed" in log


def test_native_from_pid_without_a_tty_leaves_the_window_open_on_both_ps_dialects(tmp_path):
    # No JUMP_TTY seam: the script asks ps for the tty of from_pid, started in
    # its own session so it has no controlling terminal. BSD ps prints "??",
    # Linux procps "?": both mean "no tty". Until 2026-09-19 only the macOS
    # literal was recognised and on Linux the script went on to "/dev/? not
    # writable" -- the same refusal for the wrong reason.
    old = subprocess.Popen([sys.executable, "-c", "import time\nwhile True: time.sleep(0.2)"],
                           start_new_session=True, stdin=subprocess.DEVNULL)
    try:
        home, _ = _home(tmp_path, old.pid)
        rc, calls, log = _run(home, "native-ok", tty_seam=False)
    finally:
        old.kill()
    assert rc == 0, log
    assert f"pid {old.pid} has no tty (window left open)" in log
    assert "not writable" not in log
    assert _stamp(home) == "", "no tty proven ours: nothing is stamped anywhere"
    assert not any("type-into win-OLD" in c or "close-window" in c for c in calls)


# ---------------- fallback route ----------------
def test_native_disabled_falls_back_to_keystrokes(tmp_path):
    home, _ = _home(tmp_path, 0)
    rc, calls, log = _run(home, "native-disabled")
    assert rc == 0, log
    # the dictionary is refused at the very first call — the snapshot itself
    assert "native window list unavailable" in log and "AppleScript is disabled" in log
    assert calls[1:] == ["window_jump.applescript window-names  ",
                         "window_jump.applescript cmd-n  ",
                         "window_jump.applescript window-names  ",
                         "window_jump.applescript raise-type new title nz-jump sess-1234-abcd"]
    assert "'nz-jump sess-1234-abcd' typed" in log
    # no from_pid = no stamp = no window proven ours: the front window
    # ("old title") is NOT typed into, whatever the snapshot said
    assert "own window not stamped: no from_pid" in log and "/exit NOT typed" in log
    assert not any("/exit" in c for c in calls)


def test_keys_route_exits_only_the_window_proven_ours_by_stamp(tmp_path):
    # 2026-09-17 01:35 on M5: the front window was a Sonnet session Zero had
    # opened 30 seconds earlier; v2.1 typed /exit into it. Now the snapshot
    # head ("old title") is never the target: only the name carrying the
    # stamped session id is — and that name is never taken for the new window.
    old = _sleeper()
    try:
        home, _ = _home(tmp_path, old.pid)
        rc, calls, log = _run(home, "keys-stamped")
    finally:
        old.kill()
    assert rc == 0, log
    assert "window_jump.applescript raise-type new title nz-jump sess-1234-abcd" in calls
    assert not any("⏩ nz-jump sess-123\tnz-jump" in c or "raise-type ⏩ nz-jump sess-123 nz-jump" in c for c in calls), \
        "our own stamped window must never receive nz-jump"
    assert _stamp(home) == STAMP
    assert "window_jump.applescript raise-type ⏩ nz-jump sess-123 /exit" in calls
    assert not any("raise-type old title /exit" in c for c in calls), "the front window is not ours"
    assert "/exit typed into old window '⏩ nz-jump sess-123' (proven ours by stamp)" in log


def test_old_window_is_never_the_front_window(tmp_path):
    # The AppleScript the gesture writes must not carry the v2.1 shortcut
    # (`if frontmost then return id of front window`): the old window is the
    # ONE whose title contains the session id, or unknown.
    old = _sleeper()
    try:
        home, _ = _home(tmp_path, old.pid)
        rc, calls, log = _run(home, "native-ok")
    finally:
        old.kill()
    assert rc == 0, log
    native = (home / ".organism" / "context-guard" / "window_jump_native.applescript").read_text()
    assert "frontmost" not in native and "id of front window" not in native
    assert "front window: 'old title' (not assumed ours)" in log


def test_keystroke_route_types_nothing_when_no_new_window_was_born(tmp_path):
    # The 2026-09-09 17:59 failure on M5: ⌘N, and no window with a name that
    # was not already on the desktop. Nothing may be typed.
    home, _ = _home(tmp_path, 0)
    rc, calls, log = _run(home, "keys-front-stuck", claim_after=None)
    assert rc == 1
    assert not any("type-here" in c or "raise-type" in c for c in calls)
    assert "no new window within" in log and "nothing typed" in log


# ---------------- innocence ----------------
def test_new_session_never_claims_leaves_old_window_open(tmp_path):
    old = _sleeper()
    try:
        home, _ = _home(tmp_path, old.pid)
        rc, calls, log = _run(home, "native-ok", claim_after=None)
        assert rc == 2
        assert old.poll() is None, "old session must not be ended when the new one never came up"
    finally:
        old.kill()
    assert not any("/exit" in c or "close-window" in c for c in calls)
    assert "did not report within 6s: old window left open" in log


def test_kill_switch_and_missing_file(tmp_path):
    home, pending = _home(tmp_path, 0)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "OSASCRIPT": str(tmp_path / "osascript"),
           "STUB_LOG": str(home / "calls.log"), "STUB_MODE": "native-ok", "CONTEXT_JUMP_OFF": "1"}
    assert subprocess.run(["bash", str(SCRIPT), "sess-1234-abcd"], env=env).returncode == 0
    env.pop("CONTEXT_JUMP_OFF")
    assert subprocess.run(["bash", str(SCRIPT), "no-such-session"], env=env).returncode == 1
    assert not (home / "calls.log").exists(), "no gesture without a pending file or with the switch off"


def test_values_reach_applescript_as_argv_never_spliced(tmp_path):
    # A cwd with a quote must arrive verbatim as an argument.
    home, _ = _home(tmp_path, 0, cwd="/tmp/it's \"here\"")
    rc, calls, _ = _run(home, "native-ok")
    assert rc == 0
    assert "window_jump_native.applescript new-window /tmp/it's \"here\" " in calls


def _leaves_once_stamped(stamp: Path) -> subprocess.Popen:
    # A stand-in for an old claude that is ALREADY gone when the exit-wait looks:
    # it leaves the moment its tty carries the stamp, long before /exit is typed.
    return subprocess.Popen([sys.executable, "-c",
                             "import os, sys, time\n"
                             "while True:\n"
                             "    try:\n"
                             "        if os.path.getsize(sys.argv[1]) > 0: break\n"
                             "    except OSError:\n"
                             "        pass\n"
                             "    time.sleep(0.02)\n", str(stamp)])


def test_an_old_claude_already_gone_is_reported_ended_by_exit_not_signalled(tmp_path):
    # 2026-09-18, twin of the tmux seat defect: a from_pid that had already left
    # when the exit-wait looked produced NO outcome line at all, so the log read
    # as if the gesture had stopped after typing /exit.
    old = _leaves_once_stamped(tmp_path / "home" / "stamp.tty")
    try:
        home, _ = _home(tmp_path, old.pid)
        rc, calls, log = _run(home, "native-ok")
        old.wait(timeout=5)
    finally:
        old.kill()
    assert rc == 0, log
    assert "/exit typed into old window id=win-OLD (proven ours by stamp)" in log
    assert "SIGINT" not in log, "a pid already gone is never signalled"
    assert f"old session pid {old.pid} ended by /exit" in log, "the outcome line is owed even when the pid was already gone"
    assert "old window id=win-OLD closed" in log
