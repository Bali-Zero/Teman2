"""tmux_jump.sh — the tmux gesture of the window jump, exercised with a stubbed `tmux`.

A claude that sits in a tmux pane (scripts/wa_army_launcher.sh, or a hand-made
tmux session in any terminal) is seat "tmux" for context_window_guard.py, which
spawns this script instead of the AppleScript one. Measured 2026-09-16 on M5:
five army sessions were classified headless, got no gesture and died at the 400K
deny. The seam is TMUX_BIN=<stub>: the stub records every call's argv (one line
per call, fields split on \\x1f so nothing is ever re-parsed from a joined string)
and answers per STUB_MODE. What this file pins is the DECISION — which pane gets
which keystroke: `nz-jump` into the pane tmux just handed back by id, `/exit` into
the OLD pane by ITS id, never the active pane — and every miss that must leave the
old pane untouched. No tmux server is ever started, so it runs anywhere.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRIPT = Path(os.environ.get("TMUX_JUMP_SH")
              or Path(__file__).resolve().parents[2] / "infra" / "claude-hooks" / "tmux_jump.sh")

STUB = r'''#!/bin/bash
# tmux stub: records argv, answers per STUB_MODE.
printf '%s\x1f' "$@" >> "$STUB_LOG"; echo >> "$STUB_LOG"
case "$1:$STUB_MODE" in
  display-message:*)          echo "@1"; exit 0 ;;
  new-window:no-window)       exit 1 ;;
  new-window:*)               echo "%9"; exit 0 ;;
  send-keys:keys-fail)        exit 1 ;;
  send-keys:*)                exit 0 ;;
esac
exit 0
'''


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".organism" / "context-guard").mkdir(parents=True)
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    stub = stub_dir / "tmux"
    stub.write_text(STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return home


def _pending(home: Path, frm: str, from_pid: int, cwd: str | None = None) -> Path:
    p = home / ".organism" / "context-guard" / f"pending-jump-{frm}.json"
    p.write_text(json.dumps({"from_session": frm, "from_pid": from_pid, "to_session": None,
                             "cwd": cwd if cwd is not None else str(home)}))
    return p


def _claim_later(p: Path, after: float, to: str = "s-new"):
    def _go():
        time.sleep(after)
        d = json.loads(p.read_text())
        d["to_session"] = to
        p.write_text(json.dumps(d))
    threading.Thread(target=_go, daemon=True).start()


def _run(home: Path, frm: str, mode: str = "ok", *, env_extra: dict | None = None,
         jump_wait: int = 3, exit_wait: int = 1):
    stub_log = home / "stub.log"
    env = {"HOME": str(home), "PATH": f"{home.parent / 'bin'}:/usr/bin:/bin",
           "TMUX": "/tmp/tmux-501/default,1,0", "TMUX_PANE": "%1",
           "STUB_LOG": str(stub_log), "STUB_MODE": mode,
           "JUMP_WAIT_S": str(jump_wait), "EXIT_WAIT_S": str(exit_wait)}
    env.update(env_extra or {})
    for k, v in list(env.items()):
        if v is None:
            env.pop(k)
    p = subprocess.run(["bash", str(SCRIPT), frm], env=env, capture_output=True, text=True, timeout=60)
    calls = [line.split("\x1f")[:-1] for line in stub_log.read_text().splitlines()] if stub_log.exists() else []
    log = (home / ".organism" / "context-guard" / "jump.log").read_text() if \
        (home / ".organism" / "context-guard" / "jump.log").exists() else ""
    return p.returncode, calls, log


def _sleeper() -> subprocess.Popen:
    return subprocess.Popen(["sleep", "30"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


# ---------------- guilt: the whole gesture, pane by id ----------------

def test_new_window_next_to_own_window_then_exit_into_own_pane_by_id(tmp_path):
    home = _home(tmp_path)
    sleeper = _sleeper()
    try:
        pending = _pending(home, "s-one", sleeper.pid)
        _claim_later(pending, 0.5)
        rc, calls, log = _run(home, "s-one")
        assert rc == 0, log
        launcher = f"{home}/.claude/scripts/nz-jump s-one"
        assert calls == [
            ["display-message", "-p", "-t", "%1", "#{window_id}"],
            ["new-window", "-a", "-t", "@1", "-c", str(home), "-P", "-F", "#{pane_id}"],
            ["send-keys", "-t", "%9", "-l", launcher],
            ["send-keys", "-t", "%9", "Enter"],
            ["send-keys", "-t", "%1", "-l", "/exit"],
            ["send-keys", "-t", "%1", "Enter"],
        ], calls
        assert "new window %9 opened, 'nz-jump s-one' typed" in log   # the words the guard's retry reads
        assert "new session s-new is up" in log
        assert "/exit typed into old pane %1" in log
        # /exit means nothing to `sleep`: the SIGINT fallback ends it, and says so
        assert "ended by SIGINT×2 (fallback)" in log
        assert sleeper.wait(timeout=5) is not None
    finally:
        if sleeper.poll() is None:
            sleeper.kill()


def test_a_dead_from_pid_is_reported_as_ended_by_exit_not_signalled(tmp_path):
    home = _home(tmp_path)
    dead = subprocess.run(["true"])  # a pid that is gone before the gesture starts
    pending = _pending(home, "s-dead", 999_999_9)
    _claim_later(pending, 0.3)
    rc, calls, log = _run(home, "s-dead")
    assert rc == 0 and dead.returncode == 0
    assert "SIGINT" not in log and "/exit typed into old pane %1" in log
    # the outcome line is owed even when the pid was gone before the gesture looked:
    # the first live run (scratch tmux server, 2026-09-18) ended with no outcome line at all
    assert "ended by /exit" in log


def test_launcher_path_and_cwd_reach_tmux_as_argv_never_spliced(tmp_path):
    home = _home(tmp_path)
    cwd = tmp_path / "a dir; with $tricks"
    cwd.mkdir()
    frm = "s-two words"
    pending = _pending(home, frm, 999_999_9, cwd=str(cwd))
    _claim_later(pending, 0.3)
    rc, calls, log = _run(home, frm, env_extra={"NZ_JUMP_BIN": "/opt/x/nz-jump"})
    assert rc == 0, log
    assert calls[1] == ["new-window", "-a", "-t", "@1", "-c", str(cwd), "-P", "-F", "#{pane_id}"]
    assert calls[2] == ["send-keys", "-t", "%9", "-l", f"/opt/x/nz-jump {frm}"]
    assert not (tmp_path / "tricks").exists()


def test_a_missing_cwd_falls_back_to_home_never_to_a_failed_new_window(tmp_path):
    home = _home(tmp_path)
    pending = _pending(home, "s-cwd", 999_999_9, cwd=str(tmp_path / "gone"))
    _claim_later(pending, 0.3)
    rc, calls, _ = _run(home, "s-cwd")
    assert rc == 0 and calls[1][5] == str(home)


# ---------------- innocence: every miss leaves the OLD pane untouched ----------------

def _no_exit_typed(calls):
    return not any(c[:3] == ["send-keys", "-t", "%1"] for c in calls)


def test_new_session_never_claims_leaves_old_pane_open(tmp_path):
    home = _home(tmp_path)
    _pending(home, "s-nc", 999_999_9)
    rc, calls, log = _run(home, "s-nc", jump_wait=1)
    assert rc == 2 and _no_exit_typed(calls)
    assert "did not report within 1s: old pane left open" in log
    assert calls[2][:4] == ["send-keys", "-t", "%9", "-l"]   # the new window WAS typed into


def test_no_new_window_types_nothing(tmp_path):
    home = _home(tmp_path)
    _pending(home, "s-nw", 999_999_9)
    rc, calls, log = _run(home, "s-nw", mode="no-window")
    assert rc == 1 and not any(c[0] == "send-keys" for c in calls)
    assert "nothing typed" in log and "typed'" not in log


def test_send_keys_refused_is_a_miss_the_guard_can_retry(tmp_path):
    home = _home(tmp_path)
    _pending(home, "s-sk", 999_999_9)
    rc, calls, log = _run(home, "s-sk", mode="keys-fail")
    assert rc == 1 and _no_exit_typed(calls)
    assert "nothing typed" in log and "opened, 'nz-jump" not in log


def test_outside_tmux_or_unknown_own_pane_makes_no_call(tmp_path):
    home = _home(tmp_path)
    _pending(home, "s-env", 999_999_9)
    rc, calls, log = _run(home, "s-env", env_extra={"TMUX": None})
    assert rc == 1 and calls == [] and "TMUX unset" in log and "nothing typed" in log
    rc, calls, log = _run(home, "s-env", env_extra={"TMUX_PANE": None})
    assert rc == 1 and calls == [] and "TMUX_PANE unset" in log


def test_own_pane_not_on_the_server_types_nothing(tmp_path):
    home = _home(tmp_path)
    _pending(home, "s-np", 999_999_9)
    stub = tmp_path / "bin" / "tmux"
    stub.write_text(STUB.replace('display-message:*)          echo "@1"; exit 0 ;;',
                                 'display-message:*)          exit 1 ;;'))
    rc, calls, log = _run(home, "s-np")
    assert rc == 1 and len(calls) == 1 and "not found on the server" in log


def test_kill_switch_and_missing_file(tmp_path):
    home = _home(tmp_path)
    _pending(home, "s-off", 999_999_9)
    rc, calls, log = _run(home, "s-off", env_extra={"CONTEXT_JUMP_OFF": "1"})
    assert rc == 0 and calls == [] and "disabled by CONTEXT_JUMP_OFF" in log
    rc, calls, log = _run(home, "s-none")
    assert rc == 1 and calls == [] and "no pending-jump file for 's-none'" in log


def test_no_tmux_binary_is_no_gesture_not_a_crash(tmp_path):
    home = _home(tmp_path)
    _pending(home, "s-nb", 999_999_9)
    rc, calls, log = _run(home, "s-nb", env_extra={"TMUX_BIN": "/nonexistent/tmux"})
    assert rc == 0 and calls == [] and "no tmux on PATH" in log


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", "-q", __file__]))
