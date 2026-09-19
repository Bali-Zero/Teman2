"""wa_army_watcher.sh — exercised against a REAL tmux server on a private socket.

The launcher pipes the first pane of an army session into the log and hands the
watcher the session name. The context guard's tmux gesture (tmux_jump.sh) then
moves claude into a NEW window of the same session and closes the old one;
pipe-pane is per-pane, so the new window is born unpiped and ARMY_DONE never
reaches the log (2026-09-18: finished armies reported as "scaduto" / "terminata
SENZA PR"). What this file pins: the watcher pipes every pane that has no pipe
yet, and ONLY those — `pipe-pane -o` on an already-piped pane toggles the pipe
OFF (measured on tmux 3.7b), which would silence the launcher's own pipe.

Seams: TMUX_BIN (a wrapper adding `-L <socket>`), WA_ARMY_POLL_S, a `curl` shim
on PATH that records the Telegram text instead of sending it, HOME with no
LaunchAgents so the token comes from TELEGRAM_BOT_TOKEN. Skips without tmux.
"""
from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(os.environ.get("WA_ARMY_WATCHER_SH")
              or Path(__file__).resolve().parents[2] / "scripts" / "wa_army_watcher.sh")
TMUX = shutil.which("tmux") or ("/opt/homebrew/bin/tmux" if Path("/opt/homebrew/bin/tmux").exists() else None)
ARMY = "ARMYX"
DONE_LINE = f"ARMY_DONE {ARMY} https://github.com/x/y/pull/1"
# What the TUI redraws in the pane BEFORE the army has done anything: the prompt's own
# sentinel line (docs/army-prompts/*.txt, placeholder and all) and the test-army shape
# (an `echo "ARMY_DONE …"` instruction, later redrawn again as the running command).
PROMPT_LINES = (f"ARMY_DONE {ARMY} <numero-PR-o-url>",
                f'echo "ARMY_DONE {ARMY} https://github.com/x/y/pull/1"')

CURL_SHIM = r'''#!/bin/bash
# curl shim: records the Telegram text= argument, sends nothing.
for a in "$@"; do case "$a" in text=*) printf '%s\n---\n' "${a#text=}" >> "$CURL_LOG";; esac; done
exit 0
'''

pytestmark = pytest.mark.skipif(TMUX is None, reason="needs a real tmux")


class Army:
    def __init__(self, tmp: Path, tag: str):
        self.tmp = tmp
        self.sock = f"nzwt-{os.getpid()}-{tag}"
        self.session = f"army-t-{tag}"
        self.log = tmp / "army.log"
        self.curl_log = tmp / "curl.log"
        home = tmp / "home"; home.mkdir()
        shim = tmp / "bin"; shim.mkdir()
        (shim / "curl").write_text(CURL_SHIM)
        (shim / "tmux").write_text(f'#!/bin/bash\nexec "{TMUX}" -L "{self.sock}" "$@"\n')
        for f in ("curl", "tmux"):
            (shim / f).chmod((shim / f).stat().st_mode | stat.S_IXUSR)
        self.env = {"HOME": str(home), "PATH": f"{shim}:/usr/bin:/bin", "CURL_LOG": str(self.curl_log),
                    "TELEGRAM_BOT_TOKEN": "0:fake", "TMUX_BIN": str(shim / "tmux"),
                    "WA_ARMY_POLL_S": "1", "WA_ARMY_MAX_WATCH_S": "60"}
        self.proc: subprocess.Popen | None = None

    def tmux(self, *args: str) -> str:
        return subprocess.run([TMUX, "-L", self.sock, *args], capture_output=True, text=True, timeout=10).stdout

    def launch(self):
        # the launcher's gestures: detached session, first pane piped, watcher in the background
        self.tmux("new-session", "-d", "-s", self.session, "-x", "80", "-y", "20", "/bin/sh")
        self.tmux("pipe-pane", "-t", self.session, "-o", f"cat >> '{self.log}'")
        self.proc = subprocess.Popen(["bash", str(SCRIPT), self.session, ARMY, str(self.log)],
                                     env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    def panes(self) -> dict[str, str]:
        out = self.tmux("list-panes", "-s", "-t", self.session, "-F", "#{pane_id} #{pane_pipe}")
        return dict(line.split() for line in out.splitlines() if line.strip())

    def wait_pane_piped(self, pane: str, deadline_s: float = 6.0) -> bool:
        t0 = time.time()
        while time.time() - t0 < deadline_s:
            if self.panes().get(pane) == "1":
                return True
            time.sleep(0.2)
        return False

    def wait_exit(self, deadline_s: float = 25.0) -> int:
        assert self.proc is not None
        try:
            self.proc.wait(timeout=deadline_s)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            pytest.fail("watcher still running: " + (self.proc.stderr.read() if self.proc.stderr else ""))
        return self.proc.returncode

    def alerts(self) -> str:
        return self.curl_log.read_text() if self.curl_log.exists() else ""

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        try:
            subprocess.run([TMUX, "-L", self.sock, "kill-server"], capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            pass


@pytest.fixture
def army(tmp_path: Path, request):
    a = Army(tmp_path, request.node.name[-12:].replace("_", "")[-8:] or "x")
    yield a
    a.close()


def test_after_a_window_jump_the_new_pane_is_piped_and_army_done_still_reaches_telegram(army: Army):
    army.launch()
    old = next(iter(army.panes()))
    time.sleep(1.5)                                    # a poll or two on the original pane
    # the tmux gesture: new window in the SAME session, then the old pane goes away
    army.tmux("new-window", "-t", army.session, "/bin/sh")
    army.tmux("kill-pane", "-t", old)
    (new,) = [p for p in army.panes() if p != old]
    assert army.wait_pane_piped(new), f"the watcher never piped the jumped-to pane {new}"
    army.tmux("send-keys", "-t", new, f"echo {DONE_LINE}", "Enter")
    assert army.wait_exit() == 0
    text = army.alerts()
    assert f"Armata {ARMY} HA FINITO" in text and "https://github.com/x/y/pull/1" in text, text
    assert "SENZA PR" not in text and "scaduto" not in text


def test_the_launchers_own_pipe_is_never_toggled_off_by_the_watcher(army: Army):
    army.launch()
    (old,) = army.panes()
    time.sleep(3.5)                                    # three polls over an already-piped pane
    assert army.panes()[old] == "1", "the original pane lost its pipe: pipe-pane -o toggled it"
    army.tmux("send-keys", "-t", old, f"echo {DONE_LINE}", "Enter")
    assert army.wait_exit() == 0
    assert f"Armata {ARMY} HA FINITO" in army.alerts()


def test_the_sentinel_redrawn_from_the_prompt_is_not_army_done(army: Army):
    # 2026-09-19 TESTJUMP: the watcher fired on the prompt text at launch ("HA FINITO" with
    # no PR) and was gone before the window jump, so the new pane was never re-piped.
    army.launch()
    (pane,) = army.panes()
    for line in PROMPT_LINES:                          # typed command AND its output land in the log
        army.tmux("send-keys", "-t", pane, "printf '%s\\n' " + shlex.quote(line), "Enter")
    time.sleep(3.5)                                    # three polls over the redrawn prompt
    assert army.proc is not None and army.proc.poll() is None, "the watcher exited on the prompt text"
    assert army.alerts() == "", army.alerts()
    army.tmux("send-keys", "-t", pane, f"echo {DONE_LINE}", "Enter")
    assert army.wait_exit() == 0
    text = army.alerts()
    assert f"Armata {ARMY} HA FINITO" in text and "https://github.com/x/y/pull/1" in text, text
    assert "<numero-PR-o-url>" not in text and text.count("---") == 1, text


def test_a_session_that_dies_without_army_done_is_still_reported_as_ended_without_pr(army: Army):
    army.launch()
    time.sleep(1.5)
    army.tmux("kill-session", "-t", army.session)
    assert army.wait_exit() == 0
    text = army.alerts()
    assert f"Armata {ARMY}: sessione terminata SENZA PR" in text, text
    assert "HA FINITO" not in text
